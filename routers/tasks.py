from fastapi import APIRouter, HTTPException, Depends
from models import Goal, Milestone, Task, TaskBase, TaskUpdate, TaskReadNested, TaskReorderRequest, Todo, get_current_active_user
from typing import Annotated
from routers.visibility import active_goal_ids, active_milestone_ids
from services.completion_rules import recalculate_goal_hierarchy, recalculate_task_hierarchy
from services.tracking import activate_tracking_for_milestone
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload, noload
from routers.users import User
from db import get_session
from datetime import datetime
from utils.timezone import JST
import uuid

tasks_router = APIRouter()

VALID_TASK_KINDS = {"project", "routine", "challenge"}
VALID_TASK_SCOPES = {"goal", "milestone"}


def _normalize_task_kind(kind: str | None) -> str:
    normalized = (kind or "project").strip().lower()
    if normalized not in VALID_TASK_KINDS:
        raise HTTPException(status_code=400, detail="Task kind must be project, routine, or challenge")
    return normalized


def _normalize_task_scope(scope: str | None, goal_id: uuid.UUID | None, milestone_id: uuid.UUID | None) -> str:
    normalized = (scope or ("goal" if goal_id and milestone_id is None else "milestone")).strip().lower()
    if normalized not in VALID_TASK_SCOPES:
        raise HTTPException(status_code=400, detail="Task scope must be goal or milestone")
    return normalized


def _validate_kind_scope(kind: str, scope: str) -> None:
    if kind == "routine" and scope != "goal":
        raise HTTPException(status_code=400, detail="Routine tasks belong to a goal")
    if kind in {"project", "challenge"} and scope != "milestone":
        raise HTTPException(status_code=400, detail="Project and challenge tasks belong to a milestone")

@tasks_router.get('/user/tasks')
async def get_all_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    include_subtasks: bool = True,
    include_todos: bool = True,
    session: Session = Depends(get_session),
) -> list[TaskReadNested]:
    query = select(Task).where(
        Task.user_id == current_user.id,
        Task.deleted_at.is_(None),
        (
            Task.milestone_id.in_(active_milestone_ids(current_user.id))
        ) | (
            Task.goal_id.in_(active_goal_ids(current_user.id))
        ),
    ).order_by(Task.scope, Task.goal_id, Task.milestone_id, Task.position, Task.id)
    options = []
    options.append(selectinload(Task.subtasks) if include_subtasks else noload(Task.subtasks))
    options.append(
        selectinload(Task.todos.and_(Todo.deleted_at.is_(None)))
        if include_todos
        else noload(Task.todos)
    )
    tasks = session.exec(query.options(*options)).all()
    if include_subtasks:
        for task in tasks:
            task.subtasks = sorted(
                task.subtasks or [],
                key=lambda subtask: (subtask.position or 0, str(subtask.id)),
            )
    if include_todos:
        for task in tasks:
            task.todos = sorted(
                task.todos or [],
                key=lambda todo: (todo.position or 0, str(todo.id)),
            )
    return tasks

