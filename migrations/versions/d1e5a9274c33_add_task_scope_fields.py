"""add task scope fields

Revision ID: d1e5a9274c33
Revises: b3c9f0d2a814
Create Date: 2026-07-10 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd1e5a9274c33'
down_revision: Union[str, None] = 'b3c9f0d2a814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scheduled_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('goal_id', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('scope', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_index(op.f('ix_task_goal_id'), ['goal_id'], unique=False)
        batch_op.create_index(op.f('ix_task_scheduled_date'), ['scheduled_date'], unique=False)
        batch_op.create_index(op.f('ix_task_scope'), ['scope'], unique=False)

    connection = op.get_bind()
    connection.execute(sa.text("UPDATE task SET kind = 'project' WHERE kind IS NULL"))
    connection.execute(sa.text("UPDATE task SET scope = 'milestone' WHERE scope IS NULL"))
    connection.execute(
        sa.text(
            """
            UPDATE task
            SET goal_id = (
                SELECT milestone.goal_id
                FROM milestone
                WHERE milestone.id = task.milestone_id
            )
            WHERE goal_id IS NULL AND milestone_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index(op.f('ix_task_scope'))
        batch_op.drop_index(op.f('ix_task_scheduled_date'))
        batch_op.drop_index(op.f('ix_task_goal_id'))
        batch_op.drop_column('scope')
        batch_op.drop_column('kind')
        batch_op.drop_column('goal_id')
        batch_op.drop_column('scheduled_date')
