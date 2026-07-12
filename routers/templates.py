from datetime import datetime, timedelta
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, or_, select

from db import get_session
from models import (
    Goal,
    MetricDefinition,
    Milestone,
    PriorityType,
    StatusType,
    Subtask,
    Task,
    Template,
    TemplateCreate,
    TemplateInstantiate,
    TemplateInstantiateBlueprint,
    TemplateRead,
    TemplateUpdate,
    Todo,
    User,
    get_current_active_user,
)
from utils.timezone import JST


templates_router = APIRouter()

VALID_TASK_KINDS = {"project", "routine", "challenge"}
VALID_TASK_SCOPES = {"goal", "milestone"}
VALID_METRIC_INPUT_TYPES = {"number", "text", "boolean"}


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _date_from_offset(base: datetime, item: dict[str, Any], key: str, fallback: datetime | None = None) -> datetime | None:
    direct = _parse_datetime(item.get(key))
    if direct is not None:
        return direct
    offset_key = f"{key}_offset_days"
    if offset_key in item and item[offset_key] is not None:
        try:
            return base + timedelta(days=int(item[offset_key]))
        except (TypeError, ValueError):
            return fallback
    return fallback


def _status(value: Any, default: StatusType = StatusType.OUTSTANDING) -> StatusType:
    if isinstance(value, StatusType):
        return value
    if isinstance(value, str):
        try:
            return StatusType(value.strip().lower())
        except ValueError:
            return default
    return default


def _priority(value: Any, default: PriorityType = PriorityType.MEDIUM) -> PriorityType:
    if isinstance(value, PriorityType):
        return value
    if isinstance(value, str):
        try:
            return PriorityType(value.strip().lower())
        except ValueError:
            return default
    return default


def _task_kind(value: Any) -> str:
    normalized = str(value or "project").strip().lower()
    return normalized if normalized in VALID_TASK_KINDS else "project"


def _task_scope(value: Any, milestone: Milestone | None) -> str:
    normalized = str(value or ("milestone" if milestone else "goal")).strip().lower()
    if normalized not in VALID_TASK_SCOPES:
        normalized = "milestone" if milestone else "goal"
    if milestone is not None:
        return "milestone"
    if normalized == "milestone":
        return "goal"
    return normalized


def _metric_input_type(value: Any) -> str:
    normalized = str(value or "number").strip().lower()
    return normalized if normalized in VALID_METRIC_INPUT_TYPES else "number"


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _title(item: Any, fallback: str) -> str:
    if isinstance(item, str):
        return item.strip() or fallback
    if isinstance(item, dict):
        return str(item.get("title") or item.get("name") or fallback).strip() or fallback
    return fallback


def _description(item: Any) -> str:
    return str(item.get("description") or "") if isinstance(item, dict) else ""


def _max_position(session: Session, model: Any, user: User, **filters: Any) -> int:
    statement = select(model.position).where(model.user_id == user.id)
    if hasattr(model, "deleted_at"):
        statement = statement.where(model.deleted_at.is_(None))
    for field, value in filters.items():
        column = getattr(model, field)
        statement = statement.where(column.is_(None) if value is None else column == value)
    return session.exec(statement.order_by(model.position.desc())).first() or -1


def _create_metric(
    session: Session,
    user: User,
    metric_data: Any,
    goal: Goal,
    task: Task | None,
    position: int,
) -> MetricDefinition:
    metric = MetricDefinition(
        name=_title(metric_data, f"Metric {position + 1}"),
        unit=metric_data.get("unit") if isinstance(metric_data, dict) else None,
        input_type=_metric_input_type(metric_data.get("input_type") if isinstance(metric_data, dict) else None),
        show_on_today=bool(metric_data.get("show_on_today", True)) if isinstance(metric_data, dict) else True,
        goal_id=goal.id,
        task_id=task.id if task else None,
        position=position,
        user_id=user.id,
    )
    session.add(metric)
    session.flush()
    return metric


def _create_todo_definition(
    session: Session,
    user: User,
    todo_data: Any,
    task: Task,
    position: int,
    start_dt: datetime,
) -> Todo:
    repeat_interval = "daily"
    if isinstance(todo_data, dict):
        repeat_interval = str(todo_data.get("repeat_interval") or todo_data.get("recurrence") or "daily")

    todo = Todo(
        title=_title(todo_data, f"Routine {position + 1}"),
        description=_description(todo_data) or "Recurring definition. Daily facts live in TodoOccurrence.",
        repeat_interval=repeat_interval,
        next_due_date=start_dt,
        start_datetime=start_dt,
        status=_status(todo_data.get("status") if isinstance(todo_data, dict) else None),
        priority=_priority(todo_data.get("priority") if isinstance(todo_data, dict) else None),
        task_id=task.id,
        position=position,
        user_id=user.id,
    )
    session.add(todo)
    session.flush()
    return todo


