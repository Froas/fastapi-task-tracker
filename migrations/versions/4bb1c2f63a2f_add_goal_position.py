"""add goal position

Revision ID: 4bb1c2f63a2f
Revises: 8c1e4d2a9b70
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4bb1c2f63a2f'
down_revision: Union[str, None] = '8c1e4d2a9b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), server_default='0', nullable=False))
        batch_op.create_index(op.f('ix_goal_position'), ['position'], unique=False)

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, user_id
            FROM goal
            WHERE deleted_at IS NULL
            ORDER BY user_id, start_datetime, title, id
            """
        )
    ).fetchall()
    positions_by_user: dict[str, int] = {}
    for goal_id, user_id in rows:
        key = str(user_id)
        next_position = positions_by_user.get(key, 0) + 1
        positions_by_user[key] = next_position
        connection.execute(
            sa.text("UPDATE goal SET position = :position WHERE id = :id"),
            {"position": next_position, "id": goal_id},
        )


def downgrade() -> None:
    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.drop_index(op.f('ix_goal_position'))
        batch_op.drop_column('position')
