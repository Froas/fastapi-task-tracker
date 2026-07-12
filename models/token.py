from sqlmodel import SQLModel
from .user import User
from datetime import timedelta, timezone, datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated
from sqlmodel import Session
from db import get_session
from jose.exceptions import ExpiredSignatureError, JWTError
from jose import jwt
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = os.getenv('ALGORITHM')

class Token(SQLModel):
    access_token: str
    token_type: str

class TokenData(SQLModel):
    sub: str
    

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    if not SECRET_KEY or not ALGORITHM:
        raise RuntimeError('SECRET_KEY and ALGORITHM must be configured')
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Session = Depends(get_session)
    ):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        if not SECRET_KEY or not ALGORITHM:
            raise credentials_exception
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str = payload.get("sub")
        if sub is None:
            raise credentials_exception
        token_data = TokenData(sub=sub)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception
    try:
        user_id = uuid.UUID(token_data.sub)  
    except ValueError:
        raise credentials_exception
    
    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    # if current_user.disabled:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
