"""add goal journey character

Revision ID: 84b7c3d2e1f0
Revises: 71c4d9a2f6e8
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "84b7c3d2e1f0"
down_revision: Union[str, None] = "71c4d9a2f6e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goal",
        sa.Column(
            "journey_character_id",
            sa.String(length=32),
            nullable=False,
            server_default="bat",
        ),
    )


def downgrade() -> None:
    op.drop_column("goal", "journey_character_id")
