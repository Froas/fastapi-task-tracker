from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .enums import StatusType
import uuid

if TYPE_CHECKING:
    from .user import User
    from .goal import Goal
    from .task import Task
    
class MilestoneBase(SQLModel):
    title: str
    description: str
    due_date: datetime
    goal_id: Optional[uuid.UUID] = Field(foreign_key='goal.id', default=None)

class Milestone(MilestoneBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='milestones')
    goal: 'Goal' = Relationship(back_populates='milestones')
    tasks: list["Task"] = Relationship(back_populates='milestone')
    
class MilestoneUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusType] = None
    due_date: Optional[datetime] = None
    goal_id: Optional[uuid.UUID] = None