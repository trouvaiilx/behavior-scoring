from playwright.sync_api import APIRequestContext


def _import_profile(candidate_label: str = "imported_e2e_candidate") -> dict[str, str]:
    return {
        "candidate_label": candidate_label,
        "job_role": "Backend Engineer",
        "cv_claims": "Built Python services for synthetic projects.",
        "profile_about": "Synthetic profile for end-to-end testing.",
        "posts_sample": "Shared an engineering article.",
        "comments_sample": "Provided constructive technical feedback.",
        "network_notes": "Relevant endorsements.",
    }


def test_token_grant_allows_authenticated_candidate_import(api_request: APIRequestContext):
    token_response = api_request.post(
        "/api/auth/token",
        data={"client_id": "test-import-client", "client_secret": "dev-secret-key-change-in-prod"},
    )

    assert token_response.status == 200
    token = token_response.json()["access_token"]

    import_response = api_request.post(
        "/api/candidates/import",
        data={"profiles": [_import_profile()]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert import_response.status in (200, 201)
    payload = import_response.json()
    assert payload["imported_count"] == 1
    assert len(payload["candidate_ids"]) == 1
    assert payload["candidate_ids"][0] > 0


def test_candidate_import_accepts_valid_payload(api_request: APIRequestContext):
    response = api_request.post("/api/candidates/import", data={"profiles": [_import_profile("valid_import")]})
    assert response.status in (200, 201)
    assert response.json()["status"] == "success"

