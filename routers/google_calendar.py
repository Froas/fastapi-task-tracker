from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated

from datetime import timedelta
from models import User, AccessTokenResponse, get_current_active_user, GoogleCalendar
from sqlmodel import Session, select
from db import get_session
from dotenv import load_dotenv
import uuid
from fastapi import Request
from datetime import datetime, timedelta, timezone
import os
import httpx


load_dotenv()


GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
REDIRECT = os.getenv('REDIRECT')

google_calendar_router = APIRouter()

@google_calendar_router.post('/google-calendar/token')
async def google_calendar_token(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session)
) -> dict[str, str]:
    body = await request.json()
    code = body['code']
    data_to_google = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code"
    }
    async with httpx.AsyncClient() as client:
        try:
            google_response = await client.post("https://oauth2.googleapis.com/token", data=data_to_google)
            google_response.raise_for_status() 
            google_calendar_date = google_response.json()
            expires_in_seconds = google_calendar_date['expires_in']
            calc_date = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
            googleCalendar = GoogleCalendar(
                user_id=current_user.id,
                # google_user_id=GOOGLE_CLIENT_ID,
                access_token=google_calendar_date['access_token'],
                refresh_token=google_calendar_date['refresh_token'],
                expires_at=calc_date,
                user=current_user
            )
            session.add(googleCalendar)
            session.commit()
            session.refresh(googleCalendar)
            return {"message": "Token is recieved"}
            
        except httpx.HTTPStatusError as exc:
            
            raise HTTPException(
                status_code=502,
                detail=f"Error from Google: {exc.response.text}"
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to Google: {str(exc)}"
            )

@google_calendar_router.get('/google-calendar/token/2', response_model=AccessTokenResponse)
async def save_google_calendar_token(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> AccessTokenResponse:
    google_auth_detail = session.query(GoogleCalendar).filter(GoogleCalendar.user.id == current_user.id).first()
    
    if not google_auth_detail:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar not linked for this user."
        )
    
    if not google_auth_detail.refresh_token:
        raise HTTPException(
            status_code=401, 
            detail="Missing refresh token. Please re-authenticate Google Calendar."
        )
    if google_auth_detail.expires_at > (datetime.now(timezone) + + timedelta(minutes=5)):
        return google_auth_detail.access_token
    
    refresh_playload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refreshh_token": google_auth_detail.referesh_token,
        "grant_type": refresh_playload
    }

    async with httpx.AsyncClient as client:
        try:
            response = await client.post("https://oauth2.googleapis.com/token", data=refresh_playload)
            response.raise_for_status() 
            new_token_data = response.json()
            
            google_auth_detail.access_token = new_token_data['access_token']
            new_expires_in = new_token_data['expires_in']
            google_auth_detail.expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)
          
            if 'refresh_token' in new_token_data:
                google_auth_detail.refresh_token = new_token_data['refresh_token']
            
            session.commit()
            session.refresh(google_auth_detail)
            
            return google_auth_detail.access_token

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400 or exc.response.status_code == 401:

                google_auth_detail.access_token = None 
                google_auth_detail.refresh_token = None 
                google_auth_detail.expires_at = datetime.now(timezone.utc) #
                session.commit()
                raise HTTPException(
                    status_code=401, 
                    detail=f"Failed to refresh Google token (may be revoked: {exc.response.text}). Please re-authenticate."
                )
            raise HTTPException(
                status_code=502, 
                detail=f"Error refreshing token from Google: {exc.response.text}"
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Could not connect to Google to refresh token: {str(exc)}")
