from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from db import get_session
from main import app
from models import User, get_current_active_user
from utils.timezone import JST


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


checks: list[Check] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    checks.append(Check(name=name, passed=passed, detail=detail))


def require(response, expected: int = 200) -> Any:
    if response.status_code != expected:
        raise AssertionError(f"{response.request.method} {response.request.url.path}: {response.status_code} {response.text}")
    return response.json()


def run_check(name: str, action) -> None:
    try:
        action()
        record(name, True)
    except Exception as exc:
        record(name, False, str(exc))


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    first_user = User(username="persistence-audit", email="audit@example.com", password_hash="unused")
    second_user = User(username="persistence-import", email="import@example.com", password_hash="unused")
    session.add(first_user)
    session.add(second_user)
    session.commit()
    session.refresh(first_user)
    session.refresh(second_user)
    first_user_id = first_user.id
    second_user_id = second_user.id

active_user = {"id": first_user_id}


def session_override():
    with Session(engine) as session:
        yield session


def user_override():
    with Session(engine) as session:
        return session.get(User, active_user["id"])


app.dependency_overrides[get_session] = session_override
app.dependency_overrides[get_current_active_user] = user_override
client = TestClient(app)

state: dict[str, Any] = {}
today = datetime.now(JST).date().isoformat()


def audit_hierarchy() -> None:
    goals = []
    for index in range(3):
        goal = require(client.post("/user/goals", json={
            "title": f"Audit goal {index + 1}",
            "description": "created",
            "completion_rule": {"type": "structural"},
        }))
        goals.append(goal)
    reversed_ids = [goal["id"] for goal in reversed(goals)]
    require(client.put("/user/goals/reorder", json={"goal_ids": reversed_ids}))
    reloaded_goals = require(client.get("/user/goals"))
    assert [goal["id"] for goal in reloaded_goals] == reversed_ids
    updated_goal = require(client.patch("/user/goals/update", json={
        "id": goals[0]["id"],
        "title": "Audit goal updated",
        "description": "persisted",
        "status": "started",
        "completion_rule": {"type": "consistency", "label": "Audit", "current_done": 2, "required_done": 3, "window_days": 7},
    }))
    assert updated_goal["title"] == "Audit goal updated"
    assert updated_goal["completion_rule"]["type"] == "consistency"

    goal_id = goals[0]["id"]
    milestones = []
    for index in range(3):
        milestones.append(require(client.post("/user/milestones", json={
            "title": f"Milestone {index + 1}",
            "description": "created",
            "goal_id": goal_id,
        })))
    milestone_ids = [milestone["id"] for milestone in reversed(milestones)]
    require(client.put("/user/milestones/reorder", json={"milestone_ids": milestone_ids}))
    nested = require(client.get(f"/user/goals/{goal_id}?include_milestones=true"))
    assert [milestone["id"] for milestone in nested["milestones"]] == milestone_ids
    sequential_goal = require(client.patch("/user/goals/update", json={
        "id": goal_id,
        "enforce_sequential_milestones": True,
    }))
    assert sequential_goal["enforce_sequential_milestones"] is True
    blocked = client.patch("/user/milestones/update", json={
        "id": milestones[0]["id"],
        "status": "finished",
    })
    assert blocked.status_code == 409
    require(client.patch("/user/milestones/update", json={"id": milestones[2]["id"], "status": "finished"}))
    require(client.patch("/user/milestones/update", json={"id": milestones[1]["id"], "status": "finished"}))
    require(client.patch("/user/milestones/update", json={"id": milestones[0]["id"], "status": "finished"}))
    require(client.patch("/user/milestones/update", json={
        "id": milestones[0]["id"],
        "title": "Milestone updated",
        "status": "started",
    }))
    assert require(client.get(f"/user/milestones/{milestones[0]['id']}"))["title"] == "Milestone updated"

    tasks = []
    for index in range(3):
        tasks.append(require(client.post("/user/tasks", json={
            "title": f"Task {index + 1}",
            "goal_id": goal_id,
            "milestone_id": milestones[0]["id"],
            "scope": "milestone",
            "kind": "project",
        })))
    task_ids = [task["id"] for task in reversed(tasks)]
    require(client.put("/user/tasks/reorder", json={"task_ids": task_ids}))
    milestone_detail = require(client.get(f"/user/milestones/{milestones[0]['id']}?include_tasks=true"))
    assert [task["id"] for task in milestone_detail["tasks"]] == task_ids
    require(client.patch("/user/tasks/update", json={
        "id": tasks[0]["id"],
        "title": "Task updated",
        "status": "in progress",
    }))

    routine = require(client.post("/user/tasks", json={
        "title": "Goal routine",
        "goal_id": goal_id,
        "scope": "goal",
        "kind": "routine",
    }))
    goal_detail = require(client.get(f"/user/goals/{goal_id}?include_tasks=true"))
    assert any(task["id"] == routine["id"] and task["scope"] == "goal" for task in goal_detail["tasks"])

    todos = []
    subtasks = []
    for index in range(3):
        todos.append(require(client.post("/user/todos", json={
            "title": f"Routine todo {index + 1}",
            "task_id": routine["id"],
            "repeat_interval": "daily",
        })))
        subtasks.append(require(client.post("/user/task/subtasks", json={
            "title": f"Subtask {index + 1}",
            "task_id": tasks[0]["id"],
        })))
    todo_ids = [todo["id"] for todo in reversed(todos)]
    subtask_ids = [subtask["id"] for subtask in reversed(subtasks)]
    require(client.put("/user/todos/reorder", json={"todo_ids": todo_ids}))
    require(client.put("/user/task/subtasks/reorder", json={"subtask_ids": subtask_ids}))
    routine_detail = require(client.get(f"/user/tasks/{routine['id']}"))
    task_detail = require(client.get(f"/user/tasks/{tasks[0]['id']}"))
    assert [todo["id"] for todo in routine_detail["todos"]] == todo_ids
    assert [subtask["id"] for subtask in task_detail["subtasks"]] == subtask_ids
    require(client.patch("/user/todos/update", json={"id": todos[0]["id"], "title": "Todo updated"}))
    require(client.patch("/user/task/subtasks/update", json={"id": subtasks[0]["id"], "title": "Subtask updated"}))
    assert require(client.get(f"/user/todos/{todos[0]['id']}"))["title"] == "Todo updated"
    assert require(client.get(f"/user/task/subtasks/{subtasks[0]['id']}"))["title"] == "Subtask updated"

    occurrences = require(client.get("/user/todo-occurrences/today"))
    assert len([item for item in occurrences if item["todo_id"] in todo_ids]) == 3
    occurrence = next(item for item in occurrences if item["todo_id"] == todos[0]["id"])
    updated_occurrence = require(client.patch("/user/todo-occurrences/update", json={
        "id": occurrence["id"],
        "status": "done",
    }))
    assert updated_occurrence["status"] == "done"

    state.update({
        "goal_id": goal_id,
        "milestone_id": milestones[0]["id"],
        "task_id": tasks[0]["id"],
        "routine_id": routine["id"],
        "todo_id": todos[0]["id"],
        "subtask_id": subtasks[0]["id"],
    })


