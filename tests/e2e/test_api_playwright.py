from playwright.sync_api import APIRequestContext


def _profile_payload(candidate_label: str = "api_candidate") -> dict[str, str]:
    return {
        "candidate_label": candidate_label,
        "job_role": "Backend Engineer",
        "cv_claims": "Developed Python services from 2022 to 2024.",
        "profile_about": "Backend engineer focused on reliable systems.",
        "posts_sample": "Shared a practical article about database indexing.",
        "comments_sample": "Provided constructive technical feedback.",
        "network_notes": "Relevant professional endorsements.",
    }


def test_get_health_reports_backend_and_ollama_status(api_request: APIRequestContext):
    response = api_request.get("/api/health")

    assert response.status == 200
    payload = response.json()
    assert payload["backend"] == "ok"
    assert payload["ollama"]["reachable"] is True
    assert payload["ollama"]["model_available_locally"] is True


def test_get_rubric_returns_active_rubric(api_request: APIRequestContext):
    response = api_request.get("/api/rubric")

    assert response.status == 200
    payload = response.json()
    assert payload["dimensions"]
    assert all(
        {"key", "label", "weight", "description"}.issubset(dimension)
        for dimension in payload["dimensions"]
    )
    assert payload["red_flag_note"]
    assert payload["excluded_attributes"]
    assert payload["rubric_version"]
    assert payload["rubric_hash"]


def test_post_score_returns_and_persists_score(api_request: APIRequestContext):
    response = api_request.post("/api/score", data=_profile_payload())

    assert response.status == 200
    payload = response.json()
    assert payload["id"] > 0
    assert payload["candidate_label"] == "api_candidate"
    assert payload["job_role"] == "Backend Engineer"
    assert payload["composite_score"] == 80.0
    assert payload["red_flag"]["status"] == "pass"
    assert len(payload["dimension_scores"]) == 4


def test_get_scores_returns_previously_created_score(api_request: APIRequestContext):
    create_response = api_request.post("/api/score", data=_profile_payload("listed_candidate"))
    assert create_response.status == 200

    response = api_request.get("/api/scores", params={"limit": 10, "offset": 0})

    assert response.status == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert len(payload["results"]) == 1
    assert payload["results"][0]["candidate_label"] == "listed_candidate"


def test_live_search_candidate_endpoint(api_request: APIRequestContext):
    response = api_request.post(
        "/api/candidates/live-search",
        data={
            "candidate_name": "sample_dev_test",
            "job_role": "Python Engineer",
        },
    )
    assert response.status == 200
    payload = response.json()
    assert payload["candidate_label"] == "sample_dev_test"
    assert "composite_score" in payload
    assert "red_flag" in payload

