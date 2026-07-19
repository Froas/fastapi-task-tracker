"""add milestone ownership to metric definitions

Revision ID: a8f1c3d5e702
Revises: c7d9e4a1b205
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8f1c3d5e702"
down_revision: Union[str, None] = "c7d9e4a1b205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("metricdefinition", schema=None) as batch_op:
        batch_op.add_column(sa.Column("milestone_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_metricdefinition_milestone_id", ["milestone_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_metricdefinition_milestone_id_milestone",
            "milestone",
            ["milestone_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("metricdefinition", schema=None) as batch_op:
        batch_op.drop_constraint("fk_metricdefinition_milestone_id_milestone", type_="foreignkey")
        batch_op.drop_index("ix_metricdefinition_milestone_id")
        batch_op.drop_column("milestone_id")