def _create_subtask(
    session: Session,
    user: User,
    subtask_data: Any,
    task: Task,
    position: int,
    start_dt: datetime,
) -> Subtask:
    subtask = Subtask(
        title=_title(subtask_data, f"Subtask {position + 1}"),
        description=_description(subtask_data),
        due_date=_date_from_offset(start_dt, subtask_data, "due_date", task.due_date) if isinstance(subtask_data, dict) else task.due_date,
        start_datetime=start_dt,
        status=_status(subtask_data.get("status") if isinstance(subtask_data, dict) else None),
        priority=_priority(subtask_data.get("priority") if isinstance(subtask_data, dict) else None, task.priority or PriorityType.MEDIUM),
        task_id=task.id,
        position=position,
        user_id=user.id,
    )
    session.add(subtask)
    session.flush()
    return subtask


def _create_task(
    session: Session,
    user: User,
    task_data: Any,
    goal: Goal,
    milestone: Milestone | None,
    position: int,
    start_dt: datetime,
) -> Task:
    data = task_data if isinstance(task_data, dict) else {"title": str(task_data)}
    scope = _task_scope(data.get("scope"), milestone)
    task = Task(
        title=_title(data, f"Task {position + 1}"),
        description=_description(data),
        due_date=_date_from_offset(start_dt, data, "due_date"),
        scheduled_date=_date_from_offset(start_dt, data, "scheduled_date"),
        start_datetime=start_dt,
        end_datetime=_date_from_offset(start_dt, data, "end_datetime"),
        status=_status(data.get("status")),
        priority=_priority(data.get("priority")),
        goal_id=goal.id,
        milestone_id=milestone.id if milestone else None,
        kind=_task_kind(data.get("kind")),
        scope=scope,
        position=position,
        completion_rule=data.get("completion_rule"),
        user_id=user.id,
    )
    session.add(task)
    session.flush()

    for subtask_index, subtask_data in enumerate(_items(data.get("subtasks"))):
        _create_subtask(session, user, subtask_data, task, subtask_index, start_dt)
    for todo_index, todo_data in enumerate(_items(data.get("todos"))):
        _create_todo_definition(session, user, todo_data, task, todo_index, start_dt)
    for metric_index, metric_data in enumerate(_items(data.get("metrics"))):
        _create_metric(session, user, metric_data, goal, task, metric_index)

    return task


def _create_goal_task(
    session: Session,
    user: User,
    task_data: Any,
    goal: Goal,
    position: int,
    start_dt: datetime,
) -> Task:
    data = task_data if isinstance(task_data, dict) else {"title": str(task_data)}
    data = {**data, "scope": "goal"}
    return _create_task(session, user, data, goal, None, position, start_dt)


def _create_milestone(
    session: Session,
    user: User,
    milestone_data: Any,
    goal: Goal,
    position: int,
    start_dt: datetime,
    total_duration_days: int,
) -> Milestone:
    data = milestone_data if isinstance(milestone_data, dict) else {"title": str(milestone_data)}
    default_due = start_dt + timedelta(days=max(1, round(total_duration_days * (position + 1) / 4)))
    milestone = Milestone(
        title=_title(data, f"Milestone {position + 1}"),
        description=_description(data),
        due_date=_date_from_offset(start_dt, data, "due_date", default_due),
        start_datetime=start_dt,
        status=_status(data.get("status")),
        priority=_priority(data.get("priority")),
        goal_id=goal.id,
        position=position,
        completion_rule=data.get("completion_rule"),
        user_id=user.id,
    )
    session.add(milestone)
    session.flush()

    task_items = _items(data.get("tasks"))
    legacy_titles = _items(data.get("taskTitles")) or _items(data.get("task_titles"))
    if not task_items and legacy_titles:
        task_items = [{"title": title, "kind": "project", "subtasks": []} for title in legacy_titles]

    for task_index, task_data in enumerate(task_items):
        _create_task(session, user, task_data, goal, milestone, task_index, start_dt)

    return milestone


