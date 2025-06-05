from sqlmodel import SQLModel, Field, Relationship
from passlib.context import CryptContext
from pydantic import EmailStr
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
import uuid

if TYPE_CHECKING:
    from .user import User


class GoogleCalendarBase(SQLModel):
    pass

class GoogleCalendar(GoogleCalendarBase, table=True):
    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4) 
    user_id: Optional[uuid.UUID] = Field(foreign_key='user.id')
    google_user_id: Optional[uuid.UUID] 
    access_token: str
    refresh_token: str
    expires_at: datetime = Field()
    user: 'User' = Relationship(back_populates="google_token")
    scopes: Optional[str] = None

class AccessTokenResponse(SQLModel):
    access_token: str