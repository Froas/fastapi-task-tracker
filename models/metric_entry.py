from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import date as Date, datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .daily_log import DailyLog
    from .metric_definition import MetricDefinition


class MetricEntryBase(SQLModel):
    date: Date = Field(default_factory=lambda: datetime.now(JST).date(), index=True)
    value: Optional[str] = None
    numeric_value: Optional[float] = None
    note: Optional[str] = None
    metric_definition_id: uuid.UUID = Field(foreign_key='metricdefinition.id', index=True)
    daily_log_id: Optional[uuid.UUID] = Field(foreign_key='dailylog.id', default=None)


class MetricEntry(MetricEntryBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    user_id: uuid.UUID = Field(foreign_key='user.id', index=True)
    user: 'User' = Relationship(back_populates='metric_entries')
    metric_definition: 'MetricDefinition' = Relationship(back_populates='entries')
    daily_log: Optional['DailyLog'] = Relationship(back_populates='metric_entries')


class MetricEntryUpsert(SQLModel):
    metric_definition_id: uuid.UUID
    date: Optional[Date] = None
    value: Optional[str] = None
    numeric_value: Optional[float] = None
    note: Optional[str] = None


class MetricEntryRead(MetricEntryBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
