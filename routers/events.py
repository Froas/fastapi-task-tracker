from fastapi import APIRouter, HTTPException, Depends
from models import Event, EventBase, EventUpdate, get_current_active_user
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from typing import Annotated
import uuid


events_router = APIRouter()

@events_router.get('/user/events')
async def get_all_event(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[Event]:
    event_list = current_user.events
    return event_list

@events_router.post('/user/events')
async def create_event(
    current_user: Annotated[User, Depends(get_current_active_user)],
    event_data: EventBase, 
    session: Session = Depends(get_session)
) -> Event:
    event = Event(
        title=event_data.title,
        description=event_data.description,
        start_datetime=event_data.start_datetime,
        end_datetime=event_data.end_datetime,
        event_type=event_data.event_type,
        recurrence_rule=event_data.recurrence_rule,
        location=event_data.location,
        user=current_user,
        user_id=current_user.id
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

@events_router.patch('/user/events/update', response_model=Event)
async def update_event(
    event_data: EventUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> Event:
    event = session.get(Event, event_data.id)
    if not event or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail='Event not found')
    
    update_data = event_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)
    
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

@events_router.get('/user/events/{event_id}')
async def get_event(
    current_user: Annotated[User, Depends(get_current_active_user)],
    event_id: uuid.UUID,
    session: Session = Depends(get_session)
) -> Event:
    event = session.get(Event, event_id)
    if event is None or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@events_router.delete('/user/events/{event_id}/delete')
async def delete_event(
    current_user: Annotated[User, Depends(get_current_active_user)],
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    event = session.get(Event, event_id)
    if event is None or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Event not found")
    session.delete(event)
    session.commit()
    return {"message": "Event was deleted successfully"}