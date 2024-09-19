from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from passlib.context import CryptContext
from pydantic import EmailStr
from typing import Optional
from datetime import datetime
import uuid

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

class StatusType(str, Enum):
    OUTSTANDING = "outstanding"
    STARTED = "started"
    IN_PROGRESS = "in progress"
    FINISHED = "finished"
    CLOSED = "closed"
    ABORTED = "aborted"
    
class PriorityType(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    
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
    

class TodoBase(SQLModel):
    title: str
    description: str
    priority: PriorityType
    repeat_interval: str
    next_due_date: datetime
    task_id: Optional[uuid.UUID] = Field(foreign_key='task.id', default=None)

class Todo(TodoBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key='user.id')   
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    user: 'User' = Relationship(back_populates='todos')
    task: 'Task' = Relationship(back_populates='todos')
    
class TaskBase(SQLModel):
    title: str
    description: str
    priority: PriorityType
    due_date: datetime
    milestone_id: Optional[uuid.UUID] = Field(foreign_key='milestone.id', default=None)

class Task(TaskBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key='user.id') 
    start_date: Optional[datetime]
    status: Optional[StatusType] = Field(default=StatusType.OUTSTANDING)
    user: 'User' = Relationship(back_populates='tasks')
    milestone: 'Milestone' = Relationship(back_populates='tasks')
    todos: list[Todo] = Relationship(back_populates='task')
    
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
    tasks: list[Task] = Relationship(back_populates='milestone')
    
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
    milestones: list[Milestone] = Relationship(back_populates='goal')
  
class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr
    password_hash: str
    
    def set_password(self, password: str):
        self.password_hash = pwd_context.hash(password)
        
    def verify_password(self, password: str):
        return pwd_context.verify(password, self.password_hash)
    
class UserRead(SQLModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    
class User(UserBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    goals: list[Goal] = Relationship(back_populates='user')
    milestones: list[Milestone] = Relationship(back_populates='user')
    tasks: list[Task] = Relationship(back_populates='user')
    todos: list[Todo] = Relationship(back_populates='user')
    events: list[Event] = Relationship(back_populates='user')
    

    
    
    
# TODO: Event - integration with Google Calendar throught Oauth 2.0 