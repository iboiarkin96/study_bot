"""add_new_attrs

Revision ID: 06f652426c5e
Revises: c332917d175f
Create Date: 2026-04-08 01:02:24.828706
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06f652426c5e'
down_revision: Union[str, None] = 'c332917d175f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add validation attributes to users in SQLite-safe way."""
    op.add_column(
        "users",
        sa.Column(
            "is_row_invalid",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("users", sa.Column("invalid_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove validation attributes from users."""
    op.drop_column("users", "invalid_reason")
    op.drop_column("users", "is_row_invalid")
