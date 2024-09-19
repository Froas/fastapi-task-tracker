from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from .enums import StatusType
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from .user import User
    from .milestone import Milestone
    
class GoalBase(SQLModel):
    title: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    
class GoalRead(SQLModel):
    pass

class Goal(GoalBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='goals')
    milestones: List["Milestone"] = Relationship(back_populates='goal')