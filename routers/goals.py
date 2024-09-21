from fastapi import APIRouter, HTTPException, Depends
from models import Goal, GoalBase, GoalUpdate, User, get_current_active_user
from sqlmodel import Session, select
from typing import Annotated
from db import get_session
import uuid


goals_router = APIRouter()

@goals_router.get('/user/goals')
async def get_all_goal(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Goal]:
    goal_list = current_user.goals
    return goal_list

@goals_router.post('/user/goals')
async def get_goal(
    current_user: Annotated[User, Depends(get_current_active_user)],
    goal_data: GoalBase,
    session: Session = Depends(get_session)
) -> Goal:
    goal = Goal(
        title=goal_data.title, 
        start_date=goal_data.start_date, 
        end_date=goal_data.end_date, 
        user=current_user, 
        user_id=current_user.id
    )
    if goal_data.description:
        goal.description = goal_data.description
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal

@goals_router.patch('/user/goals/update', response_model=Goal)
async def update_goal(
    goal_data: GoalUpdate,
    currente_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)    
) -> Goal:
    goal = session.get(Goal, goal_data.id)
    if not goal or goal.user_id != currente_user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    update_data = goal_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(goal, key, value)
    
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@goals_router.get('/user/goals/{goal_id}')
async def get_goal(
    current_user: Annotated[User, Depends(get_current_active_user)],
    goal_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal

@goals_router.delete('/user/goals/{goal_id}/delete')
async def delete_goal(
    current_user: Annotated[User, Depends(get_current_active_user)],
    goal_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> dict[str, str]:
    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Goal not found")
    session.delete(goal)
    session.commit()
    return {"message": "Goal was deleted successfully"}