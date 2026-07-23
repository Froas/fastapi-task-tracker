"""Provider-agnostic AI orchestration for editable goal blueprints.

The model never writes application records. It returns a small planning DTO,
which this module validates and converts into the same blueprint consumed by
the existing template materializer.
"""

from __future__ import annotations

import json
import os
import re
import socket
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request


MAX_MILESTONES = 12
MAX_TASKS_PER_MILESTONE = 6
MAX_SUBTASKS_PER_TASK = 5
MAX_TODOS_PER_TASK = 4
MAX_ROUTINES = 5

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


class AIPlannerError(RuntimeError):
    """Base error safe for the API layer to translate."""


class AIPlannerNotConfigured(AIPlannerError):
    pass


class AIPlannerUnavailable(AIPlannerError):
    pass


class AIPlannerResponseError(AIPlannerError):
    def __init__(
        self,
        message: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens


@dataclass(frozen=True)
class ProviderResult:
    payload: dict[str, Any]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class GoalPlanProvider(Protocol):
    provider_name: str
    model: str

    def generate(
        self,
        *,
        intent: str,
        answers: list[dict[str, str]],
        locale: str,
        safety_identifier: str,
    ) -> ProviderResult: ...

    def refine_milestone(
        self,
        *,
        intent: str,
        answers: list[dict[str, str]],
        draft: dict[str, Any],
        milestone_index: int,
        instruction: str,
        locale: str,
        safety_identifier: str,
    ) -> ProviderResult: ...


QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "question", "answer_type", "placeholder", "options"],
    "properties": {
        "id": {"type": "string", "minLength": 1, "maxLength": 50},
        "question": {"type": "string", "minLength": 1, "maxLength": 240},
        "answer_type": {"type": "string", "enum": ["text", "number", "date", "choice"]},
        "placeholder": {"type": "string", "maxLength": 160},
        "options": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string", "minLength": 1, "maxLength": 100},
        },
    },
}

PLAN_SHAPE_MILESTONE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "outcome", "task_count"],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 160},
        "outcome": {"type": "string", "minLength": 1, "maxLength": 500},
        "task_count": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_TASKS_PER_MILESTONE,
        },
    },
}

PLAN_SHAPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["complexity", "rationale", "milestones", "routine_count"],
    "properties": {
        "complexity": {
            "type": "string",
            "enum": ["compact", "moderate", "complex"],
        },
        "rationale": {"type": "string", "minLength": 1, "maxLength": 500},
        "milestones": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_MILESTONES,
            "items": PLAN_SHAPE_MILESTONE_SCHEMA,
        },
        "routine_count": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_ROUTINES,
        },
    },
}

TASK_STEP_SCHEMA: dict[str, Any] = {
    "type": "string",
    "minLength": 1,
    "maxLength": 160,
}

TASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title", "description", "success_criteria", "subtasks", "todos",
        "todo_repeat_interval", "kind", "tracking_mode", "routine_series_key",
        "stage_order", "required_done", "window_days",
    ],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 160},
        "description": {"type": "string", "maxLength": 500},
        "success_criteria": {"type": "string", "minLength": 1, "maxLength": 500},
        "subtasks": {
            "type": "array",
            "maxItems": MAX_SUBTASKS_PER_TASK,
            "items": TASK_STEP_SCHEMA,
        },
        "todos": {
            "type": "array",
            "maxItems": MAX_TODOS_PER_TASK,
            "items": TASK_STEP_SCHEMA,
        },
        "todo_repeat_interval": {
            "type": "string",
            "enum": ["none", "daily", "weekly", "monthly"],
        },
        "kind": {"type": "string", "enum": ["project", "challenge"]},
        "tracking_mode": {"type": "string", "enum": ["none", "bounded", "staged"]},
        "routine_series_key": {"type": "string", "maxLength": 120},
        "stage_order": {"type": "integer", "minimum": 1, "maximum": 20},
        "required_done": {"type": "integer", "minimum": 0, "maximum": 3650},
        "window_days": {"type": "integer", "minimum": 0, "maximum": 3650},
    },
}

MILESTONE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "description", "success_criteria", "due_day", "tasks"],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 160},
        "description": {"type": "string", "maxLength": 500},
        "success_criteria": {"type": "string", "minLength": 1, "maxLength": 500},
        "due_day": {"type": "integer", "minimum": 1, "maximum": 3650},
        "tasks": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_TASKS_PER_MILESTONE,
            "items": TASK_SCHEMA,
        },
    },
}

ROUTINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "description", "repeat_interval"],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 160},
        "description": {"type": "string", "maxLength": 500},
        "repeat_interval": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
    },
}

METRIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "unit", "start_value", "target_value", "direction"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "unit": {"type": "string", "maxLength": 32},
        "start_value": {"type": "number"},
        "target_value": {"type": "number"},
        "direction": {"type": "string", "enum": ["increase", "decrease"]},
    },
}

DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "title", "description", "success_criteria", "priority",
        "duration_days", "metric", "milestones", "routines",
    ],
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "description": {"type": "string", "maxLength": 1200},
        "success_criteria": {"type": "string", "minLength": 1, "maxLength": 800},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "duration_days": {"type": "integer", "minimum": 7, "maximum": 3650},
        "metric": {"anyOf": [METRIC_SCHEMA, {"type": "null"}]},
        "milestones": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_MILESTONES,
            "items": MILESTONE_SCHEMA,
        },
        "routines": {
            "type": "array",
            "maxItems": MAX_ROUTINES,
            "items": ROUTINE_SCHEMA,
        },
    },
}

