from datetime import datetime, timedelta, timezone
from typing import Annotated
import os

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import AccessTokenResponse, GoogleCalendar, User, get_current_active_user


load_dotenv()

GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
REDIRECT = os.getenv('REDIRECT')

google_calendar_router = APIRouter()


class GoogleAuthorizationCode(BaseModel):
    code: str


def _require_google_config() -> None:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not REDIRECT:
        raise HTTPException(
            status_code=503,
            detail='Google Calendar integration is not configured',
        )


@google_calendar_router.post('/google-calendar/token')
async def google_calendar_token(
    payload: GoogleAuthorizationCode,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, str]:
    _require_google_config()
    token_request = {
        'code': payload.code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': REDIRECT,
        'grant_type': 'authorization_code',
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://oauth2.googleapis.com/token',
                data=token_request,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f'Error from Google: {exc.response.text}',
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f'Could not connect to Google: {exc}',
        )

    token_data = response.json()
    existing = session.exec(
        select(GoogleCalendar).where(GoogleCalendar.user_id == current_user.id)
    ).first()
    refresh_token = token_data.get('refresh_token') or (
        existing.refresh_token if existing else None
    )
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail='Google did not return a refresh token; reconnect with consent',
        )
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(token_data.get('expires_in', 3600))
    )
    google_calendar = existing or GoogleCalendar(
        user_id=current_user.id,
        user=current_user,
        access_token=token_data['access_token'],
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    google_calendar.access_token = token_data['access_token']
    google_calendar.refresh_token = refresh_token
    google_calendar.expires_at = expires_at
    google_calendar.scopes = token_data.get('scope')
    session.add(google_calendar)
    session.commit()
    return {'message': 'Google Calendar connected'}


@google_calendar_router.get('/google-calendar/token/2', response_model=AccessTokenResponse)
async def get_google_calendar_access_token(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> AccessTokenResponse:
    _require_google_config()
    google_calendar = session.exec(
        select(GoogleCalendar).where(GoogleCalendar.user_id == current_user.id)
    ).first()
    if not google_calendar:
        raise HTTPException(
            status_code=401,
            detail='Google Calendar not linked for this user',
        )
    if not google_calendar.refresh_token:
        raise HTTPException(
            status_code=401,
            detail='Missing refresh token; reconnect Google Calendar',
        )

    expires_at = google_calendar.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        return AccessTokenResponse(access_token=google_calendar.access_token)

    refresh_request = {
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'refresh_token': google_calendar.refresh_token,
        'grant_type': 'refresh_token',
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://oauth2.googleapis.com/token',
                data=refresh_request,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 401}:
            raise HTTPException(
                status_code=401,
                detail='Google authorization expired; reconnect Google Calendar',
            )
        raise HTTPException(
            status_code=502,
            detail=f'Error refreshing Google token: {exc.response.text}',
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f'Could not connect to Google: {exc}',
        )

    token_data = response.json()
    google_calendar.access_token = token_data['access_token']
    google_calendar.expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(token_data.get('expires_in', 3600))
    )
    if token_data.get('refresh_token'):
        google_calendar.refresh_token = token_data['refresh_token']
    session.add(google_calendar)
    session.commit()
    return AccessTokenResponse(access_token=google_calendar.access_token)
