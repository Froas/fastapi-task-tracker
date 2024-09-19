from fastapi import APIRouter, HTTPException, Depends
from models import Task, TaskBase
from sqlmodel import Session, select
from routers.users import User, get_current_user
from db import get_session
import uuid

tasks_router = APIRouter()

@tasks_router.get('/user/tasks')
async def task(
    session: Session = Depends(get_session)
) -> list[Task]:
    task_list = session.exec(select(Task)).all()
    return task_list

@tasks_router.post('/user/tasks')
async def task(
    task_data: TaskBase,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
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

@tasks_router.get('/user/tasks/{task_id}')
async def task(
    task_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Task:
    task = session.get(task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task has not found")
    return task

@tasks_router.delete('/user/tasks/{task_id}/delete')
async def task(
    task_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    task = session.get(task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task has not found")
    session.delete(task)
    session.commit()
    return {"message": "Task has been deleted successfully"}