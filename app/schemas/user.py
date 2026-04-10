"""Pydantic schemas for user create endpoint."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.openapi.examples import (
    FULL_NAME_EXAMPLES,
    INVALIDATION_REASON_UUID_EXAMPLES,
    IS_ROW_INVALID_EXAMPLES,
    SYSTEM_USER_ID_EXAMPLES,
    SYSTEM_UUID_EXAMPLES,
    TIMEZONE_EXAMPLES,
    USERNAME_EXAMPLES,
)
from app.schemas.enums import TimezoneField


class UserCreateRequest(BaseModel):
    """JSON body for ``POST /api/v1/user`` (validated before idempotency and service layer).

    Field-level rules, OpenAPI examples, and timezone validation live on the ``Field``
    definitions and :data:`app.schemas.enums.TimezoneField`.
    """

    system_user_id: str = Field(
        ...,
        min_length=1,
        max_length=36,
        description="User ID in the source system (unique external identity).",
        examples=SYSTEM_USER_ID_EXAMPLES,
    )
    username: str | None = Field(
        default=None,
        max_length=255,
        description="Username or login.",
        examples=USERNAME_EXAMPLES,
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the user.",
        examples=FULL_NAME_EXAMPLES,
    )
    timezone: TimezoneField = Field(
        default="UTC",
        min_length=1,
        max_length=64,
        description="IANA timezone name (e.g. 'UTC', 'Europe/Moscow').",
        examples=TIMEZONE_EXAMPLES,
    )
    system_uuid: UUID | None = Field(
        default=None,
        description="UUID of related system.",
        examples=SYSTEM_UUID_EXAMPLES,
    )
    invalidation_reason_uuid: UUID | None = Field(
        default=None,
        description="Related invalidation reason UUID.",
        examples=INVALIDATION_REASON_UUID_EXAMPLES,
    )
    is_row_invalid: int = Field(
        default=0,
        ge=0,
        le=1,
        description="Invalid row flag (0/1).",
        examples=IS_ROW_INVALID_EXAMPLES,
    )


class UserCreateResponse(BaseModel):
    """User resource returned by create (201) and get (200); maps ORM :class:`~app.models.core.user.User`.

    Attributes:
        client_uuid: Internal client identifier (UUID string).
        created_at: Row creation timestamp (timezone-aware).
        updated_at: Last update timestamp (timezone-aware).
        is_row_invalid: Soft-invalidation flag (0 or 1).
        invalidation_reason_uuid: FK to invalidation reason, if set.
        system_user_id: External system user id when present.
        system_uuid: Related system UUID when present.
        username: Optional display username.
        full_name: Required full name.
        timezone: IANA timezone string stored for the user.
    """

    model_config = ConfigDict(from_attributes=True)

    client_uuid: str
    created_at: datetime
    updated_at: datetime
    is_row_invalid: int
    invalidation_reason_uuid: str | None
    system_user_id: str | None
    system_uuid: str | None
    username: str | None
    full_name: str
    timezone: str
