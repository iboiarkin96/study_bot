"""OpenAPI examples for standard API errors."""

from __future__ import annotations

from typing import Final

USER_EXISTS_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "USER_101",
    "key": "USER_CREATE_ALREADY_EXISTS",
    "message": "User with this `system_user_id` already exists.",
    "source": "business",
}

TIMEZONE_VALIDATION_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "error_type": "validation_error",
    "endpoint": "POST /api/v1/user",
    "errors": [
        {
            "code": "USER_007",
            "key": "USER_CREATE_TIMEZONE_INVALID",
            "message": "Field `timezone` must be a valid IANA timezone.",
            "field": "timezone",
            "source": "validation",
            "details": {
                "type": "value_error",
                "loc": ["body", "timezone"],
                "input": "Europe/Mscow",
                "ctx": {"error": {}},
            },
        }
    ],
}

USER_CREATE_REQUIRED_FIELD_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "error_type": "validation_error",
    "endpoint": "POST /api/v1/user",
    "errors": [
        {
            "code": "USER_001",
            "key": "USER_CREATE_SYSTEM_USER_ID_REQUIRED",
            "message": "Field `system_user_id` is required.",
            "field": "system_user_id",
            "source": "validation",
            "details": {
                "type": "missing",
                "loc": ["body", "system_user_id"],
                "input": {
                    "full_name": "Ivan Petrov",
                    "timezone": "UTC",
                },
                "ctx": None,
            },
        }
    ],
}

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
