"""Paths and bodies for User API tests — same sources as tools/load_testing (schema from app)."""

from __future__ import annotations

from typing import Any

from app.api.v1.user import USER_HTTP_BASE_PATH
from app.schemas.user import UserCreateRequest

# Re-export for tests: single import instead of duplicating the path string.
__all__ = [
    "USER_HTTP_BASE_PATH",
    "USER_CREATE_OPERATION",
    "user_create_body",
    "user_resource_path",
]

USER_CREATE_OPERATION: str = f"POST {USER_HTTP_BASE_PATH}"


def user_resource_path(system_user_id: str) -> str:
    """Build path ``/api/v1/user/{system_user_id}`` for GET requests.

    Args:
        system_user_id: External user id segment (unencoded).

    Returns:
        URL path without host, same base as :data:`USER_HTTP_BASE_PATH`.
    """
    return f"{USER_HTTP_BASE_PATH}/{system_user_id}"


def user_create_body(
    system_user_id: str,
    *,
    full_name: str = "Ivan Petrov",
    timezone: str = "UTC",
    username: str | None = None,
) -> dict[str, Any]:
    """Build a valid JSON body for ``POST /api/v1/user`` via :class:`~app.schemas.user.UserCreateRequest`.

    Args:
        system_user_id: Required external id.
        full_name: Display name (default for tests).
        timezone: IANA timezone (must exist in test DB seeds).
        username: Optional username.

    Returns:
        ``model_dump(mode="json")`` dict suitable for HTTP JSON body.
    """
    return UserCreateRequest(
        system_user_id=system_user_id,
        full_name=full_name,
        timezone=timezone,
        username=username,
    ).model_dump(mode="json")
