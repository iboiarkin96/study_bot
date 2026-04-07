"""cleanup uuid schema

Revision ID: d92bbf4f8a21
Revises: b31a2f4d9c10
Create Date: 2026-04-08 02:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d92bbf4f8a21"
down_revision: Union[str, None] = "b31a2f4d9c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop legacy field and normalize UUID column lengths."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("invalid_reason")
        batch_op.alter_column(
            "sysmem_name_uuid",
            existing_type=sa.String(length=255),
            type_=sa.String(length=36),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Restore legacy field and previous UUID text length."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "sysmem_name_uuid",
            existing_type=sa.String(length=36),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column("invalid_reason", sa.String(length=255), nullable=True))
