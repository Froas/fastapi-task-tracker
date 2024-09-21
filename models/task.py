from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .enums import StatusType, PriorityType
import uuid

if TYPE_CHECKING:
    from .user import User
    from .milestone import Milestone
    from .todo import Todo
    
class TaskBase(SQLModel):
    title: str
    description: str
    priority: PriorityType
    due_date: datetime
    milestone_id: Optional[uuid.UUID] = Field(foreign_key='milestone.id', default=None)

class Task(TaskBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key='user.id') 
    start_date: Optional[datetime]
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    user: 'User' = Relationship(back_populates='tasks')
    milestone: 'Milestone' = Relationship(back_populates='tasks')
    todos: List["Todo"] = Relationship(back_populates='task')
    
    
class TaskUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[PriorityType] = None
    start_date: Optional[datetime] = None
    status: Optional [StatusType] = None
    due_date: Optional[datetime] = None
    milestone_id: Optional[uuid.UUID] = None