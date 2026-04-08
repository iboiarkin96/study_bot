"""Pydantic schemas for user registration endpoint."""

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


class UserRegisterRequest(BaseModel):
    """Incoming payload for creating/updating user."""

    system_user_id: UUID = Field(
        ...,
        description="User ID in the source system (unique identity).",
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


class UserRegisterResponse(BaseModel):
    """Outgoing payload with persisted user data."""

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