@tasks_router.post('/user/tasks')
async def create_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_data: TaskBase,
    session: Session = Depends(get_session),
) -> Task:
    kind = _normalize_task_kind(task_data.kind)
    scope = _normalize_task_scope(task_data.scope, task_data.goal_id, task_data.milestone_id)
    _validate_kind_scope(kind, scope)
    goal_id = task_data.goal_id
    milestone_id = task_data.milestone_id

    if scope == "goal":
        if goal_id is None:
            raise HTTPException(status_code=400, detail='goal_id is required for goal-scope tasks')
        goal = session.exec(
            select(Goal).where(
                Goal.id == goal_id,
                Goal.user_id == current_user.id,
                Goal.deleted_at.is_(None),
            )
        ).first()
        if goal is None:
            raise HTTPException(status_code=404, detail='Goal not found')
        milestone_id = None
    else:
        if milestone_id is None:
            raise HTTPException(status_code=400, detail='milestone_id is required for milestone-scope tasks')
        milestone = session.exec(
            select(Milestone).where(
                Milestone.id == milestone_id,
                Milestone.user_id == current_user.id,
                Milestone.deleted_at.is_(None),
            )
        ).first()
        if milestone is None:
            raise HTTPException(status_code=404, detail='Milestone not found')
        if milestone.goal_id is not None:
            goal = session.exec(
                select(Goal).where(
                    Goal.id == milestone.goal_id,
                    Goal.user_id == current_user.id,
                    Goal.deleted_at.is_(None),
                )
            ).first()
            if goal is None:
                raise HTTPException(status_code=404, detail='Goal not found')
            if goal_id is not None and goal_id != milestone.goal_id:
                raise HTTPException(status_code=400, detail='goal_id does not match milestone')
            goal_id = milestone.goal_id

    max_position = session.exec(
        select(Task.position)
        .where(
            Task.goal_id == goal_id,
            Task.milestone_id == milestone_id,
            Task.scope == scope,
            Task.user_id == current_user.id,
            Task.deleted_at.is_(None),
        )
        .order_by(Task.position.desc())
    ).first()
    completion_rule = task_data.completion_rule
    if kind == "challenge" and not completion_rule:
        completion_rule = {
            "type": "consistency",
            "label": task_data.title,
            "required_done": 7,
            "window_days": 7,
        }
    task = Task(
        title=task_data.title, 
        description=task_data.description, 
        success_criteria=task_data.success_criteria,
        due_date=task_data.due_date, 
        scheduled_date=task_data.scheduled_date,
        status=task_data.status,
        end_datetime=task_data.end_datetime,
        start_datetime=task_data.start_datetime,
        priority=task_data.priority, 
        goal_id=goal_id,
        milestone_id=milestone_id,
        kind=kind,
        scope=scope,
        position=(max_position or 0) + 1,
        completion_rule=completion_rule,
        user_id=current_user.id, 
        user=current_user
    )
    session.add(task)
    if (
        kind == "challenge"
        and task.status in {StatusType.STARTED, StatusType.IN_PROGRESS}
        and milestone.status == StatusType.OUTSTANDING
    ):
        milestone.status = StatusType.STARTED
        session.add(milestone)
    session.flush()
    recalculate_task_hierarchy(session, task.id)
    session.commit()
    session.refresh(task)    
    return task

@tasks_router.patch('/user/tasks/update',  response_model=Task)
async def update_task(
    task_data: TaskUpdate,
    currente_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Task:
    task = session.get(Task, task_data.id)
    if not task or task.user_id != currente_user.id or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail='Task not found')
    next_scope = _normalize_task_scope(task_data.scope, task_data.goal_id, task_data.milestone_id) if (
        task_data.scope is not None or task_data.goal_id is not None or task_data.milestone_id is not None
    ) else task.scope
    next_kind = _normalize_task_kind(task_data.kind) if task_data.kind is not None else task.kind
    next_goal_id = task_data.goal_id if task_data.goal_id is not None else task.goal_id
    next_milestone_id = task_data.milestone_id if task_data.milestone_id is not None else task.milestone_id
    if (
        next_kind != task.kind
        or next_scope != task.scope
        or next_milestone_id != task.milestone_id
    ):
        _validate_kind_scope(next_kind, next_scope)

    if next_scope == "goal":
        if next_goal_id is None:
            raise HTTPException(status_code=400, detail='goal_id is required for goal-scope tasks')
        goal = session.exec(
            select(Goal).where(
                Goal.id == next_goal_id,
                Goal.user_id == currente_user.id,
                Goal.deleted_at.is_(None),
            )
        ).first()
        if goal is None:
            raise HTTPException(status_code=404, detail='Goal not found')
        next_milestone_id = None
    else:
        if next_milestone_id is None:
            raise HTTPException(status_code=400, detail='milestone_id is required for milestone-scope tasks')
        milestone = session.exec(
            select(Milestone).where(
                Milestone.id == next_milestone_id,
                Milestone.user_id == currente_user.id,
                Milestone.deleted_at.is_(None),
            )
        ).first()
        if milestone is None:
            raise HTTPException(status_code=404, detail='Milestone not found')
        goal = session.exec(
            select(Goal).where(
                Goal.id == milestone.goal_id,
                Goal.user_id == currente_user.id,
                Goal.deleted_at.is_(None),
            )
        ).first()
        if goal is None:
            raise HTTPException(status_code=404, detail='Goal not found')
        next_goal_id = milestone.goal_id
    
    update_data = task_data.model_dump(exclude_unset=True, exclude={'id'})
    if next_kind == "challenge" and not (task_data.completion_rule or task.completion_rule):
        update_data['completion_rule'] = {
            "type": "consistency",
            "label": task_data.title or task.title,
            "required_done": 7,
            "window_days": 7,
        }
    if 'status' in update_data and task.completion_rule:
        task.completion_rule = {**task.completion_rule, 'auto_completed': False}
    update_data['kind'] = next_kind
    update_data['scope'] = next_scope
    update_data['goal_id'] = next_goal_id
    update_data['milestone_id'] = next_milestone_id

    parent_changed = (
        next_scope != task.scope or
        next_goal_id != task.goal_id or
        next_milestone_id != task.milestone_id
    )
    if parent_changed:
        max_position = session.exec(
            select(Task.position)
            .where(
                Task.goal_id == next_goal_id,
                Task.milestone_id == next_milestone_id,
                Task.scope == next_scope,
                Task.user_id == currente_user.id,
                Task.deleted_at.is_(None),
            )
            .order_by(Task.position.desc())
        ).first()
        update_data['position'] = (max_position or 0) + 1
    for key, value in update_data.items():
        setattr(task, key, value)
    session.add(task)
    if (
        next_kind == "challenge"
        and task.status in {StatusType.STARTED, StatusType.IN_PROGRESS}
        and next_scope == "milestone"
    ):
        if milestone.status == StatusType.OUTSTANDING:
            milestone.status = StatusType.STARTED
            session.add(milestone)
        activate_tracking_for_milestone(session, milestone, active_from=datetime.now(JST).date())
    recalculate_task_hierarchy(
        session,
        task.id,
        recalculate_task='status' not in update_data,
    )
    session.commit()
    session.refresh(task)
    return task