GOAL_PLAN_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "questions", "draft", "assumptions"],
    "properties": {
        "status": {"type": "string", "enum": ["needs_clarification", "ready"]},
        "questions": {"type": "array", "maxItems": 3, "items": QUESTION_SCHEMA},
        "draft": {"anyOf": [DRAFT_SCHEMA, {"type": "null"}]},
        "assumptions": {
            "type": "array",
            "maxItems": 6,
            "items": {"type": "string", "minLength": 1, "maxLength": 240},
        },
    },
}

MILESTONE_REFINEMENT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["milestone", "assumptions"],
    "properties": {
        "milestone": MILESTONE_SCHEMA,
        "assumptions": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string", "minLength": 1, "maxLength": 240},
        },
    },
}


PLANNER_INSTRUCTIONS = """You are the planning engine inside TaskNest.
Turn a user's intention into a realistic, editable goal plan.

On the first turn, return needs_clarification whenever missing information
would materially change safety, difficulty, deadline, outcome metric, or plan.
Ask at most three high-value questions. Do not invent a baseline, deadline,
weekly availability, health constraint, budget, or other capacity constraint.
For physical training goals, baseline ability, target date, and available
training days are material. For other measurable goals, ask the equivalent
baseline, deadline, and capacity questions when absent. If the user has already
answered the material questions, prefer returning ready and state only minor
assumptions.

For ready plans:
- Write every user-facing string in the requested locale.
- When plan_shape is present, it is your own prior sizing decision. Preserve its
  milestone outline, create the requested task count for each milestone, and use
  its routine_count. Expand the shape; do not silently compress it.
- The input may include planning_context with a duration hint. Use it as context,
  not as a formula for how many entities to create.
- Decide the number of milestones, tasks, subtasks, task todos, and routines from
  the goal's actual scope, difficulty, uncertainty, user experience, and horizon.
- Use the smallest plan that still covers every meaningful outcome transition.
  Do not create calendar-shaped filler or make every milestone symmetrical.
- Split a milestone when it hides multiple independently verifiable outcomes or
  leaves a long stretch without useful evidence of progress. Merge stages whose
  success would be measured by the same evidence.
- Give each milestone enough tasks to satisfy its success criteria. A task may
  have no subtasks when it is already directly executable; otherwise create only
  the concrete subtasks needed to remove ambiguity.
- Spread due_day values across the full horizon according to dependencies and
  expected effort, not at mechanically equal intervals.
- Every task must begin with an action verb.
- Every task has observable success criteria. Do not repeat the task title as a
  subtask or todo.
- Add task todos only when an action must repeat specifically to finish
  that task. Set todo_repeat_interval to daily, weekly, or monthly when todos
  are present; otherwise return an empty todos array and use none.
  Use task todos somewhere in the plan when recurring execution is genuinely
  required, but do not manufacture repetition merely to fill the array.
- Add only the routines needed to support the plan; routines are not milestones.
- Routines are stable goal-wide systems. Do not duplicate the same behavior in
  a goal routine and a task todo.
- A milestone task with repeating todos is a challenge, not a project. Give it
  required_done and window_days. Use bounded tracking when it ends after proof.
- Use staged tracking when the same behavior becomes progressively harder across
  milestones. Give every stage the same short routine_series_key and increasing
  stage_order (for example bedtime: 01:00, then 00:30, then 00:00).
- Project tasks use tracking_mode none, an empty routine_series_key, stage_order 1,
  required_done 0, and window_days 0.
- Use a numeric metric only when it honestly measures the outcome.
- Make success criteria observable and specific.
- Keep the plan achievable; do not promise medical, financial, or legal results.
- due_day is an offset from the day the goal starts and cannot exceed duration_days.
- Do not generate database IDs or technical commentary.
"""

PLAN_SHAPE_INSTRUCTIONS = """You size a TaskNest goal plan before details are generated.
Choose the right structure yourself; there is no calendar formula or preferred count.

- Write titles, outcomes, and rationale in the requested locale.
- planning_context may contain a reference_milestone_range. Treat it as a weak
  calibration prior, never as a requirement. Start by considering it, then choose
  fewer or more milestones whenever the transition analysis supports that choice.
  If you go outside the reference, explain why in rationale. Never add filler to
  reach its minimum or merge distinct outcomes merely to stay below its maximum.
- First identify distinct workstreams, dependency transitions, uncertainty-reducing
  checkpoints, and independently verifiable changes in capability or product state.
- Use one milestone when those elements share the same evidence of success. Use
  separate milestones when combining them would hide materially different outcomes.
- Do not optimize for the fewest milestones, and do not create calendar filler.
- Long or multi-domain goals usually need intermediate evidence and reassessment;
  short focused deliverables often need only a few transitions.
- For each milestone, choose the number of project tasks actually needed to produce
  its outcome. Counts do not need to be symmetrical.
- Choose routine_count only for stable goal-wide practices. Repeating execution
  local to one task will be handled later as a task todo.
- Return only the sizing result, not the final goal, tasks, subtasks, or commentary.
"""

