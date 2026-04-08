"""Business logic for user registration workflow."""

from __future__ import annotations

from typing import Any
import uuid

from fastapi import HTTPException

from app.models.core.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRegisterRequest


class UserService:
    """Service that handles all behaviors related to user."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    @staticmethod
    def _uuid_to_str(value: Any) -> str | None:
        """Convert UUID-like values to string for ORM assignment."""
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _uuid_generation() -> str:
        """Generate a robust, random, unique UUID4 string."""
        return str(uuid.uuid4())

    def register(self, payload: UserRegisterRequest) -> User:
        """Create new user or raise if already exists."""
        su_id = str(payload.system_user_id)

        user = self.repository.get_by_system_user_id(su_id)
        if user is not None:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "101",
                    "key": "USR_REG_ALREADY_EXISTS",
                    "message": "User with this `system_user_id` already exists.",
                    "source": "business",
                },
            )

        user = User(
            system_user_id=su_id,
            username=payload.username,
            full_name=payload.full_name,
            timezone=payload.timezone,
            system_uuid=self._uuid_generation(),
            invalidation_reason_uuid=self._uuid_to_str(payload.invalidation_reason_uuid),
            is_row_invalid=payload.is_row_invalid,
        )
        return self.repository.save(user)
