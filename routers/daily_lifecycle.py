from datetime import date as Date, datetime, timedelta
from typing import Iterable
import uuid

from sqlmodel import Session, select

from models import (
    DailyDraftTodo,
    DailyLog,
    MetricEntry,
    Milestone,
    StatusType,
    Task,
    Todo,
    TodoOccurrence,
    User,
)
from routers.visibility import active_recurring_todo_ids
from services.tracking import todo_is_explicitly_active
from utils.timezone import JST


DAY_BOUNDARY_HOUR = 4
FINALIZER_LOOKBACK_DAYS = 14
FINALIZED_BY_AUTO = "auto"
COMPLETED_OCCURRENCE_STATUSES = {"done", "minimum"}
MEANINGFUL_OCCURRENCE_STATUSES = {"done", "minimum", "skipped", "excused"}
CURRENT_MILESTONE_STATUSES = {StatusType.STARTED, StatusType.IN_PROGRESS}


def logical_today(now: datetime | None = None) -> Date:
    current = now or datetime.now(JST)
    if current.hour < DAY_BOUNDARY_HOUR:
        return (current - timedelta(days=1)).date()
    return current.date()


def _date_range(start: Date, end: Date) -> Iterable[Date]:
    current = start
    while current <= end:
        yield current
        current = current + timedelta(days=1)


def _log_for_date(session: Session, user: User, selected_date: Date) -> DailyLog:
    log = session.exec(
        select(DailyLog)
        .where(DailyLog.user_id == user.id)
        .where(DailyLog.deleted_at.is_(None))
        .where(DailyLog.date == selected_date)
    ).first()
    if log is not None:
        return log

    log = DailyLog(date=selected_date, user_id=user.id)
    session.add(log)
    session.flush()
    return log


def _current_milestone_ids(milestones: Iterable[Milestone]) -> set[uuid.UUID]:
    """Pick the milestone scopes whose routines belong on Today.

    Explicitly started milestones win. When a goal has no explicitly current
    milestone, its first outstanding milestone is the implicit current one.
    This keeps existing plans useful while preventing every future milestone
    from generating occurrences at once.
    """
    by_goal: dict[uuid.UUID, list[Milestone]] = {}
    for milestone in milestones:
        if milestone.goal_id is not None:
            by_goal.setdefault(milestone.goal_id, []).append(milestone)

    selected: set[uuid.UUID] = set()
    for goal_milestones in by_goal.values():
        ordered = sorted(goal_milestones, key=lambda item: (item.position, str(item.id)))
        explicit = [item for item in ordered if item.status in CURRENT_MILESTONE_STATUSES]
        current = explicit or next(
            ([item] for item in ordered if item.status == StatusType.OUTSTANDING),
            [],
        )
        selected.update(item.id for item in current if item.id is not None)
    return selected


