from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models.ai_goal_usage import AIGoalUsage


DEFAULT_MONTHLY_REQUEST_LIMIT = 20
STALE_RESERVATION_MINUTES = 15


class AIAllowanceExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class AIAllowance:
    limit: int | None
    used: int
    remaining: int | None
    resets_at: datetime

    def as_dict(self) -> dict[str, int | str | None]:
        return {
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "resets_at": self.resets_at.isoformat().replace("+00:00", "Z"),
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def monthly_request_limit() -> int:
    raw = os.getenv("AI_GOAL_MONTHLY_REQUEST_LIMIT", str(DEFAULT_MONTHLY_REQUEST_LIMIT)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MONTHLY_REQUEST_LIMIT
    return max(-1, min(value, 10_000))


def _period(now: datetime) -> tuple[str, datetime]:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    if current.month == 12:
        reset = datetime(current.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        reset = datetime(current.year, current.month + 1, 1, tzinfo=timezone.utc)
    return f"{current.year:04d}-{current.month:02d}", reset


def _reset_label(reset: datetime) -> str:
    return f"{reset.strftime('%B')} {reset.day}"


def _active_period_records(
    session: Session,
    user_id: uuid.UUID,
    period: str,
    *,
    slotted_only: bool = True,
) -> list[AIGoalUsage]:
    statement = select(AIGoalUsage).where(
        AIGoalUsage.user_id == user_id,
        AIGoalUsage.quota_period == period,
        AIGoalUsage.counted == True,  # noqa: E712 - SQL expression
    )
    if slotted_only:
        statement = statement.where(AIGoalUsage.quota_slot.is_not(None))
    return list(session.exec(statement).all())


def get_ai_allowance(
    session: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> AIAllowance:
    current = now or _utcnow()
    period, reset = _period(current)
    limit = monthly_request_limit()
    records = _active_period_records(session, user_id, period, slotted_only=limit >= 0)
    used = len(records)
    if limit < 0:
        return AIAllowance(limit=None, used=used, remaining=None, resets_at=reset)
    return AIAllowance(limit=limit, used=used, remaining=max(limit - used, 0), resets_at=reset)


def _release_stale_reservations(
    session: Session,
    user_id: uuid.UUID,
    period: str,
    now: datetime,
) -> None:
    cutoff = now - timedelta(minutes=STALE_RESERVATION_MINUTES)
    stale = session.exec(
        select(AIGoalUsage).where(
            AIGoalUsage.user_id == user_id,
            AIGoalUsage.quota_period == period,
            AIGoalUsage.status == "started",
            AIGoalUsage.created_at < cutoff,
            AIGoalUsage.quota_slot.is_not(None),
        )
    ).all()
    for record in stale:
        record.status = "abandoned"
        record.counted = False
        record.quota_slot = None
        record.error_code = "stale_reservation"
        record.updated_at = now
        session.add(record)


def reserve_ai_usage(
    session: Session,
    *,
    user_id: uuid.UUID,
    feature: str,
    provider: str,
    model: str,
    now: datetime | None = None,
) -> AIGoalUsage:
    current = now or _utcnow()
    period, reset = _period(current)
    limit = monthly_request_limit()
    if limit == 0:
        raise AIAllowanceExceeded(
            f"Monthly AI allowance used. It resets {_reset_label(reset)} (UTC)."
        )

    attempts = max(limit, 1) + 1 if limit > 0 else 1
    for _ in range(attempts):
        _release_stale_reservations(session, user_id, period, current)
        used_slots = {
            record.quota_slot
            for record in _active_period_records(session, user_id, period)
            if record.quota_slot is not None
        }
        if limit > 0:
            slot = next((candidate for candidate in range(1, limit + 1) if candidate not in used_slots), None)
            if slot is None:
                session.commit()
                raise AIAllowanceExceeded(
                    f"Monthly AI allowance used. It resets {_reset_label(reset)} (UTC)."
                )
        else:
            slot = None

        record = AIGoalUsage(
            user_id=user_id,
            feature=feature,
            provider=provider,
            model=model,
            quota_period=period,
            quota_slot=slot,
            created_at=current,
            updated_at=current,
        )
        session.add(record)
        try:
            session.commit()
            session.refresh(record)
            return record
        except IntegrityError:
            session.rollback()
            if limit < 0:
                raise

    raise AIAllowanceExceeded(
        f"Monthly AI allowance used. It resets {_reset_label(reset)} (UTC)."
    )


def finalize_ai_usage(
    session: Session,
    usage_id: uuid.UUID,
    *,
    status: str,
    counted: bool,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    error_code: str | None = None,
    now: datetime | None = None,
) -> None:
    record = session.get(AIGoalUsage, usage_id)
    if record is None:
        return
    record.status = status[:32]
    record.counted = counted
    if not counted:
        record.quota_slot = None
    record.input_tokens = max(int(input_tokens), 0)
    record.output_tokens = max(int(output_tokens), 0)
    record.total_tokens = max(int(total_tokens), 0)
    record.error_code = error_code[:64] if error_code else None
    record.updated_at = now or _utcnow()
    session.add(record)
    session.commit()
