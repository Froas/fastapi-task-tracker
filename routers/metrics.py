from datetime import date as Date, datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models import (
    DailyLog,
    Goal,
    MetricDefinition,
    MetricDefinitionCreate,
    MetricDefinitionRead,
    MetricDefinitionUpdate,
    MetricEntry,
    MetricEntryRead,
    MetricEntryUpsert,
    Milestone,
    Task,
    TodayMetricRead,
    User,
    get_current_active_user,
)
from routers.visibility import active_goal_ids, active_task_ids
from utils.timezone import JST
from services.completion_rules import recalculate_for_metric


metrics_router = APIRouter()

VALID_METRIC_INPUT_TYPES = {"number", "text", "boolean"}


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


def _normalize_input_type(input_type: str | None) -> str:
    normalized = (input_type or "number").strip().lower()
    if normalized not in VALID_METRIC_INPUT_TYPES:
        raise HTTPException(status_code=400, detail="Metric input_type must be number, text, or boolean")
    return normalized


def _active_goal(session: Session, user: User, goal_id) -> Goal | None:
    if goal_id is None:
        return None
    return session.exec(
        select(Goal).where(
            Goal.id == goal_id,
            Goal.user_id == user.id,
            Goal.deleted_at.is_(None),
        )
    ).first()


def _active_task(session: Session, user: User, task_id) -> Task | None:
    if task_id is None:
        return None
    return session.exec(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user.id,
            Task.deleted_at.is_(None),
            Task.id.in_(active_task_ids(user.id)),
        )
    ).first()


def _active_milestone(session: Session, user: User, milestone_id) -> Milestone | None:
    if milestone_id is None:
        return None
    return session.exec(
        select(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.user_id == user.id,
            Milestone.deleted_at.is_(None),
        )
    ).first()


def _goal_for_metric(session: Session, metric: MetricDefinition) -> Goal | None:
    if metric.goal_id:
        return session.exec(
            select(Goal).where(
                Goal.id == metric.goal_id,
                Goal.deleted_at.is_(None),
            )
        ).first()

    if metric.milestone_id:
        milestone = session.get(Milestone, metric.milestone_id)
        if milestone and milestone.goal_id:
            return session.get(Goal, milestone.goal_id)
    if metric.task_id:
        task = session.get(Task, metric.task_id)
        if task and task.goal_id:
            return session.get(Goal, task.goal_id)
        if task and task.milestone_id:
            milestone = session.get(Milestone, task.milestone_id)
            if milestone and milestone.goal_id:
                return session.get(Goal, milestone.goal_id)
    return None


def _task_for_metric(session: Session, metric: MetricDefinition) -> Task | None:
    return session.get(Task, metric.task_id) if metric.task_id else None


def _metric_read(metric: MetricDefinition) -> MetricDefinitionRead:
    return MetricDefinitionRead(
        id=metric.id,
        name=metric.name,
        unit=metric.unit,
        input_type=metric.input_type,
        show_on_today=metric.show_on_today,
        goal_id=metric.goal_id,
        milestone_id=metric.milestone_id,
        task_id=metric.task_id,
        position=metric.position,
        created_at=metric.created_at,
        updated_at=metric.updated_at,
    )


def _today_metric_read(
    session: Session,
    metric: MetricDefinition,
    entry: MetricEntry | None,
    selected_date: Date,
) -> TodayMetricRead:
    goal = _goal_for_metric(session, metric)
    task = _task_for_metric(session, metric)
    return TodayMetricRead(
        **_metric_read(metric).model_dump(),
        goal_title=goal.title if goal else None,
        task_title=task.title if task else None,
        entry_id=entry.id if entry else None,
        date=entry.date if entry else selected_date,
        value=entry.value if entry else None,
        numeric_value=entry.numeric_value if entry else None,
        note=entry.note if entry else None,
    )


@metrics_router.get('/user/metric-definitions')
async def list_metric_definitions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[MetricDefinitionRead]:
    metrics = session.exec(
        select(MetricDefinition)
        .where(MetricDefinition.user_id == current_user.id)
        .where(MetricDefinition.deleted_at.is_(None))
        .order_by(MetricDefinition.goal_id, MetricDefinition.milestone_id, MetricDefinition.task_id, MetricDefinition.position, MetricDefinition.id)
    ).all()
    return [_metric_read(metric) for metric in metrics]


@metrics_router.post('/user/metric-definitions', response_model=MetricDefinitionRead)
async def create_metric_definition(
    current_user: Annotated[User, Depends(get_current_active_user)],
    metric_data: MetricDefinitionCreate,
    session: Session = Depends(get_session),
) -> MetricDefinitionRead:
    input_type = _normalize_input_type(metric_data.input_type)
    goal_id = metric_data.goal_id
    milestone_id = metric_data.milestone_id
    task_id = metric_data.task_id

    task = _active_task(session, current_user, task_id) if task_id else None
    if task_id and task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task and goal_id is None:
        goal_id = task.goal_id

    milestone = _active_milestone(session, current_user, milestone_id) if milestone_id else None
    if milestone_id and milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if milestone and goal_id is None:
        goal_id = milestone.goal_id

    if goal_id is not None and _active_goal(session, current_user, goal_id) is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    max_position = session.exec(
        select(MetricDefinition.position)
        .where(
            MetricDefinition.user_id == current_user.id,
            MetricDefinition.goal_id == goal_id,
            MetricDefinition.milestone_id == milestone_id,
            MetricDefinition.task_id == task_id,
            MetricDefinition.deleted_at.is_(None),
        )
        .order_by(MetricDefinition.position.desc())
    ).first()

    metric = MetricDefinition(
        name=metric_data.name,
        unit=metric_data.unit,
        input_type=input_type,
        show_on_today=metric_data.show_on_today,
        goal_id=goal_id,
        milestone_id=milestone_id,
        task_id=task_id,
        position=metric_data.position if metric_data.position is not None else (max_position or 0) + 1,
        user_id=current_user.id,
    )
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return _metric_read(metric)


