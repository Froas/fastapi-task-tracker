"""add cross-platform account preferences

Revision ID: d4b8e1f3a6c2
Revises: c7e1f0a2b9d4
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b8e1f3a6c2"
down_revision: Union[str, None] = "c7e1f0a2b9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("pinned_goal_ids", sa.JSON(), nullable=True))
    op.add_column("user", sa.Column("recent_goal_ids", sa.JSON(), nullable=True))
    op.add_column("user", sa.Column("goal_color_overrides", sa.JSON(), nullable=True))
    op.add_column(
        "goal",
        sa.Column(
            "enforce_sequential_milestones",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("goal", "enforce_sequential_milestones")
    op.drop_column("user", "goal_color_overrides")
    op.drop_column("user", "recent_goal_ids")
    op.drop_column("user", "pinned_goal_ids")
