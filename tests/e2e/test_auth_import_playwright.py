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
        data={"client_id": "test-import-client", "client_secret": "test-import-secret"},
    )

    assert token_response.status == 200
    assert token_response.headers["cache-control"] == "no-store"
    token = token_response.json()["access_token"]

    import_response = api_request.post(
        "/api/candidates/import",
        data={"profiles": [_import_profile()]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert import_response.status == 201
    payload = import_response.json()
    assert payload["imported_count"] == 1
    assert len(payload["candidate_ids"]) == 1
    assert payload["candidate_ids"][0] > 0


def test_candidate_import_rejects_missing_bearer_token(api_request: APIRequestContext):
    response = api_request.post("/api/candidates/import", data={"profiles": [_import_profile()]})

    assert response.status == 401
    assert response.headers["www-authenticate"] == "Bearer"
