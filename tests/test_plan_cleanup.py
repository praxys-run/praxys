"""Future-delivery cleanup tests for leaving managed-plan mode."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.plan_cleanup import (
    PlanCleanupAmbiguousTargets,
    PlanCleanupRequiresExternalMode,
    cleanup_future_plan_deliveries,
)
from api.plan_delivery.base import (
    ProviderAuthenticationRequiredError,
    ProviderRateLimitError,
    ProviderRemoveResult,
)
from db.models import (
    Base,
    PlanDelivery,
    PlanDeliveryAttempt,
    User,
    UserConfig,
    UserConnection,
)


USER_ID = "plan-cleanup-user"
TARGET = "stryd"
ACCOUNT_ID = "cleanup-provider-account"


class FakeCleanupAdapter:
    """Minimal provider adapter for owned-workout removal."""

    target = TARGET
    display_name = "Fake target"

    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.delete_failures: list[Exception] = []
        self.authenticate_calls = 0

    @property
    def account_id(self) -> str:
        return ACCOUNT_ID

    def authenticate(self) -> None:
        self.authenticate_calls += 1

    def delete_workout(
        self,
        external_id: str,
        *,
        hooks,
    ) -> ProviderRemoveResult:
        hooks.before_mutation()
        if self.delete_failures:
            raise self.delete_failures.pop(0)
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
    db.add(UserConnection(
        user_id=USER_ID,
        platform=TARGET,
        status="connected",
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
    target: str = TARGET,
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
        target=target,
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


def test_cleanup_rate_limit_stops_remaining_provider_removals(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    first = _add_delivery(
        db,
        today + timedelta(days=2),
        external_id="owned-first",
    )
    second = _add_delivery(
        db,
        today + timedelta(days=3),
        external_id="owned-second",
    )
    adapter = FakeCleanupAdapter()
    adapter.delete_failures.append(
        ProviderRateLimitError("provider rate limit")
    )

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert adapter.deleted == []
    assert [item.status for item in result.items] == ["failed", "blocked"]
    assert [item.reason for item in result.items] == [
        "provider_rate_limited",
        "provider_rate_limited",
    ]
    latest_attempt = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.delivery_id == first.id)
        .order_by(PlanDeliveryAttempt.attempt_number.desc())
    ).scalars().first()
    assert latest_attempt is not None
    assert latest_attempt.state == "failed"
    assert (
        latest_attempt.response["error_category"]
        == "provider_rate_limited"
    )
    db.refresh(second)
    assert second.state == "synced"


def test_cleanup_auth_failure_stops_batch_and_disconnects_connection(
    cleanup_db,
):
    db = cleanup_db
    today = date(2026, 8, 1)
    first = _add_delivery(
        db,
        today + timedelta(days=2),
        external_id="owned-first",
    )
    second = _add_delivery(
        db,
        today + timedelta(days=3),
        external_id="owned-second",
    )
    adapter = FakeCleanupAdapter()
    adapter.delete_failures.append(
        ProviderAuthenticationRequiredError("reconnect Garmin")
    )

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert adapter.deleted == []
    assert [item.status for item in result.items] == ["failed", "blocked"]
    assert [item.reason for item in result.items] == [
        "provider_authentication_failed",
        "provider_authentication_failed",
    ]
    latest_attempt = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.delivery_id == first.id)
        .order_by(PlanDeliveryAttempt.attempt_number.desc())
    ).scalars().first()
    assert latest_attempt is not None
    assert latest_attempt.state == "failed"
    db.refresh(second)
    assert second.state == "synced"
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    assert connection.status == "auth_required"
    assert connection.next_retry_at is None


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


def test_cleanup_infers_ledger_target_when_config_target_is_cleared(
    cleanup_db,
):
    db = cleanup_db
    today = date(2026, 8, 1)
    delivery = _add_delivery(
        db,
        today + timedelta(days=1),
        external_id="owned-with-cleared-target",
    )
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
    adapter = FakeCleanupAdapter()

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "complete"
    assert result.target == TARGET
    assert result.removed_count == 1
    assert adapter.deleted == ["owned-with-cleared-target"]
    assert db.get(PlanDelivery, delivery.id).state == "removed"


def test_cleanup_blocks_multiple_outstanding_targets(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    _add_delivery(
        db,
        today + timedelta(days=1),
        external_id="stryd-owned",
    )
    _add_delivery(
        db,
        today + timedelta(days=2),
        external_id="garmin-owned",
        target="garmin",
    )

    with pytest.raises(
        PlanCleanupAmbiguousTargets,
        match="multiple execution targets",
    ):
        cleanup_future_plan_deliveries(
            db,
            user_id=USER_ID,
            today=today,
            adapter_loader=lambda: FakeCleanupAdapter(),
        )


def test_cleanup_reports_conflict_without_external_id(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    _add_delivery(
        db,
        today + timedelta(days=1),
        state="conflict",
        external_id=None,
    )
    adapter = FakeCleanupAdapter()

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert result.removed_count == 0
    assert result.remaining_count == 1
    assert result.items[0].status == "blocked"
    assert result.items[0].reason == "delivery_conflict"
    assert adapter.authenticate_calls == 0


def test_cleanup_retries_expired_removal_lease(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    delivery = _add_delivery(
        db,
        today + timedelta(days=1),
        state="delivering",
        external_id="stale-removal",
    )
    db.add(PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        operation="remove",
        state="delivering",
        external_id=delivery.external_id,
        started_at=datetime.utcnow() - timedelta(minutes=6),
    ))
    db.commit()
    adapter = FakeCleanupAdapter()

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "complete"
    assert result.removed_count == 1
    assert result.remaining_count == 0
    assert adapter.deleted == ["stale-removal"]
    assert db.get(PlanDelivery, delivery.id).state == "removed"


def test_cleanup_stops_when_managed_state_changes(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    first = _add_delivery(
        db,
        today + timedelta(days=1),
        external_id="first-owned",
    )
    second = _add_delivery(
        db,
        today + timedelta(days=2),
        external_id="second-owned",
    )

    class StateChangingAdapter(FakeCleanupAdapter):
        def delete_workout(
            self,
            external_id: str,
            *,
            hooks,
        ) -> ProviderRemoveResult:
            result = super().delete_workout(
                external_id,
                hooks=hooks,
            )
            if len(self.deleted) == 1:
                config = db.execute(
                    select(UserConfig).where(UserConfig.user_id == USER_ID)
                ).scalar_one()
                config.plan_management = {
                    "mode": "praxys",
                    "execution_target": TARGET,
                    "delivery_enabled": True,
                    "adjustment_policy": "suggest_only",
                }
                db.commit()
            return result

    adapter = StateChangingAdapter()
    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert result.removed_count == 1
    assert result.remaining_count == 1
    assert adapter.deleted == ["first-owned"]
    assert db.get(PlanDelivery, first.id).state == "removed"
    assert db.get(PlanDelivery, second.id).state == "synced"
    assert result.items[1].reason == "managed_plan_state_changed"


def test_cleanup_blocks_degraded_connection(cleanup_db):
    db = cleanup_db
    today = date(2026, 8, 1)
    delivery = _add_delivery(
        db,
        today + timedelta(days=1),
        external_id="owned-but-disconnected",
    )
    connection = db.execute(
        select(UserConnection).where(UserConnection.user_id == USER_ID)
    ).scalar_one()
    connection.status = "auth_required"
    db.commit()
    adapter = FakeCleanupAdapter()

    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert result.removed_count == 0
    assert result.remaining_count == 1
    assert result.items[0].external_id == delivery.external_id
    assert result.items[0].status == "failed"
    assert result.items[0].reason == "connection_auth_required"
    assert adapter.authenticate_calls == 0
    assert adapter.deleted == []


def test_garmin_cleanup_rechecks_consent_before_unschedule(
    cleanup_db,
    monkeypatch,
):
    from api.plan_delivery.capabilities import (
        plan_delivery_account_fence_token,
    )

    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name
        == "garmin_plan_delivery_eligible",
    )
    db = cleanup_db
    today = date(2026, 8, 1)
    delivery = _add_delivery(
        db,
        today + timedelta(days=1),
        external_id="garmin-owned",
        target="garmin",
    )
    config = db.execute(
        select(UserConfig).where(UserConfig.user_id == USER_ID)
    ).scalar_one()
    config.plan_management = {
        "mode": "external",
        "execution_target": "garmin",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }
    config.source_options = {"garmin_region": "international"}
    connection = db.execute(
        select(UserConnection).where(UserConnection.user_id == USER_ID)
    ).scalar_one()
    connection.platform = "garmin"
    db.flush()
    connection.plan_delivery_consent = plan_delivery_account_fence_token(
        connection,
        region="international",
    )
    db.commit()

    class ConsentRevokingAdapter(FakeCleanupAdapter):
        target = "garmin"

        def authenticate(self) -> None:
            super().authenticate()
            fresh = db.execute(
                select(UserConnection).where(
                    UserConnection.user_id == USER_ID,
                    UserConnection.platform == "garmin",
                )
            ).scalar_one()
            fresh.plan_delivery_consent = None
            db.commit()

    adapter = ConsentRevokingAdapter()
    result = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert result.status == "partial"
    assert result.items[0].status == "blocked"
    assert result.items[0].reason == "delivery_account_fence_required"
    assert adapter.deleted == []
    assert db.get(PlanDelivery, delivery.id).state == "synced"
