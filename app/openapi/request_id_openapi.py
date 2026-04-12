"""OpenAPI enrichment: document optional ``X-Request-Id`` on requests and responses."""

from __future__ import annotations

from typing import Any

_REQUEST_ID_HEADER_DESC = (
    "Optional correlation id. If you send **X-Request-Id**, the same value is returned in the "
    "response header and written to server logs as **request_id** (JSON logs / Elasticsearch). "
    "If omitted, the server generates a UUID."
)

_RESPONSE_HEADER_DESC = (
    "Correlation id for this HTTP request—echo of **X-Request-Id** from the request or a "
    "server-generated UUID. Use it to match browser or Swagger calls to log lines and Kibana."
)


def enrich_openapi_with_request_id(schema: dict[str, Any]) -> None:
    """Mutate ``schema`` so every operation documents request/response ``X-Request-Id``.

    Swagger UI will show an optional header parameter and list the response header on each
    status, so Try it out flows match curl and cross-origin browser clients.

    Args:
        schema: OpenAPI document produced by :func:`fastapi.openapi.utils.get_openapi`.
    """
    response_header: dict[str, Any] = {
        "description": _RESPONSE_HEADER_DESC,
        "schema": {"type": "string"},
    }
    request_parameter: dict[str, Any] = {
        "name": "X-Request-Id",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
        "description": _REQUEST_ID_HEADER_DESC,
    }

    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return

    for _path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in (
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "trace",
            ):
                continue
            if not isinstance(operation, dict):
                continue

            params = operation.setdefault("parameters", [])
            if not _has_header_param(params, "X-Request-Id"):
                params.append(request_parameter.copy())

            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            for _code, resp in responses.items():
                if not isinstance(resp, dict):
                    continue
                hdrs = resp.setdefault("headers", {})
                hdrs.setdefault("X-Request-Id", response_header.copy())


def _has_header_param(parameters: list[Any], name: str) -> bool:
    """Return True if ``parameters`` already contains a header named ``name``."""
    for item in parameters:
        if not isinstance(item, dict):
            continue
        if item.get("in") == "header" and item.get("name") == name:
            return True
    return False
