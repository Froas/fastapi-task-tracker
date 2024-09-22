from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING, List
from datetime import datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .tag import Tag
    

class EventBase(SQLModel):
    title: str
    description: Optional[str] = None
    start_datetime: Optional[datetime]
    end_datetime: Optional[datetime]
    event_type: Optional[str] = None
    location: Optional[str] = None
    recurrence_rule: Optional[str] = None  # Правила повторения в формате RFC 5545 Библиотеки для обработки RRULE:

class Event(EventBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    create_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='events')
    tags: List['Tag'] = Relationship(back_populates='event')
    
    
class EventUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    recurrence_rule: Optional[str] = None