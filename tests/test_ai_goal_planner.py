import json
import os
import unittest
from unittest.mock import MagicMock, patch

from services.ai_goal_planner import (
    GeminiGenerateContentGoalPlanProvider,
    ProviderResult,
    _GoalPlanRequestMixin,
    _extract_gemini_usage,
    _extract_usage,
    _gemini_response_schema,
    _goal_plan_schema,
    _infer_horizon_days,
    _normalize_draft,
    _normalize_plan_shape,
    _planning_context,
    ai_goal_planner_config,
    get_goal_plan_provider,
    normalize_milestone_refinement,
    normalize_provider_result,
)


class AIGoalPlannerTests(unittest.TestCase):
    def test_goal_routines_are_not_duplicated_as_milestone_todos(self):
        draft = _normalize_draft({
            "title": "Recovery OS",
            "success_criteria": "The recovery floor is stable.",
            "duration_days": 30,
            "priority": "high",
            "metric": None,
            "routines": [{
                "title": "Phone outside bedroom",
                "repeat_interval": "daily",
            }],
            "milestones": [{
                "title": "Stabilize inputs",
                "due_day": 7,
                "tasks": [{
                    "title": "Build the sleep guardrail",
                    "success_criteria": "The guardrail runs for a week.",
                    "subtasks": [],
                    "todos": [
                        {"title": "Phone outside bedroom", "repeat_interval": "daily"},
                        {"title": "Set shutdown alarm", "repeat_interval": "daily"},
                    ],
                }],
            }],
        })

        self.assertEqual(
            [todo["title"] for todo in draft["milestones"][0]["tasks"][0]["todos"]],
            ["Set shutdown alarm"],
        )

    def test_gemini_is_the_default_provider_when_configured(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            provider = get_goal_plan_provider()
            self.assertIsInstance(provider, GeminiGenerateContentGoalPlanProvider)
            self.assertEqual(provider.model, "gemini-3.1-flash-lite")
            self.assertEqual(
                ai_goal_planner_config(),
                {"enabled": True, "profile": "Thoughtful plan", "provider": "gemini"},
            )

    def test_gemini_schema_keeps_only_density_cardinality_constraints(self):
        schema = _gemini_response_schema({
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string", "minLength": 1, "maxLength": 100},
                "items": {"type": "array", "minItems": 1, "maxItems": 3},
                "dense_items": {"type": "array", "minItems": 6, "maxItems": 8},
            },
        })
        self.assertEqual(schema["properties"]["title"], {"type": "string"})
        self.assertEqual(schema["properties"]["items"], {"type": "array"})
        self.assertEqual(schema["properties"]["dense_items"], {
            "type": "array",
            "minItems": 6,
            "maxItems": 8,
        })
        self.assertNotIn("additionalProperties", schema)

    def test_horizon_is_context_without_forcing_entity_counts(self):
        self.assertEqual(_infer_horizon_days("Become CTO within five years", []), 1825)
        self.assertEqual(_infer_horizon_days("Finish in 60 weeks", []), 420)
        self.assertEqual(
            _planning_context(74)["reference_milestone_range"],
            {"from": 2, "to": 4},
        )
        self.assertEqual(
            _planning_context(425)["reference_milestone_range"],
            {"from": 5, "to": 8},
        )
        self.assertTrue(_planning_context(1825)["reference_only"])
        schema = _goal_plan_schema(ready_only=True)
        milestones = schema["properties"]["milestones"]
        self.assertEqual((milestones["minItems"], milestones["maxItems"]), (1, 12))
        self.assertEqual(milestones["items"]["properties"]["tasks"]["minItems"], 1)

    def test_ai_plan_shape_chooses_entity_counts_before_generation(self):
        shape = _normalize_plan_shape({
            "complexity": "complex",
            "rationale": "The goal spans technical, people, and business leadership.",
            "milestones": [
                {
                    "title": "Lead technical strategy",
                    "outcome": "Architecture decisions are adopted across teams.",
                    "task_count": 3,
                },
                {
                    "title": "Own business outcomes",
                    "outcome": "A roadmap is tied to commercial metrics.",
                    "task_count": 2,
                },
            ],
            "routine_count": 2,
        })
        self.assertEqual(len(shape["milestones"]), 2)
        self.assertEqual(shape["milestones"][0]["task_count"], 3)
        self.assertEqual(shape["routine_count"], 2)

    def test_answered_request_sizes_then_generates_the_selected_shape(self):
        class FakeProvider(_GoalPlanRequestMixin):
            def __init__(self):
                self.calls = []

            def _request_structured(self, **kwargs):
                self.calls.append(kwargs)
                if kwargs["schema_name"] == "tasknest_goal_plan_shape":
                    return ProviderResult(
                        provider="test",
                        model="test-model",
                        payload={
                            "complexity": "moderate",
                            "rationale": "Two independently verifiable transitions.",
                            "milestones": [
                                {"title": "Design", "outcome": "Design approved.", "task_count": 1},
                                {"title": "Ship", "outcome": "App deployed.", "task_count": 1},
                            ],
                            "routine_count": 0,
                        },
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                    )
                return ProviderResult(
                    provider="test",
                    model="test-model",
                    payload={
                        "title": "Ship an app",
                        "description": "Build and deploy a focused application.",
                        "success_criteria": "The application is deployed.",
                        "priority": "high",
                        "duration_days": 74,
                        "metric": None,
                        "milestones": [
                            {
                                "title": "Design",
                                "description": "Define the product.",
                                "success_criteria": "Design approved.",
                                "due_day": 20,
                                "tasks": [{
                                    "title": "Create wireframes",
                                    "description": "",
                                    "success_criteria": "Wireframes are reviewed.",
                                    "subtasks": [],
                                    "todos": [],
                                    "todo_repeat_interval": "none",
                                }],
                            },
                            {
                                "title": "Ship",
                                "description": "Release the product.",
                                "success_criteria": "App deployed.",
                                "due_day": 74,
                                "tasks": [{
                                    "title": "Deploy the app",
                                    "description": "",
                                    "success_criteria": "Deployment is reachable.",
                                    "subtasks": [],
                                    "todos": [],
                                    "todo_repeat_interval": "none",
                                }],
                            },
                        ],
                        "routines": [],
                    },
                    input_tokens=20,
                    output_tokens=30,
                    total_tokens=50,
                )

        provider = FakeProvider()
        result = provider.generate(
            intent="Ship a small app in 74 days",
            answers=[{"question_id": "scope", "question": "Scope?", "value": "MVP"}],
            locale="en",
            safety_identifier="test-user",
        )
        self.assertEqual(len(provider.calls), 2)
        plan_call = provider.calls[1]
        milestone_schema = plan_call["schema"]["properties"]["milestones"]
        self.assertEqual((milestone_schema["minItems"], milestone_schema["maxItems"]), (2, 2))
        self.assertEqual(len(plan_call["input_payload"]["plan_shape"]["milestones"]), 2)
        self.assertEqual(result.payload["status"], "ready")
        self.assertIn("2 milestones, 2 tasks", result.payload["assumptions"][0])
        self.assertIn("Soft reference: 2-4 milestones", result.payload["assumptions"][0])
        self.assertEqual((result.input_tokens, result.output_tokens, result.total_tokens), (30, 35, 65))

    def test_extracts_gemini_token_usage_including_thoughts(self):
        self.assertEqual(
            _extract_gemini_usage({
                "usageMetadata": {
                    "promptTokenCount": 20,
                    "candidatesTokenCount": 17,
                    "thoughtsTokenCount": 5,
                    "totalTokenCount": 42,
                },
            }),
            (20, 22, 42),
        )

    def test_gemini_provider_requests_structured_json_without_storage(self):
        provider_response = {
            "candidates": [{
                "content": {"parts": [{"text": json.dumps({"ok": True})}]},
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 4,
                "totalTokenCount": 14,
            },
        }
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps(provider_response).encode("utf-8")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            provider = GeminiGenerateContentGoalPlanProvider()
            with patch("services.ai_goal_planner.urllib_request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value = fake_response
                result = provider._request_structured(
                    schema_name="test_schema",
                    schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
                    instructions="Return JSON.",
                    input_payload={"intent": "test"},
                    safety_identifier="hashed-user",
                    max_output_tokens=100,
                )

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertFalse(body["store"])
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        self.assertEqual(result.payload, {"ok": True})
        self.assertEqual((result.input_tokens, result.output_tokens, result.total_tokens), (10, 4, 14))

    def test_extracts_responses_api_token_usage(self):
        self.assertEqual(
            _extract_usage({
                "usage": {"input_tokens": 36, "output_tokens": 87, "total_tokens": 123},
            }),
            (36, 87, 123),
        )

    def test_clarification_is_limited_and_has_no_draft(self):
        result = normalize_provider_result(ProviderResult(
            provider="test",
            model="test-model",
            payload={
                "status": "needs_clarification",
                "questions": [{
                    "id": "deadline",
                    "question": "When should this be complete?",
                    "answer_type": "date",
                    "placeholder": "YYYY-MM-DD",
                    "options": [],
                }],
                "draft": None,
                "assumptions": [],
            },
        ))
        self.assertEqual(result["status"], "needs_clarification")
        self.assertIsNone(result["draft"])
        self.assertEqual(result["questions"][0]["id"], "deadline")

    def test_ready_plan_becomes_materializable_blueprint(self):
        result = normalize_provider_result(ProviderResult(
            provider="test",
            model="test-model",
            payload={
                "status": "ready",
                "questions": [],
                "assumptions": ["Three workouts per week are realistic."],
                "draft": {
                    "title": "Run a half marathon",
                    "description": "Build endurance without overtraining.",
                    "success_criteria": "Finish a half marathon event.",
                    "priority": "high",
                    "duration_days": 120,
                    "metric": {
                        "name": "Longest run", "unit": "km", "start_value": 5,
                        "target_value": 21.1, "direction": "increase",
                    },
                    "milestones": [{
                        "title": "Build a 10 km base",
                        "description": "Increase easy mileage.",
                        "success_criteria": "Run 10 km comfortably.",
                        "due_day": 45,
                        "tasks": [{
                            "title": "Choose a training plan",
                            "description": "Select a progression that fits the schedule.",
                            "success_criteria": "An eight-week plan is saved to the calendar.",
                            "subtasks": ["Compare two beginner plans"],
                            "todos": ["Review the training week"],
                            "todo_repeat_interval": "weekly",
                        }],
                    }],
                    "routines": [{
                        "title": "Complete scheduled runs",
                        "description": "Keep most running easy.",
                        "repeat_interval": "weekly",
                    }],
                },
            },
        ))
        blueprint = result["draft"]["blueprint"]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(blueprint["schema_version"], 3)
        self.assertEqual(blueprint["success_criteria"], "Finish a half marathon event.")
        self.assertEqual(blueprint["completion_rule"]["type"], "metric_target")
        self.assertEqual(blueprint["milestones"][0]["success_criteria"], "Run 10 km comfortably.")
        self.assertEqual(blueprint["goal_tasks"][0]["kind"], "routine")
        task = blueprint["milestones"][0]["tasks"][0]
        self.assertEqual(task["kind"], "challenge")
        self.assertEqual(task["completion_rule"]["type"], "consistency")
        self.assertEqual(task["success_criteria"], "An eight-week plan is saved to the calendar.")
        self.assertEqual(task["subtasks"][0]["title"], "Compare two beginner plans")
        self.assertEqual(task["todos"][0]["title"], "Review the training week")
        self.assertEqual(task["todos"][0]["repeat_interval"], "weekly")
        self.assertEqual(task["todos"][0]["tracking_mode"], "bounded")
        self.assertEqual(task["todos"][0]["tracking_state"], "active")

    def test_long_horizon_plan_keeps_up_to_twelve_milestones(self):
        milestones = [
            {
                "title": f"Leadership stage {index}",
                "description": "Build the next leadership capability.",
                "success_criteria": f"Stage {index} evidence is reviewed.",
                "due_day": index * 140,
                "tasks": [{
                    "title": f"Complete stage {index} project",
                    "description": "Produce observable evidence.",
                    "success_criteria": "The project is reviewed.",
                    "subtasks": ["Define the project evidence"],
                    "todos": [],
                    "todo_repeat_interval": "none",
                }],
            }
            for index in range(1, 14)
        ]
        result = normalize_provider_result(ProviderResult(
            provider="test",
            model="test-model",
            payload={
                "status": "ready",
                "questions": [],
                "assumptions": [],
                "draft": {
                    "title": "Become a CTO",
                    "description": "Build technical and organizational leadership.",
                    "success_criteria": "Secure a CTO role.",
                    "priority": "high",
                    "duration_days": 1825,
                    "metric": None,
                    "milestones": milestones,
                    "routines": [],
                },
            },
        ))
        blueprint_milestones = result["draft"]["blueprint"]["milestones"]
        self.assertEqual(len(blueprint_milestones), 12)
        self.assertEqual(blueprint_milestones[-1]["title"], "Leadership stage 12")

    def test_milestone_refinement_is_clamped_between_neighbors(self):
        blueprint = {
            "duration_days": 120,
            "priority": "high",
            "milestones": [
                {"title": "Base", "due_date_offset_days": 30},
                {"title": "Distance", "due_date_offset_days": 60},
                {"title": "Race", "due_date_offset_days": 100},
            ],
        }
        result = normalize_milestone_refinement(
            ProviderResult(
                provider="test",
                model="test-model",
                payload={
                    "milestone": {
                        "title": "Run 15 km comfortably",
                        "description": "Build the long run gradually.",
                        "success_criteria": "Finish 15 km without pain.",
                        "due_day": 110,
                        "tasks": [{
                            "title": "Schedule four progressive long runs",
                            "description": "",
                            "success_criteria": "Four runs are scheduled with recovery weeks.",
                            "subtasks": ["Choose progression distances"],
                            "todos": ["Review long-run recovery"],
                            "todo_repeat_interval": "weekly",
                        }],
                    },
                    "assumptions": ["Recovery remains stable."],
                },
            ),
            blueprint=blueprint,
            milestone_index=1,
        )
        self.assertEqual(result["milestone"]["due_date_offset_days"], 99)
        self.assertEqual(result["milestone"]["tasks"][0]["scope"], "milestone")
        self.assertEqual(result["milestone"]["tasks"][0]["subtasks"][0]["title"], "Choose progression distances")
        self.assertEqual(result["milestone"]["tasks"][0]["todos"][0]["title"], "Review long-run recovery")
        self.assertEqual(result["milestone"]["tasks"][0]["todos"][0]["repeat_interval"], "weekly")
        self.assertEqual(len(blueprint["milestones"]), 3)


if __name__ == "__main__":
    unittest.main()
