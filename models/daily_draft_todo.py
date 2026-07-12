from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import date, datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User


class DailyDraftTodoBase(SQLModel):
    title: str
    day: date = Field(default_factory=lambda: datetime.now(JST).date(), index=True)
    done: bool = Field(default=False)


class DailyDraftTodoCreate(SQLModel):
    title: str
    day: Optional[date] = None


class DailyDraftTodoUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    day: Optional[date] = None
    done: Optional[bool] = None


class DailyDraftTodo(DailyDraftTodoBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    completed_at: Optional[datetime] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='daily_draft_todos')


class DailyDraftTodoRead(DailyDraftTodoBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
