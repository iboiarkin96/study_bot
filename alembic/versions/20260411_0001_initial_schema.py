"""initial_schema

Baseline revision: full schema matching ORM models + IANA ``timezones`` seed.

Revision ID: 20260411_0001
Revises:
Create Date: 2026-04-11
"""
from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Sequence, Union

from alembic import op
from zoneinfo import ZoneInfo, available_timezones
import sqlalchemy as sa


revision: str = "20260411_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Standard offset (non-DST) for each zone — Jan 1 UTC.
_REF_DT = datetime(2026, 1, 1, tzinfo=tz.utc)


def _utc_offset_minutes(code: str) -> int:
    """Return offset from UTC in minutes for ``code`` at ``_REF_DT``."""
    try:
        return int(round(ZoneInfo(code).utcoffset(_REF_DT).total_seconds() / 60))
    except Exception:
        return 0


def upgrade() -> None:
    op.create_table(
        "timezones",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("utc_offset", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    tz_rows = [
        {"code": code, "utc_offset": _utc_offset_minutes(code)}
        for code in sorted(available_timezones())
    ]
    tz_table = sa.table(
        "timezones",
        sa.column("code", sa.String(length=64)),
        sa.column("utc_offset", sa.Integer()),
    )
    op.bulk_insert(tz_table, tz_rows)

    op.create_table(
        "systems",
        sa.Column("system_uuid", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("system_uuid"),
    )
    op.create_index(op.f("ix_systems_code"), "systems", ["code"], unique=True)

    op.create_table(
        "invalidation_reasons",
        sa.Column("invalidation_reason_uuid", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("invalidation_reason_uuid"),
    )

    op.create_table(
        "users",
        sa.Column("client_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_row_invalid", sa.Integer(), nullable=False),
        sa.Column(
            "invalidation_reason_uuid",
            sa.String(length=36),
            sa.ForeignKey("invalidation_reasons.invalidation_reason_uuid"),
            nullable=True,
        ),
        sa.Column("system_user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "system_uuid",
            sa.String(length=36),
            sa.ForeignKey("systems.system_uuid"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            sa.ForeignKey("timezones.code"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("client_uuid"),
        sa.UniqueConstraint(
            "system_user_id",
            "system_uuid",
            name="uq_users_system_user_id_system_uuid",
        ),
    )
    op.create_index(
        op.f("ix_users_invalidation_reason_uuid"),
        "users",
        ["invalidation_reason_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_users_system_uuid"),
        "users",
        ["system_uuid"],
        unique=False,
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("endpoint_path", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "endpoint_path",
            "idempotency_key",
            name="uq_idempotency_keys_endpoint_key",
        ),
    )
    op.create_index(
        op.f("ix_idempotency_keys_endpoint_path"),
        "idempotency_keys",
        ["endpoint_path"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_keys_idempotency_key"),
        "idempotency_keys",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_idempotency_keys_idempotency_key"), table_name="idempotency_keys")
    op.drop_index(op.f("ix_idempotency_keys_endpoint_path"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    op.drop_index(op.f("ix_users_system_uuid"), table_name="users")
    op.drop_index(op.f("ix_users_invalidation_reason_uuid"), table_name="users")
    op.drop_table("users")

    op.drop_table("invalidation_reasons")

    op.drop_index(op.f("ix_systems_code"), table_name="systems")
    op.drop_table("systems")

    op.drop_table("timezones")
