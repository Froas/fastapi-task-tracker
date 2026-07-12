"""add note relations and signal kind

Revision ID: e19f3a7b0c42
Revises: c2b8a9f74621
Create Date: 2026-07-11 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e19f3a7b0c42'
down_revision: Union[str, None] = 'c2b8a9f74621'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('note', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='note'))
        batch_op.add_column(sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('goal_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('task_id', sa.Uuid(), nullable=True))
        batch_op.create_foreign_key('fk_note_goal_id_goal', 'goal', ['goal_id'], ['id'])
        batch_op.create_foreign_key('fk_note_task_id_task', 'task', ['task_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('note', schema=None) as batch_op:
        batch_op.drop_constraint('fk_note_task_id_task', type_='foreignkey')
        batch_op.drop_constraint('fk_note_goal_id_goal', type_='foreignkey')
        batch_op.drop_column('task_id')
        batch_op.drop_column('goal_id')
        batch_op.drop_column('source')
        batch_op.drop_column('kind')
