"""Provider-neutral rolling managed-plan delivery tests."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from api.plan_delivery.base import (
    PreparedWorkoutDelivery,
    ProviderAuthenticationError,
    ProviderCreateResult,
    ProviderRateLimitError,
    ProviderRejectedError,
    ProviderRemoveResult,
    ProviderRemovalError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.credentials import DeliveryCredentialsInvalid
from api.plan_delivery.rolling import (
    _managed_delivery_lock_engine,
    _managed_delivery_run_lease,
    _recover_managed_inflight_attempts,
    run_rolling_delivery_for_user,
)
from api.plan_reconciliation import build_plan_reconciliation
from api.plan_resolution import restore_praxys_version
from api.managed_plan_ops import (
    ManagedPlanRecoveryBusy,
    ManagedPlanRecoveryStale,
    list_managed_plan_attention,
    recover_managed_plan_delivery,
)
from api.plan_cleanup import cleanup_future_plan_deliveries
from db.models import (
    Base,
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanRevision,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    TrainingPlan,
    User,
    UserConfig,
    UserConnection,
)
from db.plan_ledger import (
    DELIVERY_ATTEMPT_LEASE,
    append_delivery_event,
    begin_delivery_attempt,
    get_or_create_delivery,
    lock_plan_writes,
    plan_snapshot,
)


USER_ID = "managed-delivery-user"
TARGET = "stryd"
ACCOUNT_ID = "provider-account"
CP_WATTS = 280.0


class FakeDeliveryAdapter:
    """In-memory provider adapter with deterministic fingerprints."""

    target = TARGET
    display_name = "Fake target"

    def __init__(self, db: Session):
        self.db = db
        self.provider_account_id = ACCOUNT_ID
        self.calendar: list[dict[str, Any]] = []
        self.create_attempts = 0
        self.prepare_attempts = 0
        self.delete_attempts = 0
        self.fetch_attempts = 0
        self.authenticate_attempts = 0
        self.last_fetch_threshold: float | None = None
        self.create_failures: list[Exception] = []
        self.prepare_failures: list[Exception] = []
        self.delete_failures: list[Exception] = []
        self.on_create: Callable[[], None] | None = None
        self.on_delete: Callable[[], None] | None = None
        self.on_authenticate: Callable[[int], None] | None = None
        self.hidden_external_ids: set[str] = set()
        self.account_alias_matcher: (
            Callable[[str, Mapping[str, Any]], bool] | None
        ) = None

    @property
    def account_id(self) -> str:
        return self.provider_account_id

    def authenticate(self) -> None:
        """Authenticate the fake provider."""
        self.authenticate_attempts += 1
        if self.on_authenticate is not None:
            self.on_authenticate(self.authenticate_attempts)

    def matches_provider_account(
        self,
        stored_account_id: str,
        provider_references: Mapping[str, Any],
    ) -> bool:
        if self.account_alias_matcher is None:
            return False
        return self.account_alias_matcher(
            stored_account_id,
            provider_references,
        )

    def prepare_workout(
        self,
        workout: Mapping[str, Any],
        *,
        threshold_value: float,
    ) -> PreparedWorkoutDelivery:
        """Prepare one deterministic fake provider request."""
        self.prepare_attempts += 1
        if self.prepare_failures:
            raise self.prepare_failures.pop(0)
        snapshot = dict(workout)
        encoded = json.dumps(
            {
                "snapshot": snapshot,
                "threshold_value": threshold_value,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        version = hashlib.sha256(encoded).hexdigest()
        content_version = hashlib.sha256(
            b"content:" + encoded
        ).hexdigest()
        return PreparedWorkoutDelivery(
            version=version,
            content_version=content_version,
            request={
                "snapshot": snapshot,
                "content_version": content_version,
            },
        )

    def create_workout(
        self,
        prepared: PreparedWorkoutDelivery,
        *,
        hooks,
    ) -> ProviderCreateResult:
        """Create one fake calendar workout."""
        self.create_attempts += 1
        if self.create_failures:
            raise self.create_failures.pop(0)
        external_id = f"managed-{self.create_attempts}"
        snapshot = dict(prepared.request["snapshot"])
        hooks.before_mutation()
        self.calendar.append({
            **snapshot,
            "external_id": external_id,
            "provider_content_fingerprint": prepared.content_version,
            "provider_payload_fingerprint": prepared.version,
        })
        if self.on_create is not None:
            self.on_create()
        return ProviderCreateResult(
            external_id=external_id,
            provider_account_id=self.provider_account_id,
            response={"id": external_id},
        )

    def delete_workout(
        self,
        external_id: str,
        *,
        hooks,
    ) -> ProviderRemoveResult:
        """Delete one fake calendar workout."""
        self.delete_attempts += 1
        if self.delete_failures:
            raise self.delete_failures.pop(0)
        hooks.before_mutation()
        for index, row in enumerate(self.calendar):
            if row["external_id"] == external_id:
                self.calendar.pop(index)
                if self.on_delete is not None:
                    self.on_delete()
                return ProviderRemoveResult()
        if self.on_delete is not None:
            self.on_delete()
        return ProviderRemoveResult(already_absent=True)

    def fetch_calendar(
        self,
        *,
        threshold_value: float | None = None,
        days_ahead: int = 14,
        days_back: int = 0,
        timezone_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a copy of the fake calendar."""
        self.fetch_attempts += 1
        self.last_fetch_threshold = threshold_value
        return [
            dict(row)
            for row in self.calendar
            if row["external_id"] not in self.hidden_external_ids
        ]


@pytest.fixture
def managed_db(tmp_path):
    """Yield an enabled managed-plan database and fake provider."""
    engine = create_engine(f"sqlite:///{tmp_path / 'managed-delivery.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    db.add(User(
        id=USER_ID,
        email="managed-delivery@example.test",
        hashed_password="test",
    ))
    db.add(UserConfig(
        user_id=USER_ID,
        plan_management={
            "mode": "praxys",
            "execution_target": TARGET,
            "delivery_enabled": True,
            "adjustment_policy": "suggest_only",
        },
    ))
    db.add(UserConnection(
        user_id=USER_ID,
        platform=TARGET,
        status="connected",
        preferences={"plan": True},
    ))
    db.commit()
    adapter = FakeDeliveryAdapter(db)
    try:
        yield db, adapter
    finally:
        db.close()
        engine.dispose()


def _add_plan(
    db: Session,
    workout_date: date,
    *,
    workout_type: str = "easy",
    description: str = "Easy run",
) -> TrainingPlan:
    plan = TrainingPlan(
        user_id=USER_ID,
        canonical_id=str(uuid4()),
        date=workout_date,
        workout_type=workout_type,
        planned_duration_min=45,
        workout_description=description,
        source="ai",
    )
    db.add(plan)
    db.commit()
    return plan


def _run(
    db: Session,
    adapter: FakeDeliveryAdapter,
    *,
    now: datetime,
    window_start: date | None = None,
    trigger: str = "test",
):
    return run_rolling_delivery_for_user(
        db,
        user_id=USER_ID,
        trigger=trigger,
        now=now,
        window_start=window_start,
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )


@pytest.mark.parametrize(
    "plan_management,expected_reason",
    [
        (
            {
                "mode": "external",
                "execution_target": TARGET,
                "delivery_enabled": False,
                "adjustment_policy": "suggest_only",
            },
            "external_mode",
        ),
        (
            {
                "mode": "praxys",
                "execution_target": TARGET,
                "delivery_enabled": False,
                "adjustment_policy": "suggest_only",
            },
            "delivery_paused",
        ),
    ],
)
def test_default_off_modes_make_zero_provider_calls(
    managed_db,
    plan_management,
    expected_reason,
):
    db, adapter = managed_db
    db.get(UserConfig, USER_ID).plan_management = plan_management
    _add_plan(db, date(2026, 8, 2))

    result = _run(db, adapter, now=datetime(2026, 8, 1, 9))

    assert result.status == "skipped"
    assert result.reason == expected_reason
    assert adapter.fetch_attempts == 0
    assert adapter.create_attempts == 0
    assert adapter.delete_attempts == 0


def test_missing_delivery_adapter_is_blocked_as_praxys_defect(
    managed_db,
    monkeypatch,
):
    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 2))
    monkeypatch.setattr(
        "api.plan_delivery.rolling.is_plan_delivery_target_registered",
        lambda target: False,
    )

    result = _run(db, adapter, now=datetime(2026, 8, 1, 9))

    assert result.status == "blocked"
    assert result.reason == "delivery_adapter_unavailable"
    assert adapter.fetch_attempts == 0
    assert adapter.create_attempts == 0


def test_garmin_delivery_does_not_require_critical_power(
    managed_db,
    monkeypatch,
):
    from api.plan_delivery.capabilities import plan_delivery_consent_token

    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    db, adapter = managed_db
    config = db.get(UserConfig, USER_ID)
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    config.plan_management = {
        **config.plan_management,
        "execution_target": "garmin",
    }
    config.source_options = {"garmin_region": "international"}
    connection.platform = "garmin"
    connection.preferences = {"plan": True}
    db.flush()
    connection.plan_delivery_consent = plan_delivery_consent_token(
        connection,
        region="international",
    )
    db.commit()
    _add_plan(db, date(2026, 8, 2))

    result = run_rolling_delivery_for_user(
        db,
        user_id=USER_ID,
        trigger="test",
        now=datetime(2026, 8, 1, 9),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: None,
    )

    assert result.status == "complete"
    assert adapter.create_attempts == 1
    assert adapter.last_fetch_threshold is None
    assert len(adapter.calendar) == 1


