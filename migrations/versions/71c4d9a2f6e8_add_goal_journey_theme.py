"""add goal journey theme

Revision ID: 71c4d9a2f6e8
Revises: 2f1a6c8e9d40
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "71c4d9a2f6e8"
down_revision: Union[str, None] = "2f1a6c8e9d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goal",
        sa.Column(
            "journey_theme_id",
            sa.String(length=32),
            nullable=False,
            server_default="mountain",
        ),
    )


def downgrade() -> None:
    op.drop_column("goal", "journey_theme_id")
