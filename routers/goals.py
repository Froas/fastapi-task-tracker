from fastapi import APIRouter, HTTPException, Depends
from models import Goal, GoalBase, User
from routers.users import get_current_user
from sqlmodel import Session, select
from db import get_session
import uuid


goals_router = APIRouter()

@goals_router.get('/user/goals')
async def goal(
    session: Session = Depends(get_session)
) -> list[Goal]:
    goal_list = session.exec(select(Goal)).all()
    return goal_list

@goals_router.post('/user/goals')
async def goal(
    goal_data: GoalBase,
    current_user: User = Depends(get_current_user),
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


@goals_router.get('/user/goals/{goal_id}')
async def event(
    goal_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Event has not found")
    return goal

@goals_router.delete('/user/goals/{goal_id}/delete')
async def event(
    goal_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal has not found")
    session.delete(goal)
    session.commit()
    return {"message": "Goal has been deleted successfully"}