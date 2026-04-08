"""Core model for idempotency key dedup records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utc_now() -> datetime:
    """Timezone-aware UTC instant for column defaults."""
    return datetime.now(UTC)


class IdempotencyKeyRecord(Base):
    """Stored result for one idempotent write request key."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "endpoint_path",
            "idempotency_key",
            name="uq_idempotency_keys_endpoint_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint_path: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
