import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from models.ai_goal_usage import AIGoalUsage
from services.ai_usage import (
    AIAllowanceExceeded,
    finalize_ai_usage,
    get_ai_allowance,
    reserve_ai_usage,
)


class AIUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        self.user_id = uuid.uuid4()
        self.now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

    def reserve(self, session: Session) -> AIGoalUsage:
        return reserve_ai_usage(
            session,
            user_id=self.user_id,
            feature="goal_plan",
            provider="openai",
            model="test-model",
            now=self.now,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_reserves_unique_monthly_slots_and_blocks_at_limit(self) -> None:
        with patch.dict(os.environ, {"AI_GOAL_MONTHLY_REQUEST_LIMIT": "2"}):
            with Session(self.engine) as session:
                first = self.reserve(session)
                second = self.reserve(session)
                self.assertEqual({first.quota_slot, second.quota_slot}, {1, 2})
                allowance = get_ai_allowance(session, self.user_id, now=self.now)
                self.assertEqual((allowance.used, allowance.remaining), (2, 0))
                with self.assertRaises(AIAllowanceExceeded):
                    self.reserve(session)

    def test_technical_failure_releases_slot_but_keeps_audit_row(self) -> None:
        with patch.dict(os.environ, {"AI_GOAL_MONTHLY_REQUEST_LIMIT": "1"}):
            with Session(self.engine) as session:
                usage = self.reserve(session)
                finalize_ai_usage(
                    session,
                    usage.id,
                    status="provider_unavailable",
                    counted=False,
                    error_code="provider_unavailable",
                    now=self.now,
                )
                allowance = get_ai_allowance(session, self.user_id, now=self.now)
                self.assertEqual((allowance.used, allowance.remaining), (0, 1))
                replacement = self.reserve(session)
                self.assertEqual(replacement.quota_slot, 1)
                records = session.exec(select(AIGoalUsage)).all()
                self.assertEqual(len(records), 2)
                self.assertEqual(records[0].status, "provider_unavailable")
                self.assertIsNone(records[0].quota_slot)

    def test_unlimited_mode_tracks_usage_without_exhaustion(self) -> None:
        with patch.dict(os.environ, {"AI_GOAL_MONTHLY_REQUEST_LIMIT": "-1"}):
            with Session(self.engine) as session:
                self.reserve(session)
                self.reserve(session)
                allowance = get_ai_allowance(session, self.user_id, now=self.now)
                self.assertIsNone(allowance.limit)
                self.assertIsNone(allowance.remaining)
                self.assertEqual(allowance.used, 2)

    def test_stale_reservation_is_reclaimed_after_interrupted_request(self) -> None:
        with patch.dict(os.environ, {"AI_GOAL_MONTHLY_REQUEST_LIMIT": "1"}):
            with Session(self.engine) as session:
                old_now = self.now - timedelta(hours=1)
                old = reserve_ai_usage(
                    session,
                    user_id=self.user_id,
                    feature="goal_plan",
                    provider="openai",
                    model="test-model",
                    now=old_now,
                )
                replacement = self.reserve(session)
                session.refresh(old)
                self.assertEqual(old.status, "abandoned")
                self.assertFalse(old.counted)
                self.assertEqual(replacement.quota_slot, 1)


if __name__ == "__main__":
    unittest.main()
