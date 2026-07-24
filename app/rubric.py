"""
Scoring rubric definition.

Keep this file as the single source of truth for dimensions/weights,
both the LLM prompt and the weighted-score calculation read from here,
so they can never drift out of sync.
"""

# Each dimension: (key, label, weight, description)
# Weights must sum to 1.0. RED_FLAG is handled separately as a veto/escalation
# signal, not folded into the weighted average.
# NOTE ON WEIGHTS: these previously summed to 0.75 (0.25 + 0.20 + 0.20 +
# 0.10), not 1.0 as this file's own comments and total_weight()/
# weighted_composite() require -- silently under-scaling every composite
# score by 25%. Renormalized here (divide each original weight by 0.75) so
# they sum to exactly 1.0 while preserving the original relative
# importance and ordering (network_signal remains the smallest/most
# optional signal). If you intentionally want a 5th dimension instead of
# rescaling these four, add it here and rebalance weights explicitly --
# just make sure total_weight() == 1.0 stays true (there's a test for it:
# tests/test_rubric.py::test_total_weight_sums_to_one).
DIMENSIONS = [
    {
        "key": "professional_consistency",
        "label": "Professional Consistency",
        "weight": 0.33,
        "description": (
            "Does the public profile align with claimed CV/resume details "
            "(roles, dates, skills)? Score 0-100."
        ),
    },
    {
        "key": "communication_quality",
        "label": "Communication Quality",
        "weight": 0.27,
        "description": (
            "Clarity, tone, and professionalism of public posts/comments. "
            "Score 0-100."
        ),
    },
    {
        "key": "domain_engagement",
        "label": "Domain Engagement",
        "weight": 0.27,
        "description": (
            "Evidence of genuine interest/expertise in the relevant field "
            "(posts, articles, community participation). Score 0-100."
        ),
    },
    {
        "key": "network_signal",
        "label": "Network Signal",
        "weight": 0.13,
        "description": (
            "Endorsements, recommendations, and relevant professional "
            "connections. Score 0-100. Treat this as the weakest/most "
            "optional signal."
        ),
    },
]

# Red Flag Screening is NOT part of the weighted average — it is a
# pass/review/fail gate (see RFC Section 4.2 design note).
RED_FLAG_KEY = "red_flag_screen"
RED_FLAG_WEIGHT_NOTE = (
    "Red Flag Screening acts as a veto/escalation trigger, not a weighted "
    "score. A single serious red flag routes the profile to mandatory "
    "human review regardless of other dimension scores."
)

# Attributes that must NEVER influence any dimension score, directly or
# indirectly (RFC Section 4.3). The model is instructed to ignore these
# entirely when forming a judgement, even if mentioned in the input text.
EXCLUDED_ATTRIBUTES = [
    "religion",
    "ethnicity or race",
    "political affiliation or opinion",
    "marital or family status, pregnancy",
    "disability or health status",
    "sexual orientation or gender identity",
    "age (beyond legally relevant minimum working age)",
]


def total_weight() -> float:
    return round(sum(d["weight"] for d in DIMENSIONS), 4)


class IncompleteScoreError(Exception):
    """Raised when a dimension required by the rubric has no score at all,
    i.e. the model output didn't include it. Distinct from "the model gave
    it a low score" -- this is a missing-data condition and should never be
    silently averaged in as a 0, since that would quietly punish a
    candidate for a parsing/model problem rather than anything in their
    text."""


def weighted_composite(dimension_scores: dict) -> float:
    """
    dimension_scores: dict of {dimension_key: score_0_to_100}
    Returns the weighted composite score (0-100), rounded to 1 decimal.

    Raises IncompleteScoreError if a rubric dimension key is missing from
    dimension_scores entirely. Callers that want to tolerate missing
    dimensions (e.g. to still show a partial result) must catch this and
    decide explicitly how to handle it -- this function will not silently
    treat "missing" the same as "scored 0".
    """
    missing = [d["key"] for d in DIMENSIONS if d["key"] not in dimension_scores]
    if missing:
        raise IncompleteScoreError(
            f"Missing score(s) for dimension(s): {', '.join(missing)}"
        )

    total = 0.0
    for d in DIMENSIONS:
        total += dimension_scores[d["key"]] * d["weight"]
    return round(total, 1)


def rubric_hash() -> str:
    """Deterministic fingerprint of the rubric content (dimensions' keys,
    weights, descriptions, and excluded attributes). Stored alongside
    RUBRIC_VERSION so a forgotten manual version bump is still detectable:
    if the hash changes but the version string didn't, something drifted.
    """
    import hashlib
    import json as _json

    fingerprint_source = {
        "dimensions": [
            {"key": d["key"], "weight": d["weight"], "description": d["description"]}
            for d in DIMENSIONS
        ],
        "excluded_attributes": EXCLUDED_ATTRIBUTES,
    }
    payload = _json.dumps(fingerprint_source, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]