MILESTONE_REFINEMENT_INSTRUCTIONS = """You refine one milestone inside an existing TaskNest goal plan.
Return only a replacement for the requested milestone and a short list of new assumptions.

- Write every user-facing string in the requested locale.
- Preserve the milestone's role in the surrounding sequence.
- Follow the user's refinement instruction without changing the rest of the goal.
- Make success criteria observable and tasks concrete, ordered, and action-led.
- Decide how many tasks and subtasks are needed from the milestone's actual scope.
  A directly executable task may have no subtasks; never add filler for symmetry.
- Add task todos only for recurring execution that is local to completing
  that task. Set todo_repeat_interval to daily, weekly, or monthly when todos
  are present; otherwise return an empty todos array and use none.
- Do not duplicate existing goal routines or invent repetition merely to fill
  the todo array.
- Return 1-6 tasks and no routines, metrics, goal fields, IDs, or technical commentary.
- due_day must remain between the previous and next milestone due days and within the goal duration.
"""


def _text(value: Any, fallback: str = "", max_length: int = 500) -> str:
    normalized = str(value or "").strip()
    return (normalized or fallback)[:max_length]


def _integer(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _infer_horizon_days(intent: str, answers: list[dict[str, str]]) -> int | None:
    text = " ".join([
        intent,
        *[
            str(answer.get("value") or "")
            for answer in answers
            if isinstance(answer, dict)
        ],
    ]).lower()
    candidates: list[int] = []

    duration_pattern = re.compile(
        r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s*(?:-\s*)?(days?|weeks?|months?|years?|yrs?)\b",
    )
    for amount_text, unit in duration_pattern.findall(text):
        amount = NUMBER_WORDS.get(amount_text)
        if amount is None:
            try:
                amount = float(amount_text)
            except ValueError:
                continue
        if unit.startswith(("year", "yr")):
            multiplier = 365
        elif unit.startswith("month"):
            multiplier = 30
        elif unit.startswith("week"):
            multiplier = 7
        else:
            multiplier = 1
        candidates.append(round(float(amount) * multiplier))

    for raw_date in re.findall(r"\b20\d{2}[-/]\d{2}[-/]\d{2}\b", text):
        try:
            target_date = date.fromisoformat(raw_date.replace("/", "-"))
        except ValueError:
            continue
        if target_date > date.today():
            candidates.append((target_date - date.today()).days)

    return max(7, min(3650, max(candidates))) if candidates else None


def _planning_context(horizon_days: int | None) -> dict[str, Any]:
    reference_range: dict[str, int] | None = None
    if horizon_days is not None:
        if horizon_days <= 90:
            minimum, maximum = 2, 4
        elif horizon_days <= 180:
            minimum, maximum = 3, 5
        elif horizon_days <= 420:
            minimum, maximum = 4, 7
        elif horizon_days <= 900:
            minimum, maximum = 5, 8
        elif horizon_days <= 1825:
            minimum, maximum = 6, 10
        else:
            minimum, maximum = 7, 12
        reference_range = {"from": minimum, "to": maximum}
    return {
        "duration_hint_days": horizon_days,
        "reference_milestone_range": reference_range,
        "reference_only": True,
        "typical_tasks_per_milestone": {"from": 1, "to": 4},
        "typical_subtasks_per_task": {"from": 0, "to": 4},
        "typical_task_todos_per_task": {"from": 0, "to": 2},
        "typical_goal_routines": {"from": 0, "to": 3},
    }


def _goal_plan_schema(*, ready_only: bool = False) -> dict[str, Any]:
    return deepcopy(DRAFT_SCHEMA if ready_only else GOAL_PLAN_RESPONSE_SCHEMA)


def _normalize_plan_shape(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AIPlannerResponseError("The AI response did not include a plan shape")
    milestones: list[dict[str, Any]] = []
    raw_milestones = value.get("milestones")
    if isinstance(raw_milestones, list):
        for item in raw_milestones[:MAX_MILESTONES]:
            if not isinstance(item, dict):
                continue
            title = _text(item.get("title"), max_length=160)
            outcome = _text(item.get("outcome"), max_length=500)
            if not title or not outcome:
                continue
            milestones.append({
                "title": title,
                "outcome": outcome,
                "task_count": _integer(
                    item.get("task_count"),
                    1,
                    1,
                    MAX_TASKS_PER_MILESTONE,
                ),
            })
    if not milestones:
        raise AIPlannerResponseError("The AI plan shape did not include milestones")
    complexity = value.get("complexity")
    if complexity not in {"compact", "moderate", "complex"}:
        complexity = "moderate"
    return {
        "complexity": complexity,
        "rationale": _text(value.get("rationale"), max_length=500),
        "milestones": milestones,
        "routine_count": _integer(
            value.get("routine_count"),
            0,
            0,
            MAX_ROUTINES,
        ),
    }


def _normalize_question(value: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    question = _text(value.get("question"), max_length=240)
    if not question:
        return None
    answer_type = value.get("answer_type")
    if answer_type not in {"text", "number", "date", "choice"}:
        answer_type = "text"
    options = [
        _text(option, max_length=100)
        for option in value.get("options", [])[:6]
        if _text(option, max_length=100)
    ] if isinstance(value.get("options"), list) else []
    if answer_type == "choice" and not options:
        answer_type = "text"
    return {
        "id": _text(value.get("id"), f"question_{index + 1}", 50),
        "question": question,
        "answer_type": answer_type,
        "placeholder": _text(value.get("placeholder"), max_length=160),
        "options": options,
    }


def _normalize_task_steps(value: Any, maximum: int) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    steps: list[dict[str, str]] = []
    for item in value[:maximum]:
        title = (
            _text(item.get("title"), max_length=160)
            if isinstance(item, dict)
            else _text(item, max_length=160)
        )
        if not title:
            continue
        steps.append({
            "title": title,
            "description": (
                _text(item.get("description"), max_length=500)
                if isinstance(item, dict)
                else ""
            ),
        })
    return steps


def _normalize_task_todos(
    value: Any,
    maximum: int,
    shared_repeat_interval: Any,
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    todos: list[dict[str, str]] = []
    for item in value[:maximum]:
        title = (
            _text(item.get("title"), max_length=160)
            if isinstance(item, dict)
            else _text(item, max_length=160)
        )
        if not title:
            continue
        repeat_interval = (
            item.get("repeat_interval")
            if isinstance(item, dict)
            else shared_repeat_interval
        )
        if repeat_interval not in {"daily", "weekly", "monthly"}:
            repeat_interval = "weekly"
        todos.append({
            "title": title,
            "description": (
                _text(item.get("description"), max_length=500)
                if isinstance(item, dict)
                else ""
            ),
            "repeat_interval": repeat_interval,
        })
    return todos


def _normalize_planner_task(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    title = _text(value.get("title"), max_length=160)
    if not title:
        return None
    return {
        "title": title,
        "description": _text(value.get("description"), max_length=500),
        "success_criteria": _text(
            value.get("success_criteria"),
            f"{title} is demonstrably complete.",
            500,
        ),
        "subtasks": _normalize_task_steps(
            value.get("subtasks"),
            MAX_SUBTASKS_PER_TASK,
        ),
        "todos": _normalize_task_todos(
            value.get("todos"),
            MAX_TODOS_PER_TASK,
            value.get("todo_repeat_interval"),
        ),
        "kind": "challenge" if value.get("kind") == "challenge" or value.get("todos") else "project",
        "tracking_mode": value.get("tracking_mode") if value.get("tracking_mode") in {"bounded", "staged"} else "none",
        "routine_series_key": _text(value.get("routine_series_key"), max_length=120),
        "stage_order": _integer(value.get("stage_order"), 1, 1, 20),
        "required_done": _integer(value.get("required_done"), 7, 0, 3650),
        "window_days": _integer(value.get("window_days"), 7, 0, 3650),
    }


def _planner_task_to_blueprint(task: dict[str, Any], priority: str, *, active: bool) -> dict[str, Any]:
    is_challenge = task["kind"] == "challenge" and bool(task["todos"])
    tracking_mode = task["tracking_mode"] if task["tracking_mode"] in {"bounded", "staged"} else "bounded"
    return {
        "title": task["title"],
        "description": task["description"],
        "success_criteria": task["success_criteria"],
        "kind": "challenge" if is_challenge else "project",
        "scope": "milestone",
        "priority": priority,
        "status": "started" if is_challenge and active else "outstanding",
        "completion_rule": {
            "type": "consistency",
            "label": task["title"],
            "required_done": max(1, task["required_done"] or 7),
            "window_days": max(1, task["window_days"] or 7),
        } if is_challenge else {"type": "structural"},
        "subtasks": [
            {
                "title": step["title"],
                "description": step["description"],
                "priority": priority,
                "status": "outstanding",
            }
            for step in task["subtasks"]
        ],
        "todos": [
            {
                "title": todo["title"],
                "description": todo["description"],
                "repeat_interval": todo["repeat_interval"],
                "priority": priority,
                "status": "outstanding",
                "tracking_mode": tracking_mode,
                "tracking_state": "active" if active else "planned",
                "routine_series_key": task["routine_series_key"] or None,
                "stage_order": task["stage_order"],
            }
            for todo in task["todos"]
        ],
    }


def _normalize_draft(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AIPlannerResponseError("The AI response did not include a goal draft")

    title = _text(value.get("title"), max_length=200)
    success_criteria = _text(value.get("success_criteria"), max_length=800)
    if not title or not success_criteria:
        raise AIPlannerResponseError("The AI draft is missing a title or success criteria")

    priority = value.get("priority")
    if priority not in {"low", "medium", "high"}:
        priority = "medium"
    duration_days = _integer(value.get("duration_days"), 84, 7, 3650)

    milestones: list[dict[str, Any]] = []
    raw_milestones = value.get("milestones") if isinstance(value.get("milestones"), list) else []
    for index, item in enumerate(raw_milestones[:MAX_MILESTONES]):
        if not isinstance(item, dict):
            continue
        milestone_title = _text(item.get("title"), max_length=160)
        if not milestone_title:
            continue
        raw_tasks = item.get("tasks") if isinstance(item.get("tasks"), list) else []
        tasks = []
        for task in raw_tasks[:MAX_TASKS_PER_MILESTONE]:
            normalized_task = _normalize_planner_task(task)
            if normalized_task:
                tasks.append(normalized_task)
        if not tasks:
            fallback_title = f"Define the next action for {milestone_title}"
            tasks = [{
                "title": fallback_title,
                "description": "",
                "success_criteria": f"A concrete next action for {milestone_title} is defined.",
                "subtasks": [],
                "todos": [],
                "kind": "project",
                "tracking_mode": "none",
                "routine_series_key": "",
                "stage_order": 1,
                "required_done": 0,
                "window_days": 0,
            }]
        default_due = round(duration_days * (index + 1) / max(1, len(raw_milestones)))
        milestones.append({
            "title": milestone_title,
            "description": _text(item.get("description"), max_length=500),
            "success_criteria": _text(
                item.get("success_criteria"),
                f"{milestone_title} is demonstrably complete.",
                500,
            ),
            "due_day": _integer(item.get("due_day"), default_due, 1, duration_days),
            "tasks": tasks,
        })
    if not milestones:
        raise AIPlannerResponseError("The AI draft did not include any usable milestones")
    milestones.sort(key=lambda milestone: milestone["due_day"])

    routines: list[dict[str, str]] = []
    raw_routines = value.get("routines") if isinstance(value.get("routines"), list) else []
    for item in raw_routines[:MAX_ROUTINES]:
        if not isinstance(item, dict):
            continue
        routine_title = _text(item.get("title"), max_length=160)
        if not routine_title:
            continue
        repeat_interval = item.get("repeat_interval")
        if repeat_interval not in {"daily", "weekly", "monthly"}:
            repeat_interval = "weekly"
        routines.append({
            "title": routine_title,
            "description": _text(item.get("description"), max_length=500),
            "repeat_interval": repeat_interval,
        })

    # The model is instructed not to repeat a stable goal routine inside a
    # milestone task, but enforce that invariant deterministically as well.
    # Otherwise one behavior becomes two TodoDefinitions and Today asks the
    # user to check the same action twice.
    goal_routine_titles = {routine["title"].casefold() for routine in routines}
    if goal_routine_titles:
        for milestone in milestones:
            for task in milestone["tasks"]:
                task["todos"] = [
                    todo
                    for todo in task["todos"]
                    if todo["title"].casefold() not in goal_routine_titles
                ]

    metric: dict[str, Any] | None = None
    raw_metric = value.get("metric")
    if isinstance(raw_metric, dict) and _text(raw_metric.get("name"), max_length=100):
        start_value = _number(raw_metric.get("start_value"), 0)
        target_value = _number(raw_metric.get("target_value"), 1)
        if start_value != target_value:
            direction = "decrease" if target_value < start_value else "increase"
            metric = {
                "name": _text(raw_metric.get("name"), max_length=100),
                "unit": _text(raw_metric.get("unit"), max_length=32),
                "start_value": start_value,
                "target_value": target_value,
                "direction": direction,
            }

    return {
        "title": title,
        "description": _text(value.get("description"), max_length=1200),
        "success_criteria": success_criteria,
        "priority": priority,
        "duration_days": duration_days,
        "metric": metric,
        "milestones": milestones,
        "routines": routines,
    }


def draft_to_blueprint(draft: dict[str, Any]) -> dict[str, Any]:
    metric = draft.get("metric") if isinstance(draft.get("metric"), dict) else None
    completion_rule: dict[str, Any] = {"type": "structural"}
    metrics: list[dict[str, Any]] = []
    if metric:
        completion_rule = {
            "type": "metric_target",
            "metric_name": metric["name"],
            "start_value": metric["start_value"],
            "current_value": metric["start_value"],
            "target_value": metric["target_value"],
            "direction": metric["direction"],
        }
        metrics.append({
            "name": metric["name"],
            "unit": metric.get("unit") or None,
            "input_type": "number",
            "show_on_today": True,
        })

    return {
        "schema_version": 3,
        "source": {"type": "scratch", "source_title": "AI-assisted plan"},
        "status": "started",
        "priority": draft["priority"],
        "duration_days": draft["duration_days"],
        "success_criteria": draft["success_criteria"],
        "completion_rule": completion_rule,
        "journey_theme_id": "mountain",
        "metrics": metrics,
        "goal_tasks": [
            {
                "title": routine["title"],
                "description": routine["description"],
                "kind": "routine",
                "scope": "goal",
                "priority": draft["priority"],
                "status": "started",
                "todos": [{
                    "title": routine["title"],
                    "description": routine["description"],
                    "repeat_interval": routine["repeat_interval"],
                    "priority": draft["priority"],
                    "status": "outstanding",
                    "tracking_mode": "ongoing",
                    "tracking_state": "active",
                }],
            }
            for routine in draft["routines"]
        ],
        "milestones": [
            {
                "title": milestone["title"],
                "description": milestone["description"],
                "success_criteria": milestone["success_criteria"],
                "status": "started" if milestone_index == 0 else "outstanding",
                "priority": draft["priority"],
                "due_date_offset_days": milestone["due_day"],
                "completion_rule": {"type": "structural"},
                "tasks": [
                    _planner_task_to_blueprint(task, draft["priority"], active=milestone_index == 0)
                    for task in milestone["tasks"]
                ],
            }
            for milestone_index, milestone in enumerate(draft["milestones"])
        ],
    }


def normalize_provider_result(result: ProviderResult) -> dict[str, Any]:
    payload = result.payload
    if not isinstance(payload, dict):
        raise AIPlannerResponseError("The AI provider returned an invalid response")

    assumptions = [
        _text(item, max_length=240)
        for item in payload.get("assumptions", [])[:6]
        if _text(item, max_length=240)
    ] if isinstance(payload.get("assumptions"), list) else []
    questions = [
        normalized
        for index, item in enumerate(payload.get("questions", [])[:3])
        if (normalized := _normalize_question(item, index)) is not None
    ] if isinstance(payload.get("questions"), list) else []

    if payload.get("status") == "needs_clarification" and questions:
        return {
            "status": "needs_clarification",
            "questions": questions,
            "draft": None,
            "assumptions": assumptions,
            "meta": {"provider": result.provider, "model": result.model},
        }

    normalized_draft = _normalize_draft(payload.get("draft"))
    return {
        "status": "ready",
        "questions": [],
        "draft": {
            "title": normalized_draft["title"],
            "description": normalized_draft["description"],
            "success_criteria": normalized_draft["success_criteria"],
            "blueprint": draft_to_blueprint(normalized_draft),
        },
        "assumptions": assumptions,
        "meta": {"provider": result.provider, "model": result.model},
    }


def normalize_milestone_refinement(
    result: ProviderResult,
    *,
    blueprint: dict[str, Any],
    milestone_index: int,
) -> dict[str, Any]:
    milestones = blueprint.get("milestones")
    if not isinstance(milestones, list) or not 0 <= milestone_index < len(milestones):
        raise AIPlannerResponseError("The milestone to regenerate no longer exists")
    current = milestones[milestone_index]
    if not isinstance(current, dict):
        raise AIPlannerResponseError("The milestone to regenerate is invalid")
    raw = result.payload.get("milestone") if isinstance(result.payload, dict) else None
    if not isinstance(raw, dict):
        raise AIPlannerResponseError("The AI response did not include a replacement milestone")

    title = _text(raw.get("title"), max_length=160)
    success_criteria = _text(raw.get("success_criteria"), max_length=500)
    if not title or not success_criteria:
        raise AIPlannerResponseError("The replacement milestone is missing required details")

    raw_tasks = raw.get("tasks") if isinstance(raw.get("tasks"), list) else []
    tasks = []
    for task in raw_tasks[:MAX_TASKS_PER_MILESTONE]:
        normalized_task = _normalize_planner_task(task)
        if normalized_task:
            tasks.append(_planner_task_to_blueprint(
                normalized_task,
                blueprint.get("priority") or current.get("priority") or "medium",
                active=current.get("status") in {"started", "in progress"},
            ))
    if not tasks:
        raise AIPlannerResponseError("The replacement milestone did not include any usable tasks")

    duration_days = _integer(blueprint.get("duration_days"), 84, 1, 3650)
    current_due = _integer(current.get("due_date_offset_days"), 1, 1, duration_days)
    previous_due = 0
    if milestone_index > 0 and isinstance(milestones[milestone_index - 1], dict):
        previous_due = _integer(milestones[milestone_index - 1].get("due_date_offset_days"), 0, 0, duration_days)
    next_due = duration_days + 1
    if milestone_index + 1 < len(milestones) and isinstance(milestones[milestone_index + 1], dict):
        next_due = _integer(
            milestones[milestone_index + 1].get("due_date_offset_days"),
            duration_days + 1,
            1,
            duration_days + 1,
        )
    lower_bound = previous_due + 1
    upper_bound = next_due - 1
    due_day = current_due if lower_bound > upper_bound else _integer(
        raw.get("due_day"), current_due, lower_bound, upper_bound,
    )

    assumptions = [
        _text(item, max_length=240)
        for item in result.payload.get("assumptions", [])[:4]
        if _text(item, max_length=240)
    ] if isinstance(result.payload.get("assumptions"), list) else []
    return {
        "milestone": {
            "title": title,
            "description": _text(raw.get("description"), max_length=500),
            "success_criteria": success_criteria,
            "status": current.get("status") or "outstanding",
            "priority": current.get("priority") or blueprint.get("priority") or "medium",
            "due_date_offset_days": due_day,
            "completion_rule": {"type": "structural"},
            "tasks": tasks,
        },
        "assumptions": assumptions,
        "meta": {"provider": result.provider, "model": result.model},
    }


def _extract_output_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise AIPlannerResponseError("The AI provider declined this planning request")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise AIPlannerResponseError("The AI provider returned no usable plan")


def _extract_usage(response: dict[str, Any]) -> tuple[int, int, int]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return 0, 0, 0

    def token_count(name: str) -> int:
        value = usage.get(name)
        return value if isinstance(value, int) and value >= 0 else 0

    input_tokens = token_count("input_tokens")
    output_tokens = token_count("output_tokens")
    total_tokens = token_count("total_tokens") or input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


class _GoalPlanRequestMixin:
    def _request_structured(
        self,
        *,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str,
        input_payload: dict[str, Any],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ProviderResult:
        raise NotImplementedError

    def generate(
        self,
        *,
        intent: str,
        answers: list[dict[str, str]],
        locale: str,
        safety_identifier: str,
    ) -> ProviderResult:
        horizon_days = _infer_horizon_days(intent, answers)
        planning_context = _planning_context(horizon_days)
        ready_only = bool(answers)
        shape_result: ProviderResult | None = None
        plan_shape: dict[str, Any] | None = None
        if ready_only:
            shape_result = self._request_structured(
                schema_name="tasknest_goal_plan_shape",
                schema=PLAN_SHAPE_SCHEMA,
                instructions=PLAN_SHAPE_INSTRUCTIONS,
                input_payload={
                    "locale": locale,
                    "intent": intent,
                    "clarification_answers": answers,
                    "planning_context": planning_context,
                },
                safety_identifier=safety_identifier,
                max_output_tokens=1800,
            )
            plan_shape = _normalize_plan_shape(shape_result.payload)

        plan_schema = _goal_plan_schema(ready_only=ready_only)
        if ready_only and plan_shape:
            milestone_schema = plan_schema["properties"]["milestones"]
            milestone_count = len(plan_shape["milestones"])
            milestone_schema["minItems"] = milestone_count
            milestone_schema["maxItems"] = milestone_count
        result = self._request_structured(
            schema_name="tasknest_goal_plan",
            schema=plan_schema,
            instructions=PLANNER_INSTRUCTIONS,
            input_payload={
                "locale": locale,
                "intent": intent,
                "clarification_answers": answers,
                "planning_context": planning_context,
                "plan_shape": plan_shape,
                "response_mode": "ready" if ready_only else "clarify_or_ready",
            },
            safety_identifier=safety_identifier,
            max_output_tokens=6000,
        )
        if not ready_only:
            return result
        shape_input_tokens = shape_result.input_tokens if shape_result else 0
        shape_output_tokens = shape_result.output_tokens if shape_result else 0
        shape_total_tokens = shape_result.total_tokens if shape_result else 0
        shape_note = ""
        if plan_shape:
            selected_tasks = sum(
                milestone["task_count"]
                for milestone in plan_shape["milestones"]
            )
            reference = planning_context.get("reference_milestone_range")
            reference_note = (
                f" Soft reference: {reference['from']}-{reference['to']} milestones."
                if isinstance(reference, dict)
                else ""
            )
            note_prefix = (
                f"Plan shape: {len(plan_shape['milestones'])} milestones, "
                f"{selected_tasks} tasks.{reference_note}"
            )
            rationale = plan_shape["rationale"]
            rationale_limit = max(0, 239 - len(note_prefix))
            if len(rationale) > rationale_limit:
                rationale = f"{rationale[:max(0, rationale_limit - 1)].rstrip()}…"
            shape_note = f"{note_prefix} {rationale}".strip()
        return ProviderResult(
            payload={
                "status": "ready",
                "questions": [],
                "draft": result.payload,
                "assumptions": [shape_note] if shape_note else [],
            },
            provider=result.provider,
            model=result.model,
            input_tokens=shape_input_tokens + result.input_tokens,
            output_tokens=shape_output_tokens + result.output_tokens,
            total_tokens=shape_total_tokens + result.total_tokens,
        )

    def refine_milestone(
        self,
        *,
        intent: str,
        answers: list[dict[str, str]],
        draft: dict[str, Any],
        milestone_index: int,
        instruction: str,
        locale: str,
        safety_identifier: str,
    ) -> ProviderResult:
        blueprint = draft.get("blueprint") if isinstance(draft.get("blueprint"), dict) else {}
        milestones = blueprint.get("milestones") if isinstance(blueprint.get("milestones"), list) else []
        current = milestones[milestone_index] if 0 <= milestone_index < len(milestones) else None
        previous = milestones[milestone_index - 1] if milestone_index > 0 else None
        following = milestones[milestone_index + 1] if milestone_index + 1 < len(milestones) else None
        return self._request_structured(
            schema_name="tasknest_milestone_refinement",
            schema=MILESTONE_REFINEMENT_RESPONSE_SCHEMA,
            instructions=MILESTONE_REFINEMENT_INSTRUCTIONS,
            input_payload={
                "locale": locale,
                "original_intent": intent,
                "clarification_answers": answers,
                "goal": {
                    "title": draft.get("title"),
                    "description": draft.get("description"),
                    "success_criteria": draft.get("success_criteria"),
                    "duration_days": blueprint.get("duration_days"),
                },
                "refinement_instruction": instruction,
                "milestone_index": milestone_index,
                "previous_milestone": previous,
                "milestone_to_replace": current,
                "next_milestone": following,
            },
            safety_identifier=safety_identifier,
            max_output_tokens=2200,
        )


class OpenAIResponsesGoalPlanProvider(_GoalPlanRequestMixin):
    provider_name = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_GOAL_MODEL", "gpt-5.6-terra").strip() or "gpt-5.6-terra"
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.timeout = _integer(os.getenv("OPENAI_TIMEOUT_SECONDS"), 60, 10, 180)

    def _request_structured(
        self,
        *,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str,
        input_payload: dict[str, Any],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ProviderResult:
        if not self.api_key:
            raise AIPlannerNotConfigured("AI planning is not configured on this server")

        body = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": max_output_tokens,
            "safety_identifier": safety_identifier,
            "instructions": instructions,
            "input": json.dumps(input_payload, ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        request = urllib_request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=self.timeout) as response:
                provider_response = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            if exc.code == 401:
                raise AIPlannerNotConfigured("The server AI key was rejected") from exc
            if exc.code == 429:
                raise AIPlannerUnavailable("AI planning is busy. Please try again shortly") from exc
            raise AIPlannerUnavailable("AI planning is temporarily unavailable") from exc
        except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
            raise AIPlannerUnavailable("AI planning timed out. Please try again") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIPlannerResponseError("The AI provider returned an unreadable response") from exc

        input_tokens, output_tokens, total_tokens = _extract_usage(provider_response)
        try:
            output_text = _extract_output_text(provider_response)
            payload = json.loads(output_text)
        except AIPlannerResponseError as exc:
            raise AIPlannerResponseError(
                str(exc),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ) from exc
        except json.JSONDecodeError as exc:
            raise AIPlannerResponseError(
                "The AI provider returned malformed structured output",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ) from exc
        return ProviderResult(
            payload=payload,
            provider=self.provider_name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


def _gemini_response_schema(value: Any) -> Any:
    """Keep Gemini's schema small; normalizers enforce discarded limits."""
    if isinstance(value, list):
        return [_gemini_response_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    # Gemini accepts many of these JSON Schema keywords individually, but the
    # complete goal tree crosses its schema-complexity limit when they are
    # repeated through nested milestone/task/action arrays.
    # Preserve only density constraints dynamically raised to at least two.
    # This keeps long-horizon milestone/task counts enforceable without pushing
    # the full response (questions, routines, steps) over Gemini's complexity cap.
    keep_cardinality = isinstance(value.get("minItems"), int) and value["minItems"] >= 2
    unsupported = {
        "additionalProperties",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
    }
    if not keep_cardinality:
        unsupported.update({"minItems", "maxItems"})
    return {
        key: _gemini_response_schema(item)
        for key, item in value.items()
        if key not in unsupported
    }


def _extract_gemini_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            continue
        for part in parts:
            if (
                isinstance(part, dict)
                and not part.get("thought")
                and isinstance(part.get("text"), str)
                and part["text"].strip()
            ):
                return part["text"]

    feedback = response.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        raise AIPlannerResponseError("The AI provider declined this planning request")
    blocked_finishes = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}
    if any(
        isinstance(candidate, dict) and candidate.get("finishReason") in blocked_finishes
        for candidate in candidates
    ):
        raise AIPlannerResponseError("The AI provider declined this planning request")
    raise AIPlannerResponseError("The AI provider returned no usable plan")


def _extract_gemini_usage(response: dict[str, Any]) -> tuple[int, int, int]:
    usage = response.get("usageMetadata")
    if not isinstance(usage, dict):
        return 0, 0, 0

    def token_count(name: str) -> int:
        value = usage.get(name)
        return value if isinstance(value, int) and value >= 0 else 0

    input_tokens = token_count("promptTokenCount")
    output_tokens = token_count("candidatesTokenCount") + token_count("thoughtsTokenCount")
    total_tokens = token_count("totalTokenCount") or input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


class GeminiGenerateContentGoalPlanProvider(_GoalPlanRequestMixin):
    provider_name = "gemini"

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = (
            os.getenv("GEMINI_GOAL_MODEL", "gemini-3.1-flash-lite").strip()
            or "gemini-3.1-flash-lite"
        )
        self.base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/")
        self.timeout = _integer(os.getenv("GEMINI_TIMEOUT_SECONDS"), 60, 10, 180)

    def _request_structured(
        self,
        *,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str,
        input_payload: dict[str, Any],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ProviderResult:
        del schema_name, safety_identifier
        if not self.api_key:
            raise AIPlannerNotConfigured("AI planning is not configured on this server")

        body = {
            "store": False,
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{
                "role": "user",
                "parts": [{"text": json.dumps(input_payload, ensure_ascii=False)}],
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _gemini_response_schema(schema),
                "maxOutputTokens": max_output_tokens,
                "temperature": 0.3,
            },
        }
        request = urllib_request.Request(
            f"{self.base_url}/models/{self.model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=self.timeout) as response:
                provider_response = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            if exc.code in {401, 403, 404}:
                raise AIPlannerNotConfigured("The Gemini server configuration was rejected") from exc
            if exc.code == 429:
                raise AIPlannerUnavailable("AI planning is busy. Please try again shortly") from exc
            raise AIPlannerUnavailable("AI planning is temporarily unavailable") from exc
        except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
            raise AIPlannerUnavailable("AI planning timed out. Please try again") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIPlannerResponseError("The AI provider returned an unreadable response") from exc

        input_tokens, output_tokens, total_tokens = _extract_gemini_usage(provider_response)
        try:
            output_text = _extract_gemini_text(provider_response)
            payload = json.loads(output_text)
        except AIPlannerResponseError as exc:
            raise AIPlannerResponseError(
                str(exc),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ) from exc
        except json.JSONDecodeError as exc:
            raise AIPlannerResponseError(
                "The AI provider returned malformed structured output",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ) from exc
        return ProviderResult(
            payload=payload,
            provider=self.provider_name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


def get_goal_plan_provider() -> GoalPlanProvider:
    provider_name = os.getenv("AI_GOAL_PROVIDER", "gemini").strip().lower()
    if provider_name in {"gemini", "google"}:
        return GeminiGenerateContentGoalPlanProvider()
    if provider_name == "openai":
        return OpenAIResponsesGoalPlanProvider()
    raise AIPlannerNotConfigured(f"Unsupported AI goal provider: {provider_name}")


def ai_goal_planner_config() -> dict[str, Any]:
    provider_name = os.getenv("AI_GOAL_PROVIDER", "gemini").strip().lower()
    if provider_name in {"gemini", "google"}:
        provider_name = "gemini"
        enabled = bool(os.getenv("GEMINI_API_KEY", "").strip())
    else:
        enabled = provider_name == "openai" and bool(os.getenv("OPENAI_API_KEY", "").strip())
    return {"enabled": enabled, "profile": "Thoughtful plan", "provider": provider_name}
