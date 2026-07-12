from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session, delete, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from db import engine
from models import (
    DailyDraftTodo,
    DailyLog,
    Event,
    Goal,
    MetricDefinition,
    MetricEntry,
    Milestone,
    Note,
    PriorityType,
    StatusType,
    Subtask,
    Tag,
    Task,
    Todo,
    TodoOccurrence,
    User,
)
from routers.visibility import active_recurring_todo_ids
from utils.timezone import JST


engine.echo = False


def now_at(days: int = 0, hour: int = 9, minute: int = 0) -> datetime:
    current = datetime.now(JST) + timedelta(days=days)
    return current.replace(hour=hour, minute=minute, second=0, microsecond=0)


def backup_db() -> Path | None:
    db_path = BACKEND_ROOT / 'db.sqlite'
    if not db_path.exists():
        return None
    backup_dir = BACKEND_ROOT / 'backups'
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(JST).strftime('%Y%m%d-%H%M%S')
    backup_path = backup_dir / f'db-before-demo-reset-{timestamp}.sqlite'
    shutil.copy2(db_path, backup_path)
    return backup_path


def product_models_in_delete_order() -> tuple[Any, ...]:
    return (
        TodoOccurrence,
        MetricEntry,
        MetricDefinition,
        DailyLog,
        DailyDraftTodo,
        Note,
        Tag,
        Event,
        Todo,
        Subtask,
        Task,
        Milestone,
        Goal,
    )


def reset_product_data(session: Session, users: list[User]) -> dict[str, int]:
    user_ids = [user.id for user in users]
    deleted: dict[str, int] = {}

    for model in product_models_in_delete_order():
        result = session.exec(delete(model).where(model.user_id.in_(user_ids)))
        deleted[model.__name__] = result.rowcount or 0

    session.flush()
    return deleted


def add_goal(
    session: Session,
    user: User,
    title: str,
    description: str,
    status: StatusType,
    priority: PriorityType,
    position: int,
    duration_days: int,
) -> Goal:
    goal = Goal(
        title=title,
        description=description,
        start_datetime=now_at(0),
        end_datetime=now_at(duration_days),
        status=status,
        priority=priority,
        position=position,
        user_id=user.id,
    )
    session.add(goal)
    session.flush()
    return goal


def add_milestone(
    session: Session,
    user: User,
    goal: Goal,
    title: str,
    description: str,
    status: StatusType,
    priority: PriorityType,
    position: int,
    due_days: int,
) -> Milestone:
    milestone = Milestone(
        title=title,
        description=description,
        due_date=now_at(due_days),
        start_datetime=now_at(0),
        status=status,
        priority=priority,
        goal_id=goal.id,
        position=position,
        user_id=user.id,
    )
    session.add(milestone)
    session.flush()
    return milestone


def add_task(
    session: Session,
    user: User,
    goal: Goal,
    title: str,
    description: str,
    kind: str,
    scope: str,
    position: int,
    milestone: Milestone | None = None,
    status: StatusType = StatusType.OUTSTANDING,
    priority: PriorityType = PriorityType.MEDIUM,
    due_days: int | None = None,
    scheduled_days: int | None = None,
) -> Task:
    task = Task(
        title=title,
        description=description,
        due_date=now_at(due_days) if due_days is not None else None,
        scheduled_date=now_at(scheduled_days) if scheduled_days is not None else None,
        start_datetime=now_at(0),
        status=status,
        priority=priority,
        goal_id=goal.id,
        milestone_id=milestone.id if milestone else None,
        kind=kind,
        scope=scope,
        position=position,
        user_id=user.id,
    )
    session.add(task)
    session.flush()
    return task


def add_subtask(
    session: Session,
    user: User,
    task: Task,
    title: str,
    position: int,
    status: StatusType = StatusType.OUTSTANDING,
    due_days: int | None = None,
) -> Subtask:
    subtask = Subtask(
        title=title,
        description='',
        due_date=now_at(due_days) if due_days is not None else task.due_date,
        start_datetime=now_at(0),
        status=status,
        priority=task.priority or PriorityType.MEDIUM,
        task_id=task.id,
        position=position,
        user_id=user.id,
    )
    session.add(subtask)
    session.flush()
    return subtask


