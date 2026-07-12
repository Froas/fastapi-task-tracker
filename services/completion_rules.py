from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterable
import uuid

from sqlmodel import Session, select

from models import (
    Goal,
    MetricDefinition,
    MetricEntry,
    Milestone,
    StatusType,
    Subtask,
    Task,
    Todo,
    TodoOccurrence,
)
from utils.timezone import JST
from datetime import datetime


COMPLETED_OCCURRENCE_STATUSES = {"done", "minimum"}
TERMINAL_STATUSES = {
    StatusType.FINISHED,
    StatusType.CLOSED,
    StatusType.ABORTED,
    StatusType.CANCELLED,
}


@dataclass(frozen=True)
class RuleResult:
    progress: float | None
    satisfied: bool
    evaluable: bool
    rule: dict[str, Any] | None


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))


def _is_finished(status: StatusType | None) -> bool:
    return status in {StatusType.FINISHED, StatusType.CLOSED}


def _active_tasks_for_milestone(session: Session, milestone_id: uuid.UUID) -> list[Task]:
    return list(session.exec(
        select(Task).where(
            Task.milestone_id == milestone_id,
            Task.deleted_at.is_(None),
        ).order_by(Task.position, Task.id)
    ).all())


def _active_milestones_for_goal(session: Session, goal_id: uuid.UUID) -> list[Milestone]:
    return list(session.exec(
        select(Milestone).where(
            Milestone.goal_id == goal_id,
            Milestone.deleted_at.is_(None),
        ).order_by(Milestone.position, Milestone.id)
    ).all())


def _goal_tasks(session: Session, goal_id: uuid.UUID) -> list[Task]:
    return list(session.exec(
        select(Task).where(
            Task.goal_id == goal_id,
            Task.scope == "goal",
            Task.deleted_at.is_(None),
        ).order_by(Task.position, Task.id)
    ).all())


def _task_subtasks(session: Session, task_id: uuid.UUID) -> list[Subtask]:
    return list(session.exec(
        select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.position, Subtask.id)
    ).all())


def _task_ids_for_entity(session: Session, entity: Goal | Milestone | Task) -> list[uuid.UUID]:
    if isinstance(entity, Task):
        return [entity.id]
    if isinstance(entity, Milestone):
        return [task.id for task in _active_tasks_for_milestone(session, entity.id)]
    milestone_ids = [milestone.id for milestone in _active_milestones_for_goal(session, entity.id)]
    milestone_task_ids = list(session.exec(
        select(Task.id).where(
            Task.milestone_id.in_(milestone_ids),
            Task.deleted_at.is_(None),
        )
    ).all()) if milestone_ids else []
    return [task.id for task in _goal_tasks(session, entity.id)] + milestone_task_ids


def _structural_progress(session: Session, entity: Goal | Milestone | Task) -> tuple[float | None, bool]:
    if isinstance(entity, Task):
        subtasks = _task_subtasks(session, entity.id)
        if not subtasks:
            return (100.0 if _is_finished(entity.status) else None), False
        finished = sum(_is_finished(subtask.status) for subtask in subtasks)
        return (finished / len(subtasks)) * 100.0, True

    if isinstance(entity, Milestone):
        tasks = [task for task in _active_tasks_for_milestone(session, entity.id) if task.kind != "routine"]
        if not tasks:
            return (100.0 if _is_finished(entity.status) else None), False
        finished = sum(_is_finished(task.status) for task in tasks)
        return (finished / len(tasks)) * 100.0, True

    milestones = _active_milestones_for_goal(session, entity.id)
    tasks = [task for task in _goal_tasks(session, entity.id) if task.kind != "routine"]
    units: list[Goal | Milestone | Task] = [*milestones, *tasks]
    if not units:
        return (100.0 if _is_finished(entity.status) else None), False
    finished = sum(_is_finished(unit.status) for unit in units)
    return (finished / len(units)) * 100.0, True


def _metric_definitions(session: Session, entity: Goal | Milestone | Task) -> list[MetricDefinition]:
    task_ids = _task_ids_for_entity(session, entity)
    statement = select(MetricDefinition).where(MetricDefinition.deleted_at.is_(None))
    if isinstance(entity, Goal):
        statement = statement.where(MetricDefinition.goal_id == entity.id)
    elif isinstance(entity, Task):
        statement = statement.where(MetricDefinition.task_id == entity.id)
    elif task_ids:
        statement = statement.where(MetricDefinition.task_id.in_(task_ids))
    else:
        return []
    return list(session.exec(statement.order_by(MetricDefinition.position, MetricDefinition.id)).all())


