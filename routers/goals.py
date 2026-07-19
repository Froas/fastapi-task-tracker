from fastapi import APIRouter, HTTPException, Depends
from models import Goal, GoalRead, GoalUpdate, GoalCreate, GoalReadNested, GoalReorderRequest, Milestone, Task, Todo, User, get_current_active_user
from sqlmodel import Session, select
from typing import Annotated
from sqlalchemy.orm import selectinload, noload
from db import get_session
import uuid
from services.completion_rules import recalculate_goal_hierarchy


goals_router = APIRouter()

@goals_router.get('/user/goals')
async def get_all_goals(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[GoalRead]:
    return session.exec(
        select(Goal).where(
            Goal.user_id == current_user.id,
            Goal.deleted_at.is_(None),
        ).order_by(Goal.position, Goal.id)
    ).all()

@goals_router.post('/user/goals')
async def get_goal(
    current_user: Annotated[User, Depends(get_current_active_user)],
    goal_data: GoalCreate,
    session: Session = Depends(get_session)
) -> GoalRead:
    max_position = session.exec(
        select(Goal.position)
        .where(
            Goal.user_id == current_user.id,
            Goal.deleted_at.is_(None),
        )
        .order_by(Goal.position.desc())
    ).first()
    goal = Goal(
        title=goal_data.title, 
        description=goal_data.description,
        success_criteria=goal_data.success_criteria,
        start_datetime=goal_data.start_datetime, 
        end_datetime=goal_data.end_datetime, 
        completion_rule=goal_data.completion_rule,
        enforce_sequential_milestones=goal_data.enforce_sequential_milestones,
        journey_theme_id=goal_data.journey_theme_id,
        journey_character_id=goal_data.journey_character_id,
        user=current_user, 
        user_id=current_user.id,
        position=(max_position or 0) + 1,
    )
    if goal_data.description:
        goal.description = goal_data.description
    if goal_data.priority:
        goal.priority = goal_data.priority
    if goal_data.status:
        goal.status = goal_data.status

    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal

@goals_router.patch('/user/goals/update', response_model=GoalRead)
async def update_goal(
    goal_data: GoalUpdate,
    currente_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)    
) -> Goal:
    goal = session.get(Goal, goal_data.id)
    if not goal or goal.user_id != currente_user.id or goal.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    update_data = goal_data.model_dump(exclude_unset=True, exclude={'id'})
    if 'status' in update_data and goal.completion_rule:
        goal.completion_rule = {**goal.completion_rule, 'auto_completed': False}
    for key, value in update_data.items():
        setattr(goal, key, value)
    session.add(goal)
    recalculate_goal_hierarchy(session, goal.id)
    session.commit()
    session.refresh(goal)
    return goal


@goals_router.put('/user/goals/reorder')
async def reorder_goals(
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: GoalReorderRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    goal_ids = payload.goal_ids
    if not goal_ids or len(set(goal_ids)) != len(goal_ids):
        raise HTTPException(status_code=400, detail="Invalid goal list provided")

    goals = session.exec(
        select(Goal).where(
            Goal.user_id == current_user.id,
            Goal.id.in_(goal_ids),
            Goal.deleted_at.is_(None),
        )
    ).all()
    if len(goals) != len(goal_ids):
        raise HTTPException(status_code=400, detail="Invalid goal list provided")

    active_ids = set(session.exec(
        select(Goal.id).where(
            Goal.user_id == current_user.id,
            Goal.deleted_at.is_(None),
        )
    ).all())
    if active_ids != set(goal_ids):
        raise HTTPException(status_code=409, detail="Goal list is stale; refresh and retry")

    by_id = {goal.id: goal for goal in goals}
    for position, goal_id in enumerate(goal_ids, start=1):
        goal = by_id[goal_id]
        goal.position = position
        session.add(goal)
    session.commit()
    return {"message": "Goals reordered successfully"}


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
    query = select(Goal).where(
        Goal.id == goal_id,
        Goal.user_id == current_user.id,
        Goal.deleted_at.is_(None),
    )
    options = []
    if query is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    if include_milestones:
        milestone_option = selectinload(
            Goal.milestones.and_(Milestone.deleted_at.is_(None))
        )
        if include_tasks:
            task_option = selectinload(
                Milestone.tasks.and_(Task.deleted_at.is_(None))
            )
            if include_subtasks:
                task_option = task_option.options(selectinload(Task.subtasks))
            else:
                task_option = task_option.options(noload(Task.subtasks))
            if include_todos:
                task_option = task_option.options(
                    selectinload(Task.todos.and_(Todo.deleted_at.is_(None)))
                )
            else:
                task_option = task_option.options(noload(Task.todos))
            milestone_option = milestone_option.options(task_option)
        else:
            milestone_option = milestone_option.options(noload(Milestone.tasks))
        options.append(milestone_option)
    else:
        options.append(noload(Goal.milestones))
    if include_tasks:
        goal_task_option = selectinload(
            Goal.tasks.and_(Task.deleted_at.is_(None), Task.scope == 'goal')
        )
        if include_subtasks:
            goal_task_option = goal_task_option.options(selectinload(Task.subtasks))
        else:
            goal_task_option = goal_task_option.options(noload(Task.subtasks))
        if include_todos:
            goal_task_option = goal_task_option.options(
                selectinload(Task.todos.and_(Todo.deleted_at.is_(None)))
            )
        else:
            goal_task_option = goal_task_option.options(noload(Task.todos))
        options.append(goal_task_option)
    else:
        options.append(noload(Goal.tasks))

    query = query.options(*options)
    goal = session.exec(query).first()
    
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.milestones = sorted(
        goal.milestones or [],
        key=lambda milestone: (milestone.position or 0, str(milestone.id)),
    )
    goal.tasks = sorted(
        goal.tasks or [],
        key=lambda task: (task.position or 0, str(task.id)),
    )
    for task in goal.tasks:
        task.subtasks = sorted(
            task.subtasks or [],
            key=lambda subtask: (subtask.position or 0, str(subtask.id)),
        )
        task.todos = sorted(
            task.todos or [],
            key=lambda todo: (todo.position or 0, str(todo.id)),
        )
    for milestone in goal.milestones:
        milestone.tasks = sorted(
            milestone.tasks or [],
            key=lambda task: (task.position or 0, str(task.id)),
        )
        for task in milestone.tasks:
            task.subtasks = sorted(
                task.subtasks or [],
                key=lambda subtask: (subtask.position or 0, str(subtask.id)),
            )
            task.todos = sorted(
                task.todos or [],
                key=lambda todo: (todo.position or 0, str(todo.id)),
            )
    return goal

@goals_router.delete('/user/goals/{goal_id}/delete')
async def delete_goal(
    current_user: Annotated[User, Depends(get_current_active_user)],
    goal_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> dict[str, str]:
    """Soft delete: sets deleted_at. Goal goes to Trash and can be restored
    via POST /user/trash/goal/{id}/restore. Hard-delete from Trash."""
    from datetime import datetime
    from utils.timezone import JST
    goal = session.get(Goal, goal_id)
    if goal is None or goal.user_id != current_user.id or goal.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.deleted_at = datetime.now(JST)
    session.add(goal)
    session.commit()
    return {"message": "Goal moved to trash"}
