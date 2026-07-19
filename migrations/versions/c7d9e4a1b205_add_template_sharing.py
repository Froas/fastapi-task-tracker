"""add unlisted template sharing

Revision ID: c7d9e4a1b205
Revises: f2c4a6e8b013
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d9e4a1b205"
down_revision: Union[str, None] = "f2c4a6e8b013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("template", schema=None) as batch_op:
        batch_op.add_column(sa.Column("visibility", sa.String(), nullable=False, server_default="private"))
        batch_op.add_column(sa.Column("share_code", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("shared_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_template_visibility", ["visibility"], unique=False)
        batch_op.create_index("ix_template_share_code", ["share_code"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("template", schema=None) as batch_op:
        batch_op.drop_index("ix_template_share_code")
        batch_op.drop_index("ix_template_visibility")
        batch_op.drop_column("shared_at")
        batch_op.drop_column("share_code")
        batch_op.drop_column("visibility")
