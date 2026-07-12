from fastapi import APIRouter, HTTPException, Depends
from models import Event, Goal, Milestone, Subtask, Tag, TagBase, TagUpdate, Task, Todo, get_current_active_user
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from typing import Annotated
import uuid

tags_router = APIRouter()


def validate_tag_targets(tag_data: TagBase, current_user: User, session: Session) -> None:
    targets = (
        (Goal, tag_data.goal_id),
        (Milestone, tag_data.milestone_id),
        (Task, tag_data.task_id),
        (Subtask, tag_data.subtask_id),
        (Todo, tag_data.todo_id),
        (Event, tag_data.event_id),
    )
    for model, entity_id in targets:
        if entity_id is None:
            continue
        entity = session.get(model, entity_id)
        if entity is None or entity.user_id != current_user.id:
            raise HTTPException(status_code=404, detail='Tag target not found')
        if getattr(entity, 'deleted_at', None) is not None:
            raise HTTPException(status_code=404, detail='Tag target not found')

@tags_router.get('/tags')
async def get_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> list[Tag]:
    return session.exec(
        select(Tag).where(Tag.user_id == current_user.id).order_by(Tag.name)
    ).all()

@tags_router.post('/tags')
async def create_tags(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_data: TagBase,
    session: Session = Depends(get_session)
) -> Tag:
    validate_tag_targets(tag_data, current_user, session)
    tag = Tag(
        **tag_data.model_dump(exclude_unset=True),
        user=current_user,
        user_id=current_user.id
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag

@tags_router.patch('/tags/update')
async def update_tag(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_data: TagUpdate,
    session: Session = Depends(get_session)
) -> Tag:
    tag = session.get(Tag, tag_data.id)

    if tag is None or tag.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Tag not found')
    
    update_date = tag_data.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in update_date.items():
        setattr(tag, key, value)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag

@tags_router.get('/tags/{tag_id}')
async def get_tag(
    tag_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Tag:
    tag = session.get(Tag, tag_id)
    if tag is None or tag.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Tag not found')
    return tag

@tags_router.delete('/tags/delete/{tag_id}')
async def delete_tag(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> dict[str, str]:
    tag = session.get(Tag, tag_id)
    if tag is None or tag.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Tag not found')
    session.delete(tag)
    session.commit()
    return {"message": "Tag was deleted successfully"}
