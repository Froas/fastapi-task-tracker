from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import date as Date, datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .todo import Todo
    from .daily_log import DailyLog


class TodoOccurrenceBase(SQLModel):
    date: Date = Field(default_factory=lambda: datetime.now(JST).date(), index=True)
    status: str = Field(default='open')
    value: Optional[str] = None
    note: Optional[str] = None
    completed_at: Optional[datetime] = None
    todo_id: uuid.UUID = Field(foreign_key='todo.id', index=True)
    daily_log_id: Optional[uuid.UUID] = Field(foreign_key='dailylog.id', default=None)


class TodoOccurrence(TodoOccurrenceBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    user_id: uuid.UUID = Field(foreign_key='user.id', index=True)
    user: 'User' = Relationship(back_populates='todo_occurrences')
    todo: 'Todo' = Relationship(back_populates='occurrences')
    daily_log: Optional['DailyLog'] = Relationship(back_populates='todo_occurrences')


class TodoOccurrenceUpdate(SQLModel):
    id: uuid.UUID
    status: Optional[str] = None
    value: Optional[str] = None
    note: Optional[str] = None


class TodoOccurrenceRead(TodoOccurrenceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    todo_title: str
    todo_description: str = ''
    task_id: Optional[uuid.UUID] = None
    task_title: Optional[str] = None
    task_kind: Optional[str] = None
    task_scope: Optional[str] = None
    goal_id: Optional[uuid.UUID] = None
    goal_title: Optional[str] = None
    milestone_id: Optional[uuid.UUID] = None
    milestone_title: Optional[str] = None
