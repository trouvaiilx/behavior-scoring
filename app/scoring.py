"""
Core scoring logic.

Builds a rubric-grounded prompt from app/rubric.py, calls the local LLM via
Ollama, parses the (expected) JSON response, and computes the weighted
composite score. This keeps the LLM as the "nuanced dimension" scorer while
the composite math and rubric weights stay deterministic and auditable in
Python.
"""

import json
import logging
import re

from app.config import OLLAMA_MODEL, RUBRIC_VERSION
from app.ollama_client import OllamaError, generate_json
from app.rubric import (
    DIMENSIONS,
    EXCLUDED_ATTRIBUTES,
    IncompleteScoreError,
    rubric_hash,
    weighted_composite,
)
from app.schemas import (
    CandidateProfileInput,
    DimensionScore,
    RedFlagResult,
    ScoreResult,
)

logger = logging.getLogger(__name__)

_VALID_RED_FLAG_STATUSES = {"pass", "review", "fail"}

# Deterministic, best-effort keyword backstop for the excluded-attributes
# rule. This is NOT a substitute for the prompt instruction -- it can't
# understand context or nuance the way the model can -- but prompts are not
# guarantees, and this is a fairness-critical rule. If the model's
# dimension rationale text contains obvious excluded-attribute language, we
# flag it for mandatory human review rather than silently trusting that the
# model followed the instruction. False positives here are acceptable
# (they just add a review flag); false negatives are the real risk, so this
# is intentionally coarse rather than clever.
_EXCLUDED_ATTRIBUTE_KEYWORDS = {
    "religion": [
        "religion",
        "religious",
        "christian",
        "muslim",
        "jewish",
        "hindu",
        "buddhist",
        "atheist",
    ],
    "ethnicity or race": ["ethnicity", "ethnic", "race", "racial", "nationality"],
    "political affiliation or opinion": [
        "political",
        "politics",
        "republican",
        "democrat",
        "left-wing",
        "right-wing",
        "conservative",
        "liberal",
    ],
    "marital or family status, pregnancy": [
        "married",
        "marriage",
        "pregnant",
        "pregnancy",
        "children",
        "divorced",
    ],
    "disability or health status": [
        "disability",
        "disabled",
        "illness",
        "diagnosis",
        "medical condition",
        "mental health",
    ],
    "sexual orientation or gender identity": [
        "gay",
        "lesbian",
        "bisexual",
        "transgender",
        "sexual orientation",
        "gender identity",
        "lgbtq",
    ],
    "age (beyond legally relevant minimum working age)": [
        "years old",
        "age of",
        "elderly",
        "young age",
    ],
}


class ScoringError(Exception):
    pass


def _build_system_prompt() -> str:
    dim_lines = "\n".join(
        f'- "{d["key"]}" ({d["label"]}, weight {d["weight"] * 100:.0f}%): {d["description"]}'
        for d in DIMENSIONS
    )
    excluded_lines = "\n".join(f"- {a}" for a in EXCLUDED_ATTRIBUTES)

    return f"""You are a careful, conservative HR research assistant helping to test a
candidate-screening scoring rubric during an internal R&D prototype phase.
You are NOT making a hiring decision. You are scoring SAMPLE/CONSENTED text
only, to help validate whether the rubric produces sensible, consistent
output. A human will review every result before it influences anything.

Score the candidate text on these dimensions, each from 0 (very poor) to
100 (excellent). Base every score ONLY on the text provided — do not invent
facts not present in the text.

{dim_lines}

Additionally, perform a Red Flag Screen: look for explicit hate speech,
harassment, illegal activity, credible misconduct claims, or plagiarism
claims. This is NOT a weighted score — output one of "pass", "review", or
"fail". Use "review" whenever you are not fully certain, since a human will
check it. Use "fail" only for clear, explicit, serious violations.

CRITICAL — Excluded attributes: you must NEVER let any of the following
influence ANY dimension score, even indirectly. If you notice content
related to these in the text, list it under "excluded_attributes_detected"
but explicitly do NOT penalize or reward it:
{excluded_lines}

Respond with ONLY a single valid JSON object, no other text, in exactly
this shape:

{{
  "overall_summary": "<3-4 sentence plain-language summary of this candidate's overall profile, mentioning the strongest and weakest aspects. Written for a recruiter who has not read the raw text.>",
  "dimension_scores": {{
    {", ".join(f'"{d["key"]}": <0-100 integer>' for d in DIMENSIONS)}
  }},
  "dimension_rationale": {{
    {", ".join(f'"{d["key"]}": "<1-2 sentence rationale>"' for d in DIMENSIONS)}
  }},
  "red_flag_status": "<pass|review|fail>",
  "red_flag_rationale": "<1-2 sentence rationale>",
  "excluded_attributes_detected": ["<any excluded attribute categories noticed, or empty list>"]
}}"""


