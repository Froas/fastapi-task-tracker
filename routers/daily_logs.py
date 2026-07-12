from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import Annotated
from datetime import date as Date, datetime

from models import DailyLog, DailyLogCreate, DailyLogUpdate, DailyLogRead, User, get_current_active_user
from db import get_session
from routers.daily_lifecycle import finalize_past_days, logical_today
from utils.timezone import JST

daily_logs_router = APIRouter()

VALID_COLORS = {"green", "yellow", "red", "black"}


def _normalize_color(color: str | None) -> str | None:
    if color is None:
        return None
    normalized = color.strip().lower()
    if normalized not in VALID_COLORS:
        raise HTTPException(status_code=400, detail="Daily log color must be green, yellow, red, or black")
    return normalized


def _log_for_date(session: Session, user: User, selected_date: Date) -> DailyLog | None:
    return session.exec(
        select(DailyLog)
        .where(DailyLog.user_id == user.id)
        .where(DailyLog.deleted_at.is_(None))
        .where(DailyLog.date == selected_date)
    ).first()


def _create_empty_log(session: Session, user: User, selected_date: Date) -> DailyLog:
    log = DailyLog(date=selected_date, user_id=user.id)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@daily_logs_router.get('/user/daily-logs')
async def list_daily_logs(
    current_user: Annotated[User, Depends(get_current_active_user)],
    start_date: Date | None = None,
    end_date: Date | None = None,
    session: Session = Depends(get_session),
) -> list[DailyLogRead]:
    query = (
        select(DailyLog)
        .where(DailyLog.user_id == current_user.id)
        .where(DailyLog.deleted_at.is_(None))
    )
    if start_date is not None:
        query = query.where(DailyLog.date >= start_date)
    if end_date is not None:
        query = query.where(DailyLog.date <= end_date)
    return session.exec(query.order_by(DailyLog.date.desc())).all()


@daily_logs_router.get('/user/daily-logs/today')
async def get_today_daily_log(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> DailyLogRead:
    selected_date = logical_today()
    finalize_past_days(session, current_user, today=selected_date)
    session.commit()
    return _log_for_date(session, current_user, selected_date) or _create_empty_log(session, current_user, selected_date)


@daily_logs_router.get('/user/daily-logs/{selected_date}')
async def get_daily_log_by_date(
    selected_date: Date,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> DailyLogRead:
    today = logical_today()
    if selected_date < today:
        finalize_past_days(session, current_user, today=today, extra_dates=[selected_date])
        session.commit()
    return _log_for_date(session, current_user, selected_date) or _create_empty_log(session, current_user, selected_date)


@daily_logs_router.post('/user/daily-logs/finalize-past')
async def finalize_past_daily_logs(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Session = Depends(get_session),
) -> dict[str, int | str]:
    today = logical_today()
    finalized_count = finalize_past_days(session, current_user, today=today)
    session.commit()
    return {"message": "Past days finalized", "finalized": finalized_count}


@daily_logs_router.post('/user/daily-logs')
async def create_daily_log(
    current_user: Annotated[User, Depends(get_current_active_user)],
    log_data: DailyLogCreate,
    session: Session = Depends(get_session),
) -> DailyLogRead:
    selected_date = log_data.date or logical_today()
    log = _log_for_date(session, current_user, selected_date)
    if log is None:
        log = DailyLog(date=selected_date, user_id=current_user.id)

    update_data = log_data.model_dump(exclude_unset=True, exclude={"date"})
    if "color" in update_data:
        update_data["color"] = _normalize_color(update_data["color"])
    for key, value in update_data.items():
        setattr(log, key, value)
    log.updated_at = datetime.now(JST)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


@daily_logs_router.patch('/user/daily-logs/update', response_model=DailyLogRead)
async def update_daily_log(
    current_user: Annotated[User, Depends(get_current_active_user)],
    log_data: DailyLogUpdate,
    session: Session = Depends(get_session),
) -> DailyLog:
    log = session.get(DailyLog, log_data.id)
    if log is None or log.user_id != current_user.id or log.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Daily log not found")

    update_data = log_data.model_dump(exclude_unset=True, exclude={"id"})
    if "color" in update_data:
        update_data["color"] = _normalize_color(update_data["color"])

    if "date" in update_data:
        existing = _log_for_date(session, current_user, update_data["date"])
        if existing is not None and existing.id != log.id:
            raise HTTPException(status_code=409, detail="Daily log already exists for that date")

    for key, value in update_data.items():
        setattr(log, key, value)
    log.updated_at = datetime.now(JST)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log
