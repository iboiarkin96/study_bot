"""OpenAPI examples for standard API errors."""

from __future__ import annotations

from typing import Final, cast

from app.errors.common import COMMON_400, COMMON_401, COMMON_409, COMMON_413, COMMON_429
from app.errors.types import StableError
from app.errors.user import (
    USER_001,
    USER_002,
    USER_003,
    USER_004,
    USER_005,
    USER_006,
    USER_007,
    USER_008,
    USER_009,
    USER_010,
    USER_011,
    USER_012,
    USER_013,
    USER_014,
    USER_018,
    USER_025,
    USER_101,
    USER_102,
    USER_404,
)

USER_EXISTS_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_101.as_detail("business")
)

USER_NOT_FOUND_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_404.as_detail("business")
)

USER_PATCH_BODY_EMPTY_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_102.as_detail("business")
)


def _validation_error_example(
    err: StableError,
    *,
    endpoint: str = "POST /api/v1/user",
    field: str | None,
    error_type: str,
    loc: list[object],
    input_value: object,
    ctx: object,
) -> dict[str, object]:
    """Build one documented 422 example body for OpenAPI ``examples`` maps.

    Args:
        err: Stable identity from :mod:`app.errors.user`.
        endpoint: ``endpoint`` field in the error payload (method + path).
        field: Affected body field name, if any.
        error_type: Pydantic error type string.
        loc: ``loc`` path from the validation error.
        input_value: Invalid input snippet for documentation.
        ctx: Extra context from Pydantic, if any.

    Returns:
        Full JSON object matching :class:`~app.schemas.errors.ValidationErrorResponse` shape.
    """
    return {
        "error_type": "validation_error",
        "endpoint": endpoint,
        "errors": [
            {
                "code": err.code,
                "key": err.key,
                "message": err.message,
                "field": field,
                "source": "validation",
                "details": {
                    "type": error_type,
                    "loc": loc,
                    "input": input_value,
                    "ctx": ctx,
                },
            }
        ],
    }


USER_CREATE_VALIDATION_ERROR_EXAMPLES: Final[dict[str, dict[str, object]]] = {
    "missing_system_user_id": {
        "summary": "Missing required field system_user_id",
        "value": _validation_error_example(
            USER_001,
            field="system_user_id",
            error_type="missing",
            loc=["body", "system_user_id"],
            input_value={"full_name": "Ivan Petrov", "timezone": "UTC"},
            ctx=None,
        ),
    },
    "empty_system_user_id": {
        "summary": "system_user_id is empty",
        "value": _validation_error_example(
            USER_002,
            field="system_user_id",
            error_type="string_too_short",
            loc=["body", "system_user_id"],
            input_value="",
            ctx={"min_length": 1},
        ),
    },
    "missing_full_name": {
        "summary": "Missing required field full_name",
        "value": _validation_error_example(
            USER_003,
            field="full_name",
            error_type="missing",
            loc=["body", "full_name"],
            input_value={
                "system_user_id": "1",
                "system_uuid": "b2c3d4e5-0002-4000-8000-000000000002",
                "timezone": "UTC",
            },
            ctx=None,
        ),
    },
    "missing_system_uuid": {
        "summary": "Missing required field system_uuid",
        "value": _validation_error_example(
            USER_025,
            field="system_uuid",
            error_type="missing",
            loc=["body", "system_uuid"],
            input_value={"system_user_id": "1", "full_name": "Ivan Petrov", "timezone": "UTC"},
            ctx=None,
        ),
    },
    "empty_full_name": {
        "summary": "full_name is empty",
        "value": _validation_error_example(
            USER_004,
            field="full_name",
            error_type="string_too_short",
            loc=["body", "full_name"],
            input_value="",
            ctx={"min_length": 1},
        ),
    },
    "full_name_too_long": {
        "summary": "full_name exceeds max length",
        "value": _validation_error_example(
            USER_005,
            field="full_name",
            error_type="string_too_long",
            loc=["body", "full_name"],
            input_value="A" * 256,
            ctx={"max_length": 255},
        ),
    },
    "username_too_long": {
        "summary": "username exceeds max length",
        "value": _validation_error_example(
            USER_006,
            field="username",
            error_type="string_too_long",
            loc=["body", "username"],
            input_value="u" * 256,
            ctx={"max_length": 255},
        ),
    },
    "invalid_timezone": {
        "summary": "Invalid timezone name",
        "value": _validation_error_example(
            USER_007,
            field="timezone",
            error_type="value_error",
            loc=["body", "timezone"],
            input_value="Europe/Mscow",
            ctx={"error": {}},
        ),
    },
    "timezone_too_long": {
        "summary": "timezone exceeds max length",
        "value": _validation_error_example(
            USER_008,
            field="timezone",
            error_type="string_too_long",
            loc=["body", "timezone"],
            input_value="Europe/" + ("X" * 80),
            ctx={"max_length": 64},
        ),
    },
    "invalid_system_uuid": {
        "summary": "system_uuid is not a UUID",
        "value": _validation_error_example(
            USER_009,
            field="system_uuid",
            error_type="uuid_parsing",
            loc=["body", "system_uuid"],
            input_value="not-a-uuid",
            ctx={
                "error": "invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `n` at 1"
            },
        ),
    },
    "invalid_invalidation_reason_uuid": {
        "summary": "invalidation_reason_uuid is not a UUID",
        "value": _validation_error_example(
            USER_010,
            field="invalidation_reason_uuid",
            error_type="uuid_parsing",
            loc=["body", "invalidation_reason_uuid"],
            input_value="bad-uuid",
            ctx={
                "error": "invalid character: expected an optional prefix of `urn:uuid:` followed by [0-9a-fA-F-], found `b` at 1"
            },
        ),
    },
    "is_row_invalid_not_int": {
        "summary": "is_row_invalid has wrong type",
        "value": _validation_error_example(
            USER_011,
            field="is_row_invalid",
            error_type="int_parsing",
            loc=["body", "is_row_invalid"],
            input_value="yes",
            ctx=None,
        ),
    },
    "is_row_invalid_too_small": {
        "summary": "is_row_invalid is below minimum",
        "value": _validation_error_example(
            USER_012,
            field="is_row_invalid",
            error_type="greater_than_equal",
            loc=["body", "is_row_invalid"],
            input_value=-1,
            ctx={"ge": 0},
        ),
    },
    "is_row_invalid_too_large": {
        "summary": "is_row_invalid is above maximum",
        "value": _validation_error_example(
            USER_013,
            field="is_row_invalid",
            error_type="less_than_equal",
            loc=["body", "is_row_invalid"],
            input_value=2,
            ctx={"le": 1},
        ),
    },
}

