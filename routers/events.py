from fastapi import APIRouter, HTTPException, Depends
from models import Event, EventBase
from sqlmodel import Session, select
from routers.users import User, get_current_user
from db import get_session
import uuid


events_router = APIRouter()

@events_router.get('/user/events')
async def event(
    session: Session = Depends(get_session)
) -> list[Event]:
    event_list = session.exec(select(Event)).all()
    return event_list

@events_router.get('/user/events/{event_id}')
async def event(
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event has not found")
    return event

@events_router.post('/user/events')
async def event(
    event_data: EventBase, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> Event:
    event = Event(
        title=event_data.title,
        description=event_data.description,
        start_datetime=event_data.start_datetime,
        end_datetime=event_data.end_datetime,
        user=current_user,
        user_id=current_user.id
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

@events_router.delete('/user/events/{event_id}/delete')
async def event(
    event_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event has not found")
    session.delete(event)
    session.commit()
    return {"message": "Event deleted successfully"}