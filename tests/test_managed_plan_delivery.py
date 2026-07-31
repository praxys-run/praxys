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
    ProviderCreateResult,
    ProviderRejectedError,
    ProviderRemoveResult,
    ProviderRemovalError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.credentials import DeliveryCredentialsInvalid
from api.plan_delivery.rolling import run_rolling_delivery_for_user
from db.models import (
    Base,
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanRevision,
    PlanTargetCalendarSync,
    TrainingPlan,
    User,
    UserConfig,
    UserConnection,
)
from db.plan_ledger import DELIVERY_ATTEMPT_LEASE, plan_snapshot


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
        self.create_failures: list[Exception] = []
        self.prepare_failures: list[Exception] = []
        self.delete_failures: list[Exception] = []
        self.on_create: Callable[[], None] | None = None
        self.on_delete: Callable[[], None] | None = None
        self.on_authenticate: Callable[[int], None] | None = None
        self.hidden_external_ids: set[str] = set()

    @property
    def account_id(self) -> str:
        return self.provider_account_id

    def authenticate(self) -> None:
        """Authenticate the fake provider."""
        self.authenticate_attempts += 1
        if self.on_authenticate is not None:
            self.on_authenticate(self.authenticate_attempts)

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
    ) -> ProviderCreateResult:
        """Create one fake calendar workout."""
        self.create_attempts += 1
        if self.create_failures:
            raise self.create_failures.pop(0)
        external_id = f"managed-{self.create_attempts}"
        snapshot = dict(prepared.request["snapshot"])
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

    def delete_workout(self, external_id: str) -> ProviderRemoveResult:
        """Delete one fake calendar workout."""
        self.delete_attempts += 1
        if self.delete_failures:
            raise self.delete_failures.pop(0)
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
    attempts_after_failure = adapter.prepare_attempts
    blocked = _run(db, adapter, now=datetime(2026, 8, 1, 11))
    attempts_after_block = adapter.prepare_attempts
    plan.workout_description = "Corrected edit"
    db.commit()
    corrected = _run(db, adapter, now=datetime(2026, 8, 1, 12))

    assert failed.items[0].status == "failed"
    assert blocked.items[0].status == "blocked"
    assert blocked.items[0].reason == "failure_not_retryable"
    assert corrected.items[0].status == "replaced"
    assert attempts_after_block == attempts_after_failure
    assert adapter.prepare_attempts == 4
    assert adapter.delete_attempts == 1


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
