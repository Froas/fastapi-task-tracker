"""add todo tracking lifecycle

Revision ID: e3a7c5d9f102
Revises: b9e2f4a6c810
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3a7c5d9f102"
down_revision: Union[str, None] = "b9e2f4a6c810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("todo", sa.Column("tracking_mode", sa.String(), nullable=True))
    op.add_column("todo", sa.Column("tracking_state", sa.String(), nullable=True))
    op.add_column("todo", sa.Column("routine_series_key", sa.String(), nullable=True))
    op.add_column("todo", sa.Column("stage_order", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("todo", sa.Column("active_from", sa.Date(), nullable=True))
    op.add_column("todo", sa.Column("graduated_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_todo_tracking_mode"), "todo", ["tracking_mode"], unique=False)
    op.create_index(op.f("ix_todo_tracking_state"), "todo", ["tracking_state"], unique=False)
    op.create_index(op.f("ix_todo_routine_series_key"), "todo", ["routine_series_key"], unique=False)
    op.create_index(op.f("ix_todo_active_from"), "todo", ["active_from"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_todo_active_from"), table_name="todo")
    op.drop_index(op.f("ix_todo_routine_series_key"), table_name="todo")
    op.drop_index(op.f("ix_todo_tracking_state"), table_name="todo")
    op.drop_index(op.f("ix_todo_tracking_mode"), table_name="todo")
    op.drop_column("todo", "graduated_at")
    op.drop_column("todo", "active_from")
    op.drop_column("todo", "stage_order")
    op.drop_column("todo", "routine_series_key")
    op.drop_column("todo", "tracking_state")
    op.drop_column("todo", "tracking_mode")
