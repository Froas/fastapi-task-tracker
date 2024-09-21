from sqlmodel import SQLModel, Field, Relationship
from passlib.context import CryptContext
from pydantic import EmailStr
from typing import Optional, TYPE_CHECKING, List
import uuid

if TYPE_CHECKING:
    from .goal import Goal
    from .task import Task
    from .milestone import Milestone
    from .todo import Todo
    from .event import Event
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr
    password_hash: str
    
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
    goals: List["Goal"] = Relationship(back_populates='user')
    milestones: List["Milestone"] = Relationship(back_populates='user')
    tasks: List["Task"] = Relationship(back_populates='user')
    todos: List["Todo"] = Relationship(back_populates='user')
    events: List["Event"] = Relationship(back_populates='user')


class UserInDB(UserBase):
    hashed_password: str