def _metric_progress(
    session: Session,
    entity: Goal | Milestone | Task,
    rule: dict[str, Any],
) -> tuple[float | None, bool, dict[str, Any]]:
    definitions = _metric_definitions(session, entity)
    metric_id = rule.get("metric_definition_id")
    metric_name = str(rule.get("metric_name") or "").strip().casefold()
    definition = next((item for item in definitions if metric_id and str(item.id) == str(metric_id)), None)
    if definition is None and metric_name:
        definition = next((item for item in definitions if item.name.strip().casefold() == metric_name), None)
    if definition is None:
        return None, False, rule

    entry = session.exec(
        select(MetricEntry).where(
            MetricEntry.metric_definition_id == definition.id,
            MetricEntry.user_id == definition.user_id,
        ).order_by(MetricEntry.date.desc(), MetricEntry.updated_at.desc(), MetricEntry.id.desc())
    ).first()
    current = entry.numeric_value if entry and entry.numeric_value is not None else rule.get("current_value")
    target = rule.get("target_value")
    start = rule.get("start_value")
    if current is None or target is None:
        return None, False, {**rule, "metric_definition_id": str(definition.id), "metric_name": definition.name}

    current_value = float(current)
    target_value = float(target)
    direction = rule.get("direction") or "at_least"
    if direction == "at_least":
        progress = 100.0 if target_value <= 0 and current_value >= target_value else _clamp((current_value / target_value) * 100.0) if target_value else 0.0
        satisfied = current_value >= target_value
    elif direction == "at_most":
        progress = 100.0 if current_value <= target_value else _clamp((target_value / current_value) * 100.0) if current_value else 100.0
        satisfied = current_value <= target_value
    else:
        if start is None or float(start) == target_value:
            return None, False, {**rule, "current_value": current_value}
        start_value = float(start)
        if direction == "decrease":
            progress = _clamp(((start_value - current_value) / (start_value - target_value)) * 100.0)
            satisfied = current_value <= target_value
        else:
            progress = _clamp(((current_value - start_value) / (target_value - start_value)) * 100.0)
            satisfied = current_value >= target_value
    return progress, satisfied, {
        **rule,
        "metric_definition_id": str(definition.id),
        "metric_name": definition.name,
        "current_value": current_value,
    }


def _todo_ids_for_entity(session: Session, entity: Goal | Milestone | Task) -> list[uuid.UUID]:
    task_ids = _task_ids_for_entity(session, entity)
    if not task_ids:
        return []
    return list(session.exec(
        select(Todo.id).where(
            Todo.task_id.in_(task_ids),
            Todo.deleted_at.is_(None),
            Todo.repeat_interval.isnot(None),
        )
    ).all())


def _consistency_progress(
    session: Session,
    entity: Goal | Milestone | Task,
    rule: dict[str, Any],
) -> tuple[float | None, bool, dict[str, Any]]:
    required = int(rule.get("required_done") or 0)
    if required <= 0:
        return None, False, rule
    window_days = max(1, int(rule.get("window_days") or 7))
    todo_ids = _todo_ids_for_entity(session, entity)
    if not todo_ids:
        return 0.0, False, {**rule, "current_done": 0, "window_days": window_days}
    today = datetime.now(JST).date()
    start_date = today - timedelta(days=window_days - 1)
    occurrences = session.exec(
        select(TodoOccurrence).where(
            TodoOccurrence.todo_id.in_(todo_ids),
            TodoOccurrence.date >= start_date,
            TodoOccurrence.date <= today,
        )
    ).all()
    current = sum(item.status in COMPLETED_OCCURRENCE_STATUSES for item in occurrences)
    return _clamp((current / required) * 100.0), current >= required, {
        **rule,
        "current_done": current,
        "window_days": window_days,
    }


def _weighted_progress(parts: Iterable[tuple[float | None, float]]) -> tuple[float | None, bool]:
    weighted = [(value, weight) for value, weight in parts if weight > 0]
    if not weighted:
        return None, False
    weight_total = sum(weight for _, weight in weighted)
    progress = sum((value or 0.0) * weight for value, weight in weighted) / weight_total
    fully_configured = all(value is not None for value, _ in weighted)
    return progress, fully_configured and progress >= 99.999


