"""add focus flag to todo occurrences

Revision ID: c7e1f0a2b9d4
Revises: a31f6e8c2d4b
Create Date: 2026-07-14 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7e1f0a2b9d4'
down_revision: Union[str, None] = 'a31f6e8c2d4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('todooccurrence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_focus', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('todooccurrence', schema=None) as batch_op:
        batch_op.drop_column('is_focus')
