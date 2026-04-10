"""Reference model: source systems dictionary."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.core.user import User


class System(Base):
    """Catalog of upstream systems that own user identities.

    Attributes:
        system_uuid: Stable UUID string for API references.
        code: Short code
        name: Display name.
        users: Reverse relation to :class:`~app.models.core.user.User`.
    """

    __tablename__ = "systems"

    system_uuid: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="system")
