from __future__ import annotations

from datetime import date as Date, datetime, timedelta
import re

from sqlmodel import Session, select

from models import Milestone, StatusType, Task, Todo, TodoOccurrence
from utils.timezone import JST


TRACKING_MODES = {"ongoing", "bounded", "staged"}
TRACKING_STATES = {"planned", "active", "graduated", "paused"}
COMPLETED_OCCURRENCE_STATUSES = {"done", "minimum"}


def normalize_tracking_mode(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized if normalized in TRACKING_MODES else None


def normalize_tracking_state(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized if normalized in TRACKING_STATES else None


def normalize_series_key(value: str | None) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return normalized[:120] or None


def inferred_tracking_defaults(
    session: Session,
    task: Task,
    *,
    tracking_mode: str | None,
    tracking_state: str | None,
    series_key: str | None,
    stage_order: int,
) -> tuple[str | None, str | None, str | None, int]:
    mode = normalize_tracking_mode(tracking_mode)
    state = normalize_tracking_state(tracking_state)
    key = normalize_series_key(series_key)
    order = max(1, stage_order or 1)

    if mode is None:
        if task.kind == "routine" and task.scope == "goal":
            mode = "ongoing"
        elif task.kind == "challenge":
            mode = "bounded"
        else:
            # Preserve legacy project todos instead of silently changing their
            # semantics. Their Today visibility follows the legacy scope rule.
            return None, None, key, order

    if mode == "ongoing":
        return mode, state or "active", key, order

    if mode == "staged" and key is None:
        key = normalize_series_key(task.title) or str(task.id)

    if state is None:
        milestone = session.get(Milestone, task.milestone_id) if task.milestone_id else None
        if mode == "staged" and key:
            earlier = session.exec(
                select(Todo.id).join(Task, Todo.task_id == Task.id).where(
                    Todo.user_id == task.user_id,
                    Todo.deleted_at.is_(None),
                    Todo.routine_series_key == key,
                    Todo.stage_order < order,
                    Task.goal_id == task.goal_id,
                    Task.deleted_at.is_(None),
                )
            ).first()
            state = "planned" if earlier is not None else "active"
        elif task.status in {StatusType.STARTED, StatusType.IN_PROGRESS}:
            state = "active"
        elif milestone is not None and milestone.status == StatusType.OUTSTANDING:
            state = "planned"
        else:
            state = "active"
    return mode, state, key, order


def todo_is_explicitly_active(todo: Todo, selected_date: Date) -> bool:
    if todo.tracking_mode is None:
        return False
    if todo.tracking_state != "active":
        return False
    return todo.active_from is None or todo.active_from <= selected_date


def activate_tracking_for_milestone(
    session: Session,
    milestone: Milestone,
    *,
    active_from: Date | None = None,
) -> list[Todo]:
    task_ids = list(session.exec(
        select(Task.id).where(
            Task.milestone_id == milestone.id,
            Task.deleted_at.is_(None),
        )
    ).all())
    if not task_ids:
        return []
    planned = list(session.exec(
        select(Todo).where(
            Todo.task_id.in_(task_ids),
            Todo.deleted_at.is_(None),
            Todo.tracking_state == "planned",
        ).order_by(Todo.stage_order, Todo.position, Todo.id)
    ).all())
    activated: list[Todo] = []
    for todo in planned:
        if todo.tracking_mode == "staged" and todo.routine_series_key:
            unfinished_predecessor = session.exec(
                select(Todo.id).join(Task, Todo.task_id == Task.id).where(
                    Todo.user_id == todo.user_id,
                    Todo.deleted_at.is_(None),
                    Todo.routine_series_key == todo.routine_series_key,
                    Todo.stage_order < todo.stage_order,
                    Todo.tracking_state != "graduated",
                    Task.goal_id == milestone.goal_id,
                    Task.deleted_at.is_(None),
                )
            ).first()
            if unfinished_predecessor is not None:
                continue
        todo.tracking_state = "active"
        todo.active_from = active_from
        session.add(todo)
        activated.append(todo)
    return activated


def advance_tracking_after_occurrence(
    session: Session,
    occurrence: TodoOccurrence,
) -> Todo | None:
    if occurrence.status not in COMPLETED_OCCURRENCE_STATUSES:
        return None
    todo = session.get(Todo, occurrence.todo_id)
    if todo is None or todo.tracking_mode not in {"bounded", "staged"}:
        return None
    if todo.tracking_state != "active":
        return None
    task = session.get(Task, todo.task_id) if todo.task_id else None
    if task is None or task.status not in {StatusType.FINISHED, StatusType.CLOSED}:
        return None

    now = datetime.now(JST)
    todo.tracking_state = "graduated"
    todo.graduated_at = now
    session.add(todo)

    if todo.tracking_mode != "staged" or not todo.routine_series_key:
        return None

    next_todo = session.exec(
        select(Todo).join(Task, Todo.task_id == Task.id).where(
            Todo.user_id == todo.user_id,
            Todo.deleted_at.is_(None),
            Todo.routine_series_key == todo.routine_series_key,
            Todo.stage_order > todo.stage_order,
            Todo.tracking_state == "planned",
            Task.goal_id == task.goal_id,
            Task.deleted_at.is_(None),
        ).order_by(Todo.stage_order, Todo.position, Todo.id)
    ).first()
    if next_todo is None:
        return None

    next_todo.tracking_state = "active"
    next_todo.active_from = occurrence.date + timedelta(days=1)
    session.add(next_todo)

    next_task = session.get(Task, next_todo.task_id) if next_todo.task_id else None
    if next_task is not None and next_task.status == StatusType.OUTSTANDING:
        next_task.status = StatusType.STARTED
        session.add(next_task)
    next_milestone = session.get(Milestone, next_task.milestone_id) if next_task and next_task.milestone_id else None
    if next_milestone is not None and next_milestone.status == StatusType.OUTSTANDING:
        next_milestone.status = StatusType.STARTED
        session.add(next_milestone)
    return next_todo


def tracking_progress(task: Task | None) -> tuple[int | None, int | None, int | None]:
    rule = task.completion_rule if task and isinstance(task.completion_rule, dict) else None
    if not rule or rule.get("type") != "consistency":
        return None, None, None
    return (
        int(rule.get("current_done") or 0),
        int(rule.get("required_done") or 0) or None,
        int(rule.get("window_days") or 0) or None,
    )


def tracking_consumer_for_todo(session: Session, todo: Todo, parent_task: Task | None) -> Task | None:
    """Return an active challenge that deliberately counts this definition."""
    if parent_task is None or parent_task.goal_id is None:
        return None
    candidates = session.exec(
        select(Task).where(
            Task.user_id == todo.user_id,
            Task.goal_id == parent_task.goal_id,
            Task.kind == "challenge",
            Task.deleted_at.is_(None),
            Task.status.in_((StatusType.OUTSTANDING, StatusType.STARTED, StatusType.IN_PROGRESS)),
        ).order_by(Task.position, Task.id)
    ).all()
    todo_id = str(todo.id)
    for candidate in candidates:
        rule = candidate.completion_rule if isinstance(candidate.completion_rule, dict) else {}
        consistency = rule.get("consistency") if rule.get("type") == "hybrid" else rule
        if not isinstance(consistency, dict) or consistency.get("type") != "consistency":
            continue
        configured = consistency.get("todo_ids")
        if not isinstance(configured, list):
            configured = [consistency.get("todo_id")] if consistency.get("todo_id") else []
        if todo_id in {str(item) for item in configured}:
            return candidate
    return None
