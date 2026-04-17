"""Business logic for user create workflow."""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import HTTPException

from app.errors.user import USER_101, USER_102, USER_404
from app.models.core.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreateRequest, UserPatchRequest, UserUpdateRequest

logger = logging.getLogger(__name__)


class UserService:
    """Domain logic for user create, update, and lookup by ``(system_user_id, system_uuid)``."""

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

    def create(self, payload: UserCreateRequest) -> User:
        """Persist a new user or reject a duplicate composite key.

        Args:
            payload: Validated create body; uniqueness is ``(system_user_id, system_uuid)``.

        Returns:
            Persisted :class:`~app.models.core.user.User` after save.

        Raises:
            fastapi.HTTPException: 400 with ``USER_CREATE_ALREADY_EXISTS`` when the composite key exists.
        """
        su_id = str(payload.system_user_id)
        sys_uuid = str(payload.system_uuid)

        if self.repository.get_by_system_user_id_and_system_uuid(su_id, sys_uuid) is not None:
            logger.warning(
                "create_user_duplicate system_user_id=%s system_uuid=%s",
                su_id,
                sys_uuid,
            )
            raise HTTPException(
                status_code=400,
                detail=USER_101.as_detail("business"),
            )

        user = User(
            system_user_id=su_id,
            system_uuid=sys_uuid,
            username=payload.username,
            full_name=payload.full_name,
            timezone=payload.timezone,
            invalidation_reason_uuid=self._uuid_to_str(payload.invalidation_reason_uuid),
            is_row_invalid=payload.is_row_invalid,
        )
        persisted_user = self.repository.save(user)
        logger.info(
            "create_user_persisted system_user_id=%s system_uuid=%s client_uuid=%s",
            persisted_user.system_user_id,
            persisted_user.system_uuid,
            persisted_user.client_uuid,
        )
        return persisted_user

    def update(
        self,
        *,
        system_user_id: str,
        system_uuid: str,
        payload: UserUpdateRequest,
    ) -> User:
        """Replace mutable profile fields with ``payload`` for the composite key.

        Args:
            system_user_id: External user id in the source system.
            system_uuid: Source system UUID string.
            payload: Full update body (PUT semantics).

        Returns:
            Updated user row after commit.

        Raises:
            fastapi.HTTPException: 404 when no user matches the composite key.
        """
        user = self.get_or_404(system_user_id=system_user_id, system_uuid=system_uuid)
        user.username = cast(Any, payload.username)
        user.full_name = payload.full_name
        user.timezone = payload.timezone
        user.invalidation_reason_uuid = cast(
            Any, self._uuid_to_str(payload.invalidation_reason_uuid)
        )
        user.is_row_invalid = payload.is_row_invalid
        if payload.system_uuid is not None:
            user.system_uuid = cast(Any, self._uuid_to_str(payload.system_uuid))
        return self.repository.save(user)

    def patch(
        self,
        *,
        system_user_id: str,
        system_uuid: str,
        payload: UserPatchRequest,
    ) -> User:
        """Merge only set fields from ``payload`` (PATCH semantics).

        Args:
            system_user_id: External user id in the source system.
            system_uuid: Source system UUID string.
            payload: Partial body; omitted fields are left unchanged.

        Returns:
            Updated user row after commit.

        Raises:
            fastapi.HTTPException: 400 when the body omits every field, or 404 when the user is missing.
        """
        user = self.get_or_404(system_user_id=system_user_id, system_uuid=system_uuid)
        data = payload.model_dump(exclude_unset=True)
        if not data:
            logger.warning(
                "patch_user_empty_body system_user_id=%s system_uuid=%s",
                system_user_id,
                system_uuid,
            )
            raise HTTPException(
                status_code=400,
                detail=USER_102.as_detail("business"),
            )
        if "username" in data:
            user.username = cast(Any, data["username"])
        if "full_name" in data and data["full_name"] is not None:
            user.full_name = data["full_name"]
        if "timezone" in data and data["timezone"] is not None:
            user.timezone = data["timezone"]
        if "invalidation_reason_uuid" in data:
            user.invalidation_reason_uuid = cast(
                Any, self._uuid_to_str(data["invalidation_reason_uuid"])
            )
        if "is_row_invalid" in data and data["is_row_invalid"] is not None:
            user.is_row_invalid = data["is_row_invalid"]
        if "system_uuid" in data:
            su = self._uuid_to_str(data["system_uuid"])
            if su is not None:
                user.system_uuid = cast(Any, su)
        return self.repository.save(user)

    def get_or_404(self, *, system_user_id: str, system_uuid: str) -> User:
        """Load the user for the composite key or raise a business-layer 404.

        Args:
            system_user_id: External user id in the source system.
            system_uuid: Source system UUID string.

        Returns:
            ORM user when found.

        Raises:
            fastapi.HTTPException: 404 with ``USER_NOT_FOUND`` when absent.
        """
        user = self.repository.get_by_system_user_id_and_system_uuid(
            system_user_id,
            system_uuid,
        )
        if user is None:
            logger.warning(
                "get_user_not_found system_user_id=%s system_uuid=%s",
                system_user_id,
                system_uuid,
            )
            raise HTTPException(
                status_code=404,
                detail=USER_404.as_detail("business"),
            )
        return user
