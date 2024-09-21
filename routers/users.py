from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from models import User, UserBase,UserRead, Token, verify_password, create_access_token, get_current_active_user
from sqlmodel import Session, select
from db import get_session
from dotenv import load_dotenv
import uuid
import os
 
load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')

def authenticate_user(session: Session, username: str, password: str):
    statement = select(User).where(User.username == username)
    result = session.exec(statement)
    user = result.first()
    if not user: 
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user

users_router = APIRouter()


@users_router.get('/me', response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user

@users_router.get('/')
async def user(
    session: Session = Depends(get_session)
) -> list[UserRead]:
    user_list = session.exec(select(User)).all()
    print(f'ALl users{user_list}')
    return user_list



@users_router.get('/{user_id}')
async def user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> UserRead:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Event has not found")
    return user

@users_router.post('/')
async def user(
    user_data: UserBase,
    session: Session = Depends(get_session)
) -> User:
    user = User(username=user_data.username, email=user_data.email)
    user.set_password(user_data.password_hash)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@users_router.patch('/update')
async def user(
    user_data: User,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> UserRead:
    user_id = uuid.UUID(user_data.id)
    user = session.get(User, user_id)
    if user is not None & user.id != current_user.id:
        raise HTTPException(status_code=404, detail="User has not founded")
    if user_data.username is not None:
        user.username = user_data.username
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@users_router.post('/token')
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Session = Depends(get_session)
) -> Token:
    user: User  = authenticate_user(session=session, password=form_data.password, username=form_data.username)
    if not user:
        raise HTTPException(
            status_code=404,  
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type='bearer')



@users_router.delete('/{user_id}/delete')
async def user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User has not found")
    session.delete(user)
    session.commit()
    return {"message": "User has been deleted successfully"}
    
