"""Paths and bodies for User API tests — same sources as tools/load_testing (schema from app)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.api.v1.user import USER_HTTP_BASE_PATH
from app.schemas.user import UserCreateRequest, UserPatchRequest, UserUpdateRequest

# Must match ``systems`` rows seeded in ``tests.conftest`` (FK from ``users.system_uuid``).
TEST_SYSTEM_UUID = "b2c3d4e5-0002-4000-8000-000000000002"
TEST_SYSTEM_UUID_ALT = "e5f67890-0005-4000-8000-000000000005"
# Row in ``invalidation_reasons`` for FK from ``users.invalidation_reason_uuid``.
TEST_INVALIDATION_REASON_UUID = "d4e5f678-0004-4000-8000-000000000004"

# Re-export for tests: single import instead of duplicating the path string.
__all__ = [
    "USER_HTTP_BASE_PATH",
    "USER_CREATE_OPERATION",
    "TEST_SYSTEM_UUID",
    "TEST_SYSTEM_UUID_ALT",
    "TEST_INVALIDATION_REASON_UUID",
    "user_create_body",
    "user_resource_path",
    "user_patch_body",
    "user_update_body",
]

USER_CREATE_OPERATION: str = f"POST {USER_HTTP_BASE_PATH}"


def user_resource_path(
    system_user_id: str,
    *,
    system_uuid: str = TEST_SYSTEM_UUID,
) -> str:
    """Build path ``/api/v1/user/{system_uuid}/{system_user_id}`` for GET/PUT/PATCH.

    Args:
        system_user_id: External user id segment (unencoded).
        system_uuid: Source system UUID (must exist in ``systems``).

    Returns:
        URL path without host, same base as :data:`USER_HTTP_BASE_PATH`.
    """
    return f"{USER_HTTP_BASE_PATH}/{system_uuid}/{system_user_id}"


def user_create_body(
    system_user_id: str,
    *,
    full_name: str = "Ivan Petrov",
    timezone: str = "UTC",
    username: str | None = None,
    system_uuid: str = TEST_SYSTEM_UUID,
    invalidation_reason_uuid: str | None = None,
) -> dict[str, Any]:
    """Build a valid JSON body for ``POST /api/v1/user`` via :class:`~app.schemas.user.UserCreateRequest`.

    Args:
        system_user_id: Required external id.
        full_name: Display name (default for tests).
        timezone: IANA timezone (must exist in test DB seeds).
        username: Optional username.
        system_uuid: Source system UUID (must exist in ``systems``).
        invalidation_reason_uuid: Optional FK to ``invalidation_reasons`` (must exist if set).

    Returns:
        ``model_dump(mode="json")`` dict suitable for HTTP JSON body.
    """
    return UserCreateRequest(
        system_user_id=system_user_id,
        full_name=full_name,
        timezone=timezone,
        username=username,
        system_uuid=UUID(system_uuid),
        invalidation_reason_uuid=UUID(invalidation_reason_uuid)
        if invalidation_reason_uuid
        else None,
    ).model_dump(mode="json")


def user_patch_body(*, full_name: str = "Patch Only Name") -> dict[str, Any]:
    """Build a minimal valid JSON body for ``PATCH /api/v1/user/{system_uuid}/{id}``."""
    return UserPatchRequest(full_name=full_name).model_dump(mode="json", exclude_unset=True)


def user_update_body(
    *,
    full_name: str = "Petr Ivanov",
    timezone: str = "UTC",
    username: str | None = "ipetrov_updated",
    is_row_invalid: int = 0,
) -> dict[str, Any]:
    """Build a valid JSON body for ``PUT /api/v1/user/...`` via :class:`~app.schemas.user.UserUpdateRequest`."""
    return UserUpdateRequest(
        full_name=full_name,
        timezone=timezone,
        username=username,
        is_row_invalid=is_row_invalid,
    ).model_dump(mode="json")
