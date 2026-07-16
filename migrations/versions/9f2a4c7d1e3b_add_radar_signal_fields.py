"""add radar signal workflow fields

Revision ID: 9f2a4c7d1e3b
Revises: 84b7c3d2e1f0
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f2a4c7d1e3b"
down_revision: Union[str, None] = "84b7c3d2e1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("note", sa.Column("signal_domain", sa.String(), nullable=True))
    op.add_column("note", sa.Column("signal_stake", sa.String(), nullable=True))
    op.add_column("note", sa.Column("signal_decision", sa.String(), nullable=True))
    op.add_column("note", sa.Column("next_action", sa.String(), nullable=True))
    op.add_column("note", sa.Column("review_date", sa.Date(), nullable=True))
    op.add_column("note", sa.Column("deadline", sa.Date(), nullable=True))
    op.add_column("note", sa.Column("outcome", sa.String(), nullable=True))
    op.add_column("note", sa.Column("resolved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("note", "resolved_at")
    op.drop_column("note", "outcome")
    op.drop_column("note", "deadline")
    op.drop_column("note", "review_date")
    op.drop_column("note", "next_action")
    op.drop_column("note", "signal_decision")
    op.drop_column("note", "signal_stake")
    op.drop_column("note", "signal_domain")