def _active_recurring_todos(session: Session, user: User, selected_date: Date | None = None) -> list[Todo]:
    occurrence_date = selected_date or logical_today()
    todos = session.exec(
        select(Todo)
        .where(
            Todo.user_id == user.id,
            Todo.id.in_(active_recurring_todo_ids(user.id)),
        )
        .order_by(Todo.task_id, Todo.position, Todo.id)
    ).all()
    if not todos:
        return []

    task_ids = {todo.task_id for todo in todos if todo.task_id is not None}
    tasks = session.exec(
        select(Task).where(
            Task.user_id == user.id,
            Task.id.in_(task_ids),
        )
    ).all()
    tasks_by_id = {task.id: task for task in tasks}

    referenced_milestone_ids = {
        task.milestone_id for task in tasks if task.milestone_id is not None
    }
    referenced_milestones = session.exec(
        select(Milestone).where(
            Milestone.user_id == user.id,
            Milestone.id.in_(referenced_milestone_ids),
            Milestone.deleted_at.is_(None),
        )
    ).all() if referenced_milestone_ids else []
    goal_ids = {task.goal_id for task in tasks if task.goal_id is not None}
    goal_ids.update(
        milestone.goal_id
        for milestone in referenced_milestones
        if milestone.goal_id is not None
    )
    goal_milestones = session.exec(
        select(Milestone).where(
            Milestone.user_id == user.id,
            Milestone.goal_id.in_(goal_ids),
            Milestone.deleted_at.is_(None),
        )
    ).all() if goal_ids else []
    current_milestone_ids = _current_milestone_ids(goal_milestones)

    active: list[Todo] = []
    for todo in todos:
        task = tasks_by_id.get(todo.task_id)
        if task is None:
            continue
        if task.kind == "challenge" and isinstance(task.completion_rule, dict):
            rule = task.completion_rule
            consistency = rule.get("consistency") if rule.get("type") == "hybrid" else rule
            if isinstance(consistency, dict) and consistency.get("type") == "consistency":
                configured = consistency.get("todo_ids")
                if not isinstance(configured, list):
                    configured = [consistency.get("todo_id")] if consistency.get("todo_id") else []
                configured_ids = {str(item) for item in configured if item}
                own_ids = {str(item.id) for item in todos if item.task_id == task.id}
                if configured_ids and configured_ids.isdisjoint(own_ids):
                    # The challenge consumes an existing goal routine. Its
                    # local definition is not a second checkbox on Today.
                    continue
        if todo.tracking_mode is not None:
            if todo_is_explicitly_active(todo, occurrence_date):
                active.append(todo)
            continue
        if (
            task.scope == "goal"
            or task.milestone_id is None
            or task.milestone_id in current_milestone_ids
        ):
            active.append(todo)
    # Legacy plans often stored the same definition once under the goal routine
    # and again under the current milestone. Collapse only those legacy/null
    # lifecycle duplicates; explicit challenge contracts are never guessed.
    deduplicated: list[Todo] = []
    legacy_index: dict[tuple[object, str, str], int] = {}
    for todo in active:
        task = tasks_by_id.get(todo.task_id)
        if task is None or todo.tracking_mode is not None:
            deduplicated.append(todo)
            continue
        key = (
            task.goal_id or task.id,
            " ".join(todo.title.split()).casefold(),
            (todo.repeat_interval or "").casefold(),
        )
        existing_index = legacy_index.get(key)
        if existing_index is None:
            legacy_index[key] = len(deduplicated)
            deduplicated.append(todo)
            continue
        existing = deduplicated[existing_index]
        existing_task = tasks_by_id.get(existing.task_id)
        if existing_task is not None and existing_task.scope != "goal" and task.scope == "goal":
            deduplicated[existing_index] = todo
    return deduplicated


def ensure_occurrences_for_date(session: Session, user: User, selected_date: Date) -> list[TodoOccurrence]:
    daily_log = _log_for_date(session, user, selected_date)
    todos = _active_recurring_todos(session, user, selected_date)
    todo_ids = [todo.id for todo in todos if todo.id is not None]

    all_existing = session.exec(
        select(TodoOccurrence).where(
            TodoOccurrence.user_id == user.id,
            TodoOccurrence.date == selected_date,
        )
    ).all()
    existing = [occurrence for occurrence in all_existing if occurrence.todo_id in todo_ids]
    existing_by_todo = {occurrence.todo_id: occurrence for occurrence in existing}

    # Open occurrences are generated prompts, not user history. If a routine
    # leaves the active scope, remove its untouched prompt so the day finalizer
    # cannot turn a hidden future-milestone item into `missed`. Completed,
    # minimum, skipped, and excused facts are retained.
    active_todo_ids = set(todo_ids)
    for occurrence in all_existing:
        if occurrence.todo_id not in active_todo_ids and occurrence.status == "open":
            session.delete(occurrence)

    for todo in todos:
        if todo.id in existing_by_todo:
            occurrence = existing_by_todo[todo.id]
            if occurrence.daily_log_id is None:
                occurrence.daily_log_id = daily_log.id
                occurrence.updated_at = datetime.now(JST)
                session.add(occurrence)
            continue
        occurrence = TodoOccurrence(
            date=selected_date,
            status="open",
            todo_id=todo.id,
            daily_log_id=daily_log.id,
            user_id=user.id,
        )
        session.add(occurrence)
        session.flush()
        existing_by_todo[todo.id] = occurrence

    return [existing_by_todo[todo.id] for todo in todos if todo.id in existing_by_todo]