def add_todo_definition(
    session: Session,
    user: User,
    task: Task,
    title: str,
    position: int,
    repeat_interval: str = 'daily',
    priority: PriorityType = PriorityType.MEDIUM,
) -> Todo:
    todo = Todo(
        title=title,
        description='Recurring definition. Daily facts live in TodoOccurrence.',
        repeat_interval=repeat_interval,
        due_date=None,
        next_due_date=now_at(0),
        start_datetime=now_at(0),
        status=StatusType.OUTSTANDING,
        priority=priority,
        task_id=task.id,
        position=position,
        user_id=user.id,
    )
    session.add(todo)
    session.flush()
    return todo


def add_metric_definition(
    session: Session,
    user: User,
    goal: Goal,
    name: str,
    unit: str | None,
    position: int,
    task: Task | None = None,
    show_on_today: bool = True,
    input_type: str = 'number',
) -> MetricDefinition:
    metric = MetricDefinition(
        name=name,
        unit=unit,
        input_type=input_type,
        show_on_today=show_on_today,
        goal_id=goal.id,
        task_id=task.id if task else None,
        position=position,
        user_id=user.id,
    )
    session.add(metric)
    session.flush()
    return metric


def add_metric_entry(
    session: Session,
    user: User,
    daily_log: DailyLog,
    metric: MetricDefinition,
    value: str,
    numeric_value: float | None,
) -> MetricEntry:
    entry = MetricEntry(
        date=daily_log.date,
        value=value,
        numeric_value=numeric_value,
        metric_definition_id=metric.id,
        daily_log_id=daily_log.id,
        user_id=user.id,
    )
    session.add(entry)
    session.flush()
    return entry


def add_note(
    session: Session,
    user: User,
    title: str,
    body: str,
    tag: str,
    pinned: bool = False,
) -> Note:
    note = Note(
        title=title,
        body=body,
        tag=tag,
        pinned=pinned,
        user_id=user.id,
    )
    session.add(note)
    session.flush()
    return note


def seed_weight_loss(session: Session, user: User, daily_log: DailyLog) -> None:
    goal = add_goal(
        session,
        user,
        'Weight Loss 105 → 90',
        'Metric-based mountain: lose weight without turning Today into a guilt spreadsheet.',
        StatusType.STARTED,
        PriorityType.HIGH,
        0,
        120,
    )

    nutrition = add_task(
        session,
        user,
        goal,
        'Daily Nutrition',
        'Goal-scope routine: food truth, protein, water.',
        'routine',
        'goal',
        0,
        status=StatusType.STARTED,
        priority=PriorityType.HIGH,
    )
    add_todo_definition(session, user, nutrition, 'Track food', 0, priority=PriorityType.HIGH)
    add_todo_definition(session, user, nutrition, 'Hit protein target', 1)
    add_todo_definition(session, user, nutrition, 'Drink 2L water', 2)

    movement = add_task(
        session,
        user,
        goal,
        'Daily Movement',
        'Goal-scope routine: steps and light movement.',
        'routine',
        'goal',
        1,
        status=StatusType.STARTED,
    )
    add_todo_definition(session, user, movement, '10k steps', 0)
    add_todo_definition(session, user, movement, '20 minute walk', 1)

    first_cut = add_milestone(
        session,
        user,
        goal,
        '105 → 100 kg',
        'First cut: set the system and collect honest data.',
        StatusType.STARTED,
        PriorityType.HIGH,
        0,
        30,
    )
    setup = add_task(
        session,
        user,
        goal,
        'Setup nutrition system',
        'One-off setup work belongs in subtasks.',
        'project',
        'milestone',
        0,
        milestone=first_cut,
        priority=PriorityType.HIGH,
        due_days=0,
        scheduled_days=0,
    )
    add_subtask(session, user, setup, 'Calculate calorie target', 0, StatusType.FINISHED)
    add_subtask(session, user, setup, 'Define protein target', 1)
    add_subtask(session, user, setup, 'Create basic meals list', 2)

    challenge = add_task(
        session,
        user,
        goal,
        '14 days honest tracking',
        'Milestone-scope challenge with recurring definitions.',
        'challenge',
        'milestone',
        1,
        milestone=first_cut,
        status=StatusType.STARTED,
        priority=PriorityType.HIGH,
        due_days=14,
    )
    add_todo_definition(session, user, challenge, 'Track food daily', 0, priority=PriorityType.HIGH)
    add_todo_definition(session, user, challenge, 'Log morning weight', 1)
    add_subtask(session, user, challenge, 'Install/update food tracker', 0, StatusType.FINISHED)
    add_subtask(session, user, challenge, 'Choose weigh-in place', 1)

    add_milestone(
        session,
        user,
        goal,
        '100 → 95 kg',
        'Second cut: reduce variance and keep adherence high.',
        StatusType.OUTSTANDING,
        PriorityType.MEDIUM,
        1,
        75,
    )

    weight = add_metric_definition(session, user, goal, 'Weight', 'kg', 0)
    steps = add_metric_definition(session, user, goal, 'Steps', 'steps', 1)
    calories = add_metric_definition(session, user, goal, 'Calories', 'kcal', 0, task=nutrition)
    protein = add_metric_definition(session, user, goal, 'Protein', 'g', 1, task=nutrition)
    add_metric_entry(session, user, daily_log, weight, '103.8', 103.8)
    add_metric_entry(session, user, daily_log, steps, '8200', 8200)
    add_metric_entry(session, user, daily_log, calories, '2100', 2100)
    add_metric_entry(session, user, daily_log, protein, '118', 118)


