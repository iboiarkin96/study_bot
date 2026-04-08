"""OpenAPI examples for standard API errors."""

from __future__ import annotations

from typing import Final

USER_EXISTS_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "code": "101",
    "key": "USR_REG_ALREADY_EXISTS",
    "message": "User with this `system_user_id` already exists.",
    "source": "business",
}

TIMEZONE_VALIDATION_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "error_type": "validation_error",
    "endpoint": "POST /api/v1/users/register",
    "errors": [
        {
            "code": "007",
            "key": "USR_REG_TIMEZONE_INVALID",
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

REGISTER_REQUIRED_FIELD_ERROR_EXAMPLE: Final[dict[str, object]] = {
    "error_type": "validation_error",
    "endpoint": "POST /api/v1/users/register",
    "errors": [
        {
            "code": "001",
            "key": "USR_REG_SYSTEM_USER_ID_REQUIRED",
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

