from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select, or_
from typing import Annotated
from datetime import datetime, timedelta
import uuid

from models import (
    Template,
    TemplateCreate,
    TemplateUpdate,
    TemplateRead,
    TemplateInstantiate,
    Goal,
    Milestone,
    Task,
    User,
    get_current_active_user,
    StatusType,
    PriorityType,
)
from db import get_session
from utils.timezone import JST

templates_router = APIRouter()


@templates_router.get('/user/templates')
async def list_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[TemplateRead]:
    """Returns system templates (user_id IS NULL) + user's own templates."""
    rows = session.exec(
        select(Template).where(
            or_(Template.user_id.is_(None), Template.user_id == current_user.id)
        ).order_by(Template.created_at.desc())
    ).all()
    return rows


@templates_router.post('/user/templates')
async def create_template(
    current_user: Annotated[User, Depends(get_current_active_user)],
    template_data: TemplateCreate,
    session: Session = Depends(get_session),
) -> TemplateRead:
    template = Template(
        title=template_data.title,
        description=template_data.description,
        emoji=template_data.emoji,
        tags=template_data.tags,
        blueprint=template_data.blueprint,
        user_id=current_user.id,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@templates_router.patch('/user/templates/update', response_model=TemplateRead)
async def update_template(
    current_user: Annotated[User, Depends(get_current_active_user)],
    template_data: TemplateUpdate,
    session: Session = Depends(get_session),
) -> Template:
    template = session.get(Template, template_data.id)
    if template is None or template.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail="Template not found or not editable"
        )
    update_data = template_data.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in update_data.items():
        setattr(template, key, value)
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@templates_router.get('/user/templates/{template_id}')
async def get_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> TemplateRead:
    template = session.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    # System templates (user_id NULL) are readable by everyone.
    if template.user_id is not None and template.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@templates_router.delete('/user/templates/{template_id}/delete')
async def delete_template(
    current_user: Annotated[User, Depends(get_current_active_user)],
    template_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    template = session.get(Template, template_id)
    if template is None or template.user_id != current_user.id:
        raise HTTPException(
            status_code=404, detail="Template not found or not deletable"
        )
    session.delete(template)
    session.commit()
    return {"message": "Template deleted"}


@templates_router.post('/user/templates/{template_id}/instantiate')
async def instantiate_template(
    template_id: uuid.UUID,
    payload: TemplateInstantiate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> Goal:
    """Materialise a template into a real Goal with its milestone/task tree
    owned by the calling user. Returns the new Goal."""
    template = session.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.user_id is not None and template.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Template not found")

    title = payload.title_override or template.title
    start_dt = payload.start_datetime or datetime.now(JST)
    end_dt = payload.end_datetime or (start_dt + timedelta(weeks=12))

    goal = Goal(
        title=title,
        description=template.description,
        start_datetime=start_dt,
        end_datetime=end_dt,
        status=StatusType.OUTSTANDING,
        priority=PriorityType.HIGH,
        user_id=current_user.id,
    )
    session.add(goal)
    session.flush()  # populate goal.id before children

    blueprint = template.blueprint or {}
    for m_idx, m in enumerate(blueprint.get("milestones", []) or []):
        milestone = Milestone(
            title=m.get("title", f"Milestone {m_idx + 1}"),
            description=m.get("description", ""),
            position=m_idx,
            goal_id=goal.id,
            user_id=current_user.id,
        )
        session.add(milestone)
        session.flush()
        for t in m.get("tasks", []) or []:
            task = Task(
                title=t.get("title", "Task"),
                description=t.get("description", ""),
                milestone_id=milestone.id,
                user_id=current_user.id,
            )
            session.add(task)

    session.commit()
    session.refresh(goal)
    return goal