@tasks_router.put('/user/tasks/reorder')
async def reorder_tasks(
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: TaskReorderRequest,
    session: Session = Depends(get_session)
) -> dict:
    task_ids = payload.task_ids
    if not task_ids or len(set(task_ids)) != len(task_ids):
        raise HTTPException(status_code=400, detail="Invalid task list provided")
    tasks = session.exec(
        select(Task).where(
            Task.user_id == current_user.id,
            Task.id.in_(task_ids),
            Task.deleted_at.is_(None),
            (
                Task.milestone_id.in_(active_milestone_ids(current_user.id))
            ) | (
                Task.goal_id.in_(active_goal_ids(current_user.id))
            ),
        )
    ).all()
    if len(tasks) != len(task_ids):
        raise HTTPException(status_code=400, detail="Invalid task list provided")
    scopes = {task.scope for task in tasks}
    goal_ids = {task.goal_id for task in tasks}
    milestone_ids = {task.milestone_id for task in tasks}
    if len(scopes) != 1 or len(goal_ids) != 1 or len(milestone_ids) != 1:
        raise HTTPException(status_code=400, detail="Tasks must belong to one parent")
    scope = tasks[0].scope
    goal_id = tasks[0].goal_id
    milestone_id = tasks[0].milestone_id
    active_ids = set(session.exec(
        select(Task.id).where(
            Task.user_id == current_user.id,
            Task.goal_id == goal_id,
            Task.milestone_id == milestone_id,
            Task.scope == scope,
            Task.deleted_at.is_(None),
        )
    ).all())
    if active_ids != set(task_ids):
        raise HTTPException(status_code=409, detail="Task list is stale; refresh and retry")
    by_id = {task.id: task for task in tasks}
    for position, task_id in enumerate(task_ids, start=1):
        task = by_id[task_id]
        task.position = position
        session.add(task)
    session.commit()
    return {"message": "Tasks reordered successfully"}

@tasks_router.get('/user/tasks/{task_id}')
async def get_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    include_subtasks: bool = True,
    include_todos: bool = True,
    session: Session = Depends(get_session)
) -> TaskReadNested:
    query = select(Task).where(
        current_user.id == Task.user_id,
        Task.id == task_id,
        Task.deleted_at.is_(None),
    )
    if query is None:
        raise HTTPException(status_code=404, detail="Task not found")
    options = []
    
    if include_subtasks:
        options.append(selectinload(Task.subtasks))
    else:
        options.append(noload(Task.subtasks))
    if include_todos:
        options.append(selectinload(Task.todos.and_(Todo.deleted_at.is_(None))))
    else:
        options.append(noload(Task.todos))
    query = query.options(*options)
        
    task = session.exec(query).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if include_subtasks:
        task.subtasks = sorted(
            task.subtasks or [],
            key=lambda subtask: (subtask.position or 0, str(subtask.id)),
        )
    if include_todos:
        task.todos = sorted(
            task.todos or [],
            key=lambda todo: (todo.position or 0, str(todo.id)),
        )
    return task

@tasks_router.delete('/user/tasks/{task_id}/delete')
async def delete_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    from datetime import datetime
    from utils.timezone import JST
    task = session.get(Task, task_id)
    if task is None or task.user_id != current_user.id or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    goal_id = task.goal_id
    task.deleted_at = datetime.now(JST)
    session.add(task)
    session.flush()
    recalculate_goal_hierarchy(session, goal_id)
    session.commit()
    return {"message": "Task moved to trash"}
