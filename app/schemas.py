"""
Pydantic models for API request/response validation.
"""
from typing import Optional
from pydantic import BaseModel, Field


class CandidateProfileInput(BaseModel):
    """
    Structured input for a single candidate.

    IMPORTANT:
    In this prototype stage, this text should come from safe sources only —
    your own profile, a teammate's profile with explicit consent, or
    synthetic/sample text you write yourself. Do NOT paste in real
    candidate data scraped without consent and a validated legal basis.
    """
    candidate_label: str = Field(
        ..., description="Any non-identifying label for this run, e.g. 'sample_001'."
    )
    cv_claims: str = Field(
        default="",
        description="Relevant claims from the candidate's CV/resume (roles, dates, skills) to check consistency against.",
    )
    profile_about: str = Field(
        default="", description="Public 'About'/bio section text."
    )
    posts_sample: str = Field(
        default="", description="Sample of public posts/articles, concatenated as plain text."
    )
    comments_sample: str = Field(
        default="", description="Sample of public comments/interactions, concatenated as plain text."
    )
    network_notes: str = Field(
        default="", description="Free-text notes on endorsements/connections, if any."
    )


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    rationale: str


class RedFlagResult(BaseModel):
    status: str  # "pass" | "review" | "fail"
    rationale: str


class ScoreResult(BaseModel):
    id: Optional[int] = None
    candidate_label: str
    rubric_version: str
    model_used: str
    overall_summary: str = Field(
        default="", description="Model-generated plain-language summary of the overall profile."
    )
    dimension_scores: list[DimensionScore]
    composite_score: float
    red_flag: RedFlagResult
    excluded_attributes_detected: list[str] = Field(
        default_factory=list,
        description="Protected attributes the model noticed in the text but explicitly did NOT use to influence scoring.",
    )
    raw_model_output: str
    created_at: Optional[str] = None