def test_remove_accepts_provider_immutable_account_alias(managed_db):
    from api.plan_delivery.service import PlanDeliveryService
    from api.plan_delivery.rolling import _owned_removal_safe
    from db.plan_reconciliation import record_target_calendar_sync

    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 2))
    delivered = _run(db, adapter, now=datetime(2026, 8, 1, 9))
    assert delivered.status == "complete"
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    delivery.provider_references = {
        "profile_account_id": "stable-profile",
    }
    external_id = str(delivery.external_id)
    record_target_calendar_sync(
        db,
        user_id=USER_ID,
        target=TARGET,
        provider_account_id=ACCOUNT_ID,
        provider_references={
            "profile_account_id": "stable-profile",
        },
        rows=[{
            **adapter.calendar[0],
            "provider_references": {
                "profile_account_id": "stable-profile",
            },
        }],
        window_start=date(2026, 8, 1),
        window_end=date(2026, 8, 15),
        observed_at=datetime(2026, 8, 1, 9, 30),
    )
    db.commit()
    original_observation = db.execute(
        select(PlanTargetWorkout).where(
            PlanTargetWorkout.external_id == delivery.external_id,
        )
    ).scalar_one()
    adapter.provider_account_id = "renamed-calendar-account"
    adapter.account_alias_matcher = (
        lambda stored, references: (
            stored == ACCOUNT_ID
            and references.get("profile_account_id") == "stable-profile"
        )
    )
    record_target_calendar_sync(
        db,
        user_id=USER_ID,
        target=TARGET,
        provider_account_id=adapter.provider_account_id,
        provider_references={
            "profile_account_id": "stable-profile",
        },
        rows=[{
            **adapter.calendar[0],
            "provider_references": {
                "profile_account_id": "stable-profile",
            },
        }],
        window_start=date(2026, 8, 1),
        window_end=date(2026, 8, 15),
        observed_at=datetime(2026, 8, 1, 10),
    )
    db.commit()
    assert original_observation.provider_account_id == ACCOUNT_ID
    safe, reason = _owned_removal_safe(
        db,
        delivery=delivery,
        provider_account_id=adapter.provider_account_id,
    )
    assert safe is True
    assert reason is None
    service = PlanDeliveryService(
        db=db,
        user_id=USER_ID,
        target=TARGET,
        adapter_loader=lambda: adapter,
    )

    result = service.remove(external_id)

    assert result.external_id == external_id
    db.refresh(delivery)
    db.refresh(original_observation)
    assert delivery.state == "removed"
    assert original_observation.present is False
    assert adapter.delete_attempts == 1


def test_immutable_matcher_overrides_equal_display_account(managed_db):
    from api.plan_delivery.base import adapter_provider_account_matches

    _, adapter = managed_db
    adapter.account_alias_matcher = (
        lambda _stored, references: (
            references.get("profile_account_id") == "current-profile"
        )
    )

    assert not adapter_provider_account_matches(
        adapter,
        stored_account_id=ACCOUNT_ID,
        current_account_id=ACCOUNT_ID,
        provider_references={
            "profile_account_id": "different-profile",
        },
    )


def test_removed_garmin_delivery_resets_only_schedule_identity(
    managed_db,
) -> None:
    db, _ = managed_db
    snapshot = {
        "canonical_id": "c77ad913-6123-4be8-aad0-e1d426c5c804",
        "date": "2026-08-02",
        "source": "praxys",
        "workout_type": "easy",
        "planned_duration_min": 45,
    }
    delivery, _ = get_or_create_delivery(
        db,
        user_id=USER_ID,
        target="garmin",
        snapshot=snapshot,
    )
    delivery.state = "removed"
    delivery.external_id = "schedule-201"
    delivery.delivered_at = datetime(2026, 8, 1, 9)
    delivery.provider_references = {
        "profile_account_id": "international:profile",
        "template_id": "template-101",
        "template_marker": "praxys:marker",
        "payload_fingerprint": "fingerprint",
        "schedule_id": "schedule-201",
        "schedule_started": True,
        "preexisting_schedule_ids": ["manual-1"],
    }
    db.commit()

    locked, attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )

    assert disposition == "started"
    assert attempt is not None
    assert locked.external_id is None
    assert locked.delivered_at is None
    assert locked.provider_references == {
        "profile_account_id": "international:profile",
        "template_id": "template-101",
        "template_marker": "praxys:marker",
        "payload_fingerprint": "fingerprint",
    }


def test_delivery_uses_exact_fourteen_day_horizon(managed_db):
    db, adapter = managed_db
    today = date(2026, 8, 1)
    _add_plan(db, today - timedelta(days=1), description="Past")
    _add_plan(db, today, description="First")
    _add_plan(db, today + timedelta(days=13), description="Last")
    _add_plan(db, today + timedelta(days=14), description="Outside")
    _add_plan(
        db,
        today + timedelta(days=5),
        workout_type="rest",
        description="Rest",
    )

    operational_now = datetime(2026, 8, 2, 18)
    result = _run(
        db,
        adapter,
        now=operational_now,
        window_start=today,
    )

    assert result.window_start == "2026-08-01"
    assert result.window_end == "2026-08-14"
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync).where(
            PlanTargetCalendarSync.user_id == USER_ID,
            PlanTargetCalendarSync.target == TARGET,
        )
    ).scalar_one()
    assert calendar_sync.synced_at == operational_now
    assert {
        row["date"] for row in adapter.calendar
    } == {"2026-08-01", "2026-08-14"}
    assert adapter.create_attempts == 2


def test_repeated_run_is_idempotent_and_preserves_target_only_workouts(
    managed_db,
):
    db, adapter = managed_db
    workout_date = date(2026, 8, 3)
    _add_plan(db, workout_date)
    adapter.calendar.append({
        "date": workout_date.isoformat(),
        "workout_type": "manual",
        "workout_description": "External coach workout",
        "external_id": "external-manual",
        "provider_content_fingerprint": "manual-content",
        "provider_payload_fingerprint": "manual-payload",
    })

    first = _run(db, adapter, now=datetime(2026, 8, 1, 9))
    second = _run(db, adapter, now=datetime(2026, 8, 1, 10))

    assert first.status == "complete"
    assert second.status == "complete"
    assert adapter.create_attempts == 1
    assert {row["external_id"] for row in adapter.calendar} == {
        "external-manual",
        "managed-1",
    }
    assert second.items[0].reason == "matching"


def test_target_edit_blocks_only_affected_workout(managed_db):
    db, adapter = managed_db
    first_plan = _add_plan(db, date(2026, 8, 3), description="First")
    _add_plan(db, date(2026, 8, 4), description="Second")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    changed = next(
        row for row in adapter.calendar
        if row["canonical_id"] == first_plan.canonical_id
    )
    changed["workout_description"] = "Edited outside Praxys"
    changed["provider_content_fingerprint"] = "external-edit"

    result = _run(db, adapter, now=datetime(2026, 8, 1, 10))

    affected = next(
        item for item in result.items
        if item.canonical_id == first_plan.canonical_id
    )
    unaffected = next(
        item for item in result.items
        if item.canonical_id != first_plan.canonical_id
    )
    assert affected.status == "blocked"
    assert affected.reason == "target_edited"
    assert unaffected.status == "skipped"
    assert unaffected.reason == "matching"
    assert adapter.create_attempts == 2
    assert adapter.delete_attempts == 0


def test_accepted_canonical_edit_replaces_owned_workout(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    original_external_id = adapter.calendar[0]["external_id"]
    plan.workout_description = "After"
    db.commit()

    result = _run(
        db,
        adapter,
        now=datetime(2026, 8, 1, 10),
        trigger="plan_upsert",
    )

    assert result.status == "complete"
    assert result.items[0].status == "replaced"
    assert adapter.create_attempts == 2
    assert adapter.delete_attempts == 1
    assert len(adapter.calendar) == 1
    assert adapter.calendar[0]["external_id"] != original_external_id
    revision = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.user_id == USER_ID,
            PlanRevision.operation == "restore_target",
        )
    ).scalar_one()
    assert revision.actor_type == "system"
    assert revision.actor_id is None
    assert revision.origin == "managed_plan.rolling_delivery"
    assert revision.details["trigger"] == "plan_upsert"


