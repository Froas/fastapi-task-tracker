import unittest
import uuid

from sqlmodel import Session, SQLModel, create_engine, select

from models import Goal, Milestone, StatusType, Task, Todo, TodoOccurrence, User
from routers.daily_lifecycle import (
    _active_recurring_todos,
    _current_milestone_ids,
    ensure_occurrences_for_date,
    logical_today,
)


class CurrentMilestoneTests(unittest.TestCase):
    def setUp(self):
        self.goal_id = uuid.uuid4()
        self.user_id = uuid.uuid4()

    def milestone(self, position: int, status: StatusType) -> Milestone:
        return Milestone(
            title=f"Milestone {position}",
            goal_id=self.goal_id,
            user_id=self.user_id,
            position=position,
            status=status,
        )

    def test_first_outstanding_is_current_when_nothing_was_started(self):
        first = self.milestone(1, StatusType.OUTSTANDING)
        second = self.milestone(2, StatusType.OUTSTANDING)

        self.assertEqual(_current_milestone_ids([second, first]), {first.id})

    def test_explicitly_started_milestone_replaces_implicit_first(self):
        first = self.milestone(1, StatusType.OUTSTANDING)
        second = self.milestone(2, StatusType.STARTED)

        self.assertEqual(_current_milestone_ids([first, second]), {second.id})

    def test_free_order_can_have_multiple_current_milestones(self):
        first = self.milestone(1, StatusType.STARTED)
        second = self.milestone(2, StatusType.IN_PROGRESS)
        future = self.milestone(3, StatusType.OUTSTANDING)

        self.assertEqual(_current_milestone_ids([first, second, future]), {first.id, second.id})

    def test_finished_milestone_advances_to_next_outstanding(self):
        finished = self.milestone(1, StatusType.FINISHED)
        next_milestone = self.milestone(2, StatusType.OUTSTANDING)

        self.assertEqual(_current_milestone_ids([finished, next_milestone]), {next_milestone.id})

    def test_today_includes_goal_scope_and_only_the_current_milestone_scope(self):
        engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            user = User(username="daily-test", email="daily@example.com", password_hash="test")
            session.add(user)
            session.flush()
            goal = Goal(title="Recovery OS", status=StatusType.STARTED, user_id=user.id)
            session.add(goal)
            session.flush()

            first = Milestone(
                title="Week 1",
                goal_id=goal.id,
                user_id=user.id,
                position=1,
                status=StatusType.OUTSTANDING,
            )
            future = Milestone(
                title="Week 2",
                goal_id=goal.id,
                user_id=user.id,
                position=2,
                status=StatusType.OUTSTANDING,
            )
            session.add(first)
            session.add(future)
            session.flush()

            task_specs = [
                ("Daily floor", "goal", None),
                ("Daily floor", "milestone", first.id),
                ("Week 1 routine", "milestone", first.id),
                ("Week 2 routine", "milestone", future.id),
            ]
            todo_ids_by_title = {}
            for position, (title, scope, milestone_id) in enumerate(task_specs):
                task = Task(
                    title=title,
                    goal_id=goal.id,
                    milestone_id=milestone_id,
                    scope=scope,
                    kind="routine",
                    status=StatusType.STARTED,
                    position=position,
                    user_id=user.id,
                )
                session.add(task)
                session.flush()
                todo = Todo(
                    title=title,
                    repeat_interval="daily",
                    status=StatusType.OUTSTANDING,
                    task_id=task.id,
                    user_id=user.id,
                )
                session.add(todo)
                session.flush()
                todo_ids_by_title[title] = todo.id
            session.flush()

            self.assertEqual(
                {todo.title for todo in _active_recurring_todos(session, user)},
                {"Daily floor", "Week 1 routine"},
            )
            selected_date = logical_today()
            first_occurrences = ensure_occurrences_for_date(session, user, selected_date)
            self.assertEqual(len(first_occurrences), 2)

            future.status = StatusType.STARTED
            session.add(future)
            session.flush()
            self.assertEqual(
                {todo.title for todo in _active_recurring_todos(session, user)},
                {"Daily floor", "Week 2 routine"},
            )
            next_occurrences = ensure_occurrences_for_date(session, user, selected_date)
            session.flush()
            self.assertEqual(len(next_occurrences), 2)
            stored_occurrences = session.exec(select(TodoOccurrence)).all()
            self.assertEqual(len(stored_occurrences), 2)

            session.add(TodoOccurrence(
                date=selected_date,
                status="done",
                todo_id=todo_ids_by_title["Week 1 routine"],
                daily_log_id=next_occurrences[0].daily_log_id,
                user_id=user.id,
            ))
            session.flush()
            ensure_occurrences_for_date(session, user, selected_date)
            session.flush()
            preserved_history = session.exec(select(TodoOccurrence)).all()
            self.assertEqual(len(preserved_history), 3)
            self.assertIn("done", {occurrence.status for occurrence in preserved_history})


if __name__ == "__main__":
    unittest.main()
