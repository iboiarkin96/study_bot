"""Unit tests for OpenAPI enrichment with X-Request-Id."""

from __future__ import annotations

from app.openapi.request_id_openapi import enrich_openapi_with_request_id


def test_enrich_adds_request_parameter_and_response_headers() -> None:
    schema: dict = {
        "paths": {
            "/live": {
                "get": {
                    "responses": {"200": {"description": "ok"}},
                }
            }
        }
    }
    enrich_openapi_with_request_id(schema)
    op = schema["paths"]["/live"]["get"]
    names = [p["name"] for p in op["parameters"] if p.get("in") == "header"]
    assert "X-Request-Id" in names
    assert "X-Request-Id" in op["responses"]["200"]["headers"]


def test_enrich_skips_second_x_request_id_parameter() -> None:
    schema: dict = {
        "paths": {
            "/x": {
                "get": {
                    "parameters": [
                        {"name": "X-Request-Id", "in": "header", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        }
    }
    enrich_openapi_with_request_id(schema)
    params = schema["paths"]["/x"]["get"]["parameters"]
    assert len([p for p in params if p.get("name") == "X-Request-Id"]) == 1


def test_enrich_no_paths_is_noop() -> None:
    enrich_openapi_with_request_id({})