def evaluate_rule(session: Session, entity: Goal | Milestone | Task) -> RuleResult:
    raw_rule = getattr(entity, "completion_rule", None)
    rule = dict(raw_rule) if raw_rule else {"type": "structural"}
    rule_type = rule.get("type") or "structural"

    if rule_type == "metric_target":
        progress, satisfied, next_rule = _metric_progress(session, entity, rule)
        return RuleResult(progress, satisfied, progress is not None, next_rule)
    if rule_type == "consistency":
        progress, satisfied, next_rule = _consistency_progress(session, entity, rule)
        return RuleResult(progress, satisfied, progress is not None, next_rule)
    if rule_type == "hybrid":
        structural, structural_evaluable = _structural_progress(session, entity)
        outcome_rule = rule.get("outcome") or rule.get("outcome_rule")
        consistency_rule = rule.get("consistency") or rule.get("consistency_rule")
        outcome, _, next_outcome = _metric_progress(session, entity, outcome_rule) if isinstance(outcome_rule, dict) else (None, False, None)
        consistency, _, next_consistency = _consistency_progress(session, entity, consistency_rule) if isinstance(consistency_rule, dict) else (None, False, None)
        progress, satisfied = _weighted_progress([
            (structural if structural_evaluable else None, float(rule.get("structural_weight") or 0)),
            (outcome, float(rule.get("outcome_weight") or 0)),
            (consistency, float(rule.get("consistency_weight") or 0)),
        ])
        next_rule = dict(rule)
        if next_outcome is not None:
            next_rule["outcome"] = next_outcome
        if next_consistency is not None:
            next_rule["consistency"] = next_consistency
        next_rule["current_progress"] = progress
        return RuleResult(progress, satisfied, progress is not None, next_rule)

    progress, evaluable = _structural_progress(session, entity)
    return RuleResult(progress, bool(evaluable and progress is not None and progress >= 99.999), evaluable, rule)


def _apply_result(session: Session, entity: Goal | Milestone | Task) -> RuleResult:
    result = evaluate_rule(session, entity)
    next_rule = dict(result.rule or {"type": "structural"})
    if result.satisfied and entity.status not in TERMINAL_STATUSES:
        entity.status = StatusType.FINISHED
        next_rule["auto_completed"] = True
        session.add(entity)
    elif not result.satisfied and next_rule.get("auto_completed") and entity.status == StatusType.FINISHED:
        entity.status = StatusType.IN_PROGRESS
        next_rule["auto_completed"] = False
        session.add(entity)
    if next_rule != getattr(entity, "completion_rule", None):
        entity.completion_rule = next_rule
        session.add(entity)
    return result


def recalculate_task_hierarchy(session: Session, task_id: uuid.UUID | None) -> None:
    if task_id is None:
        return
    task = session.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        return
    _apply_result(session, task)
    milestone = session.get(Milestone, task.milestone_id) if task.milestone_id else None
    if milestone is not None and milestone.deleted_at is None:
        _apply_result(session, milestone)
    goal_id = task.goal_id or (milestone.goal_id if milestone else None)
    goal = session.get(Goal, goal_id) if goal_id else None
    if goal is not None and goal.deleted_at is None:
        _apply_result(session, goal)


def recalculate_goal_hierarchy(session: Session, goal_id: uuid.UUID | None) -> None:
    if goal_id is None:
        return
    goal = session.get(Goal, goal_id)
    if goal is None or goal.deleted_at is not None:
        return
    for milestone in _active_milestones_for_goal(session, goal.id):
        for task in _active_tasks_for_milestone(session, milestone.id):
            _apply_result(session, task)
        _apply_result(session, milestone)
    for task in _goal_tasks(session, goal.id):
        _apply_result(session, task)
    _apply_result(session, goal)


def recalculate_for_occurrence(session: Session, occurrence: TodoOccurrence) -> None:
    todo = session.get(Todo, occurrence.todo_id)
    recalculate_task_hierarchy(session, todo.task_id if todo else None)


def recalculate_for_metric(session: Session, metric: MetricDefinition) -> None:
    if metric.task_id:
        recalculate_task_hierarchy(session, metric.task_id)
    else:
        recalculate_goal_hierarchy(session, metric.goal_id)