def audit_auxiliary_entities() -> None:
    preferences = require(client.patch("/users/me", json={
        "nav_preferences": {"orderedIds": ["today", "goals"], "primaryIds": ["today"], "hiddenIds": []},
        "dashboard_preferences": {"orderedIds": ["today", "calendar"], "hiddenIds": ["activity"]},
        "pinned_goal_ids": [state["goal_id"]],
        "recent_goal_ids": [state["goal_id"]],
        "goal_color_overrides": {state["goal_id"]: "from-blue-500 to-purple-600"},
    }))
    assert preferences["nav_preferences"]["primaryIds"] == ["today"]
    assert preferences["dashboard_preferences"]["hiddenIds"] == ["activity"]
    assert preferences["pinned_goal_ids"] == [state["goal_id"]]
    assert preferences["recent_goal_ids"] == [state["goal_id"]]
    assert preferences["goal_color_overrides"][state["goal_id"]] == "from-blue-500 to-purple-600"

    active_user["id"] = second_user_id
    foreign_goal = require(client.post("/user/goals", json={"title": "Foreign goal"}))
    active_user["id"] = first_user_id
    foreign_relation = client.post("/user/notes", json={
        "title": "Invalid cross-account relation",
        "goal_id": foreign_goal["id"],
    })
    assert foreign_relation.status_code == 404

    event = require(client.post("/user/events", json={
        "title": "Audit event",
        "start_datetime": f"{today}T09:00:00",
        "end_datetime": f"{today}T10:00:00",
    }))
    require(client.patch("/user/events/update", json={"id": event["id"], "title": "Event updated"}))
    assert require(client.get(f"/user/events/{event['id']}"))["title"] == "Event updated"

    note = require(client.post("/user/notes", json={
        "title": "Audit note",
        "body": "created",
        "goal_id": state["goal_id"],
    }))
    require(client.patch("/user/notes/update", json={
        "id": note["id"],
        "title": "Note updated",
        "body": "persisted",
        "pinned": True,
    }))
    note_reload = require(client.get(f"/user/notes/{note['id']}"))
    assert note_reload["title"] == "Note updated" and note_reload["pinned"] is True

    signal = require(client.post("/user/notes", json={
        "title": "Audit signal",
        "kind": "signal",
        "signal_domain": "work",
        "signal_stake": "medium",
    }))
    assert signal["signal_domain"] == "work" and signal["signal_decision"] is None
    invalid_watch = client.patch("/user/notes/update", json={
        "id": signal["id"],
        "signal_decision": "watch",
    })
    assert invalid_watch.status_code == 422
    watched = require(client.patch("/user/notes/update", json={
        "id": signal["id"],
        "signal_decision": "watch",
        "review_date": today,
        "next_action": "Review the evidence",
    }))
    assert watched["review_date"] == today and watched["resolved_at"] is None
    resolved = require(client.patch("/user/notes/update", json={
        "id": signal["id"],
        "outcome": "Handled",
        "resolved_at": datetime.now(JST).isoformat(),
    }))
    assert resolved["resolved_at"] is not None and resolved["outcome"] == "Handled"

    draft = require(client.post("/user/daily-draft-todos", json={"title": "Audit draft", "day": today}))
    require(client.patch("/user/daily-draft-todos/update", json={"id": draft["id"], "done": True}))
    drafts = require(client.get(f"/user/daily-draft-todos?selected_date={today}&include_done=true"))
    assert any(item["id"] == draft["id"] and item["done"] for item in drafts)

    daily_log = require(client.post("/user/daily-logs", json={
        "date": today,
        "color": "yellow",
        "note": "created",
    }))
    require(client.patch("/user/daily-logs/update", json={
        "id": daily_log["id"],
        "color": "green",
        "note": "persisted",
    }))
    daily_log_reload = require(client.get(f"/user/daily-logs/{today}"))
    assert daily_log_reload["color"] == "green" and daily_log_reload["note"] == "persisted"

    metric = require(client.post("/user/metric-definitions", json={
        "name": "Audit metric",
        "unit": "points",
        "input_type": "number",
        "goal_id": state["goal_id"],
    }))
    require(client.patch("/user/metric-definitions/update", json={
        "id": metric["id"],
        "name": "Metric updated",
    }))
    entry = require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today,
        "numeric_value": 42,
    }))
    entry_reload = require(client.post("/user/metric-entries/upsert", json={
        "metric_definition_id": metric["id"],
        "date": today,
        "numeric_value": 43,
    }))
    assert entry_reload["id"] == entry["id"] and entry_reload["numeric_value"] == 43
    today_metrics = require(client.get(f"/user/metrics/today?selected_date={today}"))
    assert any(item["id"] == metric["id"] and item["numeric_value"] == 43 for item in today_metrics)

    state.update({
        "event_id": event["id"],
        "note_id": note["id"],
        "signal_id": signal["id"],
        "draft_id": draft["id"],
        "metric_id": metric["id"],
    })


