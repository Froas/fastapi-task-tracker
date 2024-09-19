from fastapi import APIRouter, HTTPException, Depends
from models import Milestone, MilestoneBase
from sqlmodel import Session, select
from routers.users import User, get_current_user
from db import get_session
import uuid

milestones_router = APIRouter()

@milestones_router.get('/user/milestones')
async def milestone(
    session: Session = Depends(get_session)
) -> list[Milestone]:
    milestone_list = session.exec(select(Milestone)).all()
    return milestone_list

@milestones_router.get('/user/milestones/{milestone_id}')
async def milestone(
    milestone_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Milestone:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone has not found")
    return milestone

@milestones_router.post('/user/milestones')
async def milestone(
    milestone_data: MilestoneBase,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> Milestone:
    milestone = Milestone(
        title=milestone_data.title, 
        description=milestone_data.description, 
        due_date=milestone_data.due_date, 
        user_id=current_user.id, 
        user=current_user, 
        goal_id=milestone_data.goal_id
    )
    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return milestone


@milestones_router.delete('/user/milestones/{milestone_id}/delete')
async def milestone(
    milestone_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone has not found")
    session.delete(milestone)
    session.commit()
    return {"message": "Milestone has been deleted successfully"}