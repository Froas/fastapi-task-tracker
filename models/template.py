"""Goal templates: pre-built blueprints a user can instantiate into a
real goal+milestones+tasks tree. The blueprint is stored as a JSON
payload (the design's templates page uses {milestones:[{title, tasks:[{title}]}]}).

Instantiation is a POST that copies the blueprint into real Goal/
Milestone/Task rows owned by the calling user."""

from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import datetime
from utils.timezone import JST
import uuid

if TYPE_CHECKING:
    from .user import User


class TemplateBase(SQLModel):
    title: str
    description: Optional[str] = None
    emoji: Optional[str] = None
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    # Blueprint shape: { "milestones": [ { "title", "tasks": [{ "title" }] } ] }
    blueprint: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class TemplateCreate(SQLModel):
    title: str
    description: Optional[str] = None
    emoji: Optional[str] = None
    tags: Optional[List[str]] = None
    blueprint: Optional[dict] = None


class TemplateUpdate(SQLModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    emoji: Optional[str] = None
    tags: Optional[List[str]] = None
    blueprint: Optional[dict] = None


class Template(TemplateBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(JST))
    # NULL user_id = system / built-in template visible to everyone.
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key='user.id')
    user: Optional['User'] = Relationship(back_populates='templates')


class TemplateRead(TemplateBase):
    id: uuid.UUID
    created_at: datetime
    user_id: Optional[uuid.UUID]


class TemplateInstantiate(SQLModel):
    """POST body for /user/templates/{id}/instantiate.
    Optional overrides at instantiation time."""
    title_override: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
