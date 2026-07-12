from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import Annotated
from datetime import datetime
import uuid

from models import Note, NoteCreate, NoteUpdate, NoteRead, User, get_current_active_user
from db import get_session
from utils.timezone import JST

notes_router = APIRouter()
VALID_NOTE_KINDS = {"note", "signal"}


def _note_kind(value: str | None) -> str:
    normalized = (value or "note").strip().lower()
    return normalized if normalized in VALID_NOTE_KINDS else "note"


@notes_router.get('/user/notes')
async def list_notes(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> list[NoteRead]:
    """List notes that are not in trash. Pinned first, then newest."""
    rows = session.exec(
        select(Note)
        .where(Note.user_id == current_user.id)
        .where(Note.deleted_at.is_(None))
        .order_by(Note.pinned.desc(), Note.updated_at.desc())
    ).all()
    return rows


@notes_router.post('/user/notes')
async def create_note(
    current_user: Annotated[User, Depends(get_current_active_user)],
    note_data: NoteCreate,
    session: Session = Depends(get_session),
) -> NoteRead:
    note = Note(
        title=note_data.title,
        body=note_data.body,
        tag=note_data.tag,
        pinned=note_data.pinned,
        kind=_note_kind(note_data.kind),
        source=note_data.source,
        goal_id=note_data.goal_id,
        task_id=note_data.task_id,
        user_id=current_user.id,
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@notes_router.patch('/user/notes/update', response_model=NoteRead)
async def update_note(
    current_user: Annotated[User, Depends(get_current_active_user)],
    note_data: NoteUpdate,
    session: Session = Depends(get_session),
) -> Note:
    note = session.get(Note, note_data.id)
    if note is None or note.user_id != current_user.id or note.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Note not found")
    update_data = note_data.model_dump(exclude_unset=True, exclude={"id"})
    if "kind" in update_data:
        update_data["kind"] = _note_kind(update_data["kind"])
    for key, value in update_data.items():
        setattr(note, key, value)
    note.updated_at = datetime.now(JST)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@notes_router.get('/user/notes/{note_id}')
async def get_note(
    note_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> NoteRead:
    note = session.get(Note, note_id)
    if note is None or note.user_id != current_user.id or note.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@notes_router.delete('/user/notes/{note_id}/delete')
async def delete_note(
    current_user: Annotated[User, Depends(get_current_active_user)],
    note_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Soft delete: sets deleted_at. Hard-delete happens from /user/trash."""
    note = session.get(Note, note_id)
    if note is None or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Note not found")
    note.deleted_at = datetime.now(JST)
    session.add(note)
    session.commit()
    return {"message": "Note moved to trash"}
