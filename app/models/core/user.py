"""Core business model: user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utc_now() -> datetime:
    """Timezone-aware UTC instant for column defaults."""
    return datetime.now(timezone.utc)


if TYPE_CHECKING:
    from app.models.reference.invalidation_reason import InvalidationReason
    from app.models.reference.system import System


class User(Base):
    """Application user mapped from Telegram identity."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "system_user_uuid",
            "sysmem_name_uuid",
            name="uq_users_system_user_uuid_sysmem_name_uuid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
    )
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )
    is_row_invalid: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    system_uuid: Mapped[str] = mapped_column(
        ForeignKey("systems.system_uuid"),
        nullable=True,
        index=True,
    )
    invalidation_reason_uuid: Mapped[str] = mapped_column(
        ForeignKey("invalidation_reasons.invalidation_reason_uuid"),
        nullable=True,
        index=True,
    )
    system_user_uuid: Mapped[str] = mapped_column(String(36), nullable=True)
    sysmem_name_uuid: Mapped[str] = mapped_column(String(36), nullable=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    system: Mapped["System"] = relationship(back_populates="users")
    invalidation_reason: Mapped["InvalidationReason"] = relationship(
        back_populates="users",
    )
