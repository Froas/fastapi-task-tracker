from fastapi import APIRouter, HTTPException, Depends
from models import Task, TaskBase, TaskUpdate, get_current_active_user
from typing import Annotated
from sqlmodel import Session, select
from routers.users import User
from db import get_session
import uuid

tasks_router = APIRouter()

@tasks_router.get('/user/tasks')
async def get_all_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Task]:
    task_list = current_user.tasks
    return task_list

@tasks_router.post('/user/tasks')
async def create_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_data: TaskBase,
    session: Session = Depends(get_session),
) -> Task:
    task = Task(
        title=task_data.title, 
        description=task_data.description, 
        due_date=task_data.due_date, 
        priority=task_data.priority, 
        milestone_id=task_data.milestone_id, 
        user_id=current_user.id, 
        user=current_user
    )
    session.add(task)
    session.commit()
    session.refresh(task)    
    return task

@tasks_router.patch('/user/tasks/update',  response_model=Task)
async def update_task(
    task_data: TaskUpdate,
    currente_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Task:
    task = session.get(Task, task_data.id)
    if not task or task.user_id != currente_user.id:
        raise HTTPException(status_code=404, detail='Tas not found')
    
    update_data = task_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@tasks_router.get('/user/tasks/{task_id}')
async def get_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Task:
    task = session.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@tasks_router.delete('/user/tasks/{task_id}/delete')
async def delete_task(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    task = session.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task  not found")
    session.delete(task)
    session.commit()
    return {"message": "Task was deleted successfully"}