def audit_template() -> None:
    blueprint = {
        "duration_days": 30,
        "completion_rule": {"type": "structural"},
        "metrics": [{"name": "Template metric", "unit": "points", "input_type": "number", "show_on_today": True}],
        "goal_tasks": [{
            "title": "Template routine",
            "kind": "routine",
            "scope": "goal",
            "todos": [{"title": "Repeat action", "repeat_interval": "daily"}],
            "subtasks": [{"title": "One-off setup"}],
        }],
        "milestones": [{
            "title": "Template milestone",
            "description": "checkpoint",
            "tasks": [{
                "title": "Template task",
                "subtasks": [{"title": "Template subtask"}],
                "todos": [{"title": "Template recurring", "repeat_interval": "daily"}],
            }],
        }],
    }
    template = require(client.post("/user/templates", json={
        "title": "Audit template",
        "description": "created",
        "emoji": "🧪",
        "tags": ["audit"],
        "blueprint": blueprint,
    }))
    require(client.patch("/user/templates/update", json={"id": template["id"], "description": "persisted"}))
    assert require(client.get(f"/user/templates/{template['id']}"))["description"] == "persisted"
    goal = require(client.post(f"/user/templates/{template['id']}/instantiate", json={"title_override": "Instantiated audit"}))
    detail = require(client.get(f"/user/goals/{goal['id']}?include_milestones=true&include_tasks=true&include_subtasks=true&include_todos=true"))
    assert len(detail["milestones"]) == 1
    assert len(detail["tasks"]) == 1 and detail["tasks"][0]["kind"] == "routine"
    assert len(detail["tasks"][0]["todos"]) == 1
    assert len(detail["tasks"][0]["subtasks"]) == 1
    assert len(detail["milestones"][0]["tasks"]) == 1
    state["template_id"] = template["id"]


