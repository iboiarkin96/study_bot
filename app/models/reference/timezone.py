"""Reference model: IANA timezones dictionary."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Timezone(Base):
    """Reference row: IANA zone name and UTC offset in minutes for FK from users.

    Attributes:
        id: Surrogate primary key.
        code: IANA string (e.g. ``Europe/Moscow``), unique.
        utc_offset: Offset from UTC in minutes.
    """

    __tablename__ = "timezones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    utc_offset: Mapped[int] = mapped_column(Integer, nullable=False)