def test_replacement_rechecks_pause_between_delete_and_create(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_description = "After"
    db.commit()

    def pause_delivery() -> None:
        config = db.get(UserConfig, USER_ID)
        config.plan_management = {
            **config.plan_management,
            "delivery_enabled": False,
        }

    adapter.on_delete = pause_delivery
    result = _run(
        db,
        adapter,
        now=datetime(2026, 8, 1, 10),
        trigger="plan_upsert",
    )

    assert result.items[0].status == "skipped"
    assert result.items[0].reason == "delivery_paused"
    assert adapter.delete_attempts == 1
    assert adapter.create_attempts == 1
    assert adapter.calendar == []


def test_replacement_blocks_when_connection_credentials_change(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_description = "After"
    db.commit()

    def reconnect() -> None:
        connection = db.execute(
            select(UserConnection).where(
                UserConnection.user_id == USER_ID,
                UserConnection.platform == TARGET,
            )
        ).scalar_one()
        connection.encrypted_credentials = b"new-credentials"
        connection.wrapped_dek = b"new-wrapped-key"

    adapter.on_delete = reconnect
    result = _run(
        db,
        adapter,
        now=datetime(2026, 8, 1, 10),
        trigger="plan_upsert",
    )

    assert result.items[0].status == "skipped"
    assert result.items[0].reason == "connection_changed"
    assert adapter.delete_attempts == 1
    assert adapter.create_attempts == 1
    assert adapter.calendar == []


def test_changing_owned_workout_to_rest_removes_target_copy(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_type = "rest"
    plan.workout_description = "Rest"
    db.commit()

    result = _run(
        db,
        adapter,
        now=datetime(2026, 8, 1, 10),
        trigger="plan_upsert",
    )

    assert result.status == "complete"
    assert result.items[0].action == "remove"
    assert result.items[0].status == "removed"
    assert adapter.delete_attempts == 1
    assert adapter.create_attempts == 1
    assert adapter.calendar == []


def test_rest_cleanup_rechecks_canonical_before_delete(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_type = "rest"
    plan.workout_description = "Rest"
    db.commit()

    def reactivate(attempt_number: int) -> None:
        if attempt_number == 4:
            plan.workout_type = "easy"
            plan.workout_description = "Reactivated"
            db.commit()

    adapter.on_authenticate = reactivate
    result = _run(db, adapter, now=datetime(2026, 8, 1, 10))

    assert result.items[0].status == "skipped"
    assert result.items[0].reason == "canonical_changed_during_run"
    assert adapter.delete_attempts == 0
    assert len(adapter.calendar) == 1


def test_concurrent_rest_transition_blocks_create(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")

    def change_to_rest(attempt_number: int) -> None:
        if attempt_number == 2:
            plan.workout_type = "rest"
            plan.workout_description = "Rest"
            db.commit()

    adapter.on_authenticate = change_to_rest
    result = _run(db, adapter, now=datetime(2026, 8, 1, 9))

    assert result.items[0].status == "skipped"
    assert result.items[0].reason == "canonical_became_rest"
    assert adapter.create_attempts == 0
    assert adapter.calendar == []


def test_corrected_version_does_not_inherit_definite_old_failure(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Rejected")
    adapter.create_failures.append(
        ProviderRejectedError("definite provider rejection")
    )
    failed = _run(db, adapter, now=datetime(2026, 8, 1, 9))
    blocked = _run(db, adapter, now=datetime(2026, 8, 1, 10))
    plan.workout_description = "Corrected"
    db.commit()

    corrected = _run(db, adapter, now=datetime(2026, 8, 1, 11))
    repeated = _run(db, adapter, now=datetime(2026, 8, 1, 12))

    assert failed.items[0].status == "failed"
    assert blocked.items[0].status == "blocked"
    assert blocked.items[0].reason == "failure_not_retryable"
    assert corrected.items[0].status == "delivered"
    assert repeated.items[0].status == "skipped"
    assert repeated.items[0].reason == "matching"
    assert adapter.create_attempts == 2
    assert len(adapter.calendar) == 1


def test_invalid_initial_workout_is_durable_and_not_retried(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Invalid")
    adapter.prepare_failures.append(
        ProviderRequestError("invalid workout structure")
    )

    failed = _run(db, adapter, now=datetime(2026, 8, 1, 9))
    blocked = _run(db, adapter, now=datetime(2026, 8, 1, 10))
    plan.workout_description = "Corrected"
    db.commit()
    corrected = _run(db, adapter, now=datetime(2026, 8, 1, 11))

    assert failed.items[0].status == "failed"
    assert failed.items[0].reason == "invalid_workout"
    assert blocked.items[0].status == "blocked"
    assert blocked.items[0].reason == "failure_not_retryable"
    assert corrected.items[0].status == "delivered"
    assert adapter.prepare_attempts == 2


def test_invalid_replacement_preflight_is_not_retried(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Before")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_description = "Invalid edit"
    db.commit()
    adapter.prepare_failures.append(
        ProviderRequestError("invalid replacement")
    )

    failed = _run(db, adapter, now=datetime(2026, 8, 1, 10))
    attention = list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 10, 30),
    ).items[0]
    attempts_after_failure = adapter.prepare_attempts
    blocked = _run(db, adapter, now=datetime(2026, 8, 1, 11))
    attempts_after_block = adapter.prepare_attempts
    plan.workout_description = "Corrected edit"
    db.commit()
    corrected = _run(db, adapter, now=datetime(2026, 8, 1, 12))

    assert failed.items[0].status == "failed"
    assert attention.state == "synced"
    assert attention.operation == "deliver"
    assert attention.issue == "delivery_failed"
    assert attention.failure_domain == "praxys"
    assert attention.recovery_supported is False
    assert blocked.items[0].status == "blocked"
    assert blocked.items[0].reason == "failure_not_retryable"
    assert corrected.items[0].status == "replaced"
    assert attempts_after_block == attempts_after_failure
    assert adapter.prepare_attempts == 4
    assert adapter.delete_attempts == 1


def test_reverted_canonical_clears_obsolete_preflight_attention(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Original")
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_description = "Invalid edit"
    db.commit()
    adapter.prepare_failures.append(
        ProviderRequestError("invalid replacement")
    )
    _run(db, adapter, now=datetime(2026, 8, 1, 10))

    plan.workout_description = "Original"
    db.commit()
    attention = list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 11),
    )

    assert attention.items == []


def test_deleted_canonical_clears_failed_create_attention(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3))
    adapter.create_failures.append(ProviderTransientError("provider down"))
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    assert list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 10),
    ).items

    db.delete(plan)
    db.commit()

    assert list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 11),
    ).items == []


def test_recovery_preflight_failure_cannot_create_new_delivery_version(
    managed_db,
):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3), description="Initial")
    adapter.create_failures.append(ProviderTransientError("provider down"))
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    plan.workout_description = "Corrected"
    db.commit()
    attention = list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 10),
    ).items[0]
    adapter.prepare_failures.append(
        ProviderRequestError("invalid corrected workout")
    )

    recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=datetime(2026, 8, 1, 10, 5),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )
    deliveries = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.canonical_id == plan.canonical_id
        )
    ).scalars().all()

    assert [delivery.id for delivery in deliveries] == [
        attention.recovery_id
    ]


def test_recovery_blocks_superseding_attempt_during_authentication(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3))
    adapter.create_failures.append(ProviderTransientError("provider down"))
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    attention = list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 10),
    ).items[0]
    callback_attempt = adapter.authenticate_attempts + 2

    def supersede(attempt_number: int) -> None:
        if attempt_number != callback_attempt:
            return
        adapter.on_authenticate = None
        delivery = db.get(PlanDelivery, attention.recovery_id)
        assert delivery is not None
        append_delivery_event(
            db,
            delivery,
            operation="deliver",
            state="failed",
            external_id=None,
            error="newer worker failure",
            response={
                "managed_delivery": True,
                "retryable": True,
                "trigger": "concurrent_worker",
            },
        )
        delivery.state = "failed"
        delivery.updated_at = datetime.utcnow()
        db.commit()

    adapter.on_authenticate = supersede
    recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=datetime(2026, 8, 1, 10, 5),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert adapter.create_attempts == 1
    assert adapter.calendar == []


def test_removal_recovery_rechecks_canonical_during_authentication(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3))
    canonical_id = plan.canonical_id
    workout_date = plan.date
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    db.delete(plan)
    db.commit()
    adapter.delete_failures.append(
        ProviderRemovalError("provider removal failed")
    )
    _run(db, adapter, now=datetime(2026, 8, 1, 10))
    attention = list_managed_plan_attention(
        db,
        now=datetime(2026, 8, 1, 11),
    ).items[0]
    callback_attempt = adapter.authenticate_attempts + 2

    def recreate_canonical(attempt_number: int) -> None:
        if attempt_number != callback_attempt:
            return
        adapter.on_authenticate = None
        db.add(
            TrainingPlan(
                user_id=USER_ID,
                canonical_id=canonical_id,
                date=workout_date,
                workout_type="tempo",
                planned_duration_min=50,
                workout_description="Recreated during recovery",
                source="ai",
            )
        )
        db.commit()

    adapter.on_authenticate = recreate_canonical
    recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=datetime(2026, 8, 1, 11, 5),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert adapter.delete_attempts == 1
    assert len(adapter.calendar) == 1


def test_inferred_absence_does_not_delete_hidden_moved_workout(managed_db):
    db, adapter = managed_db
    plan = _add_plan(db, date(2026, 8, 3))
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    external_id = adapter.calendar[0]["external_id"]
    adapter.calendar[0]["date"] = "2026-09-15"
    adapter.hidden_external_ids.add(external_id)
    db.delete(plan)
    db.commit()

    result = _run(db, adapter, now=datetime(2026, 8, 1, 10))

    assert result.status == "partial"
    assert result.items[0].status == "blocked"
    assert result.items[0].reason == "target_workout_absent"
    assert adapter.delete_attempts == 0
    assert adapter.calendar[0]["external_id"] == external_id


def test_inflight_create_is_recovered_from_calendar(
    managed_db,
    monkeypatch,
):
    from api.plan_delivery.service import PlanDeliveryService

    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    original = PlanDeliveryService._record_terminal_attempt
    failed_once = False

    def fail_create_finalization(self, **kwargs):
        nonlocal failed_once
        if kwargs["state"] == "synced" and not failed_once:
            failed_once = True
            raise SQLAlchemyError("forced create finalization failure")
        return original(self, **kwargs)

    monkeypatch.setattr(
        PlanDeliveryService,
        "_record_terminal_attempt",
        fail_create_finalization,
    )
    failed = _run(db, adapter, now=started_at)
    monkeypatch.setattr(
        PlanDeliveryService,
        "_record_terminal_attempt",
        original,
    )
    pending = _run(
        db,
        adapter,
        now=started_at + timedelta(minutes=5),
    )
    attempt = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.state == "delivering",
        )
    ).scalar_one()
    attempt.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()

    recovered = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=1),
    )

    assert failed.items[0].status == "failed"
    assert failed.items[0].reason == "ledger_finalization_failed"
    assert pending.items[0].reason == "pending_observation"
    assert recovered.items[0].status == "skipped"
    assert recovered.items[0].reason == "matching"
    assert adapter.create_attempts == 1
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    assert delivery.state == "synced"
    assert delivery.external_id == adapter.calendar[0]["external_id"]


