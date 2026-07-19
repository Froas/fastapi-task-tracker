from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Any
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from db import get_session
from main import app
from models import DailyLog, TodoOccurrence, User, get_current_active_user
from utils.timezone import JST


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


checks: list[Check] = []


def require(response, expected: int = 200) -> Any:
    if response.status_code != expected:
        raise AssertionError(f"{response.request.method} {response.request.url.path}: {response.status_code} {response.text}")
    return response.json()


def run_check(name: str, action) -> None:
    try:
        action()
        checks.append(Check(name, True))
    except Exception as exc:
        checks.append(Check(name, False, str(exc)))


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    user = User(username="completion-audit", email="completion@example.com", password_hash="unused")
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id


def session_override():
    with Session(engine) as session:
        yield session


def user_override():
    with Session(engine) as session:
        return session.get(User, user_id)


app.dependency_overrides[get_session] = session_override
app.dependency_overrides[get_current_active_user] = user_override
client = TestClient(app)
today = datetime.now(JST).date()


def create_goal(title: str, completion_rule: dict[str, Any]) -> dict[str, Any]:
    return require(client.post("/user/goals", json={"title": title, "completion_rule": completion_rule}))


def get_goal(goal_id: str) -> dict[str, Any]:
    return require(client.get(f"/user/goals/{goal_id}?include_milestones=true&include_tasks=true&include_subtasks=true&include_todos=true"))


def audit_structural_and_unlocking() -> None:
    goal = create_goal("Structural goal", {"type": "structural"})
    milestone_one = require(client.post("/user/milestones", json={
        "title": "First checkpoint",
        "goal_id": goal["id"],
        "completion_rule": {"type": "structural"},
    }))
    milestone_two = require(client.post("/user/milestones", json={
        "title": "Second checkpoint",
        "goal_id": goal["id"],
        "completion_rule": {"type": "structural"},
    }))
    task_one = require(client.post("/user/tasks", json={
        "title": "First task",
        "goal_id": goal["id"],
        "milestone_id": milestone_one["id"],
        "scope": "milestone",
        "completion_rule": {"type": "structural"},
    }))
    subtasks = [
        require(client.post("/user/task/subtasks", json={"title": "Step one", "task_id": task_one["id"]})),
        require(client.post("/user/task/subtasks", json={"title": "Step two", "task_id": task_one["id"]})),
    ]
    require(client.patch("/user/task/subtasks/update", json={"id": subtasks[0]["id"], "status": "finished"}))
    halfway = get_goal(goal["id"])
    first_task_halfway = halfway["milestones"][0]["tasks"][0]
    assert first_task_halfway["status"] != "finished"
    require(client.patch("/user/task/subtasks/update", json={"id": subtasks[1]["id"], "status": "finished"}))
    first_done = get_goal(goal["id"])
    assert first_done["milestones"][0]["tasks"][0]["status"] == "finished"
    assert first_done["milestones"][0]["status"] == "finished"
    assert first_done["milestones"][1]["status"] != "finished"
    assert first_done["status"] != "finished"

    task_two = require(client.post("/user/tasks", json={
        "title": "Second task",
        "goal_id": goal["id"],
        "milestone_id": milestone_two["id"],
        "scope": "milestone",
        "completion_rule": {"type": "structural"},
    }))
    final_subtask = require(client.post("/user/task/subtasks", json={"title": "Final step", "task_id": task_two["id"]}))
    require(client.patch("/user/task/subtasks/update", json={"id": final_subtask["id"], "status": "finished"}))
    completed = get_goal(goal["id"])
    assert completed["milestones"][1]["status"] == "finished"
    assert completed["status"] == "finished"
    require(client.patch("/user/task/subtasks/update", json={"id": final_subtask["id"], "status": "outstanding"}))
    reopened = get_goal(goal["id"])
    assert reopened["milestones"][1]["tasks"][0]["status"] == "in progress"
    assert reopened["milestones"][1]["status"] == "in progress"
    assert reopened["status"] == "in progress"

    require(client.patch("/user/task/subtasks/update", json={"id": final_subtask["id"], "status": "finished"}))
    require(client.get(f"/user/milestones/{milestone_two['id']}?include_tasks=true&include_subtasks=true"))
    manually_reopened_task = require(client.patch("/user/tasks/update", json={
        "id": task_two["id"],
        "status": "outstanding",
    }))
    assert manually_reopened_task["status"] == "outstanding"
    manually_reopened = get_goal(goal["id"])
    assert manually_reopened["milestones"][1]["tasks"][0]["status"] == "outstanding"
    assert manually_reopened["milestones"][1]["status"] == "in progress"
    assert manually_reopened["status"] == "in progress"


