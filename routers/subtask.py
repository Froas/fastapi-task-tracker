from fastapi import APIRouter, HTTPException, Depends
from models import Subtask, TaskBase, MilestoneUpdate, get_current_active_user
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from typing import Annotated
import uuid

subtasks_router = APIRouter()

@subtasks_router.get('/user/tasks/subtask')
async def get_all_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Subtask]:
    sub_task_list = current_user.subtasks
    return sub_task_list

