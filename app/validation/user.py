"""Mapping of user validation errors to stable API codes."""

from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.errors.common import COMMON_000
from app.errors.types import StableError
from app.errors.user import CREATE_USER_VALIDATION_RULES, UPDATE_USER_VALIDATION_RULES

PUT_PATCH_USER_BY_COMPOSITE_PATH = re.compile(r"^/api/v1/user/[^/]+/[^/]+$")


def _json_safe(value: Any) -> Any:
    """Recursively coerce values for inclusion in JSON error ``details``.

    Args:
        value: Arbitrary object from Pydantic error context.

    Returns:
        JSON-compatible structure; non-JSON types become ``str(value)``.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _field_from_loc(loc: list[Any]) -> str | None:
    """Extract JSON body field name from a Pydantic ``loc`` tuple when applicable.

    Args:
        loc: Location path from :meth:`RequestValidationError.errors`.

    Returns:
        Body field name, or ``None`` if not a simple body field error.
    """
    if len(loc) >= 2 and loc[0] == "body" and isinstance(loc[1], str):
        return loc[1]
    return None


def _resolve_update_user_rule(field: str | None, error_type: str) -> StableError:
    """Map ``(field, error_type)`` for PUT/PATCH user-by-composite-key bodies.

    Args:
        field: Body field name from :func:`_field_from_loc`, or ``None``.
        error_type: Pydantic error type string (e.g. ``missing``, ``string_too_short``).

    Returns:
        Matching rule from :data:`~app.errors.user.UPDATE_USER_VALIDATION_RULES` or
        :data:`~app.errors.common.COMMON_000`.
    """
    if field is not None and (field, error_type) in UPDATE_USER_VALIDATION_RULES:
        return UPDATE_USER_VALIDATION_RULES[(field, error_type)]
    return COMMON_000


def _resolve_create_user_rule(field: str | None, error_type: str) -> StableError:
    """Map ``(field, error_type)`` to a rule or fall back to a generic validation code.

    Args:
        field: Body field name from :func:`_field_from_loc`, or ``None``.
        error_type: Pydantic error type string (e.g. ``missing``, ``string_too_short``).

    Returns:
        Matching rule from :data:`~app.errors.user.CREATE_USER_VALIDATION_RULES` or
        :data:`~app.errors.common.COMMON_000`.
    """
    if field is not None and (field, error_type) in CREATE_USER_VALIDATION_RULES:
        return CREATE_USER_VALIDATION_RULES[(field, error_type)]
    return COMMON_000


def build_validation_error_payload(request: Request, exc: RequestValidationError) -> dict[str, Any]:
    """Normalize FastAPI/Pydantic validation errors into the API 422 contract.

    Args:
        request: Failed request (method/path select specialized rules).
        exc: Validation exception from FastAPI.

    Returns:
        Dict with ``error_type``, ``endpoint``, and ``errors`` list suitable for JSON encoding.
    """
    errors: list[dict[str, Any]] = []
    endpoint = f"{request.method} {request.url.path}"

    for item in exc.errors():
        loc = list[Any](item.get("loc", []))
        error_type = str(item.get("type", "value_error"))
        field = _field_from_loc(loc)

        if endpoint == "POST /api/v1/user":
            rule = _resolve_create_user_rule(field, error_type)
        elif request.method in ("PUT", "PATCH") and PUT_PATCH_USER_BY_COMPOSITE_PATH.match(
            request.url.path
        ):
            rule = _resolve_update_user_rule(field, error_type)
        else:
            rule = COMMON_000

        errors.append(
            {
                "code": rule.code,
                "key": rule.key,
                "message": rule.message,
                "field": field,
                "source": "validation",
                "details": {
                    "type": error_type,
                    "loc": _json_safe(loc),
                    "input": _json_safe(item.get("input")),
                    "ctx": _json_safe(item.get("ctx")),
                },
            }
        )

    return {"error_type": "validation_error", "endpoint": endpoint, "errors": errors}
