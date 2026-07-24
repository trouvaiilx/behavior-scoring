"""
Scoring rubric definition.

Keep this file as the single source of truth for dimensions/weights,
both the LLM prompt and the weighted-score calculation read from here,
so they can never drift out of sync.
"""

# Each dimension: (key, label, weight, description)
# Weights must sum to 1.0. RED_FLAG is handled separately as a veto/escalation
# signal, not folded into the weighted average.
DIMENSIONS = [
    {
        "key": "professional_consistency",
        "label": "Professional Consistency",
        "weight": 0.25,
        "description": (
            "Does the public profile align with claimed CV/resume details "
            "(roles, dates, skills)? Score 0-100."
        ),
    },
    {
        "key": "communication_quality",
        "label": "Communication Quality",
        "weight": 0.20,
        "description": (
            "Clarity, tone, and professionalism of public posts/comments. "
            "Score 0-100."
        ),
    },
    {
        "key": "domain_engagement",
        "label": "Domain Engagement",
        "weight": 0.20,
        "description": (
            "Evidence of genuine interest/expertise in the relevant field "
            "(posts, articles, community participation). Score 0-100."
        ),
    },
    {
        "key": "network_signal",
        "label": "Network Signal",
        "weight": 0.10,
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


def weighted_composite(dimension_scores: dict) -> float:
    """
    dimension_scores: dict of {dimension_key: score_0_to_100}
    Returns the weighted composite score (0-100), rounded to 1 decimal.
    Missing dimensions are treated as 0 (and should be flagged upstream).
    """
    total = 0.0
    for d in DIMENSIONS:
        score = dimension_scores.get(d["key"], 0)
        total += score * d["weight"]
    return round(total, 1)
