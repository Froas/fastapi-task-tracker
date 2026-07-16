from datetime import datetime, date as Date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db import get_session
from utils.timezone import JST
from models import (
    Event,
    DailyLog,
    DailyDraftTodo,
    Goal,
    JourneyCharacterId,
    JourneyThemeId,
    MetricDefinition,
    MetricEntry,
    Milestone,
    Note,
    PriorityType,
    StatusType,
    Subtask,
    Task,
    Todo,
    TodoOccurrence,
    User,
    get_current_active_user,
)


backup_router = APIRouter()


class BackupTodo(BaseModel):
    id: str | None = None
    title: str
    description: str | None = ''
    repeat_interval: str | None = None
    due_date: datetime | None = None
    next_due_date: datetime | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: StatusType | None = StatusType.OUTSTANDING
    priority: PriorityType | None = PriorityType.LOW
    task_id: str | None = None
    position: int | None = 0


class BackupSubtask(BaseModel):
    id: str | None = None
    title: str
    description: str | None = ''
    due_date: datetime | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: StatusType | None = StatusType.OUTSTANDING
    priority: PriorityType | None = PriorityType.LOW
    task_id: str | None = None
    position: int | None = 0


class BackupTask(BaseModel):
    id: str | None = None
    title: str
    description: str | None = ''
    due_date: datetime | None = None
    scheduled_date: datetime | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: StatusType | None = StatusType.OUTSTANDING
    priority: PriorityType | None = PriorityType.LOW
    goal_id: str | None = None
    milestone_id: str | None = None
    kind: str | None = 'project'
    scope: str | None = 'milestone'
    position: int | None = 0
    completion_rule: dict | None = None
    todos: list[BackupTodo] = Field(default_factory=list)
    subtasks: list[BackupSubtask] = Field(default_factory=list)


class BackupMilestone(BaseModel):
    id: str | None = None
    title: str
    description: str | None = ''
    due_date: datetime | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: StatusType | None = StatusType.OUTSTANDING
    priority: PriorityType | None = PriorityType.LOW
    goal_id: str | None = None
    position: int | None = 0
    completion_rule: dict | None = None
    tasks: list[BackupTask] = Field(default_factory=list)


class BackupGoal(BaseModel):
    id: str | None = None
    title: str
    description: str | None = ''
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: StatusType | None = StatusType.OUTSTANDING
    priority: PriorityType | None = PriorityType.LOW
    position: int | None = 0
    completion_rule: dict | None = None
    enforce_sequential_milestones: bool = False
    journey_theme_id: JourneyThemeId = JourneyThemeId.MOUNTAIN
    journey_character_id: JourneyCharacterId = JourneyCharacterId.BAT
    tasks: list[BackupTask] = Field(default_factory=list)
    milestones: list[BackupMilestone] = Field(default_factory=list)


class BackupEvent(BaseModel):
    id: str | None = None
    title: str
    description: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    event_type: str | None = None
    location: str | None = None
    recurrence_rule: str | None = None
    status: StatusType | None = StatusType.OUTSTANDING


class BackupDailyLog(BaseModel):
    id: str | None = None
    date: Date
    color: str | None = None
    note: str | None = None
    trigger: str | None = None
    what_helped: str | None = None
    tomorrow_minimum: str | None = None
    finalized_at: datetime | None = None
    finalized_by: str | None = None


class BackupTodoOccurrence(BaseModel):
    id: str | None = None
    date: Date
    status: str | None = 'open'
    value: str | None = None
    note: str | None = None
    completed_at: datetime | None = None
    is_focus: bool | None = False
    todo_id: str | None = None
    daily_log_id: str | None = None


class BackupMetricDefinition(BaseModel):
    id: str | None = None
    name: str
    unit: str | None = None
    input_type: str | None = 'number'
    show_on_today: bool | None = True
    goal_id: str | None = None
    task_id: str | None = None
    position: int | None = 0


class BackupMetricEntry(BaseModel):
    id: str | None = None
    date: Date
    value: str | None = None
    numeric_value: float | None = None
    note: str | None = None
    metric_definition_id: str | None = None
    daily_log_id: str | None = None


