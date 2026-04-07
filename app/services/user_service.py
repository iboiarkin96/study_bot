"""Business logic for user registration workflow."""

from __future__ import annotations

from typing import Any

from app.models.core.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRegisterRequest


class UserService:
    """Service that handles create-or-update registration behavior."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    @staticmethod
    def _uuid_to_str(value: Any) -> str | None:
        """Convert UUID-like values to string for ORM assignment."""
        if value is None:
            return None
        return str(value)

    def register(self, payload: UserRegisterRequest) -> User:
        """Create new user or update existing one by telegram_user_id."""
        user = self.repository.get_by_telegram_user_id(payload.telegram_user_id)
        if user is None:
            user = User(
                telegram_user_id=payload.telegram_user_id,
                username=payload.username,
                full_name=payload.full_name,
                timezone=payload.timezone,
                system_uuid=self._uuid_to_str(payload.system_uuid),
                invalidation_reason_uuid=self._uuid_to_str(payload.invalidation_reason_uuid),
                system_user_uuid=self._uuid_to_str(payload.system_user_uuid),
                sysmem_name_uuid=self._uuid_to_str(payload.sysmem_name_uuid),
                is_row_invalid=payload.is_row_invalid,
            )
            return self.repository.save(user)

        user.username = payload.username
        user.full_name = payload.full_name
        user.timezone = payload.timezone
        user.system_uuid = self._uuid_to_str(payload.system_uuid)
        user.invalidation_reason_uuid = self._uuid_to_str(payload.invalidation_reason_uuid)
        user.system_user_uuid = self._uuid_to_str(payload.system_user_uuid)
        user.sysmem_name_uuid = self._uuid_to_str(payload.sysmem_name_uuid)
        user.is_row_invalid = payload.is_row_invalid
        return self.repository.save(user)