def seed_recovery_os(session: Session, user: User, daily_log: DailyLog) -> None:
    goal = add_goal(
        session,
        user,
        'Recovery OS',
        'Protect sleep, shutdown, and nervous-system recovery.',
        StatusType.STARTED,
        PriorityType.HIGH,
        1,
        90,
    )

    evening = add_task(
        session,
        user,
        goal,
        'Evening Shutdown',
        'Goal-scope routine for low-friction recovery.',
        'routine',
        'goal',
        0,
        status=StatusType.STARTED,
        priority=PriorityType.HIGH,
    )
    add_todo_definition(session, user, evening, 'Phone outside bedroom', 0, priority=PriorityType.HIGH)
    add_todo_definition(session, user, evening, 'Screen off 30 minutes before sleep', 1)
    add_todo_definition(session, user, evening, 'Write shutdown note', 2)

    morning = add_task(
        session,
        user,
        goal,
        'Morning Recovery',
        'Small morning checks that make the day less random.',
        'routine',
        'goal',
        1,
        status=StatusType.STARTED,
    )
    add_todo_definition(session, user, morning, 'Morning light', 0)
    add_todo_definition(session, user, morning, 'Quick body scan', 1)

    baseline = add_milestone(
        session,
        user,
        goal,
        'Stabilize sleep baseline',
        'Get seven nights of decent recovery signal.',
        StatusType.STARTED,
        PriorityType.HIGH,
        0,
        21,
    )
    environment = add_task(
        session,
        user,
        goal,
        'Design sleep environment',
        'One-off setup for easier nights.',
        'project',
        'milestone',
        0,
        milestone=baseline,
        due_days=-1,
        scheduled_days=-1,
    )
    add_subtask(session, user, environment, 'Clear bedside clutter', 0, StatusType.FINISHED)
    add_subtask(session, user, environment, 'Prepare charger outside bedroom', 1)
    add_subtask(session, user, environment, 'Set recurring wind-down alarm', 2)

    shutdown_challenge = add_task(
        session,
        user,
        goal,
        '7 night shutdown challenge',
        'Milestone-scope routine challenge.',
        'challenge',
        'milestone',
        1,
        milestone=baseline,
        status=StatusType.STARTED,
        due_days=7,
    )
    add_todo_definition(session, user, shutdown_challenge, 'Do shutdown checklist', 0)
    add_todo_definition(session, user, shutdown_challenge, 'Log sleep quality', 1)
    add_subtask(session, user, shutdown_challenge, 'Write minimum viable shutdown', 0)

    sleep = add_metric_definition(session, user, goal, 'Sleep', 'hours', 0)
    mood = add_metric_definition(session, user, goal, 'Mood', '/10', 1)
    sleep_quality = add_metric_definition(session, user, goal, 'Sleep quality', '/10', 0, task=shutdown_challenge)
    add_metric_entry(session, user, daily_log, sleep, '6.5', 6.5)
    add_metric_entry(session, user, daily_log, mood, '6', 6)
    add_metric_entry(session, user, daily_log, sleep_quality, '5', 5)

    session.add(Event(
        title='Evening shutdown window',
        description='Seeded calendar item for Recovery OS.',
        start_datetime=now_at(0, 21, 30),
        end_datetime=now_at(0, 22, 0),
        event_type='routine',
        location='home',
        status=StatusType.OUTSTANDING,
        user_id=user.id,
    ))
    session.flush()


