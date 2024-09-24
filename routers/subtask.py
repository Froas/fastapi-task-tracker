from fastapi import APIRouter, HTTPException, Depends
from models import Subtask, SubtaskBase, SubtaskUpdate, get_current_active_user
from sqlmodel import Session
from routers.users import User
from db import get_session
from typing import Annotated
import uuid

subtasks_router = APIRouter()

@subtasks_router.get('/user/task/subtasks')
async def get_all_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Subtask]:
    sub_task_list = current_user.subtasks
    return sub_task_list

@subtasks_router.post('/user/task/subtasks')
async def create_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    subtask_data: SubtaskBase,
    session: Session = Depends(get_session),
) -> Subtask:
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
        user=current_user
    )
    session.add(task)
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
        raise HTTPException(status_code=404, detail='Tas not found')
    
    update_data = subtask_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@subtasks_router.get('/user/task/subtasks/{task_id}')
async def get_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Subtask:
    task = session.get(Subtask, task_id)
    if task is None or task.user_id != current_user.id:
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
    session.delete(task)
    session.commit()
    return {"message": "Subtask was deleted successfully"}

