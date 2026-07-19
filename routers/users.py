from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from models import (
    User,
    UserBase,
    UserRead,
    UserUpdate,
    Token,
    RefreshTokenRequest,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_current_active_user,
)
from sqlmodel import Session, select
from db import get_session
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError
import uuid
import os
 
load_dotenv()

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = max(
        1,
        int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '60')),
    )
except ValueError:
    ACCESS_TOKEN_EXPIRE_MINUTES = 60

try:
    REFRESH_TOKEN_EXPIRE_DAYS = max(
        1,
        int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '30')),
    )
except ValueError:
    REFRESH_TOKEN_EXPIRE_DAYS = 30


def issue_token_pair(user_id: uuid.UUID) -> Token:
    subject = {"sub": str(user_id)}
    return Token(
        access_token=create_access_token(
            data=subject,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        ),
        refresh_token=create_refresh_token(
            data=subject,
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        ),
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def authenticate_user(session: Session, username: str, password: str):
    statement = select(User).where(User.username == username)
    result = session.exec(statement)
    user = result.first()
    if not user: 
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


def apply_user_update(user: User, payload: UserUpdate, session: Session) -> User:
    update_data = payload.model_dump(exclude_unset=True, exclude={'id'})
    if 'username' in update_data:
        existing = session.exec(
            select(User).where(
                User.username == update_data['username'],
                User.id != user.id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
    if 'email' in update_data:
        existing = session.exec(
            select(User).where(
                User.email == update_data['email'],
                User.id != user.id,
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
    for key, value in update_data.items():
        setattr(user, key, value)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Username or email already in use")
    session.refresh(user)
    return user

users_router = APIRouter()


@users_router.get('/me', response_model=UserRead)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user

@users_router.get('/')
async def user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[UserRead]:
    return [current_user]



@users_router.get('/{user_id}')
async def user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> UserRead:
    if user_id != current_user.id:
        raise HTTPException(status_code=404, detail="User not found")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@users_router.post('/', response_model=UserRead)
async def user(
    user_data: UserBase,
    session: Session = Depends(get_session)
) -> UserRead:
    # Pre-check for a friendlier error than a raw IntegrityError trace.
    existing = session.exec(select(User).where(User.username == user_data.username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    existing_email = session.exec(select(User).where(User.email == user_data.email)).first()
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(username=user_data.username, email=user_data.email)
    user.set_password(user_data.password_hash)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # Race / unique constraint we didn't catch above.
        session.rollback()
        raise HTTPException(status_code=409, detail="Username or email already in use")
    session.refresh(user)
    return user


@users_router.patch('/update', response_model=UserRead)
async def user(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> UserRead:
    if user_data.id is not None and user_data.id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot update another user")
    user = session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return apply_user_update(user, user_data, session)


@users_router.post('/token')
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session)
) -> Token:
    user: User  = authenticate_user(session=session, password=form_data.password, username=form_data.username)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issue_token_pair(user.id)


@users_router.post('/refresh', response_model=Token)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    session: Session = Depends(get_session),
) -> Token:
    token_data = decode_refresh_token(payload.refresh_token)
    try:
        user_id = uuid.UUID(token_data.sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Could not validate refresh token")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate refresh token")
    # Return a new pair so an active session keeps sliding forward.
    return issue_token_pair(user.id)



@users_router.patch('/me', response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
):
    """Patch the calling user's profile (preferred_theme, etc.).
    Identity fields (username/email/password) go through their own endpoints."""
    user = session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.id is not None and payload.id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot update another user")
    return apply_user_update(user, payload, session)


@users_router.delete('/{user_id}/delete')
async def user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, str]:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete another user")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User has not found")
    session.delete(user)
    session.commit()
    return {"message": "User has been deleted successfully"}