def seed_tracker_mvp(session: Session, user: User, daily_log: DailyLog) -> None:
    goal = add_goal(
        session,
        user,
        'Tracker MVP',
        'Make the web MVP reliable before mobile/integrations.',
        StatusType.IN_PROGRESS,
        PriorityType.HIGH,
        2,
        45,
    )

    build_loop = add_task(
        session,
        user,
        goal,
        'Build Loop',
        'Goal-scope routine to keep the project shipping.',
        'routine',
        'goal',
        0,
        status=StatusType.STARTED,
        priority=PriorityType.HIGH,
    )
    add_todo_definition(session, user, build_loop, 'Ship one visible improvement', 0, priority=PriorityType.HIGH)
    add_todo_definition(session, user, build_loop, 'Write tomorrow slice', 1)
    add_todo_definition(session, user, build_loop, 'Update architecture notes', 2)

    today_foundation = add_milestone(
        session,
        user,
        goal,
        'Today foundation',
        'Today is composition; DailyLog is truth underneath.',
        StatusType.STARTED,
        PriorityType.HIGH,
        0,
        10,
    )
    rules = add_task(
        session,
        user,
        goal,
        'Implement TodoOccurrence rules',
        'Only recurring active todos generate dated occurrences.',
        'project',
        'milestone',
        0,
        milestone=today_foundation,
        status=StatusType.STARTED,
        priority=PriorityType.HIGH,
        due_days=-1,
        scheduled_days=-1,
    )
    add_subtask(session, user, rules, 'Filter to repeat_interval definitions', 0, StatusType.FINISHED)
    add_subtask(session, user, rules, 'Exclude inactive milestone tasks', 1, StatusType.FINISHED)
    add_subtask(session, user, rules, 'Add regression test for occurrence scope', 2)

    ui_cleanup = add_task(
        session,
        user,
        goal,
        'Today dashboard UI cleanup',
        'Group due work, routines, and metrics inside goal cards.',
        'project',
        'milestone',
        1,
        milestone=today_foundation,
        priority=PriorityType.HIGH,
        due_days=0,
        scheduled_days=0,
    )
    add_subtask(session, user, ui_cleanup, 'Move overdue into goal cards', 0)
    add_subtask(session, user, ui_cleanup, 'Add compact global summary', 1)
    add_subtask(session, user, ui_cleanup, 'Keep End Day as modal', 2)

    audit = add_milestone(
        session,
        user,
        goal,
        'Persistence audit',
        'Every button must survive refresh.',
        StatusType.OUTSTANDING,
        PriorityType.HIGH,
        1,
        21,
    )
    persistence = add_task(
        session,
        user,
        goal,
        'Audit create/update/delete flows',
        'Find buttons that only change local state.',
        'project',
        'milestone',
        0,
        milestone=audit,
        due_days=3,
    )
    add_subtask(session, user, persistence, 'Milestone delete persists', 0)
    add_subtask(session, user, persistence, 'Todo toggle persists', 1)
    add_subtask(session, user, persistence, 'Inline date edit persists', 2)

    coding = add_metric_definition(session, user, goal, 'Coding minutes', 'min', 0)
    bugs = add_metric_definition(session, user, goal, 'Bugs closed', 'bugs', 1)
    add_metric_entry(session, user, daily_log, coding, '45', 45)
    add_metric_entry(session, user, daily_log, bugs, '2', 2)


def seed_professional_radar(session: Session, user: User) -> None:
    goal = add_goal(
        session,
        user,
        'Professional Radar',
        'Parked feature seed: capture signals, connect dots, review later.',
        StatusType.CLOSED,
        PriorityType.MEDIUM,
        3,
        120,
    )

    capture = add_task(
        session,
        user,
        goal,
        'Signal Capture Loop',
        'When Signal model lands, this becomes first-class Radar data.',
        'routine',
        'goal',
        0,
        status=StatusType.CLOSED,
        priority=PriorityType.MEDIUM,
    )
    add_todo_definition(session, user, capture, 'Capture one professional signal', 0)
    add_metric_definition(session, user, goal, 'Signals captured', 'signals', 0, show_on_today=False)

    scan = add_milestone(
        session,
        user,
        goal,
        'First weekly scan',
        'Review weak signals and choose one experiment.',
        StatusType.CLOSED,
        PriorityType.MEDIUM,
        0,
        30,
    )
    radar_task = add_task(
        session,
        user,
        goal,
        'Define Radar MVP',
        'Shape the feature before implementing it.',
        'project',
        'milestone',
        0,
        milestone=scan,
        status=StatusType.CLOSED,
    )
    add_subtask(session, user, radar_task, 'Define Signal fields', 0)
    add_subtask(session, user, radar_task, 'Define review cadence', 1)

    add_note(
        session,
        user,
        'Radar signals inbox',
        'Temporary note until Signal becomes a real model: odd market asks, repeated bugs, career opportunities, strong user reactions.',
        'radar',
        pinned=True,
    )


