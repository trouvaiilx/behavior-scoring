import json

import pytest

from app.rubric import DIMENSIONS
from app.schemas import CandidateProfileInput
from app.scoring import (
    ScoringError,
    _extract_json,
    _keyword_backstop_hits,
    _safe_red_flag_status,
    _safe_score,
    score_candidate,
)


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

def test_extract_json_clean():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_code_fences():
    raw = '```json\n{"a": 1}\n```'
    assert _extract_json(raw) == {"a": 1}


def test_extract_json_with_stray_surrounding_text():
    raw = 'Sure, here is the JSON:\n{"a": 1, "b": [1, 2]}\nHope that helps!'
    assert _extract_json(raw) == {"a": 1, "b": [1, 2]}


def test_extract_json_garbage_raises():
    with pytest.raises(ScoringError):
        _extract_json("this is not json at all")


# ---------------------------------------------------------------------------
# _safe_score
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_value,expected",
    [
        (50, 50.0),
        (50.5, 50.5),
        ("75", 75.0),
        (150, 100.0),  # clamped
        (-10, 0.0),  # clamped
        (None, 0.0),  # missing
        ("not a number", 0.0),  # non-numeric
    ],
)
def test_safe_score(raw_value, expected):
    assert _safe_score(raw_value, "some_dimension") == expected


# ---------------------------------------------------------------------------
# _safe_red_flag_status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("pass", "pass"),
        ("REVIEW", "review"),
        ("fail", "fail"),
        ("maybe", "review"),  # unrecognized -> safe default
        (None, "review"),
        (123, "review"),
    ],
)
def test_safe_red_flag_status(raw_value, expected):
    assert _safe_red_flag_status(raw_value) == expected


# ---------------------------------------------------------------------------
# _keyword_backstop_hits
# ---------------------------------------------------------------------------

def test_keyword_backstop_detects_excluded_attribute_language():
    hits = _keyword_backstop_hits(["The candidate mentioned they are pregnant in one post."])
    assert "marital or family status, pregnancy" in hits


def test_keyword_backstop_no_false_positive_on_unrelated_text():
    hits = _keyword_backstop_hits(["Strong Python skills and clear writing in posts."])
    assert hits == set()


# ---------------------------------------------------------------------------
# score_candidate (end-to-end, with a mocked Ollama client)
# ---------------------------------------------------------------------------

def _sample_model_response(overrides=None):
    payload = {
        "overall_summary": "Solid technical communicator with consistent history.",
        "dimension_scores": {d["key"]: 80 for d in DIMENSIONS},
        "dimension_rationale": {d["key"]: "Consistently strong evidence." for d in DIMENSIONS},
        "red_flag_status": "pass",
        "red_flag_rationale": "No concerning content found.",
        "excluded_attributes_detected": [],
    }
    if overrides:
        payload.update(overrides)
    return json.dumps(payload)


@pytest.fixture
def sample_profile():
    return CandidateProfileInput(
        candidate_label="sample_001",
        cv_claims="Software Engineer, 2022-2024",
        profile_about="Backend engineer interested in distributed systems.",
        posts_sample="Wrote a post about database indexing strategies.",
        comments_sample="Helpful, technical comments on other people's posts.",
        network_notes="A few relevant endorsements.",
    )


async def test_score_candidate_happy_path(monkeypatch, sample_profile):
    async def fake_generate_json(system_prompt, user_prompt):
        return _sample_model_response()

    monkeypatch.setattr("app.scoring.generate_json", fake_generate_json)

    result = await score_candidate(sample_profile)

    assert result.candidate_label == "sample_001"
    assert result.red_flag.status == "pass"
    assert result.composite_score == 80.0
    assert result.rubric_hash
    assert len(result.dimension_scores) == len(DIMENSIONS)


async def test_score_candidate_applies_keyword_backstop(monkeypatch, sample_profile):
    async def fake_generate_json(system_prompt, user_prompt):
        return _sample_model_response(
            {
                "dimension_rationale": {
                    d["key"]: "Great engagement, though they mentioned being pregnant."
                    for d in DIMENSIONS
                },
                "red_flag_status": "pass",
                "excluded_attributes_detected": [],
            }
        )

    monkeypatch.setattr("app.scoring.generate_json", fake_generate_json)

    result = await score_candidate(sample_profile)

    # The model didn't self-report the excluded attribute, but the
    # deterministic backstop should catch it and force a review flag.
    assert result.red_flag.status == "review"
    assert any("pregnancy" in a.lower() for a in result.excluded_attributes_detected)


async def test_score_candidate_handles_malformed_model_output(monkeypatch, sample_profile):
    async def fake_generate_json(system_prompt, user_prompt):
        return "not valid json at all"

    monkeypatch.setattr("app.scoring.generate_json", fake_generate_json)

    with pytest.raises(ScoringError):
        await score_candidate(sample_profile)


async def test_score_candidate_defaults_bad_red_flag_status(monkeypatch, sample_profile):
    async def fake_generate_json(system_prompt, user_prompt):
        return _sample_model_response({"red_flag_status": "definitely fine trust me"})

    monkeypatch.setattr("app.scoring.generate_json", fake_generate_json)

    result = await score_candidate(sample_profile)
    assert result.red_flag.status == "review"