@pytest.mark.parametrize(
    "phase,expected_state,expected_category",
    [
        ("before_schedule", "failed", "provider_partial_create"),
        ("schedule_started", "conflict", "provider_outcome_unknown"),
        ("schedule_checkpointed", "synced", None),
    ],
)
def test_inflight_garmin_checkpoint_recovery_is_phase_safe(
    managed_db,
    phase,
    expected_state,
    expected_category,
):
    db, _ = managed_db
    workout_date = date(2026, 8, 3)
    started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    provider_references = {
        "template_marker": "praxys:garmin-partial",
        "payload_fingerprint": "b" * 64,
        "preexisting_template_ids": [],
        "template_id": "101",
    }
    if phase in {"schedule_started", "schedule_checkpointed"}:
        provider_references["schedule_started"] = True
    if phase == "schedule_checkpointed":
        provider_references["schedule_id"] = "201"
    delivery = PlanDelivery(
        user_id=USER_ID,
        canonical_key="ai:garmin-partial",
        canonical_id="garmin-partial",
        workout_date=workout_date,
        workout_version="a" * 64,
        provider_content_version="b" * 64,
        target="garmin",
        state="delivering",
        external_id=("201" if phase == "schedule_checkpointed" else None),
        provider_references=provider_references,
    )
    db.add(delivery)
    db.flush()
    attempt = PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        operation="deliver",
        state="delivering",
        response={
            "managed_delivery": True,
            "provider_account_id": ACCOUNT_ID,
            "connection_generation": "generation",
            "preexisting_external_ids": [],
        },
        started_at=started_at,
    )
    recovery_rows = [
        attempt,
        PlanTargetCalendarSync(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=ACCOUNT_ID,
            window_start=workout_date - timedelta(days=2),
            window_end=workout_date + timedelta(days=2),
            synced_at=datetime.utcnow(),
        ),
    ]
    if phase == "schedule_checkpointed":
        recovery_rows.append(PlanTargetWorkout(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=ACCOUNT_ID,
            external_id="201",
            provider_references={"template_id": "101"},
            workout_date=workout_date,
            normalized_workout={},
            observed_at=datetime.utcnow(),
        ))
    db.add_all(recovery_rows)
    db.commit()

    _recover_managed_inflight_attempts(
        db,
        user_id=USER_ID,
        target="garmin",
        provider_account_id=ACCOUNT_ID,
        connection_generation="generation",
        deliveries=[delivery],
    )

    db.refresh(delivery)
    db.refresh(attempt)
    assert delivery.state == expected_state
    assert delivery.provider_references["template_id"] == "101"
    assert attempt.state == expected_state
    if expected_category is None:
        assert attempt.response["recovered_from_calendar"] is True
        assert delivery.external_id == "201"
    else:
        assert attempt.response["error_category"] == expected_category
        assert attempt.response["retryable"] is (
            expected_state == "failed"
        )


def test_inflight_recovery_accepts_immutable_profile_account_alias(managed_db):
    db, adapter = managed_db
    workout_date = date(2026, 8, 3)
    started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    profile_references = {
        "profile_account_id": "stable-profile",
        "template_id": "101",
        "schedule_id": "201",
    }
    delivery = PlanDelivery(
        user_id=USER_ID,
        canonical_key="ai:garmin-alias-recovery",
        canonical_id="garmin-alias-recovery",
        workout_date=workout_date,
        workout_version="a" * 64,
        provider_content_version="b" * 64,
        target="garmin",
        state="delivering",
        external_id="201",
        provider_account_id=ACCOUNT_ID,
        provider_references=profile_references,
    )
    db.add(delivery)
    db.flush()
    attempt = PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        operation="deliver",
        state="delivering",
        response={
            "managed_delivery": True,
            "provider_account_id": ACCOUNT_ID,
            "provider_references": profile_references,
            "connection_generation": "generation",
            "preexisting_external_ids": [],
        },
        started_at=started_at,
    )
    current_account_id = "renamed-calendar-account"
    db.add_all([
        attempt,
        PlanTargetCalendarSync(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=current_account_id,
            provider_references={
                "profile_account_id": "stable-profile",
            },
            window_start=workout_date - timedelta(days=2),
            window_end=workout_date + timedelta(days=2),
            synced_at=datetime.utcnow(),
        ),
        PlanTargetWorkout(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=ACCOUNT_ID,
            external_id="201",
            provider_references=profile_references,
            workout_date=workout_date,
            normalized_workout={},
            observed_at=datetime.utcnow(),
        ),
    ])
    db.commit()
    adapter.provider_account_id = current_account_id
    adapter.account_alias_matcher = lambda stored, references: (
        stored == ACCOUNT_ID
        and references.get("profile_account_id") == "stable-profile"
    )

    _recover_managed_inflight_attempts(
        db,
        user_id=USER_ID,
        target="garmin",
        provider_account_id=current_account_id,
        connection_generation="generation",
        deliveries=[delivery],
        adapter=adapter,
    )

    db.refresh(delivery)
    db.refresh(attempt)
    assert delivery.state == "synced"
    assert attempt.state == "synced"
    assert delivery.external_id == "201"


@pytest.mark.parametrize("candidate_state", ["claimed", "ambiguous"])
def test_inflight_garmin_recovery_never_replays_unsafe_schedule_candidates(
    managed_db,
    candidate_state,
):
    db, _ = managed_db
    workout_date = date(2026, 8, 3)
    started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    delivery = PlanDelivery(
        user_id=USER_ID,
        canonical_key=f"ai:garmin-{candidate_state}",
        canonical_id=f"garmin-{candidate_state}",
        workout_date=workout_date,
        workout_version="c" * 64,
        provider_content_version="d" * 64,
        target="garmin",
        state="delivering",
        provider_references={
            "template_marker": f"praxys:garmin-{candidate_state}",
            "payload_fingerprint": "d" * 64,
            "preexisting_template_ids": [],
            "template_id": "101",
        },
    )
    db.add(delivery)
    db.flush()
    attempt = PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        operation="deliver",
        state="delivering",
        response={
            "managed_delivery": True,
            "provider_account_id": ACCOUNT_ID,
            "connection_generation": "generation",
            "preexisting_external_ids": [],
        },
        started_at=started_at,
    )
    observations = [
        PlanTargetWorkout(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=ACCOUNT_ID,
            external_id="201",
            provider_references={"template_id": "101"},
            workout_date=workout_date,
            normalized_workout={},
            observed_at=datetime.utcnow(),
        ),
    ]
    if candidate_state == "claimed":
        db.add(PlanDelivery(
            user_id=USER_ID,
            canonical_key="ai:other-garmin-workout",
            canonical_id="other-garmin-workout",
            workout_date=workout_date,
            workout_version="e" * 64,
            target="garmin",
            state="synced",
            external_id="201",
        ))
    else:
        observations.append(PlanTargetWorkout(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=ACCOUNT_ID,
            external_id="202",
            provider_references={"template_id": "101"},
            workout_date=workout_date,
            normalized_workout={},
            observed_at=datetime.utcnow(),
        ))
    db.add_all([
        attempt,
        *observations,
        PlanTargetCalendarSync(
            user_id=USER_ID,
            target="garmin",
            provider_account_id=ACCOUNT_ID,
            window_start=workout_date - timedelta(days=2),
            window_end=workout_date + timedelta(days=2),
            synced_at=datetime.utcnow(),
        ),
    ])
    db.commit()

    _recover_managed_inflight_attempts(
        db,
        user_id=USER_ID,
        target="garmin",
        provider_account_id=ACCOUNT_ID,
        connection_generation="generation",
        deliveries=[delivery],
    )

    db.refresh(delivery)
    db.refresh(attempt)
    assert delivery.state == "conflict"
    assert attempt.state == "conflict"
    assert attempt.response["retryable"] is False
    assert attempt.response["error_category"] == (
        "provider_identity_claimed"
        if candidate_state == "claimed"
        else "provider_outcome_unknown"
    )


def test_inflight_removal_becomes_visible_conflict(
    managed_db,
    monkeypatch,
):
    from api.plan_delivery.service import PlanDeliveryService

    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    _run(db, adapter, now=started_at)
    db.delete(plan)
    db.commit()
    original = PlanDeliveryService._record_terminal_attempt
    failed_once = False

    def fail_remove_finalization(self, **kwargs):
        nonlocal failed_once
        if kwargs["state"] == "removed" and not failed_once:
            failed_once = True
            raise SQLAlchemyError("forced remove finalization failure")
        return original(self, **kwargs)

    monkeypatch.setattr(
        PlanDeliveryService,
        "_record_terminal_attempt",
        fail_remove_finalization,
    )
    failed = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=1),
    )
    monkeypatch.setattr(
        PlanDeliveryService,
        "_record_terminal_attempt",
        original,
    )
    attempt = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.state == "delivering",
            PlanDeliveryAttempt.operation == "remove",
        )
    ).scalar_one()
    attempt.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()

    recovered = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=2),
    )

    assert failed.items[0].status == "failed"
    assert recovered.status == "partial"
    assert recovered.items[0].status == "blocked"
    assert recovered.items[0].reason == "delivery_conflict"
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    assert delivery.state == "conflict"
    assert adapter.delete_attempts == 1


