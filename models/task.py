from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .enums import StatusType, PriorityType
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .milestone import Milestone
    from .todo import Todo
    from .subtask import Subtask
    from .tag import Tag
    
class TaskBase(SQLModel):
    title: str
    description: str
    due_date: Optional[datetime]
    end_datetime: Optional[datetime]
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.LOW)
    milestone_id: Optional[uuid.UUID] = Field(foreign_key='milestone.id', default=None)

class Task(TaskBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user: 'User' = Relationship(back_populates='tasks')
    user_id: uuid.UUID = Field(foreign_key='user.id') 
    milestone: 'Milestone' = Relationship(back_populates='tasks')
    todos: List['Todo'] = Relationship(back_populates='task')
    subtasks: List['Subtask'] = Relationship(back_populates='task')
    tags: List['Tag'] = Relationship(back_populates='task')
    
    
class TaskUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[PriorityType] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional [StatusType] = None
    due_date: Optional[datetime] = None
    milestone_id: Optional[uuid.UUID] = None