def _materialize_blueprint(
    session: Session,
    user: User,
    title: str,
    description: str | None,
    blueprint: dict[str, Any],
    start_dt: datetime,
    end_dt: datetime,
) -> Goal:
    duration_days = max(1, (end_dt - start_dt).days or int(blueprint.get("duration_days") or 84))
    goal = Goal(
        title=title,
        description=description,
        start_datetime=start_dt,
        end_datetime=end_dt,
        completion_rule=blueprint.get("completion_rule"),
        status=_status(blueprint.get("status")),
        priority=_priority(blueprint.get("priority"), PriorityType.HIGH),
        position=_max_position(session, Goal, user) + 1,
        user_id=user.id,
    )
    session.add(goal)
    session.flush()

    for metric_index, metric_data in enumerate(_items(blueprint.get("metrics"))):
        _create_metric(session, user, metric_data, goal, None, metric_index)

    for task_index, task_data in enumerate(_items(blueprint.get("goal_tasks"))):
        _create_goal_task(session, user, task_data, goal, task_index, start_dt)

    for milestone_index, milestone_data in enumerate(_items(blueprint.get("milestones"))):
        _create_milestone(session, user, milestone_data, goal, milestone_index, start_dt, duration_days)

    return goal


def _template_duration(template: TemplateCreate | Template, start_dt: datetime, override_end: datetime | None) -> datetime:
    if override_end is not None:
        return override_end
    blueprint = template.blueprint or {}
    duration_days = blueprint.get("duration_days") if isinstance(blueprint, dict) else None
    if duration_days is not None:
        try:
            return start_dt + timedelta(days=int(duration_days))
        except (TypeError, ValueError):
            pass
    return start_dt + timedelta(weeks=12)


@templates_router.get('/user/templates')
async def list_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[TemplateRead]:
    rows = session.exec(
        select(Template).where(
            or_(Template.user_id.is_(None), Template.user_id == current_user.id)
        ).order_by(Template.created_at.desc())
    ).all()
    return rows


@templates_router.post('/user/templates')
async def create_template(
    current_user: Annotated[User, Depends(get_current_active_user)],
    template_data: TemplateCreate,
    session: Session = Depends(get_session),
) -> TemplateRead:
    template = Template(
        title=template_data.title,
        description=template_data.description,
        emoji=template_data.emoji,
        tags=template_data.tags,
        blueprint=template_data.blueprint,
        user_id=current_user.id,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@templates_router.post('/user/templates/instantiate-blueprint')
async def instantiate_unsaved_blueprint(
    payload: TemplateInstantiateBlueprint,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Goal:
    start_dt = payload.start_datetime or datetime.now(JST)
    end_dt = _template_duration(payload, start_dt, payload.end_datetime)
    goal = _materialize_blueprint(
        session,
        current_user,
        payload.title_override or payload.title,
        payload.description,
        payload.blueprint or {},
        start_dt,
        end_dt,
    )
    session.commit()
    session.refresh(goal)
    return goal


@templates_router.patch('/user/templates/update', response_model=TemplateRead)
async def update_template(
    current_user: Annotated[User, Depends(get_current_active_user)],
    template_data: TemplateUpdate,
    session: Session = Depends(get_session),
) -> Template:
    template = session.get(Template, template_data.id)
    if template is None or template.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail="Template not found or not editable"
        )
    update_data = template_data.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in update_data.items():
        setattr(template, key, value)
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@templates_router.get('/user/templates/{template_id}')
async def get_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> TemplateRead:
    template = session.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.user_id is not None and template.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@templates_router.delete('/user/templates/{template_id}/delete')
async def delete_template(
    current_user: Annotated[User, Depends(get_current_active_user)],
    template_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    template = session.get(Template, template_id)
    if template is None or template.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail="Template not found or not deletable"
        )
    session.delete(template)
    session.commit()
    return {"message": "Template deleted"}


@templates_router.post('/user/templates/{template_id}/instantiate')
async def instantiate_template(
    template_id: uuid.UUID,
    payload: TemplateInstantiate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Goal:
    template = session.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.user_id is not None and template.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")

    start_dt = payload.start_datetime or datetime.now(JST)
    end_dt = _template_duration(template, start_dt, payload.end_datetime)
    goal = _materialize_blueprint(
        session,
        current_user,
        payload.title_override or template.title,
        template.description,
        template.blueprint or {},
        start_dt,
        end_dt,
    )
    session.commit()
    session.refresh(goal)
    return goal
