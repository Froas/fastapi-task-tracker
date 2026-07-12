from datetime import date as Date, datetime, timedelta
from typing import Iterable

from sqlmodel import Session, select

from models import DailyDraftTodo, DailyLog, MetricEntry, Todo, TodoOccurrence, User
from routers.visibility import active_recurring_todo_ids
from utils.timezone import JST


DAY_BOUNDARY_HOUR = 4
FINALIZER_LOOKBACK_DAYS = 14
FINALIZED_BY_AUTO = "auto"
COMPLETED_OCCURRENCE_STATUSES = {"done", "minimum"}
MEANINGFUL_OCCURRENCE_STATUSES = {"done", "minimum", "skipped", "excused"}


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


def _active_recurring_todos(session: Session, user: User) -> list[Todo]:
    return session.exec(
        select(Todo)
        .where(
            Todo.user_id == user.id,
            Todo.id.in_(active_recurring_todo_ids(user.id)),
        )
        .order_by(Todo.task_id, Todo.position, Todo.id)
    ).all()


def ensure_occurrences_for_date(session: Session, user: User, selected_date: Date) -> list[TodoOccurrence]:
    daily_log = _log_for_date(session, user, selected_date)
    todos = _active_recurring_todos(session, user)
    todo_ids = [todo.id for todo in todos if todo.id is not None]

    existing = session.exec(
        select(TodoOccurrence).where(
            TodoOccurrence.user_id == user.id,
            TodoOccurrence.date == selected_date,
            TodoOccurrence.todo_id.in_(todo_ids),
        )
    ).all() if todo_ids else []
    existing_by_todo = {occurrence.todo_id: occurrence for occurrence in existing}

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
