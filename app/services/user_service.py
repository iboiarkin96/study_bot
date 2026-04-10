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
    """Domain logic for user creation and lookup by ``system_user_id``."""

    def __init__(self, repository: UserRepository) -> None:
        """Create a service that uses ``repository`` for persistence.

        Args:
            repository: User data access instance.
        """
        self.repository = repository

    @staticmethod
    def _uuid_to_str(value: Any) -> str | None:
        """Normalize optional UUID inputs to plain strings for the ORM.

        Args:
            value: UUID object or string, or ``None``.

        Returns:
            String form, or ``None`` if input was ``None``.
        """
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _uuid_generation() -> str:
        """Return a new random UUID4 string for internal surrogate keys.

        Returns:
            Lowercase hex UUID string.
        """
        return str(uuid.uuid4())

    def create(self, payload: UserCreateRequest) -> User:
        """Persist a new user or signal a duplicate ``system_user_id``.

        Args:
            payload: Validated create request body.

        Returns:
            Saved :class:`~app.models.core.user.User` entity.

        Raises:
            fastapi.HTTPException: 400 with ``USER_101`` when the user already exists.
        """
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

    def get_or_404(self, system_user_id: str) -> User:
        """Return the user for ``system_user_id`` or raise a business 404.

        Args:
            system_user_id: External identifier from the source system.

        Returns:
            Matching :class:`~app.models.core.user.User`.

        Raises:
            fastapi.HTTPException: 404 with ``USER_404`` when not found.
        """
        user = self.repository.get_by_system_user_id(system_user_id)
        if user is None:
            logger.warning("get_user_not_found system_user_id=%s", system_user_id)
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "USER_404",
                    "key": "USER_NOT_FOUND",
                    "message": "User with this `system_user_id` was not found.",
                    "source": "business",
                },
            )
        return user
