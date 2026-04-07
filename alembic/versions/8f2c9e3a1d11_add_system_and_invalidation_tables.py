"""add system and invalidation tables

Revision ID: 8f2c9e3a1d11
Revises: 06f652426c5e
Create Date: 2026-04-08 01:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f2c9e3a1d11"
down_revision: Union[str, None] = "06f652426c5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create helper tables and add composite uniqueness to users."""
    op.create_table(
        "systems",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_systems_code", "systems", ["code"], unique=True)

    op.create_table(
        "invalidation_reasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invalidation_reasons_code", "invalidation_reasons", ["code"], unique=True)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("system_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("invalidation_reason_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("system_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sysmem_name_uuid", sa.String(length=255), nullable=True))
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
        batch_op.create_unique_constraint(
            "uq_users_system_user_id_sysmem_name_uuid",
            ["system_user_id", "sysmem_name_uuid"],
        )


def downgrade() -> None:
    """Drop helper tables and remove related user fields."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_system_user_id_sysmem_name_uuid", type_="unique")
        batch_op.drop_constraint("fk_users_invalidation_reason_id_reasons", type_="foreignkey")
        batch_op.drop_constraint("fk_users_system_id_systems", type_="foreignkey")
        batch_op.drop_index("ix_users_invalidation_reason_id")
        batch_op.drop_index("ix_users_system_id")
        batch_op.drop_column("sysmem_name_uuid")
        batch_op.drop_column("system_user_id")
        batch_op.drop_column("invalidation_reason_id")
        batch_op.drop_column("system_id")

    op.drop_index("ix_invalidation_reasons_code", table_name="invalidation_reasons")
    op.drop_table("invalidation_reasons")
    op.drop_index("ix_systems_code", table_name="systems")
    op.drop_table("systems")
