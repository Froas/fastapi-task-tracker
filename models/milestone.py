from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import Optional, List, TYPE_CHECKING, Any
from datetime import datetime
from utils.timezone import JST
from .enums import StatusType, PriorityType
import uuid

if TYPE_CHECKING:
    from .user import User
    from .goal import Goal
    from .task import Task
    from .tag import Tag
    
from .task import TaskReadNested
class MilestoneBase(SQLModel):
    title: str
    description: str = ''
    due_date: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.LOW)
    goal_id: Optional[uuid.UUID] = Field(foreign_key='goal.id', default=None)
    position: int = Field(default=0, index=True) 
    completion_rule: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    # class Config:
    #     arbitrary_types_allowed = True

class Milestone(MilestoneBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    deleted_at: Optional[datetime] = Field(default=None)  # soft delete (Trash)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='milestones')
    goal: 'Goal' = Relationship(back_populates='milestones')
    tasks: list['Task'] = Relationship(back_populates='milestone')
    tags: List['Tag'] = Relationship(back_populates='milestone')

class MilestoneReadNested(MilestoneBase):
    id: uuid.UUID
    tasks: List['TaskReadNested'] = Field(default_factory=list)
    # class Config:
    #     arbitrary_types_allowed = True
    
class MilestoneRead(MilestoneBase):
    id: uuid.UUID
# class MilestoneReadNested(Milestone):
#     tasks: List['TaskReadNested']
    
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
    position: Optional[int] = None
    completion_rule: Optional[dict[str, Any]] = None


class MilestoneReorderRequest(SQLModel):
    milestone_ids: List[uuid.UUID]
