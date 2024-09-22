from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
import uuid


if TYPE_CHECKING:
    from .user import User
    from .goal import Goal
    from .milestone import Milestone
    from .task import Task
    from .subtask import Subtask
    from .todo import Todo
    from .event import Event
   
    
class TagBase(SQLModel):
    name: str
    color: Optional[str] = None
    
    goal_id: Optional[uuid.UUID] = Field(foreign_key='goal.id', default=None)
    milestone_id: Optional[uuid.UUID] = Field(foreign_key='milestone.id', default=None)
    task_id: Optional[uuid.UUID] = Field(foreign_key='task.id', default=None)
    subtask_id: Optional[uuid.UUID] = Field(foreign_key='subtask.id', default=None)
    todo_id: Optional[uuid.UUID] = Field(foreign_key='todo.id', default=None)
    event_id: Optional[uuid.UUID] = Field(foreign_key='event.id', default=None)
        
class Tag(TagBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='tags')
    goal: 'Goal' = Relationship(back_populates='tags')
    milestone: 'Milestone' = Relationship(back_populates='tags')
    task: 'Task' = Relationship(back_populates='tags')
    subtask: 'Subtask' = Relationship(back_populates='tags')
    todo: 'Todo' = Relationship(back_populates='tags')
    event: 'Event' = Relationship(back_populates='tags')
    
class TagUpdate:
    id: uuid.UUID
    name: Optional[str] = None
    color: Optional[str] = None
        