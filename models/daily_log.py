from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import date as Date, datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .todo_occurrence import TodoOccurrence
    from .metric_entry import MetricEntry


class DailyLogBase(SQLModel):
    date: Date = Field(default_factory=lambda: datetime.now(JST).date(), index=True)
    color: Optional[str] = None
    note: Optional[str] = None
    trigger: Optional[str] = None
    what_helped: Optional[str] = None
    tomorrow_minimum: Optional[str] = None
    finalized_at: Optional[datetime] = None
    finalized_by: Optional[str] = None


class DailyLogCreate(SQLModel):
    date: Optional[Date] = None
    color: Optional[str] = None
    note: Optional[str] = None
    trigger: Optional[str] = None
    what_helped: Optional[str] = None
    tomorrow_minimum: Optional[str] = None


class DailyLogUpdate(SQLModel):
    id: uuid.UUID
    date: Optional[Date] = None
    color: Optional[str] = None
    note: Optional[str] = None
    trigger: Optional[str] = None
    what_helped: Optional[str] = None
    tomorrow_minimum: Optional[str] = None


class DailyLog(DailyLogBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    deleted_at: Optional[datetime] = Field(default=None)
    user_id: uuid.UUID = Field(foreign_key='user.id', index=True)
    user: 'User' = Relationship(back_populates='daily_logs')
    todo_occurrences: list['TodoOccurrence'] = Relationship(back_populates='daily_log')
    metric_entries: list['MetricEntry'] = Relationship(back_populates='daily_log')


class DailyLogRead(DailyLogBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