_USER_PATH_EXAMPLE = "/api/v1/user/b2c3d4e5-0002-4000-8000-000000000002/134tg"
_USER_UPDATE_EP = f"PUT {_USER_PATH_EXAMPLE}"
_USER_PATCH_EP = f"PATCH {_USER_PATH_EXAMPLE}"

USER_UPDATE_VALIDATION_ERROR_EXAMPLES: Final[dict[str, dict[str, object]]] = {
    "missing_full_name": {
        "summary": "Missing required field full_name (update)",
        "value": _validation_error_example(
            USER_014,
            endpoint=_USER_UPDATE_EP,
            field="full_name",
            error_type="missing",
            loc=["body", "full_name"],
            input_value={"timezone": "UTC", "is_row_invalid": 0},
            ctx=None,
        ),
    },
    "invalid_timezone": {
        "summary": "Invalid timezone name (update)",
        "value": _validation_error_example(
            USER_018,
            endpoint=_USER_UPDATE_EP,
            field="timezone",
            error_type="value_error",
            loc=["body", "timezone"],
            input_value="Europe/Mscow",
            ctx={"error": {}},
        ),
    },
}

USER_PATCH_VALIDATION_ERROR_EXAMPLES: Final[dict[str, dict[str, object]]] = {
    "invalid_timezone": {
        "summary": "Invalid timezone name (patch)",
        "value": _validation_error_example(
            USER_018,
            endpoint=_USER_PATCH_EP,
            field="timezone",
            error_type="value_error",
            loc=["body", "timezone"],
            input_value="Europe/Mscow",
            ctx={"error": {}},
        ),
    },
}

TIMEZONE_VALIDATION_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_CREATE_VALIDATION_ERROR_EXAMPLES["invalid_timezone"]["value"]
)
USER_CREATE_REQUIRED_FIELD_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_CREATE_VALIDATION_ERROR_EXAMPLES["missing_system_user_id"]["value"]
)

SECURITY_AUTH_REQUIRED_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], COMMON_401.as_detail("security")
)

SECURITY_RATE_LIMIT_EXCEEDED_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], COMMON_429.as_detail("security")
)

SECURITY_BODY_TOO_LARGE_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], COMMON_413.as_detail("security")
)

IDEMPOTENCY_KEY_REQUIRED_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], COMMON_400.as_detail("business")
)

IDEMPOTENCY_KEY_CONFLICT_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], COMMON_409.as_detail("business")
)
