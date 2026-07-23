from datetime import datetime, timedelta
import unittest

from sqlmodel import Session, SQLModel, create_engine, select

from models import Task, Todo, User
from routers.templates import _materialize_blueprint
from utils.timezone import JST


class TemplateTrackingTests(unittest.TestCase):
    def test_materializer_reuses_matching_goal_routine_for_challenge(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        SQLModel.metadata.create_all(engine)
        start = datetime.now(JST)
        with Session(engine) as session:
            user = User(username="template", email="template@example.com", password_hash="test")
            session.add(user)
            session.flush()
            goal = _materialize_blueprint(
                session,
                user,
                "Recovery OS",
                None,
                {
                    "schema_version": 3,
                    "status": "started",
                    "goal_tasks": [{
                        "title": "Daily recovery floor",
                        "kind": "routine",
                        "scope": "goal",
                        "status": "started",
                        "todos": [{
                            "title": "Phone outside bedroom",
                            "repeat_interval": "daily",
                            "tracking_mode": "ongoing",
                            "tracking_state": "active",
                        }],
                    }],
                    "milestones": [{
                        "title": "Week 1",
                        "status": "started",
                        "tasks": [{
                            "title": "Seven clean nights",
                            "kind": "challenge",
                            "scope": "milestone",
                            "status": "started",
                            "completion_rule": {
                                "type": "consistency",
                                "required_done": 7,
                                "window_days": 7,
                            },
                            "todos": [{
                                "title": "Phone outside bedroom",
                                "repeat_interval": "daily",
                                "tracking_mode": "bounded",
                                "tracking_state": "active",
                            }],
                        }],
                    }],
                },
                start,
                start + timedelta(days=30),
            )
            session.flush()

            todos = session.exec(select(Todo).where(Todo.user_id == user.id)).all()
            challenge = session.exec(select(Task).where(Task.goal_id == goal.id, Task.kind == "challenge")).one()

            self.assertEqual(len(todos), 1)
            self.assertEqual(challenge.completion_rule["todo_ids"], [str(todos[0].id)])
            self.assertEqual(todos[0].tracking_mode, "ongoing")


if __name__ == "__main__":
    unittest.main()
