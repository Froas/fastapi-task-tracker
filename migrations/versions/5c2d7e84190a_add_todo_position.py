"""add todo position

Revision ID: 5c2d7e84190a
Revises: 4bb1c2f63a2f
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c2d7e84190a'
down_revision: Union[str, None] = '4bb1c2f63a2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('todo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), server_default='0', nullable=False))
        batch_op.create_index(op.f('ix_todo_position'), ['position'], unique=False)

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, task_id
            FROM todo
            WHERE deleted_at IS NULL
            ORDER BY task_id, start_datetime, title, id
            """
        )
    ).fetchall()
    positions_by_task: dict[str, int] = {}
    for todo_id, task_id in rows:
        key = str(task_id)
        next_position = positions_by_task.get(key, 0) + 1
        positions_by_task[key] = next_position
        connection.execute(
            sa.text("UPDATE todo SET position = :position WHERE id = :id"),
            {"position": next_position, "id": todo_id},
        )


def downgrade() -> None:
    with op.batch_alter_table('todo', schema=None) as batch_op:
        batch_op.drop_index(op.f('ix_todo_position'))
        batch_op.drop_column('position')
