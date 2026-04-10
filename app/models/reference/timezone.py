"""Reference model: IANA timezones dictionary."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Timezone(Base):
    """Reference row: IANA zone name and UTC offset in minutes for FK from users.

    Attributes:
        code: IANA string (e.g. ``Europe/Moscow``), primary key.
        utc_offset: Offset from UTC in minutes.
    """

    __tablename__ = "timezones"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    utc_offset: Mapped[int] = mapped_column(Integer, nullable=False)