def test_crash_before_create_does_not_claim_identical_manual_workout(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    snapshot = plan_snapshot(plan)
    prepared = adapter.prepare_workout(
        snapshot,
        threshold_value=CP_WATTS,
    )
    adapter.calendar.append({
        **snapshot,
        "external_id": "manual-existing",
        "provider_content_fingerprint": prepared.content_version,
        "provider_payload_fingerprint": prepared.version,
    })
    adapter.create_failures.append(RuntimeError("crash before provider send"))

    with pytest.raises(RuntimeError, match="crash before provider send"):
        _run(db, adapter, now=started_at)

    attempt = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.state == "delivering",
        )
    ).scalar_one()
    attempt.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()
    recovered = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=1),
    )

    assert recovered.status == "partial"
    assert recovered.items[0].status == "blocked"
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    assert delivery.state == "conflict"
    assert delivery.external_id is None
    assert adapter.calendar[0]["external_id"] == "manual-existing"
    assert adapter.delete_attempts == 0


def test_recovery_snapshot_includes_ids_outside_delivery_horizon(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    snapshot = plan_snapshot(plan)
    prepared = adapter.prepare_workout(
        snapshot,
        threshold_value=CP_WATTS,
    )
    adapter.calendar.append({
        "date": (started_at.date() + timedelta(days=14)).isoformat(),
        "workout_type": "manual",
        "workout_description": "Outside delivery horizon",
        "external_id": "outside-existing",
        "provider_content_fingerprint": "outside-content",
        "provider_payload_fingerprint": "outside-payload",
    })
    adapter.create_failures.append(RuntimeError("crash before provider send"))

    with pytest.raises(RuntimeError):
        _run(db, adapter, now=started_at)

    adapter.calendar[0] = {
        **snapshot,
        "external_id": "outside-existing",
        "provider_content_fingerprint": prepared.content_version,
        "provider_payload_fingerprint": prepared.version,
    }
    attempt = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.state == "delivering",
        )
    ).scalar_one()
    attempt.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()

    recovered = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=1),
    )

    assert recovered.status == "partial"
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    assert delivery.state == "conflict"
    assert delivery.external_id is None
    assert adapter.calendar[0]["external_id"] == "outside-existing"


def test_inflight_create_does_not_cross_reconnected_accounts(
    managed_db,
    monkeypatch,
):
    from api.plan_delivery.service import PlanDeliveryService

    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    snapshot = plan_snapshot(plan)
    prepared = adapter.prepare_workout(
        snapshot,
        threshold_value=CP_WATTS,
    )
    original = PlanDeliveryService._record_terminal_attempt
    failed_once = False

    def fail_create_finalization(self, **kwargs):
        nonlocal failed_once
        if kwargs["state"] == "synced" and not failed_once:
            failed_once = True
            raise SQLAlchemyError("forced create finalization failure")
        return original(self, **kwargs)

    monkeypatch.setattr(
        PlanDeliveryService,
        "_record_terminal_attempt",
        fail_create_finalization,
    )
    _run(db, adapter, now=started_at)
    monkeypatch.setattr(
        PlanDeliveryService,
        "_record_terminal_attempt",
        original,
    )
    attempt = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.state == "delivering",
        )
    ).scalar_one()
    attempt.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    connection.encrypted_credentials = b"account-b"
    connection.wrapped_dek = b"account-b-key"
    adapter.provider_account_id = "provider-account-b"
    adapter.calendar = [{
        **snapshot,
        "external_id": "manual-account-b",
        "provider_content_fingerprint": prepared.content_version,
        "provider_payload_fingerprint": prepared.version,
    }]
    db.commit()

    recovered = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=1),
    )

    assert recovered.status == "partial"
    assert recovered.items[0].status == "blocked"
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    assert delivery.state == "conflict"
    assert delivery.external_id is None
    assert adapter.calendar[0]["external_id"] == "manual-account-b"
    assert adapter.delete_attempts == 0


def test_deleted_canonical_removal_retries_with_backoff(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    _run(db, adapter, now=started_at)
    external_id = adapter.calendar[0]["external_id"]
    db.delete(plan)
    db.commit()
    adapter.delete_failures.append(ProviderRemovalError("temporary delete failure"))

    failed = _run(db, adapter, now=started_at + timedelta(minutes=1))
    backed_off = _run(db, adapter, now=started_at + timedelta(minutes=5))
    retried = _run(db, adapter, now=started_at + timedelta(minutes=20))

    assert failed.items[0].status == "failed"
    assert backed_off.items[0].status == "skipped"
    assert backed_off.items[0].reason == "retry_backoff"
    assert retried.items[0].status == "removed"
    assert adapter.delete_attempts == 2
    assert all(
        row["external_id"] != external_id for row in adapter.calendar
    )


def test_transient_create_failure_retries_after_backoff(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderTransientError("provider rate limit")
    )

    failed = _run(db, adapter, now=started_at)
    backed_off = _run(db, adapter, now=started_at + timedelta(minutes=5))
    retried = _run(db, adapter, now=started_at + timedelta(minutes=20))

    assert failed.items[0].status == "failed"
    assert failed.items[0].reason == "provider_transient"
    assert backed_off.items[0].status == "skipped"
    assert backed_off.items[0].reason == "retry_backoff"
    assert retried.items[0].status == "delivered"
    assert adapter.create_attempts == 2
    attempts = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.operation == "deliver")
        .order_by(PlanDeliveryAttempt.attempt_number)
    ).scalars().all()
    assert attempts[0].response["managed_delivery"] is True
    assert attempts[0].response["retryable"] is True
    assert attempts[1].response["managed_delivery"] is True


def test_rate_limit_stops_batch_and_backs_off_connection(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    _add_plan(db, started_at.date() + timedelta(days=3))
    adapter.create_failures.append(
        ProviderRateLimitError("provider rate limit")
    )

    result = _run(db, adapter, now=started_at)

    assert len(result.items) == 1
    assert result.items[0].status == "failed"
    assert result.items[0].reason == "provider_rate_limited"
    assert adapter.create_attempts == 1
    attempt = db.execute(select(PlanDeliveryAttempt)).scalar_one()
    assert attempt.response["counts_toward_retry_limit"] is False
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    assert connection.status == "error"
    assert connection.next_retry_at is not None


def test_create_auth_failure_terminalizes_delivery_attempt(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderAuthenticationError("provider session expired")
    )

    result = _run(db, adapter, now=started_at)

    assert len(result.items) == 1
    assert result.items[0].status == "failed"
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    attempt = db.execute(select(PlanDeliveryAttempt)).scalar_one()
    assert delivery.state == "failed"
    assert attempt.state == "failed"
    assert (
        attempt.response["error_category"]
        == "provider_authentication_failed"
    )
    assert attempt.response["counts_toward_retry_limit"] is False


def test_removal_auth_failure_does_not_consume_retry_budget(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    _run(db, adapter, now=started_at)
    db.delete(plan)
    db.commit()
    adapter.delete_failures.append(
        ProviderAuthenticationError("provider session expired")
    )

    result = _run(db, adapter, now=started_at + timedelta(minutes=1))

    assert result.items[0].status == "failed"
    attempt = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.operation == "remove")
    ).scalar_one()
    assert attempt.response["error_category"] == "provider_authentication"
    assert attempt.response["counts_toward_retry_limit"] is False


def test_removal_rate_limit_terminalizes_attempt_and_stops_batch(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    first = _add_plan(db, started_at.date() + timedelta(days=2))
    _add_plan(db, started_at.date() + timedelta(days=3))
    _run(db, adapter, now=started_at)
    db.delete(first)
    db.commit()
    adapter.delete_failures.append(
        ProviderRateLimitError("provider rate limit")
    )

    result = _run(db, adapter, now=started_at + timedelta(minutes=1))

    assert len(result.items) == 1
    assert result.items[0].status == "failed"
    removed_delivery = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.workout_date == started_at.date() + timedelta(days=2)
        )
    ).scalar_one()
    latest_attempt = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.delivery_id == removed_delivery.id)
        .order_by(PlanDeliveryAttempt.attempt_number.desc())
    ).scalars().first()
    assert removed_delivery.state == "synced"
    assert latest_attempt is not None
    assert latest_attempt.operation == "remove"
    assert latest_attempt.state == "failed"
    assert (
        latest_attempt.response["error_category"]
        == "provider_rate_limited"
    )


