from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from .user import User
    

class EventBase(SQLModel):
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    event_type: Optional[str] = None
    location: Optional[str] = None
    recurrence_rule: Optional[str] = None  # Правила повторения в формате RFC 5545 Библиотеки для обработки RRULE:

class Event(EventBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='events')
    
class EventUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    recurrence_rule: Optional[str] = None