def audit_outcome_rule() -> None:
    goal = create_goal("Outcome goal", {
        "type": "metric_target",
        "metric_name": "Weight",
        "start_value": 100,
        "target_value": 90,
        "direction": "decrease",
    })
    metric = require(client.post("/user/metric-definitions", json={
        "name": "Weight",
        "unit": "kg",
        "input_type": "number",
        "goal_id": goal["id"],
    }))
    require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today.isoformat(),
        "numeric_value": 95,
    }))
    halfway = get_goal(goal["id"])
    assert halfway["status"] != "finished"
    assert halfway["completion_rule"]["current_value"] == 95
    require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today.isoformat(),
        "numeric_value": 90,
    }))
    completed = get_goal(goal["id"])
    assert completed["status"] == "finished"
    assert completed["completion_rule"]["current_value"] == 90
    require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today.isoformat(),
        "numeric_value": 95,
    }))
    reopened = get_goal(goal["id"])
    assert reopened["status"] == "in progress"
    assert reopened["completion_rule"]["current_value"] == 95


def audit_milestone_outcome_rule() -> None:
    goal = create_goal("Milestone metric goal", {"type": "structural"})
    milestone = require(client.post("/user/milestones", json={
        "title": "Reach 95 kg",
        "goal_id": goal["id"],
        "completion_rule": {
            "type": "metric_target",
            "metric_name": "Milestone weight",
            "start_value": 100,
            "target_value": 95,
            "direction": "decrease",
        },
    }))
    metric = require(client.post("/user/metric-definitions", json={
        "name": "Milestone weight",
        "unit": "kg",
        "input_type": "number",
        "goal_id": goal["id"],
        "milestone_id": milestone["id"],
    }))
    assert metric["milestone_id"] == milestone["id"]
    require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today.isoformat(),
        "numeric_value": 95,
    }))
    completed = get_goal(goal["id"])
    assert completed["milestones"][0]["status"] == "finished"
    assert completed["status"] == "finished"


def audit_consistency_rule() -> None:
    goal = create_goal("Consistency goal", {
        "type": "consistency",
        "label": "Two reps",
        "required_done": 2,
        "window_days": 7,
    })
    routine = require(client.post("/user/tasks", json={
        "title": "Daily routine",
        "goal_id": goal["id"],
        "scope": "goal",
        "kind": "routine",
    }))
    todo = require(client.post("/user/todos", json={
        "title": "Daily rep",
        "task_id": routine["id"],
        "repeat_interval": "daily",
    }))
    distractor_routine = require(client.post("/user/tasks", json={
        "title": "Unrelated routine",
        "goal_id": goal["id"],
        "scope": "goal",
        "kind": "routine",
    }))
    distractor = require(client.post("/user/todos", json={
        "title": "Unrelated rep",
        "task_id": distractor_routine["id"],
        "repeat_interval": "daily",
    }))
    require(client.patch("/user/goals/update", json={
        "id": goal["id"],
        "completion_rule": {
            "type": "consistency",
            "label": "Two selected reps",
            "todo_id": todo["id"],
            "required_done": 2,
            "window_days": 7,
        },
    }))
    distractor_occurrence = next(
        item for item in require(client.get("/user/todo-occurrences/today")) if item["todo_id"] == distractor["id"]
    )
    require(client.patch("/user/todo-occurrences/update", json={"id": distractor_occurrence["id"], "status": "done"}))
    isolated = get_goal(goal["id"])
    assert isolated["status"] != "finished"
    assert isolated["completion_rule"]["current_done"] == 0
    today_occurrence = next(
        item for item in require(client.get("/user/todo-occurrences/today")) if item["todo_id"] == todo["id"]
    )
    yesterday = today - timedelta(days=1)
    with Session(engine) as session:
        daily_log = DailyLog(date=yesterday, user_id=user_id)
        session.add(daily_log)
        session.flush()
        occurrence = TodoOccurrence(
            date=yesterday,
            status="done",
            todo_id=uuid.UUID(todo["id"]),
            daily_log_id=daily_log.id,
            user_id=user_id,
        )
        session.add(occurrence)
        session.commit()
    require(client.patch("/user/todo-occurrences/update", json={"id": today_occurrence["id"], "status": "done"}))
    completed = get_goal(goal["id"])
    assert completed["status"] == "finished"
    assert completed["completion_rule"]["current_done"] == 2
    require(client.patch("/user/todo-occurrences/update", json={"id": today_occurrence["id"], "status": "open"}))
    reopened = get_goal(goal["id"])
    assert reopened["status"] == "in progress"
    assert reopened["completion_rule"]["current_done"] == 1