def seed_drafts_and_notes(session: Session, user: User) -> None:
    today = datetime.now(JST).date()
    drafts = (
        ('Buy groceries after work', False),
        ('Reply to one important message', False),
        ('Sketch navbar cleanup idea', True),
    )
    for title, done in drafts:
        draft = DailyDraftTodo(
            title=title,
            day=today,
            done=done,
            completed_at=datetime.now(JST) if done else None,
            user_id=user.id,
        )
        session.add(draft)

    add_note(
        session,
        user,
        'Today dashboard rule',
        'Today is the main day view. DailyLog is the truth record. Recurring TodoDefinitions create TodoOccurrences; one-off work is Subtask.',
        'architecture',
        pinned=True,
    )


def seed_occurrences(session: Session, user: User, daily_log: DailyLog) -> int:
    todos = session.exec(
        select(Todo)
        .where(Todo.id.in_(active_recurring_todo_ids(user.id)))
        .order_by(Todo.task_id, Todo.position, Todo.title)
    ).all()
    done_titles = {
        'Track food',
        '10k steps',
        'Morning light',
        'Ship one visible improvement',
        'Update architecture notes',
    }
    minimum_titles = {
        'Hit protein target',
        'Write shutdown note',
    }

    for todo in todos:
        status = 'done' if todo.title in done_titles else 'minimum' if todo.title in minimum_titles else 'open'
        occurrence = TodoOccurrence(
            date=daily_log.date,
            status=status,
            completed_at=datetime.now(JST) if status in {'done', 'minimum'} else None,
            todo_id=todo.id,
            daily_log_id=daily_log.id,
            user_id=user.id,
        )
        session.add(occurrence)

    session.flush()
    return len(todos)


def seed_clean_demo(session: Session, user: User) -> dict[str, int]:
    daily_log = DailyLog(
        date=datetime.now(JST).date(),
        color=None,
        note='Seeded Today dashboard: check routines, enter metrics, end day later.',
        user_id=user.id,
    )
    session.add(daily_log)
    session.flush()

    seed_weight_loss(session, user, daily_log)
    seed_recovery_os(session, user, daily_log)
    seed_tracker_mvp(session, user, daily_log)
    seed_professional_radar(session, user)
    seed_drafts_and_notes(session, user)
    occurrences = seed_occurrences(session, user, daily_log)

    return {
        'occurrences': occurrences,
    }


def choose_users(session: Session, username: str, reset_all_users: bool) -> tuple[list[User], User]:
    all_users = session.exec(select(User).order_by(User.username)).all()
    if not all_users:
        raise SystemExit('No users found. Create/login a user first; reset keeps users/auth intact.')

    seed_user = session.exec(select(User).where(User.username == username)).first() or all_users[0]
    reset_users = all_users if reset_all_users else [seed_user]
    return reset_users, seed_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Reset local product data and seed a clean architecture demo.')
    parser.add_argument('--username', default='naruto', help='User to receive clean demo seed. Defaults to naruto.')
    parser.add_argument('--reset-all-users', action='store_true', help='Delete product data for all users, not only --username.')
    parser.add_argument('--yes', action='store_true', help='Required to actually mutate the database.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.yes:
        raise SystemExit('Refusing to reset without --yes. A db.sqlite backup will be created before deletion.')

    backup_path = backup_db()
    if backup_path:
        print(f'Backup created: {backup_path}')
    else:
        print('No db.sqlite found to backup.')

    with Session(engine) as session:
        reset_users, seed_user = choose_users(session, args.username, args.reset_all_users)
        seed_username = seed_user.username
        deleted = reset_product_data(session, reset_users)
        seeded = seed_clean_demo(session, seed_user)
        session.commit()

    print('Deleted product rows:')
    for model_name, count in deleted.items():
        print(f'  {model_name}: {count}')
    print(f'Seeded clean demo for user: {seed_username}')
    print(f"  TodoOccurrences for today: {seeded['occurrences']}")


if __name__ == '__main__':
    main()
