"""Data access layer for user entity."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core.user import User


class UserRepository:
    """Persistence layer for :class:`~app.models.core.user.User` entities."""

    def __init__(self, session: Session) -> None:
        """Create a repository bound to one ORM session.

        Args:
            session: Active SQLAlchemy session (caller owns transaction boundaries).
        """
        self.session = session

    def get_by_system_user_id(self, system_user_id: str) -> User | None:
        """Load a user by external ``system_user_id`` if present.

        Args:
            system_user_id: Unique external identifier from the source system.

        Returns:
            ORM entity or ``None``.
        """
        stmt = select(User).where(User.system_user_id == system_user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def save(self, user: User) -> User:
        """Insert or update ``user``, commit, and refresh from the database.

        Args:
            user: Transient or attached ``User`` instance.

        Returns:
            Same instance with generated keys and timestamps populated.
        """
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
