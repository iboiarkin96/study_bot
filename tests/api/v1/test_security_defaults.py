"""Security-by-default behavior tests."""

from __future__ import annotations

from app import main as app_main
from app.core.security import InMemoryRateLimiter


def test_live_response_contains_security_headers(client) -> None:
    response = client.get("/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "app_env": "qa"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers


def test_live_returns_alive_status(client) -> None:
    response = client.get("/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "app_env": "qa"}


def test_ready_returns_db_probe_details(client) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert isinstance(body["db_latency_ms"], float)


def test_ready_returns_503_when_dependency_fails(client) -> None:
    original_probe = app_main.readiness_probe
    app_main.readiness_probe = lambda timeout_ms: (False, None, "db_error")
    try:
        response = client.get("/ready")
    finally:
        app_main.readiness_probe = original_probe

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "db_error"


def test_metrics_endpoint_exposes_prometheus_metrics(client) -> None:
    # Produce both HTTP and DB observations before scraping metrics.
    client.get("/live")
    client.get("/ready")

    response = client.get(app_main.settings.metrics_path)

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    payload = response.text
    assert "http_requests_total" in payload
    assert "http_request_duration_seconds" in payload
    assert "db_operation_duration_seconds" in payload


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
