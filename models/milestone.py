from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from utils.timezone import JST
from .enums import StatusType, PriorityType
import uuid

if TYPE_CHECKING:
    from .user import User
    from .goal import Goal
    from .task import Task
    from .tag import Tag
    
class MilestoneBase(SQLModel):
    title: str
    description: str
    due_date: Optional[datetime]
    end_datetime: Optional[datetime]
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.LOW)
    goal_id: Optional[uuid.UUID] = Field(foreign_key='goal.id', default=None)

class Milestone(MilestoneBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='milestones')
    goal: 'Goal' = Relationship(back_populates='milestones')
    tasks: list['Task'] = Relationship(back_populates='milestone')
    tags: List['Tag'] = Relationship(back_populates='milestone')
    
class MilestoneUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusType] = None
    priority: Optional[PriorityType] = None
    due_date: Optional[datetime] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    goal_id: Optional[uuid.UUID] = None