def _build_user_prompt(profile: CandidateProfileInput) -> str:
    job_role_line = f"Target Job Role: {profile.job_role}\n" if profile.job_role else ""
    return f"""Candidate label (non-identifying, for reference only): {profile.candidate_label}
{job_role_line}
--- CV / resume claims to check consistency against ---
{profile.cv_claims or "(none provided)"}

--- Public 'About' / bio text ---
{profile.profile_about or "(none provided)"}

--- Sample public posts / articles ---
{profile.posts_sample or "(none provided)"}

--- Sample public comments / interactions ---
{profile.comments_sample or "(none provided)"}

--- Network / endorsement notes ---
{profile.network_notes or "(none provided)"}
"""


def _iter_balanced_json_objects(text: str):
    """Yields every top-level balanced {...} substring in `text`, in order
    of appearance, tracking string literals/escapes so that braces inside
    quoted strings don't throw off the depth count.

    This replaces a greedy `re.search(r"\\{.*\\}")` fallback, which spans
    from the *first* '{' in the whole text to the *last* '}' -- if a model
    wraps valid JSON in commentary that itself contains stray braces (e.g.
    "Sure! Here's the {result}: {...real json...} let me know if {anything}
    is unclear"), the greedy regex can capture garbage or fail to isolate
    the actual object. Scanning for genuinely balanced objects and trying
    each one in turn is more robust to that kind of preamble/postamble.
    """
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue

        depth = 0
        in_string = False
        escape = False
        start = i
        j = i
        found_end = None
        while j < n:
            ch = text[j]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        found_end = j
                        break
            j += 1

        if found_end is not None:
            yield text[start : found_end + 1]
            i = found_end + 1
        else:
            i = start + 1


