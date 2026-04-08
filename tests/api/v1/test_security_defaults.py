"""Security-by-default behavior tests."""

from __future__ import annotations

from app import main as app_main
from app.core.security import InMemoryRateLimiter


def test_health_response_contains_security_headers(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers


def test_create_user_rejects_too_large_body(client) -> None:
    oversized_name = "A" * (app_main.settings.api_body_max_bytes + 32)
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000050",
        "full_name": oversized_name,
        "timezone": "UTC",
    }

    response = client.post("/api/v1/user", json=payload)

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["code"] == "COMMON_413"
    assert detail["key"] == "SECURITY_REQUEST_BODY_TOO_LARGE"


def test_rate_limit_returns_429(client) -> None:
    original_limiter = app_main.rate_limiter
    app_main.rate_limiter = InMemoryRateLimiter(limit=1, window_seconds=60)
    try:
        payload = {
            "system_user_id": "a1b2c3d4-0001-4000-8000-000000000051",
            "full_name": "Rate Limit User",
            "timezone": "UTC",
        }
        first = client.post(
            "/api/v1/user",
            json=payload,
            headers={"Idempotency-Key": "security-rate-limit-1"},
        )
        second = client.post(
            "/api/v1/user",
            json={
                **payload,
                "system_user_id": "a1b2c3d4-0001-4000-8000-000000000052",
            },
            headers={"Idempotency-Key": "security-rate-limit-2"},
        )
    finally:
        app_main.rate_limiter = original_limiter

    assert first.status_code == 201
    assert second.status_code == 429
    detail = second.json()["detail"]
    assert detail["code"] == "COMMON_429"
    assert detail["key"] == "SECURITY_RATE_LIMIT_EXCEEDED"
