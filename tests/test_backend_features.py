import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.schemas import DimensionScore, RedFlagResult, ScoreResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a temporary SQLite database for each test function."""
    db_file = tmp_path / "test_scores.db"
    monkeypatch.setattr(db, "DATABASE_PATH", db_file)
    db.init_db()
    yield


def _create_sample_score_result(
    label: str,
    composite: float,
    red_flag_status: str = "pass",
    job_role: str = "Developer",
    excluded_attrs: list[str] | None = None,
) -> ScoreResult:
    return ScoreResult(
        candidate_label=label,
        job_role=job_role,
        rubric_version="0.2.0",
        rubric_hash="abc123hash",
        model_used="test-model",
        overall_summary=f"Summary for {label}",
        dimension_scores=[
            DimensionScore(
                key="professional_consistency",
                label="Professional Consistency",
                score=composite,
                rationale="OK",
            ),
            DimensionScore(
                key="communication_quality",
                label="Communication Quality",
                score=composite,
                rationale="OK",
            ),
            DimensionScore(
                key="domain_engagement",
                label="Domain Engagement",
                score=composite,
                rationale="OK",
            ),
            DimensionScore(
                key="network_signal",
                label="Network Signal",
                score=composite,
                rationale="OK",
            ),
        ],
        composite_score=composite,
        red_flag=RedFlagResult(status=red_flag_status, rationale="Test rationale"),
        excluded_attributes_detected=excluded_attrs or [],
        raw_model_output="{}",
    )


def test_db_save_and_get_score():
    res = _create_sample_score_result("sample_alice", 85.5, "pass", "Backend Lead")
    score_id = db.save_score(res)
    assert score_id > 0

    fetched = db.get_score(score_id)
    assert fetched is not None
    assert fetched["candidate_label"] == "sample_alice"
    assert fetched["job_role"] == "Backend Lead"
    assert fetched["composite_score"] == 85.5
    assert fetched["red_flag"]["status"] == "pass"
    assert fetched["human_review"]["status"] == "pending"


def test_human_review_workflow_api():
    res = _create_sample_score_result("sample_bob", 45.0, "review")
    score_id = db.save_score(res)

    # Patch human review
    patch_resp = client.patch(
        f"/api/scores/{score_id}/review",
        json={"status": "approved", "notes": "HR manager confirmed clear."},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["human_review"]["status"] == "approved"
    assert data["human_review"]["notes"] == "HR manager confirmed clear."
    assert data["human_review"]["reviewed_at"] is not None

    # Verify persistent get
    detail_resp = client.get(f"/api/scores/{score_id}")
    assert detail_resp.json()["human_review"]["status"] == "approved"


def test_delete_score_api():
    res = _create_sample_score_result("sample_charlie", 70.0)
    score_id = db.save_score(res)

    del_resp = client.delete(f"/api/scores/{score_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Score run deleted"

    # Subsequent GET returns 404
    get_resp = client.get(f"/api/scores/{score_id}")
    assert get_resp.status_code == 404


def test_list_scores_filtering_search_and_sorting():
    db.save_score(
        _create_sample_score_result("alpha_candidate", 92.0, "pass", "Senior Dev")
    )
    db.save_score(
        _create_sample_score_result("beta_candidate", 30.0, "fail", "Junior Dev")
    )
    db.save_score(
        _create_sample_score_result(
            "gamma_candidate", 65.0, "review", "QA Engineer", ["religion"]
        )
    )

    # Test search by label
    resp = client.get("/api/scores?search=alpha")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["results"][0]["candidate_label"] == "alpha_candidate"

    # Test red_flag_status filter
    resp = client.get("/api/scores?red_flag_status=fail")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["results"][0]["candidate_label"] == "beta_candidate"

    # Test min/max score filter
    resp = client.get("/api/scores?min_score=60.0&max_score=95.0")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2  # alpha (92.0) and gamma (65.0)

    # Test sorting by score asc
    resp = client.get("/api/scores?sort_by=composite_score&sort_order=asc")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["composite_score"] == 30.0
    assert results[-1]["composite_score"] == 92.0


def test_analytics_summary_api():
    db.save_score(_create_sample_score_result("c1", 15.0, "fail"))
    db.save_score(_create_sample_score_result("c2", 50.0, "review"))
    db.save_score(_create_sample_score_result("c3", 90.0, "pass"))

    resp = client.get("/api/scores/analytics")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_candidates"] == 3
    assert data["composite_score_stats"]["avg"] == 51.7
    assert data["composite_score_stats"]["min"] == 15.0
    assert data["composite_score_stats"]["max"] == 90.0
    assert data["red_flag_breakdown"] == {"pass": 1, "review": 1, "fail": 1}
    assert data["score_buckets"]["0_to_20"] == 1
    assert data["score_buckets"]["41_to_60"] == 1
    assert data["score_buckets"]["81_to_100"] == 1


def test_export_scores_api():
    db.save_score(
        _create_sample_score_result("export_test", 88.0, "pass", "Lead Architect")
    )

    # Export JSON
    json_resp = client.get("/api/scores/export?format=json")
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers["content-type"]
    parsed_json = json_resp.json()
    assert len(parsed_json) == 1
    assert parsed_json[0]["candidate_label"] == "export_test"

    # Export CSV
    csv_resp = client.get("/api/scores/export?format=csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "candidate_label" in csv_resp.text
    assert "export_test" in csv_resp.text


def test_candidate_comparison_api():
    sid1 = db.save_score(_create_sample_score_result("candidate_a", 80.0, "pass"))
    sid2 = db.save_score(_create_sample_score_result("candidate_b", 60.0, "review"))

    resp = client.get(f"/api/scores/compare?ids={sid1},{sid2}")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["candidates"]) == 2
    assert data["highest_scoring_candidate"] == "candidate_a"
    assert data["lowest_scoring_candidate"] == "candidate_b"
    assert data["dimension_averages"]["professional_consistency"] == 70.0
    assert data["red_flags_summary"]["pass"] == 1
    assert data["red_flags_summary"]["review"] == 1


def test_batch_score_endpoint_mock(monkeypatch):
    """Test batch endpoint structure."""

    async def mock_score_candidate(profile):
        return _create_sample_score_result(profile.candidate_label, 75.0, "pass")

    monkeypatch.setattr("app.main.score_candidate", mock_score_candidate)

    batch_payload = {
        "profiles": [
            {"candidate_label": "batch_c1", "cv_claims": "Role 1"},
            {"candidate_label": "batch_c2", "cv_claims": "Role 2"},
        ]
    }

    resp = client.post("/api/scores/batch", json=batch_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "batch_id" in data
    batch_id = data["batch_id"]

    # Poll status endpoint
    status_resp = client.get(f"/api/scores/batch/{batch_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["total_items"] == 2
