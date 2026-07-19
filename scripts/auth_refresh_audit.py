from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from db import get_session
from main import app
from models import User, create_refresh_token
from models.token import ALGORITHM, SECRET_KEY


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    user = User(username="auth-audit", email="auth-audit@example.com", password_hash="unused")
    user.set_password("audit-password")
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id


def session_override():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_session] = session_override
client = TestClient(app)


def require_status(response, expected: int = 200):
    if response.status_code != expected:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path}: "
            f"{response.status_code} {response.text}"
        )
    return response.json()


try:
    pair = require_status(client.post(
        "/users/token",
        data={"username": "auth-audit", "password": "audit-password"},
    ))
    assert pair["access_token"]
    assert pair["refresh_token"]
    assert pair["expires_in"] == 60 * 60

    access_payload = jwt.decode(pair["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    refresh_payload = jwt.decode(pair["refresh_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == str(user_id)

    require_status(client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {pair['access_token']}"},
    ))
    require_status(client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {pair['refresh_token']}"},
    ), 401)

    refreshed = require_status(client.post(
        "/users/refresh",
        json={"refresh_token": pair["refresh_token"]},
    ))
    require_status(client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    ))

    require_status(client.post(
        "/users/refresh",
        json={"refresh_token": pair["access_token"]},
    ), 401)
    expired_refresh = create_refresh_token(
        {"sub": str(user_id)},
        expires_delta=timedelta(seconds=-1),
    )
    require_status(client.post(
        "/users/refresh",
        json={"refresh_token": expired_refresh},
    ), 401)
finally:
    app.dependency_overrides.clear()

print("Auth refresh audit passed: login, refresh, token separation, and expiry")
