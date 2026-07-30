from playwright.sync_api import APIRequestContext


def test_post_webhooks_registers_valid_subscription(api_request: APIRequestContext):
    payload = {
        "url": "https://example.test/webhooks/candidate-scores",
        "events": ["score.created", "score.reviewed"],
    }

    response = api_request.post("/api/webhooks", data=payload)

    assert response.status == 201
    body = response.json()
    assert body["id"] > 0
    assert body["url"] == payload["url"]
    assert body["events"] == payload["events"]
    assert body["created_at"]


def test_post_webhooks_rejects_invalid_url(api_request: APIRequestContext):
    response = api_request.post(
        "/api/webhooks",
        data={"url": "not-a-valid-url", "events": ["score.created"]},
    )

    assert response.status == 422
    body = response.json()
    assert body["detail"]
