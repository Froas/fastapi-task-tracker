"""add goal completion rule

Revision ID: c2b8a9f74621
Revises: a5f0e8f31b7c
Create Date: 2026-07-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2b8a9f74621'
down_revision: Union[str, None] = 'a5f0e8f31b7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completion_rule', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.drop_column('completion_rule')
