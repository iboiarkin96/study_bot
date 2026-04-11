"""Mapping of user validation errors to stable API codes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError

PUT_PATCH_USER_BY_COMPOSITE_PATH = re.compile(r"^/api/v1/user/[^/]+/[^/]+$")


@dataclass(frozen=True)
class ValidationCodeRule:
    """Stable API error identity for one Pydantic validation failure kind.

    Attributes:
        code: Short numeric or symbolic code (e.g. ``USER_001``).
        key: Machine-readable key for clients and i18n.
        message: Default English message for this rule.
    """

    code: str
    key: str
    message: str


CREATE_USER_VALIDATION_RULES: dict[tuple[str, str], ValidationCodeRule] = {
    ("system_user_id", "missing"): ValidationCodeRule(
        code="USER_001",
        key="USER_CREATE_SYSTEM_USER_ID_REQUIRED",
        message="Field `system_user_id` is required.",
    ),
    ("system_user_id", "string_too_short"): ValidationCodeRule(
        code="USER_002",
        key="USER_CREATE_SYSTEM_USER_ID_INVALID",
        message="Field `system_user_id` must not be empty.",
    ),
    ("full_name", "missing"): ValidationCodeRule(
        code="USER_003",
        key="USER_CREATE_FULL_NAME_REQUIRED",
        message="Field `full_name` is required.",
    ),
    ("full_name", "string_too_short"): ValidationCodeRule(
        code="USER_004",
        key="USER_CREATE_FULL_NAME_TOO_SHORT",
        message="Field `full_name` must not be empty.",
    ),
    ("full_name", "string_too_long"): ValidationCodeRule(
        code="USER_005",
        key="USER_CREATE_FULL_NAME_TOO_LONG",
        message="Field `full_name` exceeds max length.",
    ),
    ("username", "string_too_long"): ValidationCodeRule(
        code="USER_006",
        key="USER_CREATE_USERNAME_TOO_LONG",
        message="Field `username` exceeds max length.",
    ),
    ("timezone", "value_error"): ValidationCodeRule(
        code="USER_007",
        key="USER_CREATE_TIMEZONE_INVALID",
        message="Field `timezone` must be a valid IANA timezone.",
    ),
    ("timezone", "string_too_long"): ValidationCodeRule(
        code="USER_008",
        key="USER_CREATE_TIMEZONE_TOO_LONG",
        message="Field `timezone` exceeds max length.",
    ),
    ("system_uuid", "uuid_parsing"): ValidationCodeRule(
        code="USER_009",
        key="USER_CREATE_SYSTEM_UUID_INVALID",
        message="Field `system_uuid` must be a valid UUID.",
    ),
    ("invalidation_reason_uuid", "uuid_parsing"): ValidationCodeRule(
        code="USER_010",
        key="USER_CREATE_INVALIDATION_REASON_UUID_INVALID",
        message="Field `invalidation_reason_uuid` must be a valid UUID.",
    ),
    ("is_row_invalid", "int_parsing"): ValidationCodeRule(
        code="USER_011",
        key="USER_CREATE_IS_ROW_INVALID_TYPE",
        message="Field `is_row_invalid` must be an integer.",
    ),
    ("is_row_invalid", "greater_than_equal"): ValidationCodeRule(
        code="USER_012",
        key="USER_CREATE_IS_ROW_INVALID_MIN",
        message="Field `is_row_invalid` must be >= 0.",
    ),
    ("is_row_invalid", "less_than_equal"): ValidationCodeRule(
        code="USER_013",
        key="USER_CREATE_IS_ROW_INVALID_MAX",
        message="Field `is_row_invalid` must be <= 1.",
    ),
    ("system_uuid", "missing"): ValidationCodeRule(
        code="USER_025",
        key="USER_CREATE_SYSTEM_UUID_REQUIRED",
        message="Field `system_uuid` is required.",
    ),
}

UPDATE_USER_VALIDATION_RULES: dict[tuple[str, str], ValidationCodeRule] = {
    ("full_name", "missing"): ValidationCodeRule(
        code="USER_014",
        key="USER_UPDATE_FULL_NAME_REQUIRED",
        message="Field `full_name` is required.",
    ),
    ("full_name", "string_too_short"): ValidationCodeRule(
        code="USER_015",
        key="USER_UPDATE_FULL_NAME_TOO_SHORT",
        message="Field `full_name` must not be empty.",
    ),
    ("full_name", "string_too_long"): ValidationCodeRule(
        code="USER_016",
        key="USER_UPDATE_FULL_NAME_TOO_LONG",
        message="Field `full_name` exceeds max length.",
    ),
    ("username", "string_too_long"): ValidationCodeRule(
        code="USER_017",
        key="USER_UPDATE_USERNAME_TOO_LONG",
        message="Field `username` exceeds max length.",
    ),
    ("timezone", "value_error"): ValidationCodeRule(
        code="USER_018",
        key="USER_UPDATE_TIMEZONE_INVALID",
        message="Field `timezone` must be a valid IANA timezone.",
    ),
    ("timezone", "string_too_long"): ValidationCodeRule(
        code="USER_019",
        key="USER_UPDATE_TIMEZONE_TOO_LONG",
        message="Field `timezone` exceeds max length.",
    ),
    ("system_uuid", "uuid_parsing"): ValidationCodeRule(
        code="USER_020",
        key="USER_UPDATE_SYSTEM_UUID_INVALID",
        message="Field `system_uuid` must be a valid UUID.",
    ),
    ("invalidation_reason_uuid", "uuid_parsing"): ValidationCodeRule(
        code="USER_021",
        key="USER_UPDATE_INVALIDATION_REASON_UUID_INVALID",
        message="Field `invalidation_reason_uuid` must be a valid UUID.",
    ),
    ("is_row_invalid", "int_parsing"): ValidationCodeRule(
        code="USER_022",
        key="USER_UPDATE_IS_ROW_INVALID_TYPE",
        message="Field `is_row_invalid` must be an integer.",
    ),
    ("is_row_invalid", "greater_than_equal"): ValidationCodeRule(
        code="USER_023",
        key="USER_UPDATE_IS_ROW_INVALID_MIN",
        message="Field `is_row_invalid` must be >= 0.",
    ),
    ("is_row_invalid", "less_than_equal"): ValidationCodeRule(
        code="USER_024",
        key="USER_UPDATE_IS_ROW_INVALID_MAX",
        message="Field `is_row_invalid` must be <= 1.",
    ),
}


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


def _resolve_update_user_rule(field: str | None, error_type: str) -> ValidationCodeRule:
    """Map ``(field, error_type)`` for PUT/PATCH user-by-composite-key bodies.

    Args:
        field: Body field name from :func:`_field_from_loc`, or ``None``.
        error_type: Pydantic error type string (e.g. ``missing``, ``string_too_short``).

    Returns:
        Matching rule from :data:`UPDATE_USER_VALIDATION_RULES` or a generic ``COMMON_000`` rule.
    """
    if field is not None and (field, error_type) in UPDATE_USER_VALIDATION_RULES:
        return UPDATE_USER_VALIDATION_RULES[(field, error_type)]
    return ValidationCodeRule(
        code="COMMON_000",
        key="COMMON_VALIDATION_ERROR",
        message="Request validation failed.",
    )


def _resolve_create_user_rule(field: str | None, error_type: str) -> ValidationCodeRule:
    """Map ``(field, error_type)`` to a rule or fall back to a generic validation code.

    Args:
        field: Body field name from :func:`_field_from_loc`, or ``None``.
        error_type: Pydantic error type string (e.g. ``missing``, ``string_too_short``).

    Returns:
        Matching :class:`ValidationCodeRule` from :data:`CREATE_USER_VALIDATION_RULES`
        or a default ``COMMON_000`` rule.
    """
    if field is not None and (field, error_type) in CREATE_USER_VALIDATION_RULES:
        return CREATE_USER_VALIDATION_RULES[(field, error_type)]
    return ValidationCodeRule(
        code="COMMON_000",
        key="COMMON_VALIDATION_ERROR",
        message="Request validation failed.",
    )


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
        loc = list(item.get("loc", []))
        error_type = str(item.get("type", "value_error"))
        field = _field_from_loc(loc)

        if endpoint == "POST /api/v1/user":
            rule = _resolve_create_user_rule(field, error_type)
        elif request.method in ("PUT", "PATCH") and PUT_PATCH_USER_BY_COMPOSITE_PATH.match(
            request.url.path
        ):
            rule = _resolve_update_user_rule(field, error_type)
        else:
            rule = ValidationCodeRule(
                code="COMMON_000",
                key="COMMON_VALIDATION_ERROR",
                message="Request validation failed.",
            )

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
