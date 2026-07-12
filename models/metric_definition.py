from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import date as Date, datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .goal import Goal
    from .task import Task
    from .metric_entry import MetricEntry


class MetricDefinitionBase(SQLModel):
    name: str
    unit: Optional[str] = None
    input_type: str = Field(default='number')
    show_on_today: bool = Field(default=True)
    goal_id: Optional[uuid.UUID] = Field(foreign_key='goal.id', default=None, index=True)
    task_id: Optional[uuid.UUID] = Field(foreign_key='task.id', default=None, index=True)
    position: int = Field(default=0, index=True)


class MetricDefinition(MetricDefinitionBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    deleted_at: Optional[datetime] = Field(default=None)
    user_id: uuid.UUID = Field(foreign_key='user.id', index=True)
    user: 'User' = Relationship(back_populates='metric_definitions')
    goal: Optional['Goal'] = Relationship()
    task: Optional['Task'] = Relationship()
    entries: list['MetricEntry'] = Relationship(back_populates='metric_definition')


class MetricDefinitionCreate(SQLModel):
    name: str
    unit: Optional[str] = None
    input_type: str = 'number'
    show_on_today: bool = True
    goal_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    position: Optional[int] = None


class MetricDefinitionUpdate(SQLModel):
    id: uuid.UUID
    name: Optional[str] = None
    unit: Optional[str] = None
    input_type: Optional[str] = None
    show_on_today: Optional[bool] = None
    goal_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    position: Optional[int] = None


class MetricDefinitionRead(MetricDefinitionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TodayMetricRead(MetricDefinitionRead):
    goal_title: Optional[str] = None
    task_title: Optional[str] = None
    entry_id: Optional[uuid.UUID] = None
    date: Optional[Date] = None
    value: Optional[str] = None
    numeric_value: Optional[float] = None
    note: Optional[str] = None
