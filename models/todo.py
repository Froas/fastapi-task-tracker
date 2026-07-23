from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import date as Date, datetime
from utils.timezone import JST
from .enums import StatusType, PriorityType
import uuid


if TYPE_CHECKING:
    from .user import User
    from .task import Task
    from .tag import Tag
    from .todo_occurrence import TodoOccurrence
    
class TodoBase(SQLModel):
    title: str
    description: str = ''
    repeat_interval: Optional[str] = None
    due_date: Optional[datetime] = None
    next_due_date: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    priority: Optional[PriorityType] = Field(default=PriorityType.LOW)
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    task_id: Optional[uuid.UUID] = Field(foreign_key='task.id', default=None)
    # Tracking lifecycle. NULL means a legacy definition whose visibility is
    # inferred from its existing task/milestone hierarchy.
    tracking_mode: Optional[str] = Field(default=None, index=True)
    tracking_state: Optional[str] = Field(default=None, index=True)
    routine_series_key: Optional[str] = Field(default=None, index=True)
    stage_order: int = Field(default=1)
    active_from: Optional[Date] = Field(default=None, index=True)
    graduated_at: Optional[datetime] = None

class Todo(TodoBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    position: int = Field(default=0, index=True)
    deleted_at: Optional[datetime] = Field(default=None)  # soft delete (Trash)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='todos')
    task: 'Task' = Relationship(back_populates='todos')
    tags: List['Tag'] = Relationship(back_populates='todo')
    occurrences: List['TodoOccurrence'] = Relationship(back_populates='todo')

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
    position: Optional[int] = None
    tracking_mode: Optional[str] = None
    tracking_state: Optional[str] = None
    routine_series_key: Optional[str] = None
    stage_order: Optional[int] = None
    active_from: Optional[Date] = None
    graduated_at: Optional[datetime] = None
    
class TodoRead(TodoBase):
    id: uuid.UUID
    position: int = 0

class TodoReorderRequest(SQLModel):
    todo_ids: List[uuid.UUID]
