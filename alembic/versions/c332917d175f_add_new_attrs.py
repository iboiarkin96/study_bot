"""add_new_attrs

Revision ID: c332917d175f
Revises: 7a3a0bdc1216
Create Date: 2026-04-08 00:50:32.894704
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c332917d175f'
down_revision: Union[str, None] = '7a3a0bdc1216'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