def _has_meaningful_activity(session: Session, user: User, log: DailyLog, selected_date: Date) -> bool:
    if log.color in {"green", "yellow", "red"}:
        return True

    if any((log.note, log.trigger, log.what_helped, log.tomorrow_minimum)):
        return True

    occurrence = session.exec(
        select(TodoOccurrence).where(
            TodoOccurrence.user_id == user.id,
            TodoOccurrence.date == selected_date,
            TodoOccurrence.status.in_(MEANINGFUL_OCCURRENCE_STATUSES),
        )
    ).first()
    if occurrence is not None:
        return True

    metric_entry = session.exec(
        select(MetricEntry).where(
            MetricEntry.user_id == user.id,
            MetricEntry.date == selected_date,
        )
    ).first()
    if metric_entry is not None:
        return True

    draft_todo = session.exec(
        select(DailyDraftTodo).where(
            DailyDraftTodo.user_id == user.id,
            DailyDraftTodo.day == selected_date,
            DailyDraftTodo.deleted_at.is_(None),
        )
    ).first()
    return draft_todo is not None


def finalize_day(session: Session, user: User, selected_date: Date, today: Date | None = None) -> bool:
    current_day = today or logical_today()
    if selected_date >= current_day:
        return False

    log = _log_for_date(session, user, selected_date)
    if log.finalized_at is not None:
        return False

    now = datetime.now(JST)
    ensure_occurrences_for_date(session, user, selected_date)

    occurrences = session.exec(
        select(TodoOccurrence).where(
            TodoOccurrence.user_id == user.id,
            TodoOccurrence.date == selected_date,
        )
    ).all()
    for occurrence in occurrences:
        if occurrence.status == "open":
            occurrence.status = "missed"
            occurrence.completed_at = None
            occurrence.updated_at = now
            session.add(occurrence)

    if log.color is None:
        log.color = "yellow" if _has_meaningful_activity(session, user, log, selected_date) else "black"

    log.finalized_at = now
    log.finalized_by = FINALIZED_BY_AUTO
    log.updated_at = now
    session.add(log)
    return True


def _dates_to_finalize(session: Session, user: User, today: Date, extra_dates: Iterable[Date] | None = None) -> set[Date]:
    last_date = today - timedelta(days=1)
    cutoff = today - timedelta(days=FINALIZER_LOOKBACK_DAYS)
    dates: set[Date] = set()

    unfinalized_log_dates = session.exec(
        select(DailyLog.date)
        .where(DailyLog.user_id == user.id)
        .where(DailyLog.deleted_at.is_(None))
        .where(DailyLog.date < today)
        .where(DailyLog.finalized_at.is_(None))
    ).all()
    dates.update(date for date in unfinalized_log_dates if cutoff <= date <= last_date)

    open_occurrence_dates = session.exec(
        select(TodoOccurrence.date)
        .where(TodoOccurrence.user_id == user.id)
        .where(TodoOccurrence.date < today)
        .where(TodoOccurrence.status == "open")
    ).all()
    dates.update(date for date in open_occurrence_dates if cutoff <= date <= last_date)

    latest_log_date = session.exec(
        select(DailyLog.date)
        .where(DailyLog.user_id == user.id)
        .where(DailyLog.deleted_at.is_(None))
        .where(DailyLog.date < today)
        .order_by(DailyLog.date.desc())
    ).first()
    if latest_log_date is not None and latest_log_date < last_date:
        gap_start = max(latest_log_date + timedelta(days=1), cutoff)
        dates.update(_date_range(gap_start, last_date))

    if extra_dates is not None:
        dates.update(date for date in extra_dates if cutoff <= date <= last_date)

    return dates


def finalize_past_days(
    session: Session,
    user: User,
    today: Date | None = None,
    extra_dates: Iterable[Date] | None = None,
) -> int:
    current_day = today or logical_today()
    finalized = 0
    for selected_date in sorted(_dates_to_finalize(session, user, current_day, extra_dates)):
        if finalize_day(session, user, selected_date, today=current_day):
            finalized += 1
    return finalized
