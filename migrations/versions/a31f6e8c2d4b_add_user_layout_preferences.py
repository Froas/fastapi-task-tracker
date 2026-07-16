"""add user layout preferences

Revision ID: a31f6e8c2d4b
Revises: 9f2a4c7d1e3b
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a31f6e8c2d4b"
down_revision: Union[str, None] = "9f2a4c7d1e3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("nav_preferences", sa.JSON(), nullable=True))
    op.add_column("user", sa.Column("dashboard_preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "dashboard_preferences")
    op.drop_column("user", "nav_preferences")
