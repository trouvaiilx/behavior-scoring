import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import CandidateProfileInput

SAMPLES_PATH = Path(__file__).parent.parent / "sample_data" / "sample_profiles.json"


def test_sample_profiles_json_structure():
    """Verify that sample_profiles.json exists and every entry conforms to CandidateProfileInput schema."""
    assert SAMPLES_PATH.exists(), "sample_profiles.json should exist"
    data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))

    assert isinstance(data, list)
    assert len(data) >= 6, "Should contain at least 6 sample profiles"

    labels = set()
    for raw_profile in data:
        profile = CandidateProfileInput(**raw_profile)
        assert profile.candidate_label, "Each profile must have candidate_label"
        assert profile.candidate_label not in labels, (
            f"Duplicate label: {profile.candidate_label}"
        )
        labels.add(profile.candidate_label)


def test_api_get_samples_endpoint():
    """Verify GET /api/samples returns HTTP 200 with sample profiles."""
    client = TestClient(app)
    response = client.get("/api/samples")

    assert response.status_code == 200
    profiles = response.json()
    assert isinstance(profiles, list)
    assert len(profiles) >= 6
    for p in profiles:
        assert "candidate_label" in p
        assert "job_role" in p
