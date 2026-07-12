# from __future__ import annotations

from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import Optional, List, TYPE_CHECKING, Any
from .enums import StatusType, PriorityType
from datetime import datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User
    from .milestone import Milestone, MilestoneRead
    from .tag import Tag
    from .task import Task
    
from .milestone import MilestoneReadNested
from .task import TaskReadNested
class GoalBase(SQLModel):
    title: str
    description: Optional[str] = None
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    end_datetime: Optional[datetime] = None
    completion_rule: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    # class Config:
    #     arbitrary_types_allowed = True 
class GoalRead(GoalBase):
    id: uuid.UUID
    status: StatusType
    priority: PriorityType
    position: int = 0

class GoalCreate(SQLModel):
    title: str
    description: Optional[str] = None
    start_datetime: Optional[datetime] = Field(default_factory=lambda: datetime.now(JST))
    end_datetime: Optional[datetime] = None
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.HIGH)
    completion_rule: Optional[dict[str, Any]] = None

class Goal(GoalBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    priority: Optional[PriorityType] = Field(default=PriorityType.HIGH)
    position: int = Field(default=0, index=True)
    deleted_at: Optional[datetime] = Field(default=None)  # soft delete (Trash)
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='goals')
    milestones: List["Milestone"] = Relationship(back_populates='goal')
    tasks: List["Task"] = Relationship(back_populates='goal')
    tags: List['Tag'] = Relationship(back_populates='goal')
    
    # class Config:
    #     arbitrary_types_allowed = True
    
class GoalReadNested(GoalRead):
    milestones: List['MilestoneReadNested'] = Field(default_factory=list)
    tasks: List['TaskReadNested'] = Field(default_factory=list)
    
    # class Config:
    #     arbitrary_types_allowed = True
    
    
class GoalUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusType] = None
    priority: Optional[PriorityType] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    position: Optional[int] = None
    completion_rule: Optional[dict[str, Any]] = None

class GoalReorderRequest(SQLModel):
    goal_ids: List[uuid.UUID]