def _extract_json(raw_text: str) -> dict:
    """Ollama with format=json should return clean JSON, but smaller/local
    models don't always comply cleanly. We defensively:
    1. Strip leading/trailing markdown code fences.
    2. If that still doesn't parse, scan for balanced {...} objects
       anywhere in the text (see _iter_balanced_json_objects) and try each
       in turn, in case the model added commentary before/after the JSON.
    """
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    last_error = None
    for candidate in _iter_balanced_json_objects(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            last_error = e
            continue

    if last_error is not None:
        raise ScoringError(
            f"Model output was not valid JSON: {last_error}\nRaw output: {raw_text[:1000]}"
        ) from last_error

    raise ScoringError(
        f"Model output contained no JSON object.\nRaw output: {raw_text[:1000]}"
    )


def _safe_score(raw_value, dimension_key: str) -> float:
    """Coerce a model-provided score to a float in [0, 100]. Non-numeric or
    missing values become 0 and are logged, rather than raising and
    failing the whole request over one bad field."""
    if raw_value is None:
        logger.warning(
            "Dimension '%s' had no score in model output; defaulting to 0.",
            dimension_key,
        )
        return 0.0
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        logger.warning(
            "Dimension '%s' had a non-numeric score (%r) in model output; defaulting to 0.",
            dimension_key,
            raw_value,
        )
        return 0.0
    return max(0.0, min(100.0, value))


def _safe_red_flag_status(raw_status) -> str:
    """Validate the model's red_flag_status against the known set. Anything
    unexpected (typo, hallucinated value, wrong type) is treated as
    'review' -- the safe default that routes to a human -- rather than
    silently passed through to the DB/UI."""
    if isinstance(raw_status, str) and raw_status.lower() in _VALID_RED_FLAG_STATUSES:
        return raw_status.lower()
    logger.warning(
        "Model returned an unrecognized red_flag_status (%r); defaulting to 'review'.",
        raw_status,
    )
    return "review"


def _keyword_backstop_hits(text_fragments: list[str]) -> set[str]:
    """Deterministic secondary check for excluded-attribute language,
    scanning the model's own rationale text (not the candidate's raw
    input). See module docstring above _EXCLUDED_ATTRIBUTE_KEYWORDS for
    why this exists alongside (not instead of) the prompt instruction."""
    haystack = " ".join(t.lower() for t in text_fragments if t)
    hits = set()
    for attribute, keywords in _EXCLUDED_ATTRIBUTE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            hits.add(attribute)
    return hits


async def score_candidate(profile: CandidateProfileInput) -> ScoreResult:
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(profile)

    logger.info(
        "Scoring candidate '%s' with model '%s'.", profile.candidate_label, OLLAMA_MODEL
    )

    try:
        raw_output = await generate_json(system_prompt, user_prompt)
    except OllamaError as e:
        logger.error(
            "Ollama call failed for candidate '%s': %s", profile.candidate_label, e
        )
        raise ScoringError(str(e)) from e

    try:
        parsed = _extract_json(raw_output)
    except ScoringError:
        logger.error(
            "Could not parse model output as JSON for candidate '%s'.",
            profile.candidate_label,
        )
        raise

    raw_dim_scores = parsed.get("dimension_scores", {})
    raw_rationales = parsed.get("dimension_rationale", {})

    dimension_scores = []
    numeric_scores = {}
    for d in DIMENSIONS:
        score = _safe_score(raw_dim_scores.get(d["key"]), d["key"])
        numeric_scores[d["key"]] = score
        dimension_scores.append(
            DimensionScore(
                key=d["key"],
                label=d["label"],
                score=score,
                rationale=raw_rationales.get(d["key"], "(no rationale returned)"),
            )
        )

    try:
        composite = weighted_composite(numeric_scores)
    except IncompleteScoreError as e:
        # Every dimension is guaranteed a numeric_scores entry above (via
        # _safe_score's 0-default), so this should be unreachable in
        # practice -- but if the rubric itself changes shape mid-flight,
        # fail loudly rather than silently averaging in a 0.
        logger.error(
            "Incomplete score for candidate '%s': %s", profile.candidate_label, e
        )
        raise ScoringError(str(e)) from e

    red_flag = RedFlagResult(
        status=_safe_red_flag_status(parsed.get("red_flag_status")),
        rationale=parsed.get("red_flag_rationale", "(no rationale returned)"),
    )

    excluded_from_model = list(parsed.get("excluded_attributes_detected", []))

    # Deterministic backstop: scan the model's own summary/rationale text
    # for excluded-attribute language it may have used without flagging.
    # Anything caught here that the model didn't already report gets added
    # to the list AND forces the red flag status to at least "review", so
    # a human checks it.
    backstop_text = [parsed.get("overall_summary", ""), *raw_rationales.values()]
    backstop_hits = _keyword_backstop_hits(backstop_text)
    newly_detected = backstop_hits - {a.lower() for a in excluded_from_model}
    if newly_detected:
        logger.warning(
            "Keyword backstop found possible excluded-attribute language not "
            "self-reported by the model for candidate '%s': %s",
            profile.candidate_label,
            newly_detected,
        )
        excluded_from_model.extend(sorted(newly_detected))
        if red_flag.status == "pass":
            red_flag = RedFlagResult(
                status="review",
                rationale=(
                    red_flag.rationale
                    + " [Auto-flagged for review: possible excluded-attribute "
                    "language detected in model rationale by deterministic backstop.]"
                ),
            )

    return ScoreResult(
        candidate_label=profile.candidate_label,
        job_role=profile.job_role,
        rubric_version=RUBRIC_VERSION,
        rubric_hash=rubric_hash(),
        model_used=OLLAMA_MODEL,
        overall_summary=parsed.get("overall_summary", "(no summary returned)"),
        dimension_scores=dimension_scores,
        composite_score=composite,
        red_flag=red_flag,
        excluded_attributes_detected=excluded_from_model,
        raw_model_output=raw_output,
    )
