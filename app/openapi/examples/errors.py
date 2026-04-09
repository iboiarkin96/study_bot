"""OpenAPI examples for standard API errors."""

from __future__ import annotations

from typing import Final, cast

USER_EXISTS_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "USER_101",
    "key": "USER_CREATE_ALREADY_EXISTS",
    "message": "User with this `system_user_id` already exists.",
    "source": "business",
}

USER_NOT_FOUND_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "USER_404",
    "key": "USER_NOT_FOUND",
    "message": "User with this `system_user_id` was not found.",
    "source": "business",
}


def _validation_error_example(
    *,
    code: str,
    key: str,
    message: str,
    field: str | None,
    error_type: str,
    loc: list[object],
    input_value: object,
    ctx: object,
) -> dict[str, object]:
    return {
        "error_type": "validation_error",
        "endpoint": "POST /api/v1/user",
        "errors": [
            {
                "code": code,
                "key": key,
                "message": message,
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
            code="USER_001",
            key="USER_CREATE_SYSTEM_USER_ID_REQUIRED",
            message="Field `system_user_id` is required.",
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
            code="USER_002",
            key="USER_CREATE_SYSTEM_USER_ID_INVALID",
            message="Field `system_user_id` must not be empty.",
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
            code="USER_003",
            key="USER_CREATE_FULL_NAME_REQUIRED",
            message="Field `full_name` is required.",
            field="full_name",
            error_type="missing",
            loc=["body", "full_name"],
            input_value={"system_user_id": "1", "timezone": "UTC"},
            ctx=None,
        ),
    },
    "empty_full_name": {
        "summary": "full_name is empty",
        "value": _validation_error_example(
            code="USER_004",
            key="USER_CREATE_FULL_NAME_TOO_SHORT",
            message="Field `full_name` must not be empty.",
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
            code="USER_005",
            key="USER_CREATE_FULL_NAME_TOO_LONG",
            message="Field `full_name` exceeds max length.",
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
            code="USER_006",
            key="USER_CREATE_USERNAME_TOO_LONG",
            message="Field `username` exceeds max length.",
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
            code="USER_007",
            key="USER_CREATE_TIMEZONE_INVALID",
            message="Field `timezone` must be a valid IANA timezone.",
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
            code="USER_008",
            key="USER_CREATE_TIMEZONE_TOO_LONG",
            message="Field `timezone` exceeds max length.",
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
            code="USER_009",
            key="USER_CREATE_SYSTEM_UUID_INVALID",
            message="Field `system_uuid` must be a valid UUID.",
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
            code="USER_010",
            key="USER_CREATE_INVALIDATION_REASON_UUID_INVALID",
            message="Field `invalidation_reason_uuid` must be a valid UUID.",
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
            code="USER_011",
            key="USER_CREATE_IS_ROW_INVALID_TYPE",
            message="Field `is_row_invalid` must be an integer.",
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
            code="USER_012",
            key="USER_CREATE_IS_ROW_INVALID_MIN",
            message="Field `is_row_invalid` must be >= 0.",
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
            code="USER_013",
            key="USER_CREATE_IS_ROW_INVALID_MAX",
            message="Field `is_row_invalid` must be <= 1.",
            field="is_row_invalid",
            error_type="less_than_equal",
            loc=["body", "is_row_invalid"],
            input_value=2,
            ctx={"le": 1},
        ),
    },
}

TIMEZONE_VALIDATION_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_CREATE_VALIDATION_ERROR_EXAMPLES["invalid_timezone"]["value"]
)
USER_CREATE_REQUIRED_FIELD_ERROR_EXAMPLE: Final[dict[str, object]] = cast(
    dict[str, object], USER_CREATE_VALIDATION_ERROR_EXAMPLES["missing_system_user_id"]["value"]
)

SECURITY_AUTH_REQUIRED_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "COMMON_401",
    "key": "SECURITY_AUTH_REQUIRED",
    "message": "Missing or invalid API key in header `X-API-Key`.",
    "source": "security",
}

SECURITY_RATE_LIMIT_EXCEEDED_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "COMMON_429",
    "key": "SECURITY_RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Retry later.",
    "source": "security",
}

SECURITY_BODY_TOO_LARGE_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "COMMON_413",
    "key": "SECURITY_REQUEST_BODY_TOO_LARGE",
    "message": "Request body exceeds configured maximum size.",
    "source": "security",
}

IDEMPOTENCY_KEY_REQUIRED_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "COMMON_400",
    "key": "IDEMPOTENCY_KEY_REQUIRED",
    "message": "Missing required `Idempotency-Key` header for write operation.",
    "source": "business",
}

IDEMPOTENCY_KEY_CONFLICT_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "COMMON_409",
    "key": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
    "message": "Idempotency key was already used with another payload.",
    "source": "business",
}
