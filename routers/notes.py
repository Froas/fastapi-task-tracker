from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import Annotated
from datetime import datetime
import uuid

from models import Goal, Note, NoteCreate, NoteUpdate, NoteRead, Task, User, get_current_active_user
from db import get_session
from utils.timezone import JST

notes_router = APIRouter()
VALID_NOTE_KINDS = {"note", "signal"}
VALID_SIGNAL_DOMAINS = {
    "work", "money", "account", "health", "relationship",
    "game", "opportunity", "learning", "other",
}
VALID_SIGNAL_STAKES = {"none", "low", "medium", "high"}
VALID_SIGNAL_DECISIONS = {"ignore", "watch", "test", "act"}


def _validate_relations(
    session: Session,
    current_user: User,
    values: dict,
) -> None:
    for field_name, model, label in (
        ("goal_id", Goal, "Goal"),
        ("task_id", Task, "Task"),
    ):
        if field_name not in values or values[field_name] is None:
            continue
        entity = session.get(model, values[field_name])
        if (
            entity is None
            or entity.user_id != current_user.id
            or entity.deleted_at is not None
        ):
            raise HTTPException(status_code=404, detail=f"{label} not found")


def _note_kind(value: str | None) -> str:
    normalized = (value or "note").strip().lower()
    return normalized if normalized in VALID_NOTE_KINDS else "note"


def _normalized_choice(
    value: str | None,
    valid_values: set[str],
    *,
    field_name: str,
    fallback: str | None = None,
) -> str | None:
    if value is None:
        return fallback
    normalized = value.strip().lower()
    if not normalized:
        return fallback
    if normalized not in valid_values:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name}: {normalized}",
        )
    return normalized


def _prepare_signal_data(
    values: dict,
    *,
    current: Note | None = None,
) -> dict:
    decision_was_set = "signal_decision" in values
    kind = _note_kind(values.get("kind", current.kind if current else "note"))
    values["kind"] = kind

    radar_fields = {
        "signal_domain", "signal_stake", "signal_decision", "next_action",
        "review_date", "deadline", "outcome", "resolved_at",
    }
    if kind != "signal":
        for field in radar_fields:
            values[field] = None
        return values

    domain_value = values.get(
        "signal_domain",
        current.signal_domain if current else None,
    )
    stake_value = values.get(
        "signal_stake",
        current.signal_stake if current else None,
    )
    decision_value = values.get(
        "signal_decision",
        current.signal_decision if current else None,
    )
    values["signal_domain"] = _normalized_choice(
        domain_value,
        VALID_SIGNAL_DOMAINS,
        field_name="signal domain",
        fallback="other",
    )
    values["signal_stake"] = _normalized_choice(
        stake_value,
        VALID_SIGNAL_STAKES,
        field_name="signal stake",
        fallback="none",
    )
    values["signal_decision"] = _normalized_choice(
        decision_value,
        VALID_SIGNAL_DECISIONS,
        field_name="signal decision",
    )

    review_date = values.get(
        "review_date",
        current.review_date if current else None,
    )
    if values["signal_decision"] in {"watch", "test"} and review_date is None:
        raise HTTPException(
            status_code=422,
            detail="review_date is required for watch and test signals",
        )

    if decision_was_set:
        if values["signal_decision"] == "ignore":
            values["resolved_at"] = values.get("resolved_at") or datetime.now(JST)
        elif "resolved_at" not in values:
            values["resolved_at"] = None
    return values


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
    values = _prepare_signal_data(note_data.model_dump())
    _validate_relations(session, current_user, values)
    note = Note(**values, user_id=current_user.id)
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
    update_data = _prepare_signal_data(update_data, current=note)
    _validate_relations(session, current_user, update_data)
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
