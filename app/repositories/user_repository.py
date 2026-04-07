"""Data access layer for user entity."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core.user import User


class UserRepository:
    """Repository for CRUD operations on users."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        """Fetch user by Telegram id."""
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def save(self, user: User) -> User:
        """Persist user and refresh entity values."""
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
