"""Reference model: invalidation reason dictionary."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.core.user import User


class InvalidationReason(Base):
    """Dictionary of reasons for row invalidation."""

    __tablename__ = "invalidation_reasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invalidation_reason_uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="invalidation_reason")
