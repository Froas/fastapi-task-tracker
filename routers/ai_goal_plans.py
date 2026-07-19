import asyncio
import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from db import get_session
from models import User, get_current_active_user
from services.ai_goal_planner import (
    AIPlannerNotConfigured,
    AIPlannerResponseError,
    AIPlannerUnavailable,
    ai_goal_planner_config,
    get_goal_plan_provider,
    normalize_milestone_refinement,
    normalize_provider_result,
)
from services.ai_usage import (
    AIAllowanceExceeded,
    finalize_ai_usage,
    get_ai_allowance,
    reserve_ai_usage,
)


ai_goal_plans_router = APIRouter()


class AIGoalPlanAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=50)
    question: str = Field(min_length=1, max_length=240)
    value: str = Field(min_length=1, max_length=1000)


class AIGoalPlanRequest(BaseModel):
    intent: str = Field(min_length=5, max_length=2000)
    answers: list[AIGoalPlanAnswer] = Field(default_factory=list, max_length=6)
    locale: Literal["en"] = "en"


class AIGoalDraftPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1200)
    success_criteria: str = Field(min_length=1, max_length=800)
    blueprint: dict


class AIGoalMilestoneRefineRequest(BaseModel):
    intent: str = Field(min_length=5, max_length=2000)
    answers: list[AIGoalPlanAnswer] = Field(default_factory=list, max_length=6)
    draft: AIGoalDraftPayload
    milestone_index: int = Field(ge=0, le=5)
    instruction: str = Field(min_length=3, max_length=500)
    locale: Literal["en"] = "en"


@ai_goal_plans_router.get('/user/ai/goal-drafts/config')
async def get_ai_goal_planner_config(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict:
    config = ai_goal_planner_config()
    config["allowance"] = get_ai_allowance(session, current_user.id).as_dict()
    return config


def _finalize_request(
    session: Session,
    usage_id,
    *,
    status: str,
    counted: bool,
    result=None,
    error_code: str | None = None,
) -> None:
    finalize_ai_usage(
        session,
        usage_id,
        status=status,
        counted=counted,
        input_tokens=result.input_tokens if result else 0,
        output_tokens=result.output_tokens if result else 0,
        total_tokens=result.total_tokens if result else 0,
        error_code=error_code,
    )


def _attach_allowance(response: dict, session: Session, user_id) -> dict:
    response.setdefault("meta", {})["allowance"] = get_ai_allowance(session, user_id).as_dict()
    return response


@ai_goal_plans_router.post('/user/ai/goal-drafts')
async def generate_ai_goal_draft(
    payload: AIGoalPlanRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict:
    usage = None
    result = None
    try:
        provider = get_goal_plan_provider()
        usage = reserve_ai_usage(
            session,
            user_id=current_user.id,
            feature="goal_plan",
            provider=provider.provider_name,
            model=provider.model,
        )
        safety_identifier = hashlib.sha256(str(current_user.id).encode("utf-8")).hexdigest()[:64]
        result = await asyncio.to_thread(
            provider.generate,
            intent=payload.intent.strip(),
            answers=[answer.model_dump() for answer in payload.answers],
            locale=payload.locale,
            safety_identifier=safety_identifier,
        )
        response = normalize_provider_result(result)
        _finalize_request(session, usage.id, status="succeeded", counted=True, result=result)
        return _attach_allowance(response, session, current_user.id)
    except AIAllowanceExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIPlannerNotConfigured as exc:
        if usage is not None:
            _finalize_request(
                session, usage.id, status="not_configured", counted=False, error_code="not_configured",
            )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIPlannerUnavailable as exc:
        if usage is not None:
            _finalize_request(
                session, usage.id, status="provider_unavailable", counted=False, error_code="provider_unavailable",
            )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIPlannerResponseError as exc:
        if usage is not None:
            _finalize_request(
                session,
                usage.id,
                status="response_error",
                counted=True,
                result=result or exc,
                error_code="response_error",
            )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        if usage is not None:
            _finalize_request(
                session, usage.id, status="internal_error", counted=False, error_code="internal_error",
            )
        raise


@ai_goal_plans_router.post('/user/ai/goal-drafts/refine-milestone')
async def refine_ai_goal_milestone(
    payload: AIGoalMilestoneRefineRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict:
    blueprint = payload.draft.blueprint
    milestones = blueprint.get("milestones") if isinstance(blueprint.get("milestones"), list) else []
    if payload.milestone_index >= len(milestones):
        raise HTTPException(status_code=400, detail="The milestone to regenerate no longer exists")
    usage = None
    result = None
    try:
        provider = get_goal_plan_provider()
        usage = reserve_ai_usage(
            session,
            user_id=current_user.id,
            feature="milestone_refinement",
            provider=provider.provider_name,
            model=provider.model,
        )
        safety_identifier = hashlib.sha256(str(current_user.id).encode("utf-8")).hexdigest()[:64]
        result = await asyncio.to_thread(
            provider.refine_milestone,
            intent=payload.intent.strip(),
            answers=[answer.model_dump() for answer in payload.answers],
            draft=payload.draft.model_dump(),
            milestone_index=payload.milestone_index,
            instruction=payload.instruction.strip(),
            locale=payload.locale,
            safety_identifier=safety_identifier,
        )
        response = normalize_milestone_refinement(
            result,
            blueprint=blueprint,
            milestone_index=payload.milestone_index,
        )
        _finalize_request(session, usage.id, status="succeeded", counted=True, result=result)
        return _attach_allowance(response, session, current_user.id)
    except AIAllowanceExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIPlannerNotConfigured as exc:
        if usage is not None:
            _finalize_request(
                session, usage.id, status="not_configured", counted=False, error_code="not_configured",
            )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIPlannerUnavailable as exc:
        if usage is not None:
            _finalize_request(
                session, usage.id, status="provider_unavailable", counted=False, error_code="provider_unavailable",
            )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIPlannerResponseError as exc:
        if usage is not None:
            _finalize_request(
                session,
                usage.id,
                status="response_error",
                counted=True,
                result=result or exc,
                error_code="response_error",
            )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        if usage is not None:
            _finalize_request(
                session, usage.id, status="internal_error", counted=False, error_code="internal_error",
            )
        raise
