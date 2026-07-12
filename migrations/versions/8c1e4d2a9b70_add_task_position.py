"""add task position

Revision ID: 8c1e4d2a9b70
Revises: 7b2d0e61c4a9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8c1e4d2a9b70'
down_revision: Union[str, None] = '7b2d0e61c4a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), server_default='0', nullable=False))
        batch_op.create_index(op.f('ix_task_position'), ['position'], unique=False)

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, milestone_id
            FROM task
            WHERE deleted_at IS NULL
            ORDER BY milestone_id, start_datetime, title, id
            """
        )
    ).fetchall()
    positions_by_milestone: dict[str, int] = {}
    for task_id, milestone_id in rows:
        key = str(milestone_id)
        next_position = positions_by_milestone.get(key, 0) + 1
        positions_by_milestone[key] = next_position
        connection.execute(
            sa.text("UPDATE task SET position = :position WHERE id = :id"),
            {"position": next_position, "id": task_id},
        )


def downgrade() -> None:
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index(op.f('ix_task_position'))
        batch_op.drop_column('position')
