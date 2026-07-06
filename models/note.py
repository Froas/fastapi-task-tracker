from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User


class NoteBase(SQLModel):
    title: str
    body: Optional[str] = None
    tag: Optional[str] = None  # free-form text tag for color/category grouping
    pinned: bool = Field(default=False)


class NoteCreate(SQLModel):
    title: str
    body: Optional[str] = None
    tag: Optional[str] = None
    pinned: bool = False


class NoteUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    body: Optional[str] = None
    tag: Optional[str] = None
    pinned: Optional[bool] = None


class Note(NoteBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    deleted_at: Optional[datetime] = Field(default=None)  # soft delete
    user_id: uuid.UUID = Field(foreign_key='user.id')
    user: 'User' = Relationship(back_populates='notes')


class NoteRead(NoteBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
