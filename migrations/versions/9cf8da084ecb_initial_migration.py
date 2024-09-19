"""Initial migration

Revision ID: 9cf8da084ecb
Revises: 
Create Date: 2024-09-18 15:08:15.160548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9cf8da084ecb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('password_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)
    op.create_table('event',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('start_datetime', sa.DateTime(), nullable=False),
    sa.Column('end_datetime', sa.DateTime(), nullable=False),
    sa.Column('event_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('location', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('recurrence_rule', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('goal',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('start_date', sa.DateTime(), nullable=False),
    sa.Column('end_date', sa.DateTime(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('OUTSTANDING', 'STARTED', 'IN_PROGRESS', 'FINISHED', 'CLOSED', 'ABORTED', name='statustype'), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('milestone',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('goal_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('OUTSTANDING', 'STARTED', 'IN_PROGRESS', 'FINISHED', 'CLOSED', 'ABORTED', name='statustype'), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['goal_id'], ['goal.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('task',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='prioritytype'), nullable=False),
    sa.Column('due_date', sa.DateTime(), nullable=False),
    sa.Column('milestone_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('start_date', sa.DateTime(), nullable=True),
    sa.Column('status', sa.Enum('OUTSTANDING', 'STARTED', 'IN_PROGRESS', 'FINISHED', 'CLOSED', 'ABORTED', name='statustype'), nullable=True),
    sa.ForeignKeyConstraint(['milestone_id'], ['milestone.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('todo',
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='prioritytype'), nullable=False),
    sa.Column('repeat_interval', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('next_due_date', sa.DateTime(), nullable=False),
    sa.Column('task_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('OUTSTANDING', 'STARTED', 'IN_PROGRESS', 'FINISHED', 'CLOSED', 'ABORTED', name='statustype'), nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['task.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('todo')
    op.drop_table('task')
    op.drop_table('milestone')
    op.drop_table('goal')
    op.drop_table('event')
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_table('user')
    # ### end Alembic commands ###
