from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIGoalUsage(SQLModel, table=True):
    """Prompt-free accounting record for one AI goal-planning request."""

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "quota_period",
            "quota_slot",
            name="uq_ai_goal_usage_period_slot",
        ),
    )

    id: Optional[uuid.UUID] = Field(primary_key=True, default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    feature: str = Field(max_length=40, index=True)
    provider: str = Field(max_length=40)
    model: str = Field(max_length=100)
    status: str = Field(default="started", max_length=32, index=True)
    counted: bool = Field(default=True)
    quota_period: str = Field(max_length=7, index=True)
    quota_slot: Optional[int] = Field(default=None)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    error_code: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)
