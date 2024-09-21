from fastapi import APIRouter, HTTPException, Depends
from models import Milestone, MilestoneBase, MilestoneUpdate, get_current_active_user
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from typing import Annotated
import uuid

milestones_router = APIRouter()

@milestones_router.get('/user/milestones')
async def get_all_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Milestone]:
    milestone_list = current_user.milestones
    return milestone_list

@milestones_router.post('/user/milestones')
async def create_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    milestone_data: MilestoneBase,
    session: Session = Depends(get_session)
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

@milestones_router.patch('/user/milestones/update', response_model=Milestone)
async def update_milestone(
    milestone_data: MilestoneUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Milestone:
    milestone = session.get(Milestone, milestone_data.id)
    
    if not milestone or milestone.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Milestone not found')
    
    update_data = milestone_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(milestone, key, value)

    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return milestone
    

@milestones_router.get('/user/milestones/{milestone_id}')
async def get_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    milestone_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Milestone:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None or milestone.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return milestone

@milestones_router.delete('/user/milestones/{milestone_id}/delete')
async def delete_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    milestone_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None or milestone.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Milestone not found")
    session.delete(milestone)
    session.commit()
    return {"message": "Milestone was deleted successfully"}