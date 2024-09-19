from fastapi import APIRouter, HTTPException, Depends
from models import Todo, TodoBase
from sqlmodel import Session, select
from routers.users import User, get_current_user
from db import get_session
import uuid


todos_router = APIRouter()

@todos_router.get('/user/todos')
async def todo(
    session: Session = Depends(get_session)
) -> list[Todo]:
    todo = session.exec(select(Todo)).all()
    return todo

@todos_router.get('/user/todos/{todo_id}')
async def todo(
    todo_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Todo:
    todo = session.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo has not found")
    return todo

@todos_router.post('/user/todos')
async def todo(
    todo_data: TodoBase,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> Todo:
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        priority=todo_data.priority,
        repeat_interval=todo_data.repeat_interval,
        next_due_date=todo_data.next_due_date,
        task_id=todo_data.task_id,
        user_id=current_user.id,
        user=current_user
    )
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


@todos_router.delete('/user/todos/{todo_id}/delete')
async def todo(
    todo_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    todo = session.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo has not found")
    session.delete(todo)
    session.commit()
    return {"message": "Todo has been deleted successfully"}