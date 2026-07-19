"""add success criteria

Revision ID: f2c4a6e8b013
Revises: d4b8e1f3a6c2
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2c4a6e8b013"
down_revision: Union[str, None] = "d4b8e1f3a6c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("goal", sa.Column("success_criteria", sa.Text(), nullable=True))
    op.add_column("milestone", sa.Column("success_criteria", sa.Text(), nullable=True))
    op.add_column("task", sa.Column("success_criteria", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("task", "success_criteria")
    op.drop_column("milestone", "success_criteria")
    op.drop_column("goal", "success_criteria")
