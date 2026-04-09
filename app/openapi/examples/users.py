"""OpenAPI examples for user endpoints and schemas."""

from __future__ import annotations

from typing import Final

SYSTEM_USER_ID_EXAMPLES: Final[list[str]] = ["134tg"]
USERNAME_EXAMPLES: Final[list[str]] = ["ipetrov"]
FULL_NAME_EXAMPLES: Final[list[str]] = ["Ivan Petrov"]
TIMEZONE_EXAMPLES: Final[list[str]] = ["Europe/Moscow", "UTC", "America/New_York"]
SYSTEM_UUID_EXAMPLES: Final[list[str]] = ["b2c3d4e5-0002-4000-8000-000000000002"]
INVALIDATION_REASON_UUID_EXAMPLES: Final[list[str]] = ["c3d4e5f6-0003-4000-8000-000000000003"]
IS_ROW_INVALID_EXAMPLES: Final[list[int]] = [0, 1]

USER_CREATE_REQUEST_EXAMPLES: Final[dict[str, dict[str, object]]] = {
    "default": {
        "summary": "Basic registration",
        "value": {
            "system_user_id": SYSTEM_USER_ID_EXAMPLES[0],
            "full_name": FULL_NAME_EXAMPLES[0],
            "username": USERNAME_EXAMPLES[0],
            "timezone": TIMEZONE_EXAMPLES[0],
            "system_uuid": SYSTEM_UUID_EXAMPLES[0],
            "invalidation_reason_uuid": None,
            "is_row_invalid": 0,
        },
    },
    "minimal": {
        "summary": "Only required fields",
        "value": {
            "system_user_id": SYSTEM_USER_ID_EXAMPLES[0],
            "full_name": FULL_NAME_EXAMPLES[0],
        },
    },
}
