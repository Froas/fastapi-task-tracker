"""Trash — unified view + restore/purge over soft-deleted rows across
Goal / Milestone / Task / Todo / Event / Note.

`deleted_at IS NOT NULL` on each table means the row is in trash. List
endpoints elsewhere filter `WHERE deleted_at IS NULL`. From here we can
restore (clear deleted_at) or hard-delete (session.delete)."""

from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import Annotated, Literal, Any
from datetime import datetime
from pydantic import BaseModel
import uuid

from models import (
    Goal, Milestone, Task, Todo, Event, Note,
    User, get_current_active_user,
)
from db import get_session
from utils.timezone import JST

trash_router = APIRouter()

KindLiteral = Literal["goal", "milestone", "task", "todo", "event", "note"]
MODEL_BY_KIND = {
    "goal": Goal,
    "milestone": Milestone,
    "task": Task,
    "todo": Todo,
    "event": Event,
    "note": Note,
}


class TrashItem(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    deleted_at: datetime


@trash_router.get('/user/trash')
async def list_trash(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[TrashItem]:
    """Union of soft-deleted items across all supported entities."""
    items: list[TrashItem] = []
    for kind, Model in MODEL_BY_KIND.items():
        rows = session.exec(
            select(Model)
            .where(Model.user_id == current_user.id)
            .where(Model.deleted_at.is_not(None))
            .order_by(Model.deleted_at.desc())
        ).all()
        for row in rows:
            items.append(
                TrashItem(
                    id=row.id,
                    kind=kind,
                    title=getattr(row, 'title', '(untitled)') or '(untitled)',
                    deleted_at=row.deleted_at,
                )
            )
    items.sort(key=lambda i: i.deleted_at, reverse=True)
    return items


def _fetch(kind: str, item_id: uuid.UUID, session: Session, user: User):
    Model = MODEL_BY_KIND.get(kind)
    if Model is None:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {kind}")
    row = session.get(Model, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@trash_router.post('/user/trash/{kind}/{item_id}/restore')
async def restore_item(
    kind: KindLiteral,
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, str]:
    row = _fetch(kind, item_id, session, current_user)
    if row.deleted_at is None:
        return {"message": "Already restored"}
    row.deleted_at = None
    session.add(row)
    session.commit()
    return {"message": f"{kind} restored"}


@trash_router.delete('/user/trash/{kind}/{item_id}')
async def purge_item(
    kind: KindLiteral,
    item_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Hard delete — removes the row permanently."""
    row = _fetch(kind, item_id, session, current_user)
    session.delete(row)
    session.commit()
    return {"message": f"{kind} permanently deleted"}


@trash_router.delete('/user/trash')
async def empty_trash(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Hard-delete every soft-deleted row for the current user."""
    total = 0
    for Model in MODEL_BY_KIND.values():
        rows = session.exec(
            select(Model)
            .where(Model.user_id == current_user.id)
            .where(Model.deleted_at.is_not(None))
        ).all()
        for row in rows:
            session.delete(row)
            total += 1
    session.commit()
    return {"message": f"Trash emptied", "removed": total}
