from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from utils.timezone import JST
from .enums import StatusType, PriorityType
import uuid


if TYPE_CHECKING:
    from .user import User
    from .task import Task
    from .tag import Tag
    
class TodoBase(SQLModel):
    title: str
    description: str
    repeat_interval: Optional[str]
    due_date: Optional[datetime]
    next_due_date: Optional[datetime]
    end_datetime: Optional[datetime]
    priority: Optional[PriorityType] = Field(default=PriorityType.LOW)
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    task_id: Optional[uuid.UUID] = Field(foreign_key='task.id', default=None)

class Todo(TodoBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key='user.id')   
    user: 'User' = Relationship(back_populates='todos')
    task: 'Task' = Relationship(back_populates='todos')
    tags: List['Tag'] = Relationship(back_populates='todo')

class TodoUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[PriorityType] = None
    status: Optional[StatusType] = None
    repeat_interval: Optional[str] = None
    next_due_date: Optional[datetime] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    due_date: Optional[datetime] = None
    task_id: Optional[uuid.UUID] = None
    
class TodoRead(TodoBase):
    id: uuid.UUID
    
    
# 24bc30ef-ecf2-42d6-8377-0e1d9d4f9667
# 702794fa-e8ea-4492-9a8a-523c7ffea078
# 0c01d895-5fc3-486d-bb5a-ada73f822353
# 
# 
# 