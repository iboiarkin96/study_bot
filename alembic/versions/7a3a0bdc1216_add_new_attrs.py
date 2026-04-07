"""add_new_attrs

Revision ID: 7a3a0bdc1216
Revises: 20260408_0001
Create Date: 2026-04-08 00:48:50.016637
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a3a0bdc1216'
down_revision: Union[str, None] = '20260408_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
