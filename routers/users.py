from fastapi import APIRouter, HTTPException, Depends, Query, Path
from fastapi_users import FastAPIUsers, models as fastapi_models
from fastapi_users.authentication import JWTStrategy, AuthenticationBackend, BearerTransport
# from fastapi_users.db import SQL
from models import User, UserBase,UserRead
from sqlmodel import Session, select
from db import get_session
import uuid



SECRET = "YOUR_SECRET_KEY"

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

def get_user_db(session: Session = Depends(get_session)):
    pass
    # yield SQLModelUserDatabase(User, session)

# Создание экземпляра FastAPI Users
# fastapi_users = FastAPIUsers(
#     get_user_db,
#     [auth_backend],
#     User,
#     fastapi_models.BaseUserCreate,
#     fastapi_models.BaseUserUpdate,
#     fastapi_models.BaseUserDB,
# )

# Определение текущего пользователя
# current_user = fastapi_users.current_user()


users_router = APIRouter()

async def get_current_user(
    session: Session = Depends(get_session)
) -> UserRead:
    user_list = session.exec(select(User)).all()
    return user_list[0]

@users_router.get('/')
async def user(
    session: Session = Depends(get_session)
) -> list[UserRead]:
    user_list = session.exec(select(User)).all()
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

@users_router.patch('/update')
async def user(
    user_data: User,
    session: Session = Depends(get_session)
) -> UserRead:
    user_id = uuid.UUID(user_data.id)
    user = session.get(User, user_id)
    if user_data.username is not None:
        user.username = user_data.username
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# users_router.include_router(
#     fastapi_users.get_auth_router(auth_backend),
#     prefix="/auth/jwt",
#     tags=["auth"],
# )
# users_router.include_router(
#     fastapi_users.get_register_router(),
#     prefix="/auth",
#     tags=["auth"],
# )

# users_router.include_router(
#     fastapi_users.get_users_router(),
#     prefix="/users",
#     tags=["users"],
# )