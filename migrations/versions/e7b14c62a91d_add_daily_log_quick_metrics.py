"""add daily log quick metrics

Revision ID: e7b14c62a91d
Revises: d1e5a9274c33
Create Date: 2026-07-10 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b14c62a91d'
down_revision: Union[str, None] = 'd1e5a9274c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('dailylog', schema=None) as batch_op:
        batch_op.add_column(sa.Column('weight', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('calories', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('sleep_hours', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('steps', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('dailylog', schema=None) as batch_op:
        batch_op.drop_column('steps')
        batch_op.drop_column('sleep_hours')
        batch_op.drop_column('calories')
        batch_op.drop_column('weight')
