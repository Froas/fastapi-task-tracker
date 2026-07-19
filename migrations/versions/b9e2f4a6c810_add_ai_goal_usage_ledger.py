"""add prompt-free AI goal usage ledger

Revision ID: b9e2f4a6c810
Revises: a8f1c3d5e702
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9e2f4a6c810"
down_revision: Union[str, None] = "a8f1c3d5e702"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aigoalusage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("feature", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("quota_period", sa.String(length=7), nullable=False),
        sa.Column("quota_slot", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "quota_period",
            "quota_slot",
            name="uq_ai_goal_usage_period_slot",
        ),
    )
    op.create_index("ix_aigoalusage_created_at", "aigoalusage", ["created_at"], unique=False)
    op.create_index("ix_aigoalusage_feature", "aigoalusage", ["feature"], unique=False)
    op.create_index("ix_aigoalusage_quota_period", "aigoalusage", ["quota_period"], unique=False)
    op.create_index("ix_aigoalusage_status", "aigoalusage", ["status"], unique=False)
    op.create_index("ix_aigoalusage_user_id", "aigoalusage", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_aigoalusage_user_id", table_name="aigoalusage")
    op.drop_index("ix_aigoalusage_status", table_name="aigoalusage")
    op.drop_index("ix_aigoalusage_quota_period", table_name="aigoalusage")
    op.drop_index("ix_aigoalusage_feature", table_name="aigoalusage")
    op.drop_index("ix_aigoalusage_created_at", table_name="aigoalusage")
    op.drop_table("aigoalusage")
