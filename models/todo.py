from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .enums import StatusType, PriorityType
import uuid


if TYPE_CHECKING:
    from .user import User
    from .task import Task
    
class TodoBase(SQLModel):
    title: str
    description: str
    priority: PriorityType
    repeat_interval: str
    next_due_date: datetime
    task_id: Optional[uuid.UUID] = Field(foreign_key='task.id', default=None)

class Todo(TodoBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key='user.id')   
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    user: 'User' = Relationship(back_populates='todos')
    task: 'Task' = Relationship(back_populates='todos')