def audit_hybrid_rule() -> None:
    goal = create_goal("Hybrid goal", {
        "type": "hybrid",
        "structural_weight": 20,
        "outcome_weight": 40,
        "consistency_weight": 40,
        "outcome": {
            "type": "metric_target",
            "metric_name": "Score",
            "start_value": 0,
            "target_value": 10,
            "direction": "at_least",
        },
        "consistency": {
            "type": "consistency",
            "label": "One rep",
            "required_done": 1,
            "window_days": 7,
        },
    })
    milestone = require(client.post("/user/milestones", json={"title": "Hybrid checkpoint", "goal_id": goal["id"]}))
    task = require(client.post("/user/tasks", json={
        "title": "Hybrid structure",
        "goal_id": goal["id"],
        "milestone_id": milestone["id"],
        "scope": "milestone",
    }))
    subtask = require(client.post("/user/task/subtasks", json={"title": "Hybrid step", "task_id": task["id"]}))
    routine = require(client.post("/user/tasks", json={
        "title": "Hybrid routine",
        "goal_id": goal["id"],
        "scope": "goal",
        "kind": "routine",
    }))
    todo = require(client.post("/user/todos", json={
        "title": "Hybrid rep",
        "task_id": routine["id"],
        "repeat_interval": "daily",
    }))
    metric = require(client.post("/user/metric-definitions", json={
        "name": "Score",
        "input_type": "number",
        "goal_id": goal["id"],
    }))

    require(client.patch("/user/task/subtasks/update", json={"id": subtask["id"], "status": "finished"}))
    assert get_goal(goal["id"])["status"] != "finished"
    require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today.isoformat(),
        "numeric_value": 10,
    }))
    assert get_goal(goal["id"])["status"] != "finished"
    occurrence = next(
        item for item in require(client.get("/user/todo-occurrences/today")) if item["todo_id"] == todo["id"]
    )
    require(client.patch("/user/todo-occurrences/update", json={"id": occurrence["id"], "status": "done"}))
    completed = get_goal(goal["id"])
    assert completed["status"] == "finished"
    assert completed["completion_rule"]["current_progress"] == 100


run_check("structural task → milestone → goal completion and next unlock", audit_structural_and_unlocking)
run_check("outcome metric target completion", audit_outcome_rule)
run_check("milestone-owned outcome metric completion", audit_milestone_outcome_rule)
run_check("consistency occurrence completion", audit_consistency_rule)
run_check("hybrid weighted completion waits for every configured lane", audit_hybrid_rule)

app.dependency_overrides.clear()

passed = sum(check.passed for check in checks)
failed = len(checks) - passed
for check in checks:
    marker = "PASS" if check.passed else "FAIL"
    suffix = f" — {check.detail}" if check.detail else ""
    print(f"[{marker}] {check.name}{suffix}")
print(f"\nCompletion rules audit: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
