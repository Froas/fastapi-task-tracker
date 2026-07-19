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
    refresh_token: str
    token_type: str
    expires_in: int


class RefreshTokenRequest(SQLModel):
    refresh_token: str

class TokenData(SQLModel):
    sub: str
    

def _create_token(data: dict, token_type: str, expires_delta: timedelta):
    if not SECRET_KEY or not ALGORITHM:
        raise RuntimeError('SECRET_KEY and ALGORITHM must be configured')
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "type": token_type})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    return _create_token(data, "access", expires_delta or timedelta(minutes=15))


def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    return _create_token(data, "refresh", expires_delta or timedelta(days=30))


def decode_refresh_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not SECRET_KEY or not ALGORITHM:
            raise credentials_exception
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise credentials_exception
        return TokenData(sub=sub)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception

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
        # Refresh tokens must never be accepted as API bearer tokens. Tokens
        # without a type are accepted temporarily for pre-refresh-flow sessions.
        if payload.get("type") not in (None, "access"):
            raise credentials_exception
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
