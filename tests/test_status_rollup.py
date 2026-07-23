from datetime import datetime
import unittest

from sqlmodel import Session, SQLModel, create_engine

from models import Goal, Milestone, StatusType, Subtask, Task, Todo, TodoOccurrence, User
from services.completion_rules import recalculate_for_occurrence, recalculate_task_hierarchy
from utils.timezone import JST


class StatusRollupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)

    def _user(self, session: Session, suffix: str) -> User:
        user = User(
            username=f"rollup-{suffix}",
            email=f"rollup-{suffix}@example.com",
            password_hash="test",
        )
        session.add(user)
        session.flush()
        return user

    def test_finished_step_marks_task_milestone_and_goal_in_progress(self):
        with Session(self.engine) as session:
            user = self._user(session, "steps")
            goal = Goal(title="Recovery OS", status=StatusType.OUTSTANDING, user_id=user.id)
            session.add(goal)
            session.flush()
            milestone = Milestone(
                title="Week 1",
                status=StatusType.OUTSTANDING,
                goal_id=goal.id,
                user_id=user.id,
            )
            session.add(milestone)
            session.flush()
            task = Task(
                title="Install phone boundaries",
                kind="project",
                scope="milestone",
                status=StatusType.OUTSTANDING,
                goal_id=goal.id,
                milestone_id=milestone.id,
                user_id=user.id,
            )
            session.add(task)
            session.flush()
            session.add_all([
                Subtask(title="Finished step", status=StatusType.FINISHED, task_id=task.id, user_id=user.id),
                Subtask(title="Open step", status=StatusType.OUTSTANDING, task_id=task.id, user_id=user.id),
            ])
            session.flush()

            recalculate_task_hierarchy(session, task.id)
            session.flush()

            self.assertEqual(task.status, StatusType.IN_PROGRESS)
            self.assertEqual(milestone.status, StatusType.IN_PROGRESS)
            self.assertEqual(goal.status, StatusType.IN_PROGRESS)

    def test_started_task_activates_parents_without_claiming_progress(self):
        with Session(self.engine) as session:
            user = self._user(session, "started")
            goal = Goal(title="Recovery OS", status=StatusType.OUTSTANDING, user_id=user.id)
            session.add(goal)
            session.flush()
            milestone = Milestone(
                title="Week 1",
                status=StatusType.OUTSTANDING,
                goal_id=goal.id,
                user_id=user.id,
            )
            session.add(milestone)
            session.flush()
            task = Task(
                title="Prepare",
                kind="project",
                scope="milestone",
                status=StatusType.STARTED,
                goal_id=goal.id,
                milestone_id=milestone.id,
                user_id=user.id,
            )
            session.add(task)
            session.flush()

            recalculate_task_hierarchy(session, task.id)
            session.flush()

            self.assertEqual(task.status, StatusType.STARTED)
            self.assertEqual(milestone.status, StatusType.STARTED)
            self.assertEqual(goal.status, StatusType.STARTED)

    def test_completed_occurrence_marks_routine_and_goal_in_progress(self):
        with Session(self.engine) as session:
            user = self._user(session, "routine")
            goal = Goal(title="Recovery OS", status=StatusType.OUTSTANDING, user_id=user.id)
            session.add(goal)
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
            todo = Todo(
                title="Phone outside bedroom",
                repeat_interval="daily",
                status=StatusType.OUTSTANDING,
                task_id=routine.id,
                user_id=user.id,
            )
            session.add(todo)
            session.flush()
            occurrence = TodoOccurrence(
                date=datetime.now(JST).date(),
                status="done",
                todo_id=todo.id,
                user_id=user.id,
            )
            session.add(occurrence)
            session.flush()

            recalculate_for_occurrence(session, occurrence)
            session.flush()

            self.assertEqual(routine.status, StatusType.IN_PROGRESS)
            self.assertEqual(goal.status, StatusType.IN_PROGRESS)


if __name__ == "__main__":
    unittest.main()