def audit_trash() -> None:
    for kind, item_id, path in [
        ("event", state["event_id"], f"/user/events/{state['event_id']}/delete"),
        ("note", state["note_id"], f"/user/notes/{state['note_id']}/delete"),
        ("todo", state["todo_id"], f"/user/todos/{state['todo_id']}/delete"),
    ]:
        require(client.delete(path))
        trash = require(client.get("/user/trash"))
        assert any(item["kind"] == kind and item["id"] == item_id for item in trash)
        require(client.post(f"/user/trash/{kind}/{item_id}/restore"))
        trash_after = require(client.get("/user/trash"))
        assert not any(item["kind"] == kind and item["id"] == item_id for item in trash_after)
    assert require(client.get(f"/user/events/{state['event_id']}"))["title"] == "Event updated"
    assert require(client.get(f"/user/notes/{state['note_id']}"))["title"] == "Note updated"
    assert require(client.get(f"/user/todos/{state['todo_id']}"))["title"] == "Todo updated"


def audit_backup_round_trip() -> None:
    exported = require(client.get("/user/backup/export"))
    exported_goal = next(goal for goal in exported["goals"] if goal["id"] == state["goal_id"])
    assert exported_goal.get("completion_rule") is not None, "completion_rule missing from exported goal"
    exported_note = next(note for note in exported["notes"] if note["id"] == state["note_id"])
    exported_signal = next(note for note in exported["notes"] if note["id"] == state["signal_id"])
    assert exported_note["goal_id"] == state["goal_id"]
    assert exported_signal["kind"] == "signal" and exported_signal["signal_decision"] == "watch"
    assert any(draft["id"] == state["draft_id"] and draft["done"] for draft in exported["daily_draft_todos"])

    active_user["id"] = second_user_id
    imported = require(client.post("/user/backup/import", json=exported))
    assert imported["imported"]["goals"] == len(exported["goals"])
    imported_goals = require(client.get("/user/goals"))
    imported_goal = next(goal for goal in imported_goals if goal["title"] == "Audit goal updated")
    assert imported_goal.get("completion_rule") == exported_goal.get("completion_rule")
    imported_detail = require(client.get(f"/user/goals/{imported_goal['id']}?include_milestones=true&include_tasks=true&include_subtasks=true&include_todos=true"))
    assert imported_detail["milestones"] and imported_detail["tasks"]
    imported_notes = require(client.get("/user/notes"))
    imported_note = next(note for note in imported_notes if note["title"] == "Note updated")
    imported_signal = next(note for note in imported_notes if note["title"] == "Audit signal")
    assert imported_note["goal_id"] == imported_goal["id"]
    assert imported_signal["kind"] == "signal" and imported_signal["signal_decision"] == "watch"
    imported_drafts = require(client.get(f"/user/daily-draft-todos?selected_date={today}&include_done=true"))
    assert any(draft["title"] == "Audit draft" and draft["done"] for draft in imported_drafts)
    active_user["id"] = first_user_id


def audit_hard_delete_subtask() -> None:
    require(client.delete(f"/user/task/subtasks/{state['subtask_id']}/delete"))
    response = client.get(f"/user/task/subtasks/{state['subtask_id']}")
    assert response.status_code == 404


run_check("hierarchy CRUD, reorder, nested reload, occurrences", audit_hierarchy)
run_check("events, notes, drafts, daily logs, metrics", audit_auxiliary_entities)
run_check("template CRUD and full blueprint instantiation", audit_template)
run_check("soft delete, trash listing, restore, reload", audit_trash)
run_check("JSON backup/import round trip", audit_backup_round_trip)
run_check("subtask hard delete", audit_hard_delete_subtask)

app.dependency_overrides.clear()

passed = sum(check.passed for check in checks)
failed = len(checks) - passed
for check in checks:
    marker = "PASS" if check.passed else "FAIL"
    suffix = f" — {check.detail}" if check.detail else ""
    print(f"[{marker}] {check.name}{suffix}")
print(f"\nPersistence audit: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