def test_replacement_rate_limit_stops_batch_and_backs_off_connection(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    first = _add_plan(
        db,
        started_at.date() + timedelta(days=2),
        description="Before",
    )
    _add_plan(db, started_at.date() + timedelta(days=3))
    _run(db, adapter, now=started_at)
    first.workout_description = "After"
    db.commit()
    adapter.create_failures.append(
        ProviderRateLimitError("provider rate limit")
    )

    result = _run(db, adapter, now=started_at + timedelta(minutes=1))

    assert len(result.items) == 1
    assert result.items[0].action == "replace"
    assert result.items[0].status == "failed"
    assert result.items[0].reason == "provider_rate_limited"
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    assert connection.consecutive_failures == 1
    assert connection.next_retry_at is not None


def test_delivery_success_cannot_reopen_disconnected_connection(managed_db):
    from api.plan_delivery.rolling import _record_connection_success
    from db.connection_credentials import connection_credentials_generation

    db, _ = managed_db
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    generation = connection_credentials_generation(connection)
    connection.status = "disconnected"
    db.commit()

    assert not _record_connection_success(
        db,
        user_id=USER_ID,
        target=TARGET,
        connection_generation=generation,
    )
    db.expire_all()
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    assert connection.status == "disconnected"


def test_nested_managed_delivery_run_is_serialized(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    nested_results = []
    adapter.on_create = lambda: nested_results.append(
        _run(db, adapter, now=started_at)
    )

    result = _run(db, adapter, now=started_at)

    assert result.status == "complete"
    assert adapter.create_attempts == 1
    assert len(nested_results) == 1
    assert nested_results[0].status == "skipped"
    assert nested_results[0].reason == "delivery_run_busy"


def test_stale_success_cannot_clear_newer_connection_backoff(managed_db):
    from api.plan_delivery.rolling import (
        _connection_health_fence,
        _record_connection_success,
    )
    from db.connection_credentials import connection_credentials_generation

    db, _ = managed_db
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    generation = connection_credentials_generation(connection)
    health_fence = _connection_health_fence(connection)
    connection.status = "error"
    connection.consecutive_failures = 1
    connection.next_retry_at = datetime.utcnow() + timedelta(hours=1)
    connection.last_error = "ProviderRateLimitError: rate limited"
    db.commit()

    assert not _record_connection_success(
        db,
        user_id=USER_ID,
        target=TARGET,
        connection_generation=generation,
        expected_health_fence=health_fence,
    )
    db.refresh(connection)
    assert connection.status == "error"
    assert connection.consecutive_failures == 1
    assert connection.next_retry_at is not None


def test_transient_create_retry_stops_at_durable_cap(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.extend(
        ProviderTransientError("provider rate limit")
        for _ in range(5)
    )

    for attempt_number in range(5):
        result = _run(
            db,
            adapter,
            now=started_at + timedelta(hours=7 * attempt_number),
        )
        assert result.items[0].status == "failed"

    capped = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=42),
    )

    assert capped.status == "partial"
    assert capped.items[0].status == "blocked"
    assert capped.items[0].reason == "retry_limit_reached"
    assert adapter.create_attempts == 5


def test_pause_is_rechecked_before_each_mutation(managed_db):
    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 3), description="First")
    _add_plan(db, date(2026, 8, 4), description="Second")

    def pause_delivery() -> None:
        config = db.get(UserConfig, USER_ID)
        config.plan_management = {
            **config.plan_management,
            "delivery_enabled": False,
        }

    adapter.on_create = pause_delivery
    result = _run(db, adapter, now=datetime(2026, 8, 1, 9))

    assert adapter.create_attempts == 1
    assert len(adapter.calendar) == 1
    assert any(
        item.status == "skipped" and item.reason == "delivery_paused"
        for item in result.items
    )


def test_disconnect_blocks_delivery_before_provider_access(managed_db):
    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 3))
    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    connection.status = "disconnected"
    db.commit()

    result = _run(db, adapter, now=datetime(2026, 8, 1, 9))

    assert result.status == "skipped"
    assert result.reason == "connection_disconnected"
    assert adapter.fetch_attempts == 0
    assert adapter.create_attempts == 0


def test_invalid_credentials_require_reconnect(managed_db):
    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 3))

    result = run_rolling_delivery_for_user(
        db,
        user_id=USER_ID,
        trigger="test",
        now=datetime(2026, 8, 1, 9),
        adapter_loader=lambda session, user_id, target: (
            _ for _ in ()
        ).throw(DeliveryCredentialsInvalid("cannot decrypt")),
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    assert result.status == "blocked"
    assert result.reason == "DeliveryCredentialsInvalid"
    assert connection.status == "auth_required"
    assert connection.next_retry_at is None
    assert adapter.create_attempts == 0


def test_stale_credential_failure_does_not_overwrite_reconnect(managed_db):
    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 3))

    def stale_loader(session, user_id, target):
        connection = session.execute(
            select(UserConnection).where(
                UserConnection.user_id == USER_ID,
                UserConnection.platform == TARGET,
            )
        ).scalar_one()
        connection.encrypted_credentials = b"replacement"
        connection.wrapped_dek = b"replacement-key"
        connection.status = "connected"
        session.commit()
        raise DeliveryCredentialsInvalid("old credentials failed")

    result = run_rolling_delivery_for_user(
        db,
        user_id=USER_ID,
        trigger="test",
        now=datetime(2026, 8, 1, 9),
        adapter_loader=stale_loader,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    connection = db.execute(
        select(UserConnection).where(
            UserConnection.user_id == USER_ID,
            UserConnection.platform == TARGET,
        )
    ).scalar_one()
    assert result.status == "blocked"
    assert result.reason == "connection_changed"
    assert connection.status == "connected"
    assert connection.consecutive_failures == 0
    assert connection.next_retry_at is None
    assert adapter.create_attempts == 0


def test_leaving_managed_mode_keeps_delivered_workouts(managed_db):
    db, adapter = managed_db
    _add_plan(db, date(2026, 8, 3))
    _run(db, adapter, now=datetime(2026, 8, 1, 9))
    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "mode": "external",
        "delivery_enabled": False,
    }
    db.commit()

    result = _run(db, adapter, now=datetime(2026, 8, 1, 10))

    assert result.status == "skipped"
    assert result.reason == "external_mode"
    assert adapter.delete_attempts == 0
    assert len(adapter.calendar) == 1
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    assert delivery.state == "synced"


def test_managed_plan_full_lifecycle_preserves_external_workout(managed_db):
    db, adapter = managed_db
    today = date(2026, 8, 1)
    plan = _add_plan(db, today + timedelta(days=2))
    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "mode": "external",
        "delivery_enabled": False,
    }
    manual_id = "external-coach-workout"
    adapter.calendar.append({
        "date": plan.date.isoformat(),
        "workout_type": "manual",
        "workout_description": "External coach workout",
        "external_id": manual_id,
        "provider_content_fingerprint": "external-content",
        "provider_payload_fingerprint": "external-payload",
    })
    db.commit()

    config.plan_management = {
        **config.plan_management,
        "mode": "praxys",
        "delivery_enabled": True,
    }
    db.commit()
    adopted = _run(db, adapter, now=datetime(2026, 8, 1, 9))
    managed = next(
        row for row in adapter.calendar
        if row["external_id"] != manual_id
    )
    managed["workout_description"] = "Edited outside Praxys"
    managed["provider_content_fingerprint"] = "external-edit"
    conflicted = _run(db, adapter, now=datetime(2026, 8, 1, 10))

    reconciliation = build_plan_reconciliation(
        db,
        user_id=USER_ID,
        target=TARGET,
        start=today,
        end=today + timedelta(days=13),
    )
    assert reconciliation is not None
    item = reconciliation.canonical_items[plan.canonical_id]
    resolved = restore_praxys_version(
        db,
        user_id=USER_ID,
        target=TARGET,
        item=item,
        threshold_value=CP_WATTS,
        adapter_loader=lambda: adapter,
    )

    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "delivery_enabled": False,
    }
    db.commit()
    paused = _run(db, adapter, now=datetime(2026, 8, 1, 11))
    config.plan_management = {
        **config.plan_management,
        "delivery_enabled": True,
    }
    db.commit()
    resumed = _run(db, adapter, now=datetime(2026, 8, 1, 12))
    config.plan_management = {
        **config.plan_management,
        "mode": "external",
        "delivery_enabled": False,
    }
    db.commit()
    left = _run(db, adapter, now=datetime(2026, 8, 1, 13))
    cleanup = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=today,
        adapter_loader=lambda: adapter,
    )

    assert adopted.items[0].status == "delivered"
    assert any(
        result.status == "blocked" and result.reason == "target_edited"
        for result in conflicted.items
    )
    assert resolved.action == "restore_praxys"
    assert paused.status == "skipped"
    assert paused.reason == "delivery_paused"
    assert resumed.status == "complete"
    assert left.status == "skipped"
    assert left.reason == "external_mode"
    assert cleanup.status == "complete"
    assert cleanup.removed_count == 1
    assert [row["external_id"] for row in adapter.calendar] == [manual_id]
    assert db.get(TrainingPlan, plan.id) is not None


def test_managed_attention_classifies_retry_exhaustion_without_pii(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.extend(
        ProviderTransientError("private provider detail")
        for _ in range(5)
    )
    for attempt_number in range(5):
        _run(
            db,
            adapter,
            now=started_at + timedelta(hours=7 * attempt_number),
        )

    response = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=36),
    )

    assert len(response.items) == 1
    item = response.items[0]
    assert item.issue == "retry_exhausted"
    assert item.failure_domain == "provider"
    assert item.recovery_supported is True
    assert item.operation == "deliver"
    assert item.attempt_count == 5
    serialized = response.model_dump_json()
    assert "managed-delivery@example.test" not in serialized
    assert ACCOUNT_ID not in serialized
    assert "private provider detail" not in serialized


def test_operator_recovery_reconciles_and_replays_one_exhausted_failure(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.extend(
        ProviderTransientError("provider rate limit")
        for _ in range(5)
    )
    for attempt_number in range(5):
        _run(
            db,
            adapter,
            now=started_at + timedelta(hours=7 * attempt_number),
        )
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=36),
    ).items[0]
    untouched = _add_plan(
        db,
        started_at.date() + timedelta(days=3),
        description="Not part of operator recovery",
    )

    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=started_at + timedelta(hours=36),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )
    repeated = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=started_at + timedelta(hours=36, minutes=1),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert recovered.status == "complete"
    assert recovered.final_state == "synced"
    assert recovered.successful_items == 1
    assert repeated == recovered
    assert adapter.create_attempts == 6
    assert len(adapter.calendar) == 1
    assert db.execute(
        select(PlanDelivery).where(
            PlanDelivery.canonical_id == untouched.canonical_id
        )
    ).scalar_one_or_none() is None
    revisions = db.execute(
        select(PlanRevision)
        .where(PlanRevision.origin == "admin.managed_plan_recovery")
        .order_by(PlanRevision.created_at, PlanRevision.id)
    ).scalars().all()
    assert [revision.operation for revision in revisions] == [
        "managed_recovery_requested",
        "managed_recovery_completed",
    ]
    assert all(
        len(revision.idempotency_key) <= 128
        for revision in revisions
    )
    assert revisions[0].actor_type == "admin"
    assert revisions[0].actor_id == "admin-user"
    assert revisions[1].details["response"]["final_state"] == "synced"