@metrics_router.patch('/user/metric-definitions/update', response_model=MetricDefinitionRead)
async def update_metric_definition(
    metric_data: MetricDefinitionUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> MetricDefinitionRead:
    metric = session.get(MetricDefinition, metric_data.id)
    if metric is None or metric.user_id != current_user.id or metric.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Metric definition not found")

    update_data = metric_data.model_dump(exclude_unset=True, exclude={"id"})
    if "input_type" in update_data:
        update_data["input_type"] = _normalize_input_type(update_data["input_type"])

    next_goal_id = update_data.get("goal_id", metric.goal_id)
    next_milestone_id = update_data.get("milestone_id", metric.milestone_id)
    next_task_id = update_data.get("task_id", metric.task_id)
    task = _active_task(session, current_user, next_task_id) if next_task_id else None
    if next_task_id and task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task and next_goal_id is None:
        next_goal_id = task.goal_id
        update_data["goal_id"] = next_goal_id
    milestone = _active_milestone(session, current_user, next_milestone_id) if next_milestone_id else None
    if next_milestone_id and milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if milestone and next_goal_id is None:
        next_goal_id = milestone.goal_id
        update_data["goal_id"] = next_goal_id
    if next_goal_id is not None and _active_goal(session, current_user, next_goal_id) is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    for key, value in update_data.items():
        setattr(metric, key, value)
    metric.updated_at = datetime.now(JST)
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return _metric_read(metric)


@metrics_router.delete('/user/metric-definitions/{metric_id}/delete')
async def delete_metric_definition(
    metric_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, str]:
    metric = session.get(MetricDefinition, metric_id)
    if metric is None or metric.user_id != current_user.id or metric.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Metric definition not found")
    metric.deleted_at = datetime.now(JST)
    metric.updated_at = datetime.now(JST)
    session.add(metric)
    session.commit()
    return {"message": "Metric definition moved to trash"}


@metrics_router.get('/user/metrics/today')
async def get_today_metrics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    selected_date: Date | None = None,
    session: Session = Depends(get_session),
) -> list[TodayMetricRead]:
    metric_date = selected_date or datetime.now(JST).date()
    _log_for_date(session, current_user, metric_date)

    metrics = session.exec(
        select(MetricDefinition)
        .where(
            MetricDefinition.user_id == current_user.id,
            MetricDefinition.deleted_at.is_(None),
            MetricDefinition.show_on_today == True,
            (
                (MetricDefinition.task_id.is_(None))
                & (MetricDefinition.goal_id.in_(active_goal_ids(current_user.id)))
            ) | (
                (MetricDefinition.task_id.isnot(None))
                & (MetricDefinition.task_id.in_(active_task_ids(current_user.id)))
            ),
        )
        .order_by(MetricDefinition.goal_id, MetricDefinition.milestone_id, MetricDefinition.task_id, MetricDefinition.position, MetricDefinition.id)
    ).all()
    metric_ids = [metric.id for metric in metrics if metric.id is not None]
    entries = session.exec(
        select(MetricEntry).where(
            MetricEntry.user_id == current_user.id,
            MetricEntry.date == metric_date,
            MetricEntry.metric_definition_id.in_(metric_ids),
        )
    ).all() if metric_ids else []
    entries_by_metric = {entry.metric_definition_id: entry for entry in entries}

    session.commit()
    return [_today_metric_read(session, metric, entries_by_metric.get(metric.id), metric_date) for metric in metrics]


@metrics_router.post('/user/metric-entries/upsert', response_model=MetricEntryRead)
async def upsert_metric_entry(
    entry_data: MetricEntryUpsert,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> MetricEntryRead:
    metric = session.exec(
        select(MetricDefinition).where(
            MetricDefinition.id == entry_data.metric_definition_id,
            MetricDefinition.user_id == current_user.id,
            MetricDefinition.deleted_at.is_(None),
        )
    ).first()
    if metric is None:
        raise HTTPException(status_code=404, detail="Metric definition not found")

    entry_date = entry_data.date or datetime.now(JST).date()
    daily_log = _log_for_date(session, current_user, entry_date)
    entry = session.exec(
        select(MetricEntry).where(
            MetricEntry.user_id == current_user.id,
            MetricEntry.metric_definition_id == metric.id,
            MetricEntry.date == entry_date,
        )
    ).first()
    if entry is None:
        entry = MetricEntry(
            date=entry_date,
            metric_definition_id=metric.id,
            daily_log_id=daily_log.id,
            user_id=current_user.id,
        )

    entry.value = entry_data.value
    entry.numeric_value = entry_data.numeric_value
    entry.note = entry_data.note
    entry.updated_at = datetime.now(JST)
    session.add(entry)
    session.flush()
    recalculate_for_metric(session, metric)
    session.commit()
    session.refresh(entry)
    return entry
