from fastapi import APIRouter, HTTPException, Depends
from models import Goal, Milestone, MilestoneBase, MilestoneRead, MilestoneReadNested, MilestoneUpdate, MilestoneReorderRequest, Task, Todo, get_current_active_user
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload, noload
from routers.users import User
from db import get_session
from typing import Annotated
from routers.visibility import active_goal_ids
from services.completion_rules import recalculate_goal_hierarchy
import uuid

milestones_router = APIRouter()

@milestones_router.get('/user/milestones')
async def get_all_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[MilestoneRead]:
    return session.exec(
        select(Milestone).where(
            Milestone.user_id == current_user.id,
            Milestone.deleted_at.is_(None),
            Milestone.goal_id.in_(active_goal_ids(current_user.id)),
        ).order_by(Milestone.goal_id, Milestone.position, Milestone.id)
    ).all()

@milestones_router.post('/user/milestones')
async def create_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    milestone_data: MilestoneBase,
    session: Session = Depends(get_session)
) -> MilestoneRead:
    if milestone_data.goal_id is None:
        raise HTTPException(status_code=400, detail='goal_id is required')
    goal = session.exec(
        select(Goal).where(
            Goal.id == milestone_data.goal_id,
            Goal.user_id == current_user.id,
            Goal.deleted_at.is_(None),
        )
    ).first()
    if goal is None:
        raise HTTPException(status_code=404, detail='Goal not found')
    max_position = session.exec(
        select(Milestone.position)
        .where(
            Milestone.goal_id == milestone_data.goal_id,
            Milestone.user_id == current_user.id,
            Milestone.deleted_at.is_(None),
        )
        .order_by(Milestone.position.desc())
    ).first()
    new_position = (max_position or 0) + 1 
    milestone = Milestone(
        title=milestone_data.title, 
        description=milestone_data.description, 
        due_date=milestone_data.due_date, 
        start_datetime=milestone_data.start_datetime,
        user_id=current_user.id, 
        user=current_user, 
        goal_id=milestone_data.goal_id,
        position=new_position,
        status=milestone_data.status,
        priority=milestone_data.priority,
        end_datetime=milestone_data.end_datetime,
        completion_rule=milestone_data.completion_rule,
    )
    session.add(milestone)
    recalculate_goal_hierarchy(session, milestone.goal_id)
    session.commit()
    session.refresh(milestone)
    return milestone

@milestones_router.patch('/user/milestones/update', response_model=MilestoneRead)
async def update_milestone(
    milestone_data: MilestoneUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Milestone:
    milestone = session.get(Milestone, milestone_data.id)
    
    if not milestone or milestone.user_id != current_user.id or milestone.deleted_at is not None:
        raise HTTPException(status_code=404, detail='Milestone not found')
    if milestone_data.goal_id is not None:
        goal = session.exec(
            select(Goal).where(
                Goal.id == milestone_data.goal_id,
                Goal.user_id == current_user.id,
                Goal.deleted_at.is_(None),
            )
        ).first()
        if goal is None:
            raise HTTPException(status_code=404, detail='Goal not found')
    
    update_data = milestone_data.model_dump(exclude_unset=True, exclude={'id'})
    if 'status' in update_data and milestone.completion_rule:
        milestone.completion_rule = {**milestone.completion_rule, 'auto_completed': False}
    for key, value in update_data.items():
        setattr(milestone, key, value)

    session.add(milestone)
    recalculate_goal_hierarchy(session, milestone.goal_id)
    session.commit()
    session.refresh(milestone)
    return milestone
    
@milestones_router.put('/user/milestones/reorder')
async def reorder_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: MilestoneReorderRequest,
    session: Session = Depends(get_session)
) -> dict:
    milestone_ids = payload.milestone_ids
    if not milestone_ids or len(set(milestone_ids)) != len(milestone_ids):
        raise HTTPException(status_code=400, detail="Invalid milestone list provided")
    milestones = session.exec(
        select(Milestone).where(
            Milestone.user_id == current_user.id,
            Milestone.id.in_(milestone_ids),
            Milestone.deleted_at.is_(None),
        )
    ).all()
    if len(milestones) != len(milestone_ids):
        raise HTTPException(status_code=400, detail="Invalid milestone list provided")
    goal_ids = {milestone.goal_id for milestone in milestones}
    if len(goal_ids) != 1:
        raise HTTPException(status_code=400, detail="Milestones must belong to one goal")
    active_ids = set(session.exec(
        select(Milestone.id).where(
            Milestone.user_id == current_user.id,
            Milestone.goal_id == milestones[0].goal_id,
            Milestone.deleted_at.is_(None),
        )
    ).all())
    if active_ids != set(milestone_ids):
        raise HTTPException(status_code=409, detail="Milestone list is stale; refresh and retry")
    by_id = {milestone.id: milestone for milestone in milestones}
    for position, milestone_id in enumerate(milestone_ids, start=1):
        milestone = by_id[milestone_id]
        milestone.position = position
        session.add(milestone)
    session.commit()
    return {"message": "Milestones reordered successfully"}

@milestones_router.get('/user/milestones/{milestone_id}')
async def get_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    milestone_id: uuid.UUID,
    include_tasks: bool = False,
    include_subtasks: bool = False,
    include_todos: bool = False,
    session: Session = Depends(get_session)
) -> MilestoneReadNested:
    
    query = select(Milestone).where(
        Milestone.user_id == current_user.id,
        Milestone.id == milestone_id,
        Milestone.deleted_at.is_(None),
        Milestone.goal_id.in_(active_goal_ids(current_user.id)),
    )
    if query is None:
        raise HTTPException(status_code=404, detail="Query not found")
    
    options = []
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
        options.append(task_option)
    else:
        options.append(noload(Milestone.tasks))
    
    query = query.options(*options)
    milestone = session.exec(query).first()

    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
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
    return milestone

@milestones_router.delete('/user/milestones/{milestone_id}/delete')
async def delete_milestone(
    current_user: Annotated[User, Depends(get_current_active_user)],
    milestone_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    # Soft delete: marks deleted_at and skips the position-shift that
    # hard-delete would have done. Restoring from Trash puts the milestone
    # back at its original position; if that position is taken, the user
    # can drag-reorder. (Position shifts on hard-delete happen in trash
    # router's purge.)
    from datetime import datetime
    from utils.timezone import JST
    milestone = session.get(Milestone, milestone_id)
    if milestone is None or milestone.user_id != current_user.id or milestone.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    milestone.deleted_at = datetime.now(JST)
    session.add(milestone)
    session.flush()
    recalculate_goal_hierarchy(session, milestone.goal_id)
    session.commit()
    return {"message": "Milestone moved to trash"}
