from app import db
from app.config import API_SECRET_KEY
from playwright.sync_api import APIRequestContext


def test_post_auth_token_accepts_valid_credentials(api_request: APIRequestContext):
    response = api_request.post(
        "/api/auth/token",
        data={"client_id": "playwright-e2e", "client_secret": API_SECRET_KEY},
    )

    assert response.status == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_post_auth_token_rejects_invalid_credentials(api_request: APIRequestContext):
    response = api_request.post(
        "/api/auth/token",
        data={"client_id": "playwright-e2e", "client_secret": "not-the-api-secret"},
    )

    assert response.status == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "Invalid client credentials"


def test_post_candidates_import_persists_profiles(api_request: APIRequestContext):
    profiles = [
        {
            "candidate_label": "import_candidate_one",
            "job_role": "Platform Engineer",
            "cv_claims": "Built reliable Python services.",
            "profile_about": "Systems engineer.",
        },
        {
            "candidate_label": "import_candidate_two",
            "job_role": "Data Engineer",
            "cv_claims": "Developed batch data pipelines.",
            "profile_about": "Data platform specialist.",
        },
    ]

    response = api_request.post("/api/candidates/import", data={"profiles": profiles})

    assert response.status == 200
    body = response.json()
    assert body["imported_count"] == len(profiles)
    assert len(body["candidate_ids"]) == len(profiles)
    assert all(candidate_id > 0 for candidate_id in body["candidate_ids"])

    with db._connect() as connection:
        rows = connection.execute(
            """
            SELECT id, candidate_label, job_role, cv_claims, profile_about
            FROM candidates
            WHERE id IN (?, ?)
            ORDER BY id
            """,
            body["candidate_ids"],
        ).fetchall()

    assert [row["id"] for row in rows] == body["candidate_ids"]
    assert [row["candidate_label"] for row in rows] == [
        profile["candidate_label"] for profile in profiles
    ]
    assert [row["job_role"] for row in rows] == [profile["job_role"] for profile in profiles]
    assert [row["cv_claims"] for row in rows] == [profile["cv_claims"] for profile in profiles]
    assert [row["profile_about"] for row in rows] == [profile["profile_about"] for profile in profiles]
