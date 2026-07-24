"""
Pydantic models for API request/response validation.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import MAX_FIELD_CHARS

RedFlagStatus = Literal["pass", "review", "fail"]


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
        ...,
        min_length=1,
        max_length=200,
        description="Any non-identifying label for this run, e.g. 'sample_001'.",
    )
    cv_claims: str = Field(
        default="",
        max_length=MAX_FIELD_CHARS,
        description="Relevant claims from the candidate's CV/resume (roles, dates, skills) to check consistency against.",
    )
    profile_about: str = Field(
        default="",
        max_length=MAX_FIELD_CHARS,
        description="Public 'About'/bio section text.",
    )
    posts_sample: str = Field(
        default="",
        max_length=MAX_FIELD_CHARS,
        description="Sample of public posts/articles, concatenated as plain text.",
    )
    comments_sample: str = Field(
        default="",
        max_length=MAX_FIELD_CHARS,
        description="Sample of public comments/interactions, concatenated as plain text.",
    )
    network_notes: str = Field(
        default="",
        max_length=MAX_FIELD_CHARS,
        description="Free-text notes on endorsements/connections, if any.",
    )

    @field_validator("candidate_label")
    @classmethod
    def _label_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("candidate_label cannot be blank")
        return v

    @field_validator(
        "cv_claims", "profile_about", "posts_sample", "comments_sample", "network_notes"
    )
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return v.strip() if v else v


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    rationale: str


class RedFlagResult(BaseModel):
    status: RedFlagStatus
    rationale: str


class ScoreResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: Optional[int] = None
    candidate_label: str
    rubric_version: str
    rubric_hash: str = Field(
        default="",
        description="Content fingerprint of the rubric at scoring time, to catch un-bumped version drift.",
    )
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
