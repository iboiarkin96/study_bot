"""move to uuid keys and reference relations

Revision ID: b31a2f4d9c10
Revises: 8f2c9e3a1d11
Create Date: 2026-04-08 02:10:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b31a2f4d9c10"
down_revision: Union[str, None] = "8f2c9e3a1d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_uuid_expr() -> str:
    """Return SQL expression that generates UUID-like text in SQLite."""
    return (
        "lower(hex(randomblob(4))) || '-' || "
        "lower(hex(randomblob(2))) || '-' || "
        "'4' || substr(lower(hex(randomblob(2))), 2) || '-' || "
        "substr('89ab', abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))), 2) || '-' || "
        "lower(hex(randomblob(6)))"
    )


def upgrade() -> None:
    """Introduce UUID keys for core/reference links and constraints."""
    # Add UUID columns to reference tables and backfill.
    op.add_column("systems", sa.Column("system_uuid", sa.String(length=36), nullable=True))
    op.execute(f"UPDATE systems SET system_uuid = ({_sqlite_uuid_expr()}) WHERE system_uuid IS NULL")
    op.create_index("ix_systems_system_uuid", "systems", ["system_uuid"], unique=True)
    with op.batch_alter_table("systems", schema=None) as batch_op:
        batch_op.alter_column("system_uuid", existing_type=sa.String(length=36), nullable=False)

    op.add_column(
        "invalidation_reasons",
        sa.Column("invalidation_reason_uuid", sa.String(length=36), nullable=True),
    )
    op.execute(
        "UPDATE invalidation_reasons "
        f"SET invalidation_reason_uuid = ({_sqlite_uuid_expr()}) "
        "WHERE invalidation_reason_uuid IS NULL"
    )
    op.create_index(
        "ix_invalidation_reasons_invalidation_reason_uuid",
        "invalidation_reasons",
        ["invalidation_reason_uuid"],
        unique=True,
    )
    with op.batch_alter_table("invalidation_reasons", schema=None) as batch_op:
        batch_op.alter_column(
            "invalidation_reason_uuid",
            existing_type=sa.String(length=36),
            nullable=False,
        )

    # Add UUID columns to users and backfill.
    op.add_column("users", sa.Column("client_uuid", sa.String(length=36), nullable=True))
    op.execute(f"UPDATE users SET client_uuid = ({_sqlite_uuid_expr()}) WHERE client_uuid IS NULL")
    op.create_index("ix_users_client_uuid", "users", ["client_uuid"], unique=True)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("client_uuid", existing_type=sa.String(length=36), nullable=False)

    op.add_column("users", sa.Column("system_uuid", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("invalidation_reason_uuid", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("system_user_uuid", sa.String(length=36), nullable=True))

    op.execute(
        """
        UPDATE users
        SET system_uuid = (
            SELECT s.system_uuid FROM systems s WHERE s.id = users.system_id
        )
        WHERE system_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET invalidation_reason_uuid = (
            SELECT r.invalidation_reason_uuid
            FROM invalidation_reasons r
            WHERE r.id = users.invalidation_reason_id
        )
        WHERE invalidation_reason_id IS NOT NULL
        """
    )
    op.execute("UPDATE users SET system_user_uuid = CAST(system_user_id AS TEXT) WHERE system_user_id IS NOT NULL")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index("ix_users_system_uuid", ["system_uuid"], unique=False)
        batch_op.create_index("ix_users_invalidation_reason_uuid", ["invalidation_reason_uuid"], unique=False)
        batch_op.create_foreign_key(
            "fk_users_system_uuid_systems",
            "systems",
            ["system_uuid"],
            ["system_uuid"],
        )
        batch_op.create_foreign_key(
            "fk_users_invalidation_reason_uuid_reasons",
            "invalidation_reasons",
            ["invalidation_reason_uuid"],
            ["invalidation_reason_uuid"],
        )
        batch_op.drop_constraint("uq_users_system_user_id_sysmem_name_uuid", type_="unique")
        batch_op.create_unique_constraint(
            "uq_users_system_user_uuid_sysmem_name_uuid",
            ["system_user_uuid", "sysmem_name_uuid"],
        )
        batch_op.drop_constraint("fk_users_system_id_systems", type_="foreignkey")
        batch_op.drop_constraint("fk_users_invalidation_reason_id_reasons", type_="foreignkey")
        batch_op.drop_index("ix_users_system_id")
        batch_op.drop_index("ix_users_invalidation_reason_id")
        batch_op.drop_column("system_id")
        batch_op.drop_column("invalidation_reason_id")
        batch_op.drop_column("system_user_id")


def downgrade() -> None:
    """Revert UUID key migration to integer foreign key references."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("system_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("invalidation_reason_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("system_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_users_system_id", ["system_id"], unique=False)
        batch_op.create_index("ix_users_invalidation_reason_id", ["invalidation_reason_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_users_system_id_systems",
            "systems",
            ["system_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_users_invalidation_reason_id_reasons",
            "invalidation_reasons",
            ["invalidation_reason_id"],
            ["id"],
        )
        batch_op.drop_constraint("uq_users_system_user_uuid_sysmem_name_uuid", type_="unique")
        batch_op.create_unique_constraint(
            "uq_users_system_user_id_sysmem_name_uuid",
            ["system_user_id", "sysmem_name_uuid"],
        )
        batch_op.drop_constraint("fk_users_system_uuid_systems", type_="foreignkey")
        batch_op.drop_constraint("fk_users_invalidation_reason_uuid_reasons", type_="foreignkey")
        batch_op.drop_index("ix_users_system_uuid")
        batch_op.drop_index("ix_users_invalidation_reason_uuid")
        batch_op.drop_column("system_uuid")
        batch_op.drop_column("invalidation_reason_uuid")
        batch_op.drop_column("system_user_uuid")
        batch_op.drop_index("ix_users_client_uuid")
        batch_op.drop_column("client_uuid")

    op.drop_index("ix_invalidation_reasons_invalidation_reason_uuid", table_name="invalidation_reasons")
    op.drop_column("invalidation_reasons", "invalidation_reason_uuid")

    op.drop_index("ix_systems_system_uuid", table_name="systems")
    op.drop_column("systems", "system_uuid")
