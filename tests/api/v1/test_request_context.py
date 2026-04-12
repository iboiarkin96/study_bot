"""Tests for X-Request-Id middleware and correlation headers."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def test_live_returns_x_request_id(client: TestClient) -> None:
    response = client.get("/live")
    assert response.status_code == 200
    rid = response.headers.get("X-Request-Id")
    assert rid
    assert _UUID_RE.match(rid)


def test_client_supplied_x_request_id_preserved(client: TestClient) -> None:
    custom = "upstream-trace-abc-123"
    response = client.get("/live", headers={"X-Request-Id": custom})
    assert response.headers.get("X-Request-Id") == custom


def test_invalid_x_request_id_replaced_with_uuid(client: TestClient) -> None:
    response = client.get("/live", headers={"X-Request-Id": "bad id spaces"})
    rid = response.headers.get("X-Request-Id")
    assert rid
    assert _UUID_RE.match(rid)


def test_cors_expose_headers_lists_x_request_id_for_browser_clients(client: TestClient) -> None:
    """Cross-origin fetches may read listed response headers (Swagger UI, SPAs on another port)."""
    response = client.get(
        "/live",
        headers={"Origin": "http://127.0.0.1:3000"},
    )
    assert response.status_code == 200
    expose = response.headers.get("access-control-expose-headers", "")
    assert "x-request-id" in expose.lower()


def test_openapi_lists_x_request_id_on_live_operation(client: TestClient) -> None:
    """Swagger shows optional request header and response header for correlation."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    live_get = spec["paths"]["/live"]["get"]
    param_names = [p["name"] for p in live_get.get("parameters", []) if p.get("in") == "header"]
    assert "X-Request-Id" in param_names
    assert "X-Request-Id" in live_get["responses"]["200"]["headers"]
