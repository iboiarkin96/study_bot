"""Business logic for user create workflow."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException

from app.models.core.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreateRequest

logger = logging.getLogger(__name__)


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

    def create(self, payload: UserCreateRequest) -> User:
        """Create new user or raise if already exists."""
        su_id = str(payload.system_user_id)

        user = self.repository.get_by_system_user_id(su_id)
        if user is not None:
            logger.warning("create_user_duplicate system_user_id=%s", su_id)
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "USER_101",
                    "key": "USER_CREATE_ALREADY_EXISTS",
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
        persisted_user = self.repository.save(user)
        logger.info(
            "create_user_persisted system_user_id=%s client_uuid=%s",
            persisted_user.system_user_id,
            persisted_user.client_uuid,
        )
        return persisted_user
