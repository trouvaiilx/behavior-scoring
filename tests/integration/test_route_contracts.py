from app.main import app


CORE_OPERATIONS = {
    "/api/health": {"get"},
    "/api/rubric": {"get"},
    "/api/score": {"post"},
    "/api/scores": {"get"},
    "/api/scores/analytics": {"get"},
    "/api/scores/export": {"get"},
    "/api/scores/compare": {"get"},
    "/api/scores/{score_id}": {"get", "delete"},
    "/api/scores/{score_id}/review": {"patch"},
    "/api/scores/batch": {"post"},
    "/api/scores/batch/{batch_id}": {"get"},
}


def test_core_routes_use_the_api_prefix_and_expected_operations():
    paths = app.openapi()["paths"]

    assert sum(len(methods) for methods in CORE_OPERATIONS.values()) == 12
    for path, expected_methods in CORE_OPERATIONS.items():
        assert path.startswith("/api/")
        assert path in paths
        assert expected_methods.issubset(paths[path])


def test_scoring_request_schemas_match_the_public_contract():
    paths = app.openapi()["paths"]

    score_schema = paths["/api/score"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    batch_schema = paths["/api/scores/batch"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    review_schema = paths["/api/scores/{score_id}/review"]["patch"]["requestBody"]["content"]["application/json"]["schema"]

    assert score_schema["$ref"] == "#/components/schemas/CandidateProfileInput"
    assert batch_schema["$ref"] == "#/components/schemas/BatchScoreRequest"
    assert review_schema["$ref"] == "#/components/schemas/HumanReviewUpdate"
