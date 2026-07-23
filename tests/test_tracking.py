from datetime import datetime, timedelta
import unittest

from sqlmodel import Session, SQLModel, create_engine

from models import Goal, Milestone, StatusType, Task, Todo, TodoOccurrence, User
from routers.daily_lifecycle import _active_recurring_todos
from services.completion_rules import recalculate_for_occurrence
from services.tracking import advance_tracking_after_occurrence
from utils.timezone import JST


class TrackingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)

    def test_staged_challenge_graduates_and_activates_next_stage_tomorrow(self):
        today = datetime.now(JST).date()
        with Session(self.engine) as session:
            user = User(username="tracking", email="tracking@example.com", password_hash="test")
            session.add(user)
            session.flush()
            goal = Goal(title="Recovery OS", status=StatusType.STARTED, user_id=user.id)
            session.add(goal)
            session.flush()
            first_milestone = Milestone(
                title="Week 1",
                goal_id=goal.id,
                user_id=user.id,
                position=1,
                status=StatusType.STARTED,
            )
            next_milestone = Milestone(
                title="Week 2",
                goal_id=goal.id,
                user_id=user.id,
                position=2,
                status=StatusType.OUTSTANDING,
            )
            session.add(first_milestone)
            session.add(next_milestone)
            session.flush()

            first_task = Task(
                title="Sleep before 01:00",
                kind="challenge",
                scope="milestone",
                status=StatusType.STARTED,
                goal_id=goal.id,
                milestone_id=first_milestone.id,
                user_id=user.id,
                completion_rule={"type": "consistency", "required_done": 2, "window_days": 2},
            )
            next_task = Task(
                title="Sleep before 00:30",
                kind="challenge",
                scope="milestone",
                status=StatusType.OUTSTANDING,
                goal_id=goal.id,
                milestone_id=next_milestone.id,
                user_id=user.id,
                completion_rule={"type": "consistency", "required_done": 2, "window_days": 2},
            )
            session.add(first_task)
            session.add(next_task)
            session.flush()
            first_todo = Todo(
                title="Sleep before 01:00",
                repeat_interval="daily",
                tracking_mode="staged",
                tracking_state="active",
                routine_series_key="bedtime",
                stage_order=1,
                task_id=first_task.id,
                user_id=user.id,
            )
            next_todo = Todo(
                title="Sleep before 00:30",
                repeat_interval="daily",
                tracking_mode="staged",
                tracking_state="planned",
                routine_series_key="bedtime",
                stage_order=2,
                task_id=next_task.id,
                user_id=user.id,
            )
            session.add(first_todo)
            session.add(next_todo)
            session.flush()

            yesterday = TodoOccurrence(
                date=today - timedelta(days=1),
                status="done",
                todo_id=first_todo.id,
                user_id=user.id,
            )
            current = TodoOccurrence(
                date=today,
                status="done",
                todo_id=first_todo.id,
                user_id=user.id,
            )
            session.add(yesterday)
            session.add(current)
            session.flush()

            recalculate_for_occurrence(session, current)
            session.flush()
            self.assertEqual(first_task.status, StatusType.FINISHED)
            activated = advance_tracking_after_occurrence(session, current)
            session.flush()

            self.assertEqual(first_todo.tracking_state, "graduated")
            self.assertEqual(activated.id, next_todo.id)
            self.assertEqual(next_todo.tracking_state, "active")
            self.assertEqual(next_todo.active_from, today + timedelta(days=1))
            self.assertEqual(next_task.status, StatusType.STARTED)
            self.assertEqual(next_milestone.status, StatusType.STARTED)
            self.assertEqual(_active_recurring_todos(session, user, today), [])
            self.assertEqual(
                [todo.id for todo in _active_recurring_todos(session, user, today + timedelta(days=1))],
                [next_todo.id],
            )

    def test_challenge_can_complete_from_an_existing_goal_routine(self):
        today = datetime.now(JST).date()
        with Session(self.engine) as session:
            user = User(username="shared", email="shared@example.com", password_hash="test")
            session.add(user)
            session.flush()
            goal = Goal(title="Recovery OS", status=StatusType.STARTED, user_id=user.id)
            session.add(goal)
            session.flush()
            milestone = Milestone(
                title="Week 1",
                goal_id=goal.id,
                user_id=user.id,
                position=1,
                status=StatusType.STARTED,
            )
            session.add(milestone)
            session.flush()
            routine = Task(
                title="Daily recovery floor",
                kind="routine",
                scope="goal",
                status=StatusType.STARTED,
                goal_id=goal.id,
                user_id=user.id,
            )
            session.add(routine)
            session.flush()
            routine_todo = Todo(
                title="Phone outside bedroom",
                repeat_interval="daily",
                tracking_mode="ongoing",
                tracking_state="active",
                task_id=routine.id,
                user_id=user.id,
            )
            session.add(routine_todo)
            session.flush()
            challenge = Task(
                title="Seven clean nights",
                kind="challenge",
                scope="milestone",
                status=StatusType.STARTED,
                goal_id=goal.id,
                milestone_id=milestone.id,
                user_id=user.id,
                completion_rule={
                    "type": "consistency",
                    "required_done": 1,
                    "window_days": 7,
                    "todo_ids": [str(routine_todo.id)],
                },
            )
            session.add(challenge)
            session.flush()
            duplicate_challenge_todo = Todo(
                title="Phone outside bedroom",
                repeat_interval="daily",
                tracking_mode="bounded",
                tracking_state="active",
                task_id=challenge.id,
                user_id=user.id,
            )
            session.add(duplicate_challenge_todo)
            session.flush()
            self.assertEqual(
                [todo.id for todo in _active_recurring_todos(session, user, today)],
                [routine_todo.id],
            )
            occurrence = TodoOccurrence(
                date=today,
                status="done",
                todo_id=routine_todo.id,
                user_id=user.id,
            )
            session.add(occurrence)
            session.flush()

            recalculate_for_occurrence(session, occurrence)
            session.flush()

            self.assertEqual(challenge.status, StatusType.FINISHED)
            self.assertEqual(challenge.completion_rule["current_done"], 1)


if __name__ == "__main__":
    unittest.main()
