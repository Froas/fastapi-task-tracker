from datetime import date as Date, datetime, timedelta
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models import (
    Goal,
    Milestone,
    Task,
    Todo,
    TodoOccurrence,
    TodoOccurrenceRead,
    TodoOccurrenceUpdate,
    User,
    get_current_active_user,
)
from routers.daily_lifecycle import ensure_occurrences_for_date, finalize_past_days, logical_today
from utils.timezone import JST
from services.completion_rules import recalculate_for_occurrence


todo_occurrences_router = APIRouter()

VALID_OCCURRENCE_STATUSES = {"open", "done", "minimum", "skipped", "missed", "excused"}
COMPLETED_OCCURRENCE_STATUSES = {"done", "minimum"}


def _normalize_status(status: str | None) -> str | None:
    if status is None:
        return None
    normalized = status.strip().lower()
    if normalized not in VALID_OCCURRENCE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Occurrence status must be open, done, minimum, skipped, missed, or excused",
        )
    return normalized


def _goal_for_task(session: Session, task: Task | None, milestone: Milestone | None) -> Goal | None:
    goal_id = task.goal_id if task and task.goal_id else milestone.goal_id if milestone else None
    if goal_id is None:
        return None
    return session.exec(
        select(Goal).where(
            Goal.id == goal_id,
            Goal.deleted_at.is_(None),
        )
    ).first()


def _read_occurrence(session: Session, occurrence: TodoOccurrence) -> TodoOccurrenceRead:
    todo = session.get(Todo, occurrence.todo_id)
    task = session.get(Task, todo.task_id) if todo and todo.task_id else None
    milestone = session.get(Milestone, task.milestone_id) if task and task.milestone_id else None
    goal = _goal_for_task(session, task, milestone)

    return TodoOccurrenceRead(
        id=occurrence.id,
        date=occurrence.date,
        status=occurrence.status,
        value=occurrence.value,
        note=occurrence.note,
        completed_at=occurrence.completed_at,
        is_focus=occurrence.is_focus,
        todo_id=occurrence.todo_id,
        daily_log_id=occurrence.daily_log_id,
        created_at=occurrence.created_at,
        updated_at=occurrence.updated_at,
        todo_title=todo.title if todo else "",
        todo_description=todo.description if todo else "",
        task_id=task.id if task else None,
        task_title=task.title if task else None,
        task_kind=task.kind if task else None,
        task_scope=task.scope if task else None,
        goal_id=goal.id if goal else None,
        goal_title=goal.title if goal else None,
        milestone_id=milestone.id if milestone else None,
        milestone_title=milestone.title if milestone else None,
    )


@todo_occurrences_router.get('/user/todo-occurrences')
async def list_todo_occurrences(
    current_user: Annotated[User, Depends(get_current_active_user)],
    selected_date: Date | None = None,
    session: Session = Depends(get_session),
) -> list[TodoOccurrenceRead]:
    occurrence_date = selected_date or logical_today()
    today = logical_today()
    if occurrence_date < today:
        finalize_past_days(session, current_user, today=today, extra_dates=[occurrence_date])
        session.commit()

    occurrences = session.exec(
        select(TodoOccurrence)
        .where(TodoOccurrence.user_id == current_user.id)
        .where(TodoOccurrence.date == occurrence_date)
        .order_by(TodoOccurrence.created_at, TodoOccurrence.id)
    ).all()
    return [_read_occurrence(session, occurrence) for occurrence in occurrences]


@todo_occurrences_router.get('/user/todo-occurrences/today')
async def get_today_todo_occurrences(
    current_user: Annotated[User, Depends(get_current_active_user)],
    selected_date: Date | None = None,
    session: Session = Depends(get_session),
) -> list[TodoOccurrenceRead]:
    occurrence_date = selected_date or logical_today()
    today = logical_today()
    finalize_past_days(session, current_user, today=today, extra_dates=[occurrence_date] if occurrence_date < today else None)
    ordered_occurrences = ensure_occurrences_for_date(session, current_user, occurrence_date)
    session.commit()
    for occurrence in ordered_occurrences:
        session.refresh(occurrence)
    return [_read_occurrence(session, occurrence) for occurrence in ordered_occurrences]


@todo_occurrences_router.get('/user/todo-occurrences/history')
async def list_todo_occurrence_history(
    current_user: Annotated[User, Depends(get_current_active_user)],
    start_date: Date | None = None,
    end_date: Date | None = None,
    status: str | None = None,
    goal_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
) -> list[TodoOccurrenceRead]:
    today = logical_today()
    range_end = end_date or today
    range_start = start_date or (range_end - timedelta(days=30))
    if range_start > range_end:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    finalize_past_days(session, current_user, today=today)
    session.commit()

    requested_statuses = {
        item.strip().lower()
        for item in (status or "done,minimum,skipped,missed,excused").split(",")
        if item.strip()
    }
    invalid_statuses = requested_statuses - VALID_OCCURRENCE_STATUSES
    if invalid_statuses:
        raise HTTPException(
            status_code=400,
            detail="Occurrence status must be open, done, minimum, skipped, missed, or excused",
        )

    statement = (
        select(TodoOccurrence)
        .where(TodoOccurrence.user_id == current_user.id)
        .where(TodoOccurrence.date >= range_start)
        .where(TodoOccurrence.date <= range_end)
    )
    if requested_statuses:
        statement = statement.where(TodoOccurrence.status.in_(requested_statuses))

    occurrences = session.exec(
        statement.order_by(TodoOccurrence.date.desc(), TodoOccurrence.created_at.desc(), TodoOccurrence.id)
    ).all()
    items = [_read_occurrence(session, occurrence) for occurrence in occurrences]
    if goal_id is not None:
        items = [item for item in items if item.goal_id == goal_id]
    if task_id is not None:
        items = [item for item in items if item.task_id == task_id]
    return items


@todo_occurrences_router.patch('/user/todo-occurrences/update', response_model=TodoOccurrenceRead)
async def update_todo_occurrence(
    occurrence_data: TodoOccurrenceUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> TodoOccurrenceRead:
    occurrence = session.get(TodoOccurrence, occurrence_data.id)
    if occurrence is None or occurrence.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Todo occurrence not found")

    next_status = _normalize_status(occurrence_data.status)
    if next_status is not None:
        occurrence.status = next_status
        occurrence.completed_at = datetime.now(JST) if next_status in COMPLETED_OCCURRENCE_STATUSES else None
    if occurrence_data.value is not None:
        occurrence.value = occurrence_data.value
    if occurrence_data.note is not None:
        occurrence.note = occurrence_data.note
    if occurrence_data.is_focus is not None:
        occurrence.is_focus = occurrence_data.is_focus

    occurrence.updated_at = datetime.now(JST)
    session.add(occurrence)
    recalculate_for_occurrence(session, occurrence)
    session.commit()
    session.refresh(occurrence)
    return _read_occurrence(session, occurrence)
