"""backfill hierarchy activity statuses

Revision ID: f7c2d9a4e611
Revises: e3a7c5d9f102
Create Date: 2026-07-23 10:12:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7c2d9a4e611"
down_revision: Union[str, None] = "e3a7c5d9f102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum values are persisted by SQLAlchemy using their member names.
    op.execute(sa.text("""
        UPDATE task
        SET status = 'IN_PROGRESS'
        WHERE status IN ('OUTSTANDING', 'STARTED')
          AND deleted_at IS NULL
          AND (
            EXISTS (
              SELECT 1 FROM subtask
              WHERE subtask.task_id = task.id
                AND subtask.status IN ('IN_PROGRESS', 'FINISHED', 'CLOSED')
            )
            OR EXISTS (
              SELECT 1 FROM todo
              WHERE todo.task_id = task.id
                AND todo.deleted_at IS NULL
                AND todo.status IN ('IN_PROGRESS', 'FINISHED', 'CLOSED')
            )
            OR EXISTS (
              SELECT 1
              FROM todooccurrence
              JOIN todo ON todo.id = todooccurrence.todo_id
              WHERE todo.task_id = task.id
                AND todo.deleted_at IS NULL
                AND todooccurrence.status IN ('done', 'minimum')
            )
          )
    """))
    op.execute(sa.text("""
        UPDATE task
        SET status = 'STARTED'
        WHERE status = 'OUTSTANDING'
          AND deleted_at IS NULL
          AND (
            EXISTS (
              SELECT 1 FROM subtask
              WHERE subtask.task_id = task.id AND subtask.status = 'STARTED'
            )
            OR EXISTS (
              SELECT 1 FROM todo
              WHERE todo.task_id = task.id
                AND todo.deleted_at IS NULL
                AND todo.status = 'STARTED'
            )
          )
    """))
    op.execute(sa.text("""
        UPDATE milestone
        SET status = 'IN_PROGRESS'
        WHERE status IN ('OUTSTANDING', 'STARTED')
          AND deleted_at IS NULL
          AND EXISTS (
            SELECT 1 FROM task
            WHERE task.milestone_id = milestone.id
              AND task.deleted_at IS NULL
              AND task.status IN ('IN_PROGRESS', 'FINISHED', 'CLOSED')
          )
    """))
    op.execute(sa.text("""
        UPDATE milestone
        SET status = 'STARTED'
        WHERE status = 'OUTSTANDING'
          AND deleted_at IS NULL
          AND EXISTS (
            SELECT 1 FROM task
            WHERE task.milestone_id = milestone.id
              AND task.deleted_at IS NULL
              AND task.status = 'STARTED'
          )
    """))
    op.execute(sa.text("""
        UPDATE goal
        SET status = 'IN_PROGRESS'
        WHERE status IN ('OUTSTANDING', 'STARTED')
          AND deleted_at IS NULL
          AND (
            EXISTS (
              SELECT 1 FROM milestone
              WHERE milestone.goal_id = goal.id
                AND milestone.deleted_at IS NULL
                AND milestone.status IN ('IN_PROGRESS', 'FINISHED', 'CLOSED')
            )
            OR EXISTS (
              SELECT 1 FROM task
              WHERE task.goal_id = goal.id
                AND task.deleted_at IS NULL
                AND (task.scope = 'goal' OR task.milestone_id IS NULL)
                AND task.status IN ('IN_PROGRESS', 'FINISHED', 'CLOSED')
            )
          )
    """))
    op.execute(sa.text("""
        UPDATE goal
        SET status = 'STARTED'
        WHERE status = 'OUTSTANDING'
          AND deleted_at IS NULL
          AND (
            EXISTS (
              SELECT 1 FROM milestone
              WHERE milestone.goal_id = goal.id
                AND milestone.deleted_at IS NULL
                AND milestone.status = 'STARTED'
            )
            OR EXISTS (
              SELECT 1 FROM task
              WHERE task.goal_id = goal.id
                AND task.deleted_at IS NULL
                AND (task.scope = 'goal' OR task.milestone_id IS NULL)
                AND task.status = 'STARTED'
            )
          )
    """))


def downgrade() -> None:
    # Activity-derived statuses cannot be distinguished reliably from manual
    # statuses, so the data backfill is intentionally irreversible.
    pass