class BackupNote(BaseModel):
    id: str | None = None
    title: str
    body: str | None = None
    tag: str | None = None
    pinned: bool = False
    kind: str = "note"
    source: str | None = None
    goal_id: str | None = None
    task_id: str | None = None
    signal_domain: str | None = None
    signal_stake: str | None = None
    signal_decision: str | None = None
    next_action: str | None = None
    review_date: Date | None = None
    deadline: Date | None = None
    outcome: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BackupDailyDraftTodo(BaseModel):
    id: str | None = None
    title: str
    day: Date
    done: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class BackupPayload(BaseModel):
    version: Literal[1]
    exportedAt: str | datetime | None = None
    goals: list[BackupGoal] = Field(default_factory=list)
    milestones: list[BackupMilestone] = Field(default_factory=list)
    tasks: list[BackupTask] = Field(default_factory=list)
    todos: list[BackupTodo] = Field(default_factory=list)
    subtasks: list[BackupSubtask] = Field(default_factory=list)
    events: list[BackupEvent] = Field(default_factory=list)
    daily_logs: list[BackupDailyLog] = Field(default_factory=list)
    todo_occurrences: list[BackupTodoOccurrence] = Field(default_factory=list)
    metric_definitions: list[BackupMetricDefinition] = Field(default_factory=list)
    metric_entries: list[BackupMetricEntry] = Field(default_factory=list)
    notes: list[BackupNote] = Field(default_factory=list)
    daily_draft_todos: list[BackupDailyDraftTodo] = Field(default_factory=list)


def _key(value: object | None) -> str | None:
    return str(value) if value is not None else None


def _status(value: StatusType | None) -> str:
    return (value or StatusType.OUTSTANDING).value


def _priority(value: PriorityType | None) -> str:
    return (value or PriorityType.LOW).value


def _serialize_todo(todo: Todo) -> dict:
    return {
        'id': str(todo.id),
        'title': todo.title,
        'description': todo.description or '',
        'repeat_interval': todo.repeat_interval,
        'due_date': todo.due_date,
        'next_due_date': todo.next_due_date,
        'start_datetime': todo.start_datetime,
        'end_datetime': todo.end_datetime,
        'status': _status(todo.status),
        'priority': _priority(todo.priority),
        'task_id': str(todo.task_id) if todo.task_id else None,
        'position': todo.position or 0,
    }


def _serialize_subtask(subtask: Subtask) -> dict:
    return {
        'id': str(subtask.id),
        'title': subtask.title,
        'description': subtask.description or '',
        'due_date': subtask.due_date,
        'start_datetime': subtask.start_datetime,
        'end_datetime': subtask.end_datetime,
        'status': _status(subtask.status),
        'priority': _priority(subtask.priority),
        'task_id': str(subtask.task_id) if subtask.task_id else None,
        'position': subtask.position or 0,
    }


def _serialize_task(
    task: Task,
    todos_by_task: dict[str, list[dict]],
    subtasks_by_task: dict[str, list[dict]],
) -> dict:
    task_id = str(task.id)
    return {
        'id': task_id,
        'title': task.title,
        'description': task.description or '',
        'due_date': task.due_date,
        'scheduled_date': task.scheduled_date,
        'start_datetime': task.start_datetime,
        'end_datetime': task.end_datetime,
        'status': _status(task.status),
        'priority': _priority(task.priority),
        'goal_id': str(task.goal_id) if task.goal_id else None,
        'milestone_id': str(task.milestone_id) if task.milestone_id else None,
        'kind': task.kind or 'project',
        'scope': task.scope or 'milestone',
        'position': task.position or 0,
        'completion_rule': task.completion_rule,
        'todos': todos_by_task.get(task_id, []),
        'subtasks': subtasks_by_task.get(task_id, []),
    }


