"""add daily logs

Revision ID: b3c9f0d2a814
Revises: 9a4d2d1c0b73
Create Date: 2026-07-10 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b3c9f0d2a814'
down_revision: Union[str, None] = '9a4d2d1c0b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dailylog',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('color', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('note', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('trigger', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('what_helped', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('tomorrow_minimum', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dailylog_date', 'dailylog', ['date'], unique=False)
    op.create_index('ix_dailylog_user_id', 'dailylog', ['user_id'], unique=False)
    op.create_index('ix_dailylog_user_date', 'dailylog', ['user_id', 'date'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_dailylog_user_date', table_name='dailylog')
    op.drop_index('ix_dailylog_user_id', table_name='dailylog')
    op.drop_index('ix_dailylog_date', table_name='dailylog')
    op.drop_table('dailylog')
