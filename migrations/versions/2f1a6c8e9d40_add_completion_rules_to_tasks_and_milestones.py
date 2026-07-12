"""add completion rules to tasks and milestones

Revision ID: 2f1a6c8e9d40
Revises: e19f3a7b0c42
Create Date: 2026-07-11 23:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f1a6c8e9d40"
down_revision: Union[str, None] = "e19f3a7b0c42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("milestone") as batch_op:
        batch_op.add_column(sa.Column("completion_rule", sa.JSON(), nullable=True))
    with op.batch_alter_table("task") as batch_op:
        batch_op.add_column(sa.Column("completion_rule", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task") as batch_op:
        batch_op.drop_column("completion_rule")
    with op.batch_alter_table("milestone") as batch_op:
        batch_op.drop_column("completion_rule")
