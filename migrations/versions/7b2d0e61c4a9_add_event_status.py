"""add event status

Revision ID: 7b2d0e61c4a9
Revises: 3d7630cc67ea
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7b2d0e61c4a9'
down_revision: Union[str, None] = '3d7630cc67ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'status',
                sa.Enum(
                    'OUTSTANDING',
                    'STARTED',
                    'IN_PROGRESS',
                    'FINISHED',
                    'CLOSED',
                    'ABORTED',
                    'CANCELLED',
                    name='statustype',
                ),
                server_default='OUTSTANDING',
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('status')
