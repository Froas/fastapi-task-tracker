from fastapi import APIRouter, HTTPException, Depends
from models import Goal, GoalBase, GoalUpdate, GoalReadNested, Milestone, Task, User, get_current_active_user
from sqlmodel import Session, select
from typing import Annotated
from sqlalchemy.orm import selectinload, noload
from db import get_session
import uuid


goals_router = APIRouter()

@goals_router.get('/user/goals')
async def get_all_goals(
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
        description=goal_data.description,
        start_datetime=goal_data.start_datetime, 
        end_datetime=goal_data.end_datetime, 
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
    session: Session = Depends(get_session),
    include_milestones: bool = False,
    include_tasks: bool = False,
    include_subtasks: bool = False,
    include_todos: bool = False
) -> GoalReadNested:
    # query = select(Goal).where(Goal.id == goal_id).where(Goal.user_id == current_user.id)
    query = select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id)
    options = []
    if query is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    if include_milestones:
        milestone_option = selectinload(Goal.milestones)
        if include_tasks:
            task_option = selectinload(Milestone.tasks)
            if include_subtasks:
                task_option = task_option.options(selectinload(Task.subtasks))
            else:
                task_option = task_option.options(noload(Task.subtasks))
            if include_todos:
                task_option = task_option.options(selectinload(Task.todos))
            else:
                task_option = task_option.options(noload(Task.todos))
            milestone_option = milestone_option.options(task_option)
        else:
            milestone_option = milestone_option.options(noload(Milestone.tasks))
        options.append(milestone_option)
    else:
        options.append(noload(Goal.milestones))

    query = query.options(*options)
    goal = session.exec(query).first()
    
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