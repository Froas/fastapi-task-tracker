from sqlmodel import SQLModel, Field, Relationship
from passlib.context import CryptContext
from pydantic import EmailStr, BaseModel
from typing import Optional, TYPE_CHECKING, List
import uuid

if TYPE_CHECKING:
    from .goal import Goal
    from .task import Task
    from .milestone import Milestone
    from .todo import Todo
    from .event import Event
    from .tag import Tag
    from .subtask import Subtask
    from .google_calendar import GoogleCalendar
    from .note import Note
    from .template import Template

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr
    password_hash: str
    # Design theme preference (e.g. "notion", "glass", "pixel", "bento", ...).
    # Mirrored from the frontend DesignThemeProvider so theme follows the
    # user across devices. Nullable = use device default.
    preferred_theme: Optional[str] = Field(default=None)

    def set_password(self, password: str):
        self.password_hash = pwd_context.hash(password)
    
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)
    
class UserRead(SQLModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    
class User(UserBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    goals: List['Goal'] = Relationship(back_populates='user')
    milestones: List['Milestone'] = Relationship(back_populates='user')
    tasks: List['Task'] = Relationship(back_populates='user')
    todos: List['Todo'] = Relationship(back_populates='user')
    events: List['Event'] = Relationship(back_populates='user')
    subtasks: List['Subtask'] = Relationship(back_populates='user')
    tags: List['Tag'] = Relationship(back_populates='user')
    notes: List['Note'] = Relationship(back_populates='user')
    templates: List['Template'] = Relationship(back_populates='user')
    google_token: Optional['GoogleCalendar'] = Relationship(back_populates='user')


class UserUpdate(SQLModel):
    """Patchable user fields. Username/email/password go through dedicated
    endpoints; this is for non-identity profile bits."""
    preferred_theme: Optional[str] = None


class UserInDB(UserBase):
    hashed_password: str

