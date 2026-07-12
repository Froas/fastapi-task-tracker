from fastapi import APIRouter, HTTPException, Depends
from models import Task, Subtask, SubtaskBase, SubtaskUpdate, SubtaskReorderRequest, get_current_active_user
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from typing import Annotated
from routers.visibility import active_task_ids
from services.completion_rules import recalculate_task_hierarchy
import uuid

subtasks_router = APIRouter()

@subtasks_router.get('/user/task/subtasks')
async def get_all_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[Subtask]:
    return session.exec(
        select(Subtask).where(
            Subtask.user_id == current_user.id,
            Subtask.task_id.in_(active_task_ids(current_user.id)),
        ).order_by(Subtask.task_id, Subtask.position, Subtask.id)
    ).all()

@subtasks_router.post('/user/task/subtasks')
async def create_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    subtask_data: SubtaskBase,
    session: Session = Depends(get_session),
) -> Subtask:
    if subtask_data.task_id is None:
        raise HTTPException(status_code=400, detail='task_id is required')
    if subtask_data.task_id is not None:
        parent = session.exec(
            select(Task).where(
                Task.id == subtask_data.task_id,
                Task.user_id == current_user.id,
                Task.deleted_at.is_(None),
                Task.id.in_(active_task_ids(current_user.id)),
            )
        ).first()
        if parent is None:
            raise HTTPException(status_code=404, detail='Task not found')
    max_position = session.exec(
        select(Subtask.position)
        .where(
            Subtask.user_id == current_user.id,
            Subtask.task_id == subtask_data.task_id,
        )
        .order_by(Subtask.position.desc())
    ).first()
    task = Subtask(
        title=subtask_data.title, 
        description=subtask_data.description, 
        due_date=subtask_data.due_date, 
        status=subtask_data.status,
        end_datetime=subtask_data.end_datetime,
        start_datetime=subtask_data.start_datetime,
        priority=subtask_data.priority, 
        task_id=subtask_data.task_id, 
        user_id=current_user.id, 
        user=current_user,
        position=(max_position or 0) + 1,
    )
    session.add(task)
    recalculate_task_hierarchy(session, task.task_id)
    session.commit()
    session.refresh(task)    
    return task

@subtasks_router.patch('/user/task/subtasks/update',  response_model=Subtask)
async def update_task(
    subtask_data: SubtaskUpdate,
    currente_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Subtask:
    task = session.get(Subtask, subtask_data.id)
    if not task or task.user_id != currente_user.id:
        raise HTTPException(status_code=404, detail='Subtask not found')
    if subtask_data.task_id is not None:
        parent = session.exec(
            select(Task).where(
                Task.id == subtask_data.task_id,
                Task.user_id == currente_user.id,
                Task.deleted_at.is_(None),
                Task.id.in_(active_task_ids(currente_user.id)),
            )
        ).first()
        if parent is None:
            raise HTTPException(status_code=404, detail='Task not found')
    
    update_data = subtask_data.model_dump(exclude_unset=True, exclude={'id'})
    if subtask_data.task_id is not None and subtask_data.task_id != task.task_id and 'position' not in update_data:
        max_position = session.exec(
            select(Subtask.position)
            .where(
                Subtask.user_id == currente_user.id,
                Subtask.task_id == subtask_data.task_id,
            )
            .order_by(Subtask.position.desc())
        ).first()
        update_data['position'] = (max_position or 0) + 1
    for key, value in update_data.items():
        setattr(task, key, value)
    
    session.add(task)
    recalculate_task_hierarchy(session, task.task_id)
    session.commit()
    session.refresh(task)
    return task

@subtasks_router.put('/user/task/subtasks/reorder')
async def reorder_subtasks(
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: SubtaskReorderRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    subtask_ids = payload.subtask_ids
    if not subtask_ids or len(set(subtask_ids)) != len(subtask_ids):
        raise HTTPException(status_code=400, detail="Invalid subtask list provided")

    subtasks = session.exec(
        select(Subtask).where(
            Subtask.user_id == current_user.id,
            Subtask.id.in_(subtask_ids),
            Subtask.task_id.in_(active_task_ids(current_user.id)),
        )
    ).all()
    if len(subtasks) != len(subtask_ids):
        raise HTTPException(status_code=400, detail="Invalid subtask list provided")
    task_ids = {subtask.task_id for subtask in subtasks}
    if len(task_ids) != 1:
        raise HTTPException(status_code=400, detail="Subtasks must belong to one task")

    task_id = subtasks[0].task_id
    active_ids = set(session.exec(
        select(Subtask.id).where(
            Subtask.user_id == current_user.id,
            Subtask.task_id == task_id,
        )
    ).all())
    if active_ids != set(subtask_ids):
        raise HTTPException(status_code=409, detail="Subtask list is stale; refresh and retry")

    by_id = {subtask.id: subtask for subtask in subtasks}
    for position, subtask_id in enumerate(subtask_ids, start=1):
        subtask = by_id[subtask_id]
        subtask.position = position
        session.add(subtask)
    session.commit()
    return {"message": "Subtasks reordered successfully"}

@subtasks_router.get('/user/task/subtasks/{task_id}')
async def get_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Subtask:
    task = session.exec(
        select(Subtask).where(
            Subtask.id == task_id,
            Subtask.user_id == current_user.id,
            Subtask.task_id.in_(active_task_ids(current_user.id)),
        )
    ).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Subtask not found")
    return task

@subtasks_router.delete('/user/task/subtasks/{task_id}/delete')
async def delete_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    task = session.get(Subtask, task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subtask  not found")
    parent_task_id = task.task_id
    session.delete(task)
    session.flush()
    recalculate_task_hierarchy(session, parent_task_id)
    session.commit()
    return {"message": "Subtask was deleted successfully"}
