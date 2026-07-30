import json
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import MAX_FIELD_CHARS

RedFlagStatus = Literal["pass", "review", "fail"]
HumanReviewStatus = Literal["pending", "approved", "rejected", "overridden"]


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
    job_role: str = Field(
        default="",
        max_length=200,
        description="Optional target job role for context (e.g. 'Senior Software Engineer').",
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
        "job_role",
        "cv_claims",
        "profile_about",
        "posts_sample",
        "comments_sample",
        "network_notes",
    )
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return v.strip() if v else v


class CandidateImportRequest(BaseModel):
    profiles: list[CandidateProfileInput] = Field(default_factory=list, max_length=100)
    json_file: Optional[str] = Field(default=None, max_length=MAX_FIELD_CHARS * 100)

    @model_validator(mode="after")
    def _load_json_file_profiles(self):
        if self.json_file is None:
            if not self.profiles:
                raise ValueError("profiles cannot be empty")
            return self

        if self.profiles:
            raise ValueError("provide either profiles or json_file, not both")

        try:
            payload = json.loads(self.json_file)
        except json.JSONDecodeError as exc:
            raise ValueError("json_file must contain valid JSON") from exc

        if isinstance(payload, dict):
            payload = payload.get("profiles")
        if not isinstance(payload, list) or not payload:
            raise ValueError("json_file must contain a non-empty profile list")
        if len(payload) > 100:
            raise ValueError("a maximum of 100 profiles can be imported at once")

        self.profiles = [CandidateProfileInput.model_validate(profile) for profile in payload]
        return self


class CandidateImportResponse(BaseModel):
    imported_count: int
    candidate_ids: list[int]
    status: Literal["success"] = "success"


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    rationale: str


class RedFlagResult(BaseModel):
    status: RedFlagStatus
    rationale: str


class HumanReviewInfo(BaseModel):
    status: HumanReviewStatus = "pending"
    notes: str = ""
    reviewed_at: str | None = None


class HumanReviewUpdate(BaseModel):
    status: HumanReviewStatus
    notes: str = Field(default="", max_length=1000)


class TokenRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=200)
    client_secret: str = Field(..., min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class WebhookRegisterRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    events: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("url")
    @classmethod
    def _valid_webhook_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid HTTP(S) URL")
        return value

    @field_validator("events")
    @classmethod
    def _valid_events(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("events cannot contain blank values")
        return cleaned


class WebhookResponse(BaseModel):
    id: int
    url: str
    events: list[str]
    created_at: str


class ScoreResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int | None = None
    candidate_label: str
    job_role: str = ""
    rubric_version: str
    rubric_hash: str = Field(
        default="",
        description="Content fingerprint of the rubric at scoring time, to catch un-bumped version drift.",
    )
    model_used: str
    overall_summary: str = Field(
        default="",
        description="Model-generated plain-language summary of the overall profile.",
    )
    dimension_scores: list[DimensionScore]
    composite_score: float
    red_flag: RedFlagResult
    human_review: HumanReviewInfo = Field(
        default_factory=lambda: HumanReviewInfo(status="pending", notes="")
    )
    excluded_attributes_detected: list[str] = Field(
        default_factory=list,
        description="Protected attributes the model noticed in the text but explicitly did NOT use to influence scoring.",
    )
    raw_model_output: str
    created_at: str | None = None


class AnalyticsSummaryResponse(BaseModel):
    total_candidates: int
    composite_score_stats: dict[str, float]
    red_flag_breakdown: dict[str, int]
    human_review_breakdown: dict[str, int]
    excluded_attributes_counts: dict[str, int]
    score_buckets: dict[str, int]


class BatchScoreRequest(BaseModel):
    profiles: list[CandidateProfileInput] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of candidate profiles to score.",
    )


class BatchItemResult(BaseModel):
    candidate_label: str
    status: Literal["completed", "failed"]
    score_result: ScoreResult | None = None
    error: str | None = None


class BatchJobStatusResponse(BaseModel):
    batch_id: str
    status: Literal["processing", "completed", "failed"]
    total_items: int
    completed_items: int
    failed_items: int
    results: list[BatchItemResult]


class CandidateComparisonResponse(BaseModel):
    candidates: list[ScoreResult]
    dimension_averages: dict[str, float]
    highest_scoring_candidate: str | None = None
    lowest_scoring_candidate: str | None = None
    red_flags_summary: dict[str, int]


class LiveSearchRequest(BaseModel):
    candidate_name: str = Field(..., min_length=1, max_length=200)
    job_role: str = Field(default="", max_length=200)


class RubricDimensionInput(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    weight: float = Field(..., ge=0.0, le=1.0)
    description: str = Field(..., min_length=1, max_length=1000)


class RubricVersionRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    dimensions: list[RubricDimensionInput] = Field(..., min_length=1)
    excluded_attributes: list[str] | None = Field(default=None)


class RubricVersionResponse(BaseModel):
    version: str
    rubric_hash: str
    dimensions: list[dict]
    excluded_attributes: list[str]
    message: str


class UsageStatsResponse(BaseModel):
    total_scores_run: int
    total_candidates: int
    configured_model: str
    database_path: str
    uptime_seconds: float


