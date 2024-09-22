from sqlmodel import SQLModel, Field, Relationship
# from models  Task, User, Tag
from typing import Optional, TYPE_CHECKING, List
from .enums import StatusType, PriorityType
from datetime import datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .tag import Tag
    from .task import Task
    

class SubtaskBase(SQLModel):
    title: str
    descrpition: str
    due_date: Optional[datetime]
    end_datetime: Optional[datetime]
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.LOW)
    task_id: Optional[uuid.uuid4] = Field(foreign_key='task.id', default=None)
    

class Subtask(SubtaskBase, table=True):
    id: Optional[uuid.uuid4] = Field(primary_key=uuid.uuid4, default_factory=uuid.uuid4)
    user_id: uuid.uuid4 = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='subtasks')
    task: 'Task' = Relationship(back_populates='subtasks')
    tags: List['Tag'] = Relationship(back_populates='subtask')
    

class SubtaskUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[PriorityType] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional [StatusType] = None
    due_date: Optional[datetime] = None
    task_id: Optional[uuid.UUID] = None

class SubtaskRead(SQLModel):
    pass