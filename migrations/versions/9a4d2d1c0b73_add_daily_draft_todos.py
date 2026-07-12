"""add daily draft todos

Revision ID: 9a4d2d1c0b73
Revises: 6f8a2d4b71c0
Create Date: 2026-07-08 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9a4d2d1c0b73'
down_revision: Union[str, None] = '6f8a2d4b71c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dailydrafttodo',
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('done', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_dailydrafttodo_day', 'dailydrafttodo', ['day'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_dailydrafttodo_day', table_name='dailydrafttodo')
    op.drop_table('dailydrafttodo')
