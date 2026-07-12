import uuid

from sqlmodel import select

from models import Goal, Milestone, StatusType, Task, Todo


ACTIVE_STATUSES = (
    StatusType.OUTSTANDING,
    StatusType.STARTED,
    StatusType.IN_PROGRESS,
)


def active_goal_ids(user_id: uuid.UUID):
    return select(Goal.id).where(
        Goal.user_id == user_id,
        Goal.deleted_at.is_(None),
        Goal.status.in_(ACTIVE_STATUSES),
    )


def active_milestone_ids(user_id: uuid.UUID):
    return select(Milestone.id).where(
        Milestone.user_id == user_id,
        Milestone.deleted_at.is_(None),
        Milestone.status.in_(ACTIVE_STATUSES),
        Milestone.goal_id.in_(active_goal_ids(user_id)),
    )


def active_task_ids(user_id: uuid.UUID):
    return select(Task.id).where(
        Task.user_id == user_id,
        Task.deleted_at.is_(None),
        Task.status.in_(ACTIVE_STATUSES),
        (
            (Task.milestone_id.isnot(None))
            & (Task.milestone_id.in_(active_milestone_ids(user_id)))
        ) | (
            (Task.milestone_id.is_(None))
            & (Task.goal_id.in_(active_goal_ids(user_id)))
        ),
    )


def active_recurring_todo_ids(user_id: uuid.UUID):
    return select(Todo.id).where(
        Todo.user_id == user_id,
        Todo.deleted_at.is_(None),
        Todo.status.in_(ACTIVE_STATUSES),
        Todo.repeat_interval.isnot(None),
        Todo.repeat_interval != '',
        Todo.task_id.in_(active_task_ids(user_id)),
    )
