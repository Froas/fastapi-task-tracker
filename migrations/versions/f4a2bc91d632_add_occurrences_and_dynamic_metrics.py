"""add occurrences and dynamic metrics

Revision ID: f4a2bc91d632
Revises: e7b14c62a91d
Create Date: 2026-07-10 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f4a2bc91d632'
down_revision: Union[str, None] = 'e7b14c62a91d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'todooccurrence',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('note', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('todo_id', sa.Uuid(), nullable=False),
        sa.Column('daily_log_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['daily_log_id'], ['dailylog.id']),
        sa.ForeignKeyConstraint(['todo_id'], ['todo.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_todooccurrence_date', 'todooccurrence', ['date'], unique=False)
    op.create_index('ix_todooccurrence_todo_id', 'todooccurrence', ['todo_id'], unique=False)
    op.create_index('ix_todooccurrence_user_id', 'todooccurrence', ['user_id'], unique=False)
    op.create_index('ix_todooccurrence_user_todo_date', 'todooccurrence', ['user_id', 'todo_id', 'date'], unique=True)

    op.create_table(
        'metricdefinition',
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('input_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('show_on_today', sa.Boolean(), nullable=False),
        sa.Column('goal_id', sa.Uuid(), nullable=True),
        sa.Column('task_id', sa.Uuid(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goal.id']),
        sa.ForeignKeyConstraint(['task_id'], ['task.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_metricdefinition_goal_id', 'metricdefinition', ['goal_id'], unique=False)
    op.create_index('ix_metricdefinition_task_id', 'metricdefinition', ['task_id'], unique=False)
    op.create_index('ix_metricdefinition_position', 'metricdefinition', ['position'], unique=False)
    op.create_index('ix_metricdefinition_user_id', 'metricdefinition', ['user_id'], unique=False)

    op.create_table(
        'metricentry',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('numeric_value', sa.Float(), nullable=True),
        sa.Column('note', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('metric_definition_id', sa.Uuid(), nullable=False),
        sa.Column('daily_log_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['daily_log_id'], ['dailylog.id']),
        sa.ForeignKeyConstraint(['metric_definition_id'], ['metricdefinition.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_metricentry_date', 'metricentry', ['date'], unique=False)
    op.create_index('ix_metricentry_metric_definition_id', 'metricentry', ['metric_definition_id'], unique=False)
    op.create_index('ix_metricentry_user_id', 'metricentry', ['user_id'], unique=False)
    op.create_index('ix_metricentry_user_metric_date', 'metricentry', ['user_id', 'metric_definition_id', 'date'], unique=True)

    with op.batch_alter_table('dailylog', schema=None) as batch_op:
        batch_op.drop_column('steps')
        batch_op.drop_column('sleep_hours')
        batch_op.drop_column('calories')
        batch_op.drop_column('weight')


def downgrade() -> None:
    with op.batch_alter_table('dailylog', schema=None) as batch_op:
        batch_op.add_column(sa.Column('weight', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('calories', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('sleep_hours', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('steps', sa.Integer(), nullable=True))

    op.drop_index('ix_metricentry_user_metric_date', table_name='metricentry')
    op.drop_index('ix_metricentry_user_id', table_name='metricentry')
    op.drop_index('ix_metricentry_metric_definition_id', table_name='metricentry')
    op.drop_index('ix_metricentry_date', table_name='metricentry')
    op.drop_table('metricentry')

    op.drop_index('ix_metricdefinition_user_id', table_name='metricdefinition')
    op.drop_index('ix_metricdefinition_position', table_name='metricdefinition')
    op.drop_index('ix_metricdefinition_task_id', table_name='metricdefinition')
    op.drop_index('ix_metricdefinition_goal_id', table_name='metricdefinition')
    op.drop_table('metricdefinition')

    op.drop_index('ix_todooccurrence_user_todo_date', table_name='todooccurrence')
    op.drop_index('ix_todooccurrence_user_id', table_name='todooccurrence')
    op.drop_index('ix_todooccurrence_todo_id', table_name='todooccurrence')
    op.drop_index('ix_todooccurrence_date', table_name='todooccurrence')
    op.drop_table('todooccurrence')