def _serialize_milestone(
    milestone: Milestone,
    tasks_by_milestone: dict[str, list[dict]],
) -> dict:
    milestone_id = str(milestone.id)
    return {
        'id': milestone_id,
        'title': milestone.title,
        'description': milestone.description or '',
        'due_date': milestone.due_date,
        'start_datetime': milestone.start_datetime,
        'end_datetime': milestone.end_datetime,
        'status': _status(milestone.status),
        'priority': _priority(milestone.priority),
        'goal_id': str(milestone.goal_id) if milestone.goal_id else None,
        'position': milestone.position or 0,
        'completion_rule': milestone.completion_rule,
        'tasks': tasks_by_milestone.get(milestone_id, []),
    }


def _serialize_goal(
    goal: Goal,
    milestones_by_goal: dict[str, list[dict]],
    tasks_by_goal: dict[str, list[dict]],
) -> dict:
    goal_id = str(goal.id)
    return {
        'id': goal_id,
        'title': goal.title,
        'description': goal.description or '',
        'start_datetime': goal.start_datetime,
        'end_datetime': goal.end_datetime,
        'status': _status(goal.status),
        'priority': _priority(goal.priority),
        'position': goal.position or 0,
        'completion_rule': goal.completion_rule,
        'enforce_sequential_milestones': goal.enforce_sequential_milestones,
        'journey_theme_id': goal.journey_theme_id,
        'journey_character_id': goal.journey_character_id,
        'tasks': tasks_by_goal.get(goal_id, []),
        'milestones': milestones_by_goal.get(goal_id, []),
    }


def _serialize_event(event: Event) -> dict:
    return {
        'id': str(event.id),
        'title': event.title,
        'description': event.description,
        'start_datetime': event.start_datetime,
        'end_datetime': event.end_datetime,
        'event_type': event.event_type,
        'location': event.location,
        'recurrence_rule': event.recurrence_rule,
        'status': _status(event.status),
    }


def _serialize_daily_log(log: DailyLog) -> dict:
    return {
        'id': str(log.id),
        'date': log.date,
        'color': log.color,
        'note': log.note,
        'trigger': log.trigger,
        'what_helped': log.what_helped,
        'tomorrow_minimum': log.tomorrow_minimum,
        'finalized_at': log.finalized_at,
        'finalized_by': log.finalized_by,
    }


def _serialize_todo_occurrence(occurrence: TodoOccurrence) -> dict:
    return {
        'id': str(occurrence.id),
        'date': occurrence.date,
        'status': occurrence.status,
        'value': occurrence.value,
        'note': occurrence.note,
        'completed_at': occurrence.completed_at,
        'is_focus': occurrence.is_focus,
        'todo_id': str(occurrence.todo_id) if occurrence.todo_id else None,
        'daily_log_id': str(occurrence.daily_log_id) if occurrence.daily_log_id else None,
    }


def _serialize_metric_definition(metric: MetricDefinition) -> dict:
    return {
        'id': str(metric.id),
        'name': metric.name,
        'unit': metric.unit,
        'input_type': metric.input_type,
        'show_on_today': metric.show_on_today,
        'goal_id': str(metric.goal_id) if metric.goal_id else None,
        'task_id': str(metric.task_id) if metric.task_id else None,
        'position': metric.position or 0,
    }


def _serialize_metric_entry(entry: MetricEntry) -> dict:
    return {
        'id': str(entry.id),
        'date': entry.date,
        'value': entry.value,
        'numeric_value': entry.numeric_value,
        'note': entry.note,
        'metric_definition_id': str(entry.metric_definition_id) if entry.metric_definition_id else None,
        'daily_log_id': str(entry.daily_log_id) if entry.daily_log_id else None,
    }


def _serialize_note(note: Note) -> dict:
    return {
        'id': str(note.id),
        'title': note.title,
        'body': note.body,
        'tag': note.tag,
        'pinned': note.pinned,
        'kind': note.kind,
        'source': note.source,
        'goal_id': str(note.goal_id) if note.goal_id else None,
        'task_id': str(note.task_id) if note.task_id else None,
        'signal_domain': note.signal_domain,
        'signal_stake': note.signal_stake,
        'signal_decision': note.signal_decision,
        'next_action': note.next_action,
        'review_date': note.review_date,
        'deadline': note.deadline,
        'outcome': note.outcome,
        'resolved_at': note.resolved_at,
        'created_at': note.created_at,
        'updated_at': note.updated_at,
    }


