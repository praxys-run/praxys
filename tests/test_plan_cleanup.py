"""Future-delivery cleanup tests for leaving managed-plan mode."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.plan_cleanup import (
    PlanCleanupRequiresExternalMode,
    cleanup_future_plan_deliveries,
)
from api.plan_delivery.base import ProviderRemoveResult
from db.models import Base, PlanDelivery, User, UserConfig


USER_ID = "plan-cleanup-user"
TARGET = "stryd"
ACCOUNT_ID = "cleanup-provider-account"


class FakeCleanupAdapter:
    """Minimal provider adapter for owned-workout removal."""

    target = TARGET
    display_name = "Fake target"

    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.authenticate_calls = 0

    @property
    def account_id(self) -> str:
        return ACCOUNT_ID

    def authenticate(self) -> None:
        self.authenticate_calls += 1

    def delete_workout(self, external_id: str) -> ProviderRemoveResult:
        self.deleted.append(external_id)
        return ProviderRemoveResult()


@pytest.fixture
def cleanup_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'plan-cleanup.db'}")
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = session_factory()
    db.add(User(
        id=USER_ID,
        email="plan-cleanup@example.test",
        hashed_password="test",
    ))
    db.add(UserConfig(
        user_id=USER_ID,
        plan_management={
            "mode": "external",
            "execution_target": TARGET,
            "delivery_enabled": False,
            "adjustment_policy": "suggest_only",
        },
    ))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _add_delivery(
    db: Session,
    workout_date: date,
    *,
    state: str = "synced",
    external_id: str | None,
) -> PlanDelivery:
    canonical_id = str(uuid4())
    delivery = PlanDelivery(
        user_id=USER_ID,
        canonical_key=f"ai:{canonical_id}",
        canonical_id=canonical_id,
        workout_date=workout_date,
        workout_version=str(uuid4()).replace("-", ""),
        plan_version=str(uuid4()).replace("-", ""),
        provider_content_version=str(uuid4()).replace("-", ""),
        target=TARGET,
        state=state,
        external_id=external_id,
        provider_account_id=ACCOUNT_ID,
    )
    db.add(delivery)
    db.commit()
    return delivery


def test_cleanup_removes_only_future_synced_deliveries(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    removable = _add_delivery(
        db,
        today + timedelta(days=2),
        external_id="owned-future",
    )
    blocked = _add_delivery(
        db,
        today + timedelta(days=3),
        state="conflict",
        external_id="conflicted-future",
    )
    past = _add_delivery(
        db,
        today - timedelta(days=1),
        external_id="owned-past",
    )
    adapter = FakeCleanupAdapter()

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert result.removed_count == 1
    assert result.remaining_count == 1
    assert adapter.deleted == ["owned-future"]
    assert db.get(PlanDelivery, removable.id).state == "removed"
    assert db.get(PlanDelivery, blocked.id).state == "conflict"
    assert db.get(PlanDelivery, past.id).state == "synced"
    assert [
        (item.external_id, item.status, item.reason)
        for item in result.items
    ] == [
        ("owned-future", "removed", None),
        ("conflicted-future", "blocked", "delivery_conflict"),
    ]


def test_cleanup_requires_external_mode(cleanup_db):
    db = cleanup_db
    config = db.execute(
        select(UserConfig).where(UserConfig.user_id == USER_ID)
    ).scalar_one()
    config.plan_management = {
        "mode": "praxys",
        "execution_target": TARGET,
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }
    db.commit()

    with pytest.raises(
        PlanCleanupRequiresExternalMode,
        match="Leave managed mode",
    ):
        cleanup_future_plan_deliveries(
            db,
            user_id=USER_ID,
            today=date(2026, 8, 1),
            adapter_loader=lambda: FakeCleanupAdapter(),
        )


def test_cleanup_without_target_is_a_noop(cleanup_db):
    db = cleanup_db
    config = db.execute(
        select(UserConfig).where(UserConfig.user_id == USER_ID)
    ).scalar_one()
    config.plan_management = {
        "mode": "external",
        "execution_target": None,
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }
    db.commit()

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=date(2026, 8, 1),
        adapter_loader=lambda: FakeCleanupAdapter(),
    )

    assert result.status == "complete"
    assert result.target is None
    assert result.items == ()