def test_operator_recovery_completes_replacement_after_failed_removal(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(
        db,
        started_at.date() + timedelta(days=2),
        description="Before replacement",
    )
    _run(db, adapter, now=started_at)
    plan.workout_description = "After replacement"
    db.commit()
    adapter.delete_failures.extend(
        ProviderRemovalError("provider removal failed")
        for _ in range(5)
    )
    for attempt_number in range(5):
        failed = _run(
            db,
            adapter,
            now=started_at + timedelta(
                hours=1 + 7 * attempt_number,
            ),
        )
        assert failed.items[0].status == "failed"

    recovery_at = started_at + timedelta(hours=36)
    attention = list_managed_plan_attention(
        db,
        now=recovery_at,
    ).items[0]
    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=recovery_at,
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert attention.operation == "remove"
    assert recovered.status == "complete"
    assert recovered.final_state == "synced"
    assert recovered.successful_items == 1
    assert adapter.create_attempts == 2
    assert adapter.delete_attempts == 6
    assert len(adapter.calendar) == 1
    assert (
        adapter.calendar[0]["workout_description"]
        == "After replacement"
    )


def test_replacement_recovery_requires_authoritative_synced_version(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(
        db,
        started_at.date() + timedelta(days=2),
        description="Before replacement",
    )
    _run(db, adapter, now=started_at)
    plan.workout_description = "After replacement"
    db.commit()
    adapter.delete_failures.append(
        ProviderRemovalError("provider removal failed")
    )
    _run(db, adapter, now=started_at + timedelta(hours=1))
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=2),
    ).items[0]
    callback_attempt = adapter.authenticate_attempts + 2

    def supersede(attempt_number: int) -> None:
        if attempt_number != callback_attempt:
            return
        adapter.on_authenticate = None
        delivery = db.get(PlanDelivery, attention.recovery_id)
        assert delivery is not None
        append_delivery_event(
            db,
            delivery,
            operation="remove",
            state="failed",
            external_id=delivery.external_id,
            error="newer worker failure",
            response={
                "managed_delivery": True,
                "retryable": True,
                "trigger": "concurrent_worker",
                "resolution": "restore_praxys",
            },
        )
        delivery.state = "synced"
        delivery.updated_at = datetime.utcnow()
        db.commit()

    adapter.on_authenticate = supersede
    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=started_at + timedelta(hours=2),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert recovered.status == "blocked"
    assert recovered.reason == "recovery_incomplete"
    assert recovered.final_state == "missing"
    assert recovered.successful_items == 0
    assert adapter.create_attempts == 1
    assert len(adapter.calendar) == 1


def test_recovery_completion_rechecks_concurrent_canonical_removal(
    managed_db,
    monkeypatch,
):
    from api import managed_plan_ops

    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderTransientError("provider unavailable")
    )
    _run(db, adapter, now=started_at)
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=1),
    ).items[0]
    real_run = managed_plan_ops.run_rolling_delivery_for_user

    def run_then_remove_canonical(session, **kwargs):
        result = real_run(session, **kwargs)
        lock_plan_writes(session, USER_ID)
        current = session.get(TrainingPlan, plan.id)
        assert current is not None
        session.delete(current)
        session.commit()
        return result

    monkeypatch.setattr(
        managed_plan_ops,
        "run_rolling_delivery_for_user",
        run_then_remove_canonical,
    )

    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=started_at + timedelta(hours=1),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert recovered.status == "skipped"
    assert recovered.reason == "recovery_superseded"
    assert recovered.final_state == "synced"
    assert adapter.create_attempts == 2
    assert len(adapter.calendar) == 1


def test_operator_stale_inflight_recovery_does_not_duplicate_provider_workout(
    managed_db,
):
    db, adapter = managed_db
    delivered_at = datetime.utcnow() - timedelta(minutes=15)
    stuck_at = delivered_at + timedelta(minutes=5)
    _add_plan(db, delivered_at.date() + timedelta(days=2))
    delivered = _run(db, adapter, now=delivered_at)
    delivery = db.execute(select(PlanDelivery)).scalar_one()
    first_attempt = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.delivery_id == delivery.id)
    ).scalar_one()
    delivery.state = "delivering"
    delivery.external_id = None
    delivery.updated_at = stuck_at
    db.add(PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=2,
        operation="deliver",
        state="delivering",
        external_id=None,
        response={
            **first_attempt.response,
            "managed_delivery": True,
        },
        started_at=stuck_at,
    ))
    db.commit()
    recovery_at = datetime.utcnow()
    attention = list_managed_plan_attention(
        db,
        now=recovery_at,
    ).items[0]

    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=recovery_at,
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert delivered.items[0].status == "delivered"
    assert attention.issue == "stuck_inflight"
    assert recovered.status == "complete"
    assert recovered.final_state == "synced"
    assert adapter.create_attempts == 1
    assert len(adapter.calendar) == 1


def test_managed_delivery_lock_engine_unwraps_connection(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'lease-bind.db'}")
    connection = engine.connect()
    try:
        assert _managed_delivery_lock_engine(engine) is engine
        assert _managed_delivery_lock_engine(connection) is engine
    finally:
        connection.close()
        engine.dispose()


def test_confirmed_removal_marks_same_profile_alias_absent(managed_db):
    from db.plan_reconciliation import mark_target_workout_absent

    db, _ = managed_db
    observation = PlanTargetWorkout(
        user_id=USER_ID,
        target="garmin",
        provider_account_id="international:old-display",
        external_id="schedule-alias",
        provider_references={
            "profile_account_id": "international:stable-profile",
        },
        workout_date=date.today() + timedelta(days=2),
        normalized_workout={},
        present=True,
        observed_at=datetime.utcnow(),
    )
    db.add(observation)
    db.commit()

    assert mark_target_workout_absent(
        db,
        user_id=USER_ID,
        target="garmin",
        provider_account_id="international:new-display",
        external_id="schedule-alias",
        provider_references={
            "profile_account_id": "international:stable-profile",
        },
    )
    db.commit()
    db.refresh(observation)

    assert observation.present is False


def test_postgres_delivery_lease_reuses_one_connection(monkeypatch):
    events: list[str] = []

    class FakeResult:
        def scalar_one(self):
            return True

    class FakeConnection:
        def execute(self, statement, parameters):
            events.append(str(statement))
            assert parameters["lock_key"]
            return FakeResult()

        def commit(self):
            events.append("commit")

        def __enter__(self):
            events.append("connect")
            return self

        def __exit__(self, exc_type, exc, traceback):
            del exc_type, exc, traceback
            events.append("disconnect")

    class FakeDialect:
        name = "postgresql"

    class FakeEngine:
        dialect = FakeDialect()

        def __init__(self):
            self.connection = FakeConnection()
            self.connect_calls = 0

        def connect(self):
            self.connect_calls += 1
            return self.connection

    class FakeParentSession:
        def __init__(self, engine):
            self.engine = engine
            self.rollback_calls = 0
            self.expire_calls = 0

        def get_bind(self):
            return self.engine

        def rollback(self):
            self.rollback_calls += 1

        def expire_all(self):
            self.expire_calls += 1

    class FakeLeasedSession:
        def __init__(self):
            self.rollback_calls = 0
            self.close_calls = 0

        def rollback(self):
            self.rollback_calls += 1

        def close(self):
            self.close_calls += 1

    engine = FakeEngine()
    parent = FakeParentSession(engine)
    leased = FakeLeasedSession()
    monkeypatch.setattr(
        "api.plan_delivery.rolling.Session",
        lambda **kwargs: (
            leased
            if kwargs == {"bind": engine.connection, "autoflush": False}
            else pytest.fail(f"unexpected Session args: {kwargs}")
        ),
    )

    with _managed_delivery_run_lease(parent, "postgres-user") as run_db:
        assert run_db is leased
        events.append("work")

    assert engine.connect_calls == 1
    assert parent.rollback_calls == 1
    assert parent.expire_calls == 1
    assert leased.rollback_calls == 1
    assert leased.close_calls == 1
    assert events == [
        "connect",
        "SELECT pg_try_advisory_lock(:lock_key)",
        "commit",
        "work",
        "SELECT pg_advisory_unlock(:lock_key)",
        "commit",
        "disconnect",
    ]


