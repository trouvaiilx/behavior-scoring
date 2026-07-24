"""
Core scoring logic.

Builds a rubric-grounded prompt from app/rubric.py, calls the local LLM via
Ollama, parses the (expected) JSON response, and computes the weighted
composite score. This keeps the LLM as the "nuanced dimension" scorer while
the composite math and rubric weights stay deterministic and auditable in
Python.
"""
import json
import re

from app.config import OLLAMA_MODEL, RUBRIC_VERSION
from app.ollama_client import generate_json, OllamaError
from app.rubric import DIMENSIONS, RED_FLAG_KEY, EXCLUDED_ATTRIBUTES, weighted_composite
from app.schemas import CandidateProfileInput, ScoreResult, DimensionScore, RedFlagResult


class ScoringError(Exception):
    pass


def _build_system_prompt() -> str:
    dim_lines = "\n".join(
        f'- "{d["key"]}" ({d["label"]}, weight {d["weight"]*100:.0f}%): {d["description"]}'
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
    return f"""Candidate label (non-identifying, for reference only): {profile.candidate_label}

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


def _extract_json(raw_text: str) -> dict:
    """Ollama with format=json should return clean JSON, but we defensively
    strip markdown code fences etc. in case the model wraps it anyway."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ScoringError(f"Model output was not valid JSON: {e}\nRaw output: {raw_text[:1000]}") from e


async def score_candidate(profile: CandidateProfileInput) -> ScoreResult:
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(profile)

    try:
        raw_output = await generate_json(system_prompt, user_prompt)
    except OllamaError as e:
        raise ScoringError(str(e)) from e

    parsed = _extract_json(raw_output)

    raw_dim_scores = parsed.get("dimension_scores", {})
    raw_rationales = parsed.get("dimension_rationale", {})

    dimension_scores = []
    numeric_scores = {}
    for d in DIMENSIONS:
        score = raw_dim_scores.get(d["key"])
        if score is None:
            score = 0
        score = max(0, min(100, float(score)))
        numeric_scores[d["key"]] = score
        dimension_scores.append(
            DimensionScore(
                key=d["key"],
                label=d["label"],
                score=score,
                rationale=raw_rationales.get(d["key"], "(no rationale returned)"),
            )
        )

    composite = weighted_composite(numeric_scores)

    red_flag = RedFlagResult(
        status=parsed.get("red_flag_status", "review"),
        rationale=parsed.get("red_flag_rationale", "(no rationale returned)"),
    )

    return ScoreResult(
        candidate_label=profile.candidate_label,
        rubric_version=RUBRIC_VERSION,
        model_used=OLLAMA_MODEL,
        overall_summary=parsed.get("overall_summary", "(no summary returned)"),
        dimension_scores=dimension_scores,
        composite_score=composite,
        red_flag=red_flag,
        excluded_attributes_detected=parsed.get("excluded_attributes_detected", []),
        raw_model_output=raw_output,
    )
