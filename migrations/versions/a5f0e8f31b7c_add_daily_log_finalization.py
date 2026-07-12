"""add daily log finalization

Revision ID: a5f0e8f31b7c
Revises: f4a2bc91d632
Create Date: 2026-07-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a5f0e8f31b7c'
down_revision: Union[str, None] = 'f4a2bc91d632'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('dailylog', schema=None) as batch_op:
        batch_op.add_column(sa.Column('finalized_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('finalized_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('dailylog', schema=None) as batch_op:
        batch_op.drop_column('finalized_by')
        batch_op.drop_column('finalized_at')
