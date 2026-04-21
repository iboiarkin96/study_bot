"""Core business model: user."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utc_now() -> datetime:
    """Return current UTC time with tzinfo for :class:`~datetime.datetime` columns.

    Returns:
        Timezone-aware ``datetime`` in UTC.
    """
    return datetime.now(UTC)


if TYPE_CHECKING:
    from app.models.reference.invalidation_reason import InvalidationReason
    from app.models.reference.system import System


class User(Base):
    """End-user row keyed by external ``system_user_id`` and internal ``client_uuid``.

    Relationships: :attr:`system`, :attr:`invalidation_reason`. Timezone must exist in the
    ``timezones`` reference table.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "system_user_id",
            "system_uuid",
            name="uq_users_system_user_id_system_uuid",
        ),
    )

    client_uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        primary_key=True,
        default=lambda: str(uuid4()),
    )
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
    invalidation_reason_uuid: Mapped[str] = mapped_column(
        ForeignKey("invalidation_reasons.invalidation_reason_uuid"),
        nullable=True,
        index=True,
    )
    system_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    system_uuid: Mapped[str] = mapped_column(
        ForeignKey("systems.system_uuid"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("timezones.code"),
        nullable=False,
        default="UTC",
    )

    system: Mapped[System] = relationship(back_populates="users")
    invalidation_reason: Mapped[InvalidationReason | None] = relationship(
        back_populates="users",
    )
