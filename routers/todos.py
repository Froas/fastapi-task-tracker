from fastapi import APIRouter, HTTPException, Depends
from models import Task, Todo, TodoBase, TodoRead, TodoUpdate, TodoReorderRequest, get_current_active_user
from typing import Annotated
from routers.visibility import active_task_ids
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from services.tracking import (
    TRACKING_MODES,
    TRACKING_STATES,
    inferred_tracking_defaults,
)
import uuid


todos_router = APIRouter()


def _validate_tracking(value: str | None, allowed: set[str], field: str) -> None:
    if value is not None and value.strip().lower() not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")

@todos_router.get('/user/todos')
async def get_all_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[TodoRead]:
    return session.exec(
        select(Todo).where(
            Todo.user_id == current_user.id,
            Todo.deleted_at.is_(None),
            Todo.task_id.in_(active_task_ids(current_user.id)),
        ).order_by(Todo.task_id, Todo.position, Todo.id)
    ).all()

@todos_router.get('/user/todos/{todo_id}')
async def get_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Todo:
    todo = session.exec(
        select(Todo).where(
            Todo.id == todo_id,
            Todo.user_id == current_user.id,
            Todo.deleted_at.is_(None),
            Todo.task_id.in_(active_task_ids(current_user.id)),
        )
    ).first()
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo

@todos_router.post('/user/todos')
async def create_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_data: TodoBase,
    session: Session = Depends(get_session)
) -> Todo:
    if todo_data.task_id is None:
        raise HTTPException(status_code=400, detail='task_id is required')
    if todo_data.task_id is not None:
        task = session.exec(
            select(Task).where(
                Task.id == todo_data.task_id,
                Task.user_id == current_user.id,
                Task.deleted_at.is_(None),
                Task.id.in_(active_task_ids(current_user.id)),
            )
        ).first()
        if task is None:
            raise HTTPException(status_code=404, detail='Task not found')
    _validate_tracking(todo_data.tracking_mode, TRACKING_MODES, "tracking_mode")
    _validate_tracking(todo_data.tracking_state, TRACKING_STATES, "tracking_state")
    tracking_mode, tracking_state, series_key, stage_order = inferred_tracking_defaults(
        session,
        task,
        tracking_mode=todo_data.tracking_mode,
        tracking_state=todo_data.tracking_state,
        series_key=todo_data.routine_series_key,
        stage_order=todo_data.stage_order,
    )
    max_position = session.exec(
        select(Todo.position)
        .where(
            Todo.user_id == current_user.id,
            Todo.task_id == todo_data.task_id,
            Todo.deleted_at.is_(None),
        )
        .order_by(Todo.position.desc())
    ).first()
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        priority=todo_data.priority,
        status=todo_data.status,
        due_date=todo_data.due_date,
        repeat_interval=todo_data.repeat_interval,
        next_due_date=todo_data.next_due_date,
        start_datetime=todo_data.start_datetime,
        end_datetime=todo_data.end_datetime,
        task_id=todo_data.task_id,
        tracking_mode=tracking_mode,
        tracking_state=tracking_state,
        routine_series_key=series_key,
        stage_order=stage_order,
        active_from=todo_data.active_from,
        graduated_at=todo_data.graduated_at,
        user_id=current_user.id,
        user=current_user,
        position=(max_position or 0) + 1,
    )
    session.add(todo)
    if task.kind == "challenge" and not task.completion_rule:
        task.completion_rule = {
            "type": "consistency",
            "label": task.title,
            "required_done": 7,
            "window_days": 7,
        }
        session.add(task)
    session.commit()
    session.refresh(todo)
    return todo

@todos_router.patch('/user/todos/update', response_model=Todo)
async def update_todo(
    todo_data: TodoUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Todo:
    todo = session.get(Todo, todo_data.id)
    if not todo or todo.user_id != current_user.id or todo.deleted_at is not None:
        raise HTTPException(status_code=404, detail='Todo not found')
    if todo_data.task_id is not None:
        task = session.exec(
            select(Task).where(
                Task.id == todo_data.task_id,
                Task.user_id == current_user.id,
                Task.deleted_at.is_(None),
                Task.id.in_(active_task_ids(current_user.id)),
            )
        ).first()
        if task is None:
            raise HTTPException(status_code=404, detail='Task not found')

    _validate_tracking(todo_data.tracking_mode, TRACKING_MODES, "tracking_mode")
    _validate_tracking(todo_data.tracking_state, TRACKING_STATES, "tracking_state")

    update_data = todo_data.model_dump(exclude_unset=True, exclude={'id'})
    target_task = task if todo_data.task_id is not None else session.get(Task, todo.task_id)
    if target_task is not None and any(
        key in update_data
        for key in ("tracking_mode", "tracking_state", "routine_series_key", "stage_order", "task_id")
    ):
        tracking_mode, tracking_state, series_key, stage_order = inferred_tracking_defaults(
            session,
            target_task,
            tracking_mode=update_data.get("tracking_mode", todo.tracking_mode),
            tracking_state=update_data.get("tracking_state", todo.tracking_state),
            series_key=update_data.get("routine_series_key", todo.routine_series_key),
            stage_order=update_data.get("stage_order", todo.stage_order),
        )
        update_data.update({
            "tracking_mode": tracking_mode,
            "tracking_state": tracking_state,
            "routine_series_key": series_key,
            "stage_order": stage_order,
        })
    if todo_data.task_id is not None and todo_data.task_id != todo.task_id and 'position' not in update_data:
        max_position = session.exec(
            select(Todo.position)
            .where(
                Todo.user_id == current_user.id,
                Todo.task_id == todo_data.task_id,
                Todo.deleted_at.is_(None),
            )
            .order_by(Todo.position.desc())
        ).first()
        update_data['position'] = (max_position or 0) + 1
    for key, value in update_data.items():
        setattr(todo, key, value)
        
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo
    

@todos_router.put('/user/todos/reorder')
async def reorder_todos(
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: TodoReorderRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    todo_ids = payload.todo_ids
    if not todo_ids or len(set(todo_ids)) != len(todo_ids):
        raise HTTPException(status_code=400, detail="Invalid todo list provided")

    todos = session.exec(
        select(Todo).where(
            Todo.user_id == current_user.id,
            Todo.id.in_(todo_ids),
            Todo.deleted_at.is_(None),
            Todo.task_id.in_(active_task_ids(current_user.id)),
        )
    ).all()
    if len(todos) != len(todo_ids):
        raise HTTPException(status_code=400, detail="Invalid todo list provided")
    task_ids = {todo.task_id for todo in todos}
    if len(task_ids) != 1:
        raise HTTPException(status_code=400, detail="Todos must belong to one task")

    task_id = todos[0].task_id
    active_ids = set(session.exec(
        select(Todo.id).where(
            Todo.user_id == current_user.id,
            Todo.task_id == task_id,
            Todo.deleted_at.is_(None),
        )
    ).all())
    if active_ids != set(todo_ids):
        raise HTTPException(status_code=409, detail="Todo list is stale; refresh and retry")

    by_id = {todo.id: todo for todo in todos}
    for position, todo_id in enumerate(todo_ids, start=1):
        todo = by_id[todo_id]
        todo.position = position
        session.add(todo)
    session.commit()
    return {"message": "Todos reordered successfully"}



@todos_router.delete('/user/todos/{todo_id}/delete')
async def delete_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    from datetime import datetime
    from utils.timezone import JST
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id or todo.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Todo not found")
    todo.deleted_at = datetime.now(JST)
    session.add(todo)
    session.commit()
    return {"message": "Todo moved to trash"}