def _serialize_daily_draft_todo(todo: DailyDraftTodo) -> dict:
    return {
        'id': str(todo.id),
        'title': todo.title,
        'day': todo.day,
        'done': todo.done,
        'created_at': todo.created_at,
        'updated_at': todo.updated_at,
        'completed_at': todo.completed_at,
    }


@backup_router.get('/user/backup/export')
async def export_backup(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict:
    goals = session.exec(
        select(Goal)
        .where(Goal.user_id == current_user.id, Goal.deleted_at.is_(None))
        .order_by(Goal.position, Goal.id)
    ).all()
    goal_ids = [goal.id for goal in goals]

    milestones = session.exec(
        select(Milestone)
        .where(
            Milestone.user_id == current_user.id,
            Milestone.deleted_at.is_(None),
            Milestone.goal_id.in_(goal_ids),
        )
        .order_by(Milestone.goal_id, Milestone.position, Milestone.id)
    ).all() if goal_ids else []
    milestone_ids = [milestone.id for milestone in milestones]

    tasks = session.exec(
        select(Task)
        .where(
            Task.user_id == current_user.id,
            Task.deleted_at.is_(None),
            (Task.milestone_id.in_(milestone_ids)) | (Task.goal_id.in_(goal_ids)),
        )
        .order_by(Task.scope, Task.goal_id, Task.milestone_id, Task.position, Task.id)
    ).all() if goal_ids else []
    task_ids = [task.id for task in tasks]

    todos = session.exec(
        select(Todo)
        .where(
            Todo.user_id == current_user.id,
            Todo.deleted_at.is_(None),
            Todo.task_id.in_(task_ids),
        )
        .order_by(Todo.task_id, Todo.position, Todo.id)
    ).all() if task_ids else []

    subtasks = session.exec(
        select(Subtask)
        .where(
            Subtask.user_id == current_user.id,
            Subtask.task_id.in_(task_ids),
        )
        .order_by(Subtask.task_id, Subtask.position, Subtask.id)
    ).all() if task_ids else []

    events = session.exec(
        select(Event)
        .where(Event.user_id == current_user.id, Event.deleted_at.is_(None))
        .order_by(Event.start_datetime, Event.id)
    ).all()

    daily_logs = session.exec(
        select(DailyLog)
        .where(DailyLog.user_id == current_user.id, DailyLog.deleted_at.is_(None))
        .order_by(DailyLog.date, DailyLog.id)
    ).all()
    daily_log_ids = [log.id for log in daily_logs]

    todo_occurrences = session.exec(
        select(TodoOccurrence)
        .where(
            TodoOccurrence.user_id == current_user.id,
            TodoOccurrence.todo_id.in_([todo.id for todo in todos]),
        )
        .order_by(TodoOccurrence.date, TodoOccurrence.id)
    ).all() if todos else []

    metric_definitions = session.exec(
        select(MetricDefinition)
        .where(
            MetricDefinition.user_id == current_user.id,
            MetricDefinition.deleted_at.is_(None),
        )
        .order_by(MetricDefinition.goal_id, MetricDefinition.task_id, MetricDefinition.position, MetricDefinition.id)
    ).all()
    metric_definition_ids = [metric.id for metric in metric_definitions]

    metric_entries = session.exec(
        select(MetricEntry)
        .where(
            MetricEntry.user_id == current_user.id,
            MetricEntry.metric_definition_id.in_(metric_definition_ids),
            MetricEntry.daily_log_id.in_(daily_log_ids),
        )
        .order_by(MetricEntry.date, MetricEntry.id)
    ).all() if metric_definition_ids and daily_log_ids else []

    notes = session.exec(
        select(Note)
        .where(Note.user_id == current_user.id, Note.deleted_at.is_(None))
        .order_by(Note.created_at, Note.id)
    ).all()

    daily_draft_todos = session.exec(
        select(DailyDraftTodo)
        .where(
            DailyDraftTodo.user_id == current_user.id,
            DailyDraftTodo.deleted_at.is_(None),
        )
        .order_by(DailyDraftTodo.day, DailyDraftTodo.created_at, DailyDraftTodo.id)
    ).all()

    todos_by_task: dict[str, list[dict]] = {}
    for todo in todos:
        if todo.task_id:
            todos_by_task.setdefault(str(todo.task_id), []).append(_serialize_todo(todo))

    subtasks_by_task: dict[str, list[dict]] = {}
    for subtask in subtasks:
        if subtask.task_id:
            subtasks_by_task.setdefault(str(subtask.task_id), []).append(_serialize_subtask(subtask))

    serialized_tasks = [
        _serialize_task(task, todos_by_task, subtasks_by_task)
        for task in tasks
    ]
    tasks_by_milestone: dict[str, list[dict]] = {}
    tasks_by_goal: dict[str, list[dict]] = {}
    for task in serialized_tasks:
        milestone_id = task.get('milestone_id')
        if milestone_id:
            tasks_by_milestone.setdefault(milestone_id, []).append(task)
        if task.get('scope') == 'goal':
            goal_id = task.get('goal_id')
            if goal_id:
                tasks_by_goal.setdefault(goal_id, []).append(task)

    serialized_milestones = [
        _serialize_milestone(milestone, tasks_by_milestone)
        for milestone in milestones
    ]
    milestones_by_goal: dict[str, list[dict]] = {}
    for milestone in serialized_milestones:
        goal_id = milestone.get('goal_id')
        if goal_id:
            milestones_by_goal.setdefault(goal_id, []).append(milestone)

    return {
        'version': 1,
        'exportedAt': datetime.utcnow().isoformat() + 'Z',
        'goals': [_serialize_goal(goal, milestones_by_goal, tasks_by_goal) for goal in goals],
        'milestones': serialized_milestones,
        'tasks': serialized_tasks,
        'todos': [_serialize_todo(todo) for todo in todos],
        'subtasks': [_serialize_subtask(subtask) for subtask in subtasks],
        'events': [_serialize_event(event) for event in events],
        'daily_logs': [_serialize_daily_log(log) for log in daily_logs],
        'todo_occurrences': [_serialize_todo_occurrence(occurrence) for occurrence in todo_occurrences],
        'metric_definitions': [_serialize_metric_definition(metric) for metric in metric_definitions],
        'metric_entries': [_serialize_metric_entry(entry) for entry in metric_entries],
        'notes': [_serialize_note(note) for note in notes],
        'daily_draft_todos': [_serialize_daily_draft_todo(todo) for todo in daily_draft_todos],
    }


@backup_router.post('/user/backup/import')
async def import_backup(
    payload: BackupPayload,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict:
    goal_id_map: dict[str, object] = {}
    milestone_id_map: dict[str, object] = {}
    task_id_map: dict[str, object] = {}
    todo_id_map: dict[str, object] = {}
    daily_log_id_map: dict[str, object] = {}
    metric_definition_id_map: dict[str, object] = {}
    imported = {
        'goals': 0,
        'milestones': 0,
        'tasks': 0,
        'todos': 0,
        'subtasks': 0,
        'events': 0,
        'daily_logs': 0,
        'todo_occurrences': 0,
        'metric_definitions': 0,
        'metric_entries': 0,
        'notes': 0,
        'daily_draft_todos': 0,
    }
    skipped = {
        'milestones': 0,
        'tasks': 0,
        'todos': 0,
        'subtasks': 0,
        'todo_occurrences': 0,
        'metric_definitions': 0,
        'metric_entries': 0,
    }
    seen = {
        'goals': set(),
        'milestones': set(),
        'tasks': set(),
        'todos': set(),
        'subtasks': set(),
        'metric_definitions': set(),
        'metric_entries': set(),
        'todo_occurrences': set(),
        'notes': set(),
        'daily_draft_todos': set(),
    }

    def already_seen(kind: str, item_id: str | None) -> bool:
        if item_id is None:
            return False
        if item_id in seen[kind]:
            return True
        seen[kind].add(item_id)
        return False

    def create_todo(todo_data: BackupTodo, parent_task_id: object | None = None) -> None:
        todo_key = _key(todo_data.id)
        if already_seen('todos', todo_key):
            return
        new_task_id = parent_task_id or task_id_map.get(_key(todo_data.task_id) or '')
        if new_task_id is None:
            skipped['todos'] += 1
            return
        todo = Todo(
            title=todo_data.title,
            description=todo_data.description or '',
            repeat_interval=todo_data.repeat_interval,
            due_date=todo_data.due_date,
            next_due_date=todo_data.next_due_date,
            start_datetime=todo_data.start_datetime,
            end_datetime=todo_data.end_datetime,
            status=todo_data.status or StatusType.OUTSTANDING,
            priority=todo_data.priority or PriorityType.LOW,
            task_id=new_task_id,
            position=todo_data.position or 0,
            user_id=current_user.id,
            user=current_user,
        )
        session.add(todo)
        session.flush()
        if todo_key:
            todo_id_map[todo_key] = todo.id
        imported['todos'] += 1

    def create_subtask(subtask_data: BackupSubtask, parent_task_id: object | None = None) -> None:
        subtask_key = _key(subtask_data.id)
        if already_seen('subtasks', subtask_key):
            return
        new_task_id = parent_task_id or task_id_map.get(_key(subtask_data.task_id) or '')
        if new_task_id is None:
            skipped['subtasks'] += 1
            return
        subtask = Subtask(
            title=subtask_data.title,
            description=subtask_data.description or '',
            due_date=subtask_data.due_date,
            start_datetime=subtask_data.start_datetime,
            end_datetime=subtask_data.end_datetime,
            status=subtask_data.status or StatusType.OUTSTANDING,
            priority=subtask_data.priority or PriorityType.LOW,
            task_id=new_task_id,
            position=subtask_data.position or 0,
            user_id=current_user.id,
            user=current_user,
        )
        session.add(subtask)
        session.flush()
        imported['subtasks'] += 1

    def create_task(
        task_data: BackupTask,
        parent_milestone_id: object | None = None,
        parent_goal_id: object | None = None,
    ) -> None:
        task_key = _key(task_data.id)
        if already_seen('tasks', task_key):
            return
        new_scope = (task_data.scope or ('goal' if parent_goal_id and not parent_milestone_id else 'milestone')).lower()
        new_goal_id = parent_goal_id or goal_id_map.get(_key(task_data.goal_id) or '')
        new_milestone_id = parent_milestone_id or milestone_id_map.get(_key(task_data.milestone_id) or '')
        if new_scope == 'milestone' and new_milestone_id is None:
            skipped['tasks'] += 1
            return
        if new_scope == 'goal' and new_goal_id is None:
            skipped['tasks'] += 1
            return
        task = Task(
            title=task_data.title,
            description=task_data.description or '',
            due_date=task_data.due_date,
            scheduled_date=task_data.scheduled_date,
            start_datetime=task_data.start_datetime,
            end_datetime=task_data.end_datetime,
            status=task_data.status or StatusType.OUTSTANDING,
            priority=task_data.priority or PriorityType.LOW,
            goal_id=new_goal_id,
            milestone_id=new_milestone_id if new_scope == 'milestone' else None,
            kind=task_data.kind or 'project',
            scope=new_scope,
            position=task_data.position or 0,
            completion_rule=task_data.completion_rule,
            user_id=current_user.id,
            user=current_user,
        )
        session.add(task)
        session.flush()
        if task_key:
            task_id_map[task_key] = task.id
        imported['tasks'] += 1
        for todo_data in task_data.todos:
            create_todo(todo_data, task.id)
        for subtask_data in task_data.subtasks:
            create_subtask(subtask_data, task.id)

    def create_milestone(milestone_data: BackupMilestone, parent_goal_id: object | None = None) -> None:
        milestone_key = _key(milestone_data.id)
        if already_seen('milestones', milestone_key):
            return
        new_goal_id = parent_goal_id or goal_id_map.get(_key(milestone_data.goal_id) or '')
        if new_goal_id is None:
            skipped['milestones'] += 1
            return
        milestone = Milestone(
            title=milestone_data.title,
            description=milestone_data.description or '',
            due_date=milestone_data.due_date,
            start_datetime=milestone_data.start_datetime,
            end_datetime=milestone_data.end_datetime,
            status=milestone_data.status or StatusType.OUTSTANDING,
            priority=milestone_data.priority or PriorityType.LOW,
            goal_id=new_goal_id,
            position=milestone_data.position or 0,
            completion_rule=milestone_data.completion_rule,
            user_id=current_user.id,
            user=current_user,
        )
        session.add(milestone)
        session.flush()
        if milestone_key:
            milestone_id_map[milestone_key] = milestone.id
        imported['milestones'] += 1
        for task_data in milestone_data.tasks:
            create_task(task_data, milestone.id)

    try:
        for goal_data in payload.goals:
            goal_key = _key(goal_data.id)
            if already_seen('goals', goal_key):
                continue
            goal = Goal(
                title=goal_data.title,
                description=goal_data.description or '',
                start_datetime=goal_data.start_datetime,
                end_datetime=goal_data.end_datetime,
                status=goal_data.status or StatusType.OUTSTANDING,
                priority=goal_data.priority or PriorityType.LOW,
                position=goal_data.position or 0,
                completion_rule=goal_data.completion_rule,
                enforce_sequential_milestones=goal_data.enforce_sequential_milestones,
                journey_theme_id=goal_data.journey_theme_id,
                journey_character_id=goal_data.journey_character_id,
                user_id=current_user.id,
                user=current_user,
            )
            session.add(goal)
            session.flush()
            if goal_key:
                goal_id_map[goal_key] = goal.id
            imported['goals'] += 1
            for task_data in goal_data.tasks:
                create_task(task_data, parent_goal_id=goal.id)
            for milestone_data in goal_data.milestones:
                create_milestone(milestone_data, goal.id)

        for milestone_data in payload.milestones:
            create_milestone(milestone_data)

        for task_data in payload.tasks:
            create_task(task_data)

        for todo_data in payload.todos:
            create_todo(todo_data)

        for subtask_data in payload.subtasks:
            create_subtask(subtask_data)

        for event_data in payload.events:
            event = Event(
                title=event_data.title,
                description=event_data.description,
                start_datetime=event_data.start_datetime,
                end_datetime=event_data.end_datetime,
                event_type=event_data.event_type,
                location=event_data.location,
                recurrence_rule=event_data.recurrence_rule,
                status=event_data.status or StatusType.OUTSTANDING,
                user_id=current_user.id,
                user=current_user,
            )
            session.add(event)
            imported['events'] += 1

        for log_data in payload.daily_logs:
            existing_log = session.exec(
                select(DailyLog)
                .where(DailyLog.user_id == current_user.id)
                .where(DailyLog.deleted_at.is_(None))
                .where(DailyLog.date == log_data.date)
            ).first()
            daily_log = existing_log or DailyLog(
                date=log_data.date,
                user_id=current_user.id,
                user=current_user,
            )
            daily_log.color = log_data.color
            daily_log.note = log_data.note
            daily_log.trigger = log_data.trigger
            daily_log.what_helped = log_data.what_helped
            daily_log.tomorrow_minimum = log_data.tomorrow_minimum
            daily_log.finalized_at = log_data.finalized_at
            daily_log.finalized_by = log_data.finalized_by
            daily_log.updated_at = datetime.now(JST)
            session.add(daily_log)
            session.flush()
            log_key = _key(log_data.id)
            if log_key:
                daily_log_id_map[log_key] = daily_log.id
            imported['daily_logs'] += 1

        for metric_data in payload.metric_definitions:
            metric_key = _key(metric_data.id)
            if already_seen('metric_definitions', metric_key):
                continue
            new_goal_id = goal_id_map.get(_key(metric_data.goal_id) or '') if metric_data.goal_id else None
            new_task_id = task_id_map.get(_key(metric_data.task_id) or '') if metric_data.task_id else None
            if metric_data.goal_id and new_goal_id is None:
                skipped['metric_definitions'] += 1
                continue
            if metric_data.task_id and new_task_id is None:
                skipped['metric_definitions'] += 1
                continue
            metric = MetricDefinition(
                name=metric_data.name,
                unit=metric_data.unit,
                input_type=metric_data.input_type or 'number',
                show_on_today=True if metric_data.show_on_today is None else metric_data.show_on_today,
                goal_id=new_goal_id,
                task_id=new_task_id,
                position=metric_data.position or 0,
                user_id=current_user.id,
                user=current_user,
            )
            session.add(metric)
            session.flush()
            if metric_key:
                metric_definition_id_map[metric_key] = metric.id
            imported['metric_definitions'] += 1

        for occurrence_data in payload.todo_occurrences:
            occurrence_key = _key(occurrence_data.id)
            if already_seen('todo_occurrences', occurrence_key):
                continue
            new_todo_id = todo_id_map.get(_key(occurrence_data.todo_id) or '')
            if new_todo_id is None:
                skipped['todo_occurrences'] += 1
                continue
            new_daily_log_id = daily_log_id_map.get(_key(occurrence_data.daily_log_id) or '') if occurrence_data.daily_log_id else None
            occurrence = TodoOccurrence(
                date=occurrence_data.date,
                status=occurrence_data.status or 'open',
                value=occurrence_data.value,
                note=occurrence_data.note,
                completed_at=occurrence_data.completed_at,
                is_focus=occurrence_data.is_focus or False,
                todo_id=new_todo_id,
                daily_log_id=new_daily_log_id,
                user_id=current_user.id,
                user=current_user,
            )
            session.add(occurrence)
            imported['todo_occurrences'] += 1

        for entry_data in payload.metric_entries:
            entry_key = _key(entry_data.id)
            if already_seen('metric_entries', entry_key):
                continue
            new_metric_definition_id = metric_definition_id_map.get(_key(entry_data.metric_definition_id) or '')
            if new_metric_definition_id is None:
                skipped['metric_entries'] += 1
                continue
            new_daily_log_id = daily_log_id_map.get(_key(entry_data.daily_log_id) or '') if entry_data.daily_log_id else None
            entry = MetricEntry(
                date=entry_data.date,
                value=entry_data.value,
                numeric_value=entry_data.numeric_value,
                note=entry_data.note,
                metric_definition_id=new_metric_definition_id,
                daily_log_id=new_daily_log_id,
                user_id=current_user.id,
                user=current_user,
            )
            session.add(entry)
            imported['metric_entries'] += 1

        for note_data in payload.notes:
            note_key = _key(note_data.id)
            if already_seen('notes', note_key):
                continue
            note = Note(
                title=note_data.title,
                body=note_data.body,
                tag=note_data.tag,
                pinned=note_data.pinned,
                kind=note_data.kind,
                source=note_data.source,
                goal_id=goal_id_map.get(note_data.goal_id or ''),
                task_id=task_id_map.get(note_data.task_id or ''),
                signal_domain=note_data.signal_domain,
                signal_stake=note_data.signal_stake,
                signal_decision=note_data.signal_decision,
                next_action=note_data.next_action,
                review_date=note_data.review_date,
                deadline=note_data.deadline,
                outcome=note_data.outcome,
                resolved_at=note_data.resolved_at,
                created_at=note_data.created_at or datetime.now(JST),
                updated_at=note_data.updated_at or datetime.now(JST),
                user_id=current_user.id,
                user=current_user,
            )
            session.add(note)
            imported['notes'] += 1

        for draft_data in payload.daily_draft_todos:
            draft_key = _key(draft_data.id)
            if already_seen('daily_draft_todos', draft_key):
                continue
            draft = DailyDraftTodo(
                title=draft_data.title,
                day=draft_data.day,
                done=draft_data.done,
                created_at=draft_data.created_at or datetime.now(JST),
                updated_at=draft_data.updated_at or datetime.now(JST),
                completed_at=draft_data.completed_at,
                user_id=current_user.id,
                user=current_user,
            )
            session.add(draft)
            imported['daily_draft_todos'] += 1

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        'message': 'Backup imported',
        'imported': imported,
        'skipped': skipped,
    }
