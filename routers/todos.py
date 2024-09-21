from fastapi import APIRouter, HTTPException, Depends
from models import Todo, TodoBase, TodoUpdate, get_current_active_user
from typing import Annotated
from sqlmodel import Session, select
from routers.users import User
from db import get_session
import uuid


todos_router = APIRouter()

@todos_router.get('/user/todos')
async def get_all_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Todo]:
    todo = current_user.todos
    return todo

@todos_router.get('/user/todos/{todo_id}')
async def get_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Todo:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo

@todos_router.post('/user/todos')
async def create_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_data: TodoBase,
    session: Session = Depends(get_session)
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

@todos_router.patch('/user/todos/update', response_model=Todo)
async def update_todo(
    todo_data: TodoUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Todo:
    todo = session.get(Todo, todo_data.id)
    if not todo or todo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Todo not found')

    update_data = todo_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(todo, key, value)
        
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo
    


@todos_router.delete('/user/todos/{todo_id}/delete')
async def delete_todo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    todo_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Todo not found")
    session.delete(todo)
    session.commit()
    return {"message": "Todo was deleted successfully"}