def test_attention_excludes_failed_version_superseded_by_synced_delivery(
    managed_db,
):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.extend(
        ProviderTransientError("provider rate limit")
        for _ in range(5)
    )
    for attempt_number in range(5):
        _run(
            db,
            adapter,
            now=started_at + timedelta(hours=7 * attempt_number),
        )
    stale_attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=35),
    ).items[0]
    plan.workout_description = "Corrected after retry exhaustion"
    db.commit()

    corrected = _run(
        db,
        adapter,
        now=started_at + timedelta(hours=36),
    )
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=37),
    )
    deliveries = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.canonical_id == plan.canonical_id
        )
    ).scalars().all()

    assert corrected.items[0].status == "delivered"
    assert sorted(delivery.state for delivery in deliveries) == [
        "failed",
        "synced",
    ]
    assert attention.items == []
    with pytest.raises(ManagedPlanRecoveryStale):
        recover_managed_plan_delivery(
            db,
            admin_user_id="admin-user",
            delivery_id=stale_attention.recovery_id,
            expected_version=stale_attention.expected_version,
            now=started_at + timedelta(hours=37),
            adapter_loader=lambda session, user_id, target: adapter,
            threshold_loader=lambda session, user_id: CP_WATTS,
        )
    assert adapter.create_attempts == 6
    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "mode": "external",
        "delivery_enabled": False,
    }
    db.commit()
    cleanup = cleanup_future_plan_deliveries(
        db,
        user_id=USER_ID,
        today=started_at.date(),
        adapter_loader=lambda: adapter,
    )
    post_cleanup = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=38),
    )

    assert cleanup.status == "complete"
    assert post_cleanup.items == []
    assert {
        delivery.state
        for delivery in db.execute(
            select(PlanDelivery).where(
                PlanDelivery.canonical_id == plan.canonical_id
            )
        ).scalars()
    } == {"removed"}


def test_attention_recovers_exhausted_managed_removal(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    _run(db, adapter, now=started_at)
    db.delete(plan)
    db.commit()
    adapter.delete_failures.extend(
        ProviderRemovalError("provider removal failed")
        for _ in range(5)
    )
    for attempt_number in range(5):
        failed = _run(
            db,
            adapter,
            now=started_at + timedelta(hours=1 + 7 * attempt_number),
        )
        assert failed.items[0].status == "failed"

    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=36),
    ).items[0]
    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=started_at + timedelta(hours=36),
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert attention.state == "synced"
    assert attention.operation == "remove"
    assert attention.issue == "retry_exhausted"
    assert attention.failure_domain == "provider"
    assert attention.recovery_supported is True
    assert recovered.status == "complete"
    assert recovered.final_state == "removed"
    assert recovered.successful_items == 1
    assert adapter.delete_attempts == 6
    assert adapter.calendar == []


def test_operator_recovery_rejects_canonical_change_after_queue(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    plan = _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderTransientError("provider rate limit")
    )
    _run(db, adapter, now=started_at)
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=1),
    ).items[0]
    plan.workout_description = "Changed after queue snapshot"
    db.commit()

    with pytest.raises(ManagedPlanRecoveryStale):
        recover_managed_plan_delivery(
            db,
            admin_user_id="admin-user",
            delivery_id=attention.recovery_id,
            expected_version=attention.expected_version,
            now=started_at + timedelta(hours=1),
            adapter_loader=lambda session, user_id, target: adapter,
            threshold_loader=lambda session, user_id: CP_WATTS,
        )

    assert adapter.create_attempts == 1
    assert adapter.calendar == []


def test_operator_recovery_starts_one_stale_pending_delivery(managed_db):
    db, adapter = managed_db
    recovery_at = datetime.utcnow()
    plan = _add_plan(db, recovery_at.date() + timedelta(days=2))
    snapshot = plan_snapshot(plan)
    prepared = adapter.prepare_workout(
        snapshot,
        threshold_value=CP_WATTS,
    )
    delivery, _ = get_or_create_delivery(
        db,
        user_id=USER_ID,
        target=TARGET,
        snapshot=snapshot,
        workout_version_override=prepared.version,
        provider_content_version_override=prepared.content_version,
    )
    delivery.updated_at = (
        recovery_at - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()
    attention = list_managed_plan_attention(
        db,
        now=recovery_at,
    ).items[0]

    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=recovery_at,
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert attention.issue == "stale_pending"
    assert attention.recovery_supported is True
    assert recovered.status == "complete"
    assert recovered.final_state == "synced"
    assert recovered.successful_items == 1
    assert adapter.create_attempts == 1
    assert len(adapter.calendar) == 1


def test_operator_recovery_never_writes_different_pending_version(
    managed_db,
):
    db, adapter = managed_db
    recovery_at = datetime.utcnow()
    plan = _add_plan(db, recovery_at.date() + timedelta(days=2))
    delivery, _ = get_or_create_delivery(
        db,
        user_id=USER_ID,
        target=TARGET,
        snapshot=plan_snapshot(plan),
    )
    delivery.updated_at = (
        recovery_at - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()
    attention = list_managed_plan_attention(
        db,
        now=recovery_at,
    ).items[0]

    recovered = recover_managed_plan_delivery(
        db,
        admin_user_id="admin-user",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=recovery_at,
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert recovered.status == "partial"
    assert recovered.final_state == "pending"
    assert recovered.failed_items == 1
    assert adapter.create_attempts == 0
    assert adapter.calendar == []
    assert db.execute(select(PlanDelivery)).scalars().all() == [delivery]


def test_operator_recovery_rejects_stale_queue_version(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderTransientError("provider rate limit")
    )
    _run(db, adapter, now=started_at)
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=1),
    ).items[0]
    delivery = db.get(PlanDelivery, attention.recovery_id)
    delivery.updated_at = delivery.updated_at + timedelta(seconds=1)
    db.commit()

    with pytest.raises(ManagedPlanRecoveryStale):
        recover_managed_plan_delivery(
            db,
            admin_user_id="admin-user",
            delivery_id=attention.recovery_id,
            expected_version=attention.expected_version,
            now=started_at + timedelta(hours=1),
            adapter_loader=lambda session, user_id, target: adapter,
            threshold_loader=lambda session, user_id: CP_WATTS,
        )

    assert adapter.create_attempts == 1


def test_operator_recovery_rejects_equivalent_active_request(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderTransientError("provider rate limit")
    )
    _run(db, adapter, now=started_at)
    attention = list_managed_plan_attention(
        db,
        now=started_at + timedelta(hours=1),
    ).items[0]
    db.add(PlanRevision(
        user_id=USER_ID,
        operation="managed_recovery_requested",
        actor_type="admin",
        actor_id="first-admin",
        origin="admin.managed_plan_recovery",
        before_snapshot=[],
        after_snapshot=[],
        details={
            "delivery_id": attention.recovery_id,
            "expected_version": attention.expected_version,
        },
        idempotency_key="managed-recovery-active",
        created_at=started_at + timedelta(hours=1),
    ))
    db.commit()

    with pytest.raises(ManagedPlanRecoveryBusy):
        recover_managed_plan_delivery(
            db,
            admin_user_id="second-admin",
            delivery_id=attention.recovery_id,
            expected_version=attention.expected_version,
            now=started_at + timedelta(hours=1, minutes=1),
            adapter_loader=lambda session, user_id, target: adapter,
            threshold_loader=lambda session, user_id: CP_WATTS,
        )

    assert adapter.create_attempts == 1


def test_operator_recovery_takes_over_expired_request_lease(managed_db):
    db, adapter = managed_db
    started_at = datetime.utcnow()
    _add_plan(db, started_at.date() + timedelta(days=2))
    adapter.create_failures.append(
        ProviderTransientError("provider rate limit")
    )
    _run(db, adapter, now=started_at)
    recovery_at = started_at + timedelta(hours=1)
    attention = list_managed_plan_attention(
        db,
        now=recovery_at,
    ).items[0]
    db.add(PlanRevision(
        user_id=USER_ID,
        operation="managed_recovery_requested",
        actor_type="admin",
        actor_id="first-admin",
        origin="admin.managed_plan_recovery",
        before_snapshot=[],
        after_snapshot=[],
        details={
            "delivery_id": attention.recovery_id,
            "expected_version": attention.expected_version,
        },
        idempotency_key="managed-recovery-expired",
        created_at=recovery_at - timedelta(minutes=6),
    ))
    db.commit()

    result = recover_managed_plan_delivery(
        db,
        admin_user_id="second-admin",
        delivery_id=attention.recovery_id,
        expected_version=attention.expected_version,
        now=recovery_at,
        adapter_loader=lambda session, user_id, target: adapter,
        threshold_loader=lambda session, user_id: CP_WATTS,
    )

    assert result.status == "complete"
    assert adapter.create_attempts == 2
    revisions = db.execute(
        select(PlanRevision).where(
            PlanRevision.origin == "admin.managed_plan_recovery",
        )
    ).scalars().all()
    assert sum(
        revision.operation == "managed_recovery_requested"
        for revision in revisions
    ) == 2
    assert sum(
        revision.operation == "managed_recovery_completed"
        for revision in revisions
    ) == 1


def test_unknown_provider_outcome_remains_user_resolved(managed_db):
    db, _ = managed_db
    plan = _add_plan(db, datetime.utcnow().date() + timedelta(days=2))
    delivery = PlanDelivery(
        user_id=USER_ID,
        canonical_key=f"ai:{plan.canonical_id}",
        canonical_id=plan.canonical_id,
        workout_date=plan.date,
        workout_version="a" * 64,
        plan_version="a" * 64,
        target=TARGET,
        state="conflict",
    )
    db.add(delivery)
    db.flush()
    db.add(PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        operation="deliver",
        state="conflict",
        response={
            "managed_delivery": True,
            "retryable": False,
            "error_category": "provider_outcome_unknown",
        },
        completed_at=datetime.utcnow(),
    ))
    db.commit()

    item = list_managed_plan_attention(db).items[0]

    assert item.issue == "provider_outcome_unknown"
    assert item.failure_domain == "provider"
    assert item.recovery_supported is False
    assert item.recovery_blocked_reason == "user_resolution_required"
