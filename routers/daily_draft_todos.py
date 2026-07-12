from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select, or_
from typing import Annotated
from datetime import date, datetime
import uuid

from models import DailyDraftTodo, DailyDraftTodoCreate, DailyDraftTodoUpdate, DailyDraftTodoRead, User, get_current_active_user
from db import get_session
from utils.timezone import JST

daily_draft_todos_router = APIRouter()


def _clean_title(title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Title is required")
    return cleaned


@daily_draft_todos_router.get('/user/daily-draft-todos')
async def list_daily_draft_todos(
    current_user: Annotated[User, Depends(get_current_active_user)],
    day: date | None = None,
    include_done: bool = True,
    include_carryover: bool = True,
    session: Session = Depends(get_session),
) -> list[DailyDraftTodoRead]:
    selected_day = day or datetime.now(JST).date()
    query = (
        select(DailyDraftTodo)
        .where(DailyDraftTodo.user_id == current_user.id)
        .where(DailyDraftTodo.deleted_at.is_(None))
    )
    if include_carryover:
        query = query.where(DailyDraftTodo.day <= selected_day)
        if include_done:
            query = query.where(or_(DailyDraftTodo.day == selected_day, DailyDraftTodo.done == False))
    else:
        query = query.where(DailyDraftTodo.day == selected_day)
    if not include_done:
        query = query.where(DailyDraftTodo.done == False)
    rows = session.exec(
        query.order_by(DailyDraftTodo.done.asc(), DailyDraftTodo.day.asc(), DailyDraftTodo.created_at.asc())
    ).all()
    return rows


@daily_draft_todos_router.post('/user/daily-draft-todos')
async def create_daily_draft_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_data: DailyDraftTodoCreate,
    session: Session = Depends(get_session),
) -> DailyDraftTodoRead:
    todo = DailyDraftTodo(
        title=_clean_title(todo_data.title),
        day=todo_data.day or datetime.now(JST).date(),
        user_id=current_user.id,
    )
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


@daily_draft_todos_router.patch('/user/daily-draft-todos/update', response_model=DailyDraftTodoRead)
async def update_daily_draft_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_data: DailyDraftTodoUpdate,
    session: Session = Depends(get_session),
) -> DailyDraftTodo:
    todo = session.get(DailyDraftTodo, todo_data.id)
    if todo is None or todo.user_id != current_user.id or todo.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Daily draft todo not found")

    update_data = todo_data.model_dump(exclude_unset=True, exclude={"id"})
    if "title" in update_data:
        update_data["title"] = _clean_title(update_data["title"])
    if "done" in update_data:
        next_done = bool(update_data["done"])
        if next_done and not todo.done:
            todo.completed_at = datetime.now(JST)
        if not next_done:
            todo.completed_at = None

    for key, value in update_data.items():
        setattr(todo, key, value)
    todo.updated_at = datetime.now(JST)
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


@daily_draft_todos_router.delete('/user/daily-draft-todos/{todo_id}/delete')
async def delete_daily_draft_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    todo = session.get(DailyDraftTodo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Daily draft todo not found")
    todo.deleted_at = datetime.now(JST)
    session.add(todo)
    session.commit()
    return {"message": "Daily draft todo deleted"}
