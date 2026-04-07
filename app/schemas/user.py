"""Pydantic schemas for user registration endpoint."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    """Incoming payload for creating/updating user."""

    telegram_user_id: int = Field(..., gt=0, description="Unique Telegram user identifier.")
    username: str | None = Field(default=None, max_length=255, description="Telegram username.")
    full_name: str = Field(..., min_length=1, max_length=255, description="Display name.")
    timezone: str = Field(default="UTC", min_length=1, max_length=64, description="Timezone name.")
    system_uuid: UUID | None = Field(default=None, description="Related system UUID.")
    invalidation_reason_uuid: UUID | None = Field(
        default=None,
        description="Related invalidation reason UUID.",
    )
    system_user_uuid: UUID | None = Field(default=None, description="User UUID in source system.")
    sysmem_name_uuid: UUID | None = Field(default=None, description="System memory/name UUID.")
    is_row_invalid: int = Field(default=0, ge=0, le=1, description="Invalid row flag (0/1).")


class UserRegisterResponse(BaseModel):
    """Outgoing payload with persisted user data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_uuid: str
    telegram_user_id: int
    username: str | None
    full_name: str
    timezone: str
    system_uuid: str | None
    invalidation_reason_uuid: str | None
    system_user_uuid: str | None
    sysmem_name_uuid: str | None
    is_row_invalid: int
    created_at: datetime
    updated_at: datetime
