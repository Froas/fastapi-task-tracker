from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from .enums import StatusType, PriorityType
from datetime import datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .milestone import Milestone
    from .tag import Tag
    
class GoalBase(SQLModel):
    title: str
    description: Optional[str]
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    end_datetime: Optional[datetime]
    
class GoalRead(SQLModel):
    pass

class Goal(GoalBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.HIGH)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='goals')
    milestones: List["Milestone"] = Relationship(back_populates='goal')
    tags: List['Tag'] = Relationship(back_populates='goal')
    
class GoalUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusType] = None
    priority: Optional[PriorityType] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None