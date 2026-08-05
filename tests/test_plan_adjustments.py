"""Conservative automatic plan-adjustment policy and lifecycle tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from analysis.plan_adjustments import evaluate_conservative_plan_adjustment
from api.plan_adjustments import (
    PlanAdjustmentConflictError,
    PlanAdjustmentNotFoundError,
    _record_delivery_consequence,
    apply_conservative_plan_adjustment,
    list_plan_adjustments,
    run_plan_adjustment_for_user,
    undo_plan_adjustment,
)
from db.cache_revision import get_revisions
from db.models import (
    Activity,
    Base,
    PlanDelivery,
    PlanRevision,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    RecoveryData,
    TrainingPlan,
    User,
    UserConfig,
)
from db.plan_ledger import (
    canonical_workout_key,
    plan_snapshot,
    workout_version,
)


USER_ID = "adjustment-user"
OTHER_USER_ID = "other-adjustment-user"
TODAY = date(2026, 9, 14)


def _hard_workout(
    *,
    source: str = "praxys",
    workout_origin: str = "generated",
) -> dict[str, Any]:
    return {
        "canonical_id": "11111111-1111-4111-8111-111111111111",
        "date": TODAY.isoformat(),
        "workout_type": "threshold",
        "planned_duration_min": 50.0,
        "planned_distance_km": 10.0,
        "target_power_min": 260.0,
        "target_power_max": 280.0,
        "workout_description": "Threshold repeats",
        "source": source,
        "workout_origin": workout_origin,
        "meta": {"generation": 3},
    }


def _recovery(
    *,
    status: str = "fatigued",
    stale: bool = False,
    include_hrv: bool = True,
) -> dict[str, Any]:
    return {
        "status": status,
        "hrv_latest_date": TODAY.isoformat(),
        "hrv_is_stale": stale,
        "hrv": (
            {
                "today_ms": 38.0,
                "today_ln": 3.64,
                "baseline_mean_ln": 3.95,
                "baseline_sd_ln": 0.18,
                "threshold_ln": 3.77,
            }
            if include_hrv
            else None
        ),
    }


def _signal(
    *,
    reason_code: str = "hrv_below_hard",
    recommendation: str = "rest",
) -> dict[str, Any]:
    return {
        "recommendation": recommendation,
        "reason_code": reason_code,
        "reason": "Recovery caution",
        "plan": {"workout_type": "threshold"},
    }


def _evaluate(**overrides: Any) -> dict[str, Any]:
    inputs = {
        "policy": "auto_conservative",
        "management_mode": "praxys",
        "workouts": [_hard_workout()],
        "training_signal": _signal(),
        "recovery_analysis": _recovery(),
        "has_completed_activity": False,
        "target_evidence_state": "not_applicable",
    }
    inputs.update(overrides)
    return evaluate_conservative_plan_adjustment(**inputs)


def test_safe_default_never_changes_a_workout() -> None:
    decision = _evaluate(policy="suggest_only")

    assert decision["status"] == "disabled"
    assert decision["reason_code"] == "suggest_only"
    assert decision["after"] is None


def test_empty_workout_slot_is_a_no_change() -> None:
    decision = _evaluate(workouts=[])

    assert decision["status"] == "no_change"
    assert decision["reason_code"] == "no_workout"


def test_only_praxys_owned_workouts_are_eligible() -> None:
    decision = _evaluate(workouts=[_hard_workout(source="stryd")])

    assert decision["status"] == "no_change"
    assert decision["reason_code"] == "external_workout"
    assert decision["bounds"]["external_workouts_changed"] == 0


def test_legacy_praxys_alias_remains_eligible() -> None:
    decision = _evaluate(workouts=[_hard_workout(source="ai")])

    assert decision["status"] == "adjust"
    assert decision["after"]["source"] == "ai"


@pytest.mark.parametrize("origin", ["manual", "accepted_target", "legacy", None])
def test_only_praxys_generated_workouts_are_eligible(
    origin: str | None,
) -> None:
    decision = _evaluate(
        workouts=[_hard_workout(workout_origin=origin or "")],
    )

    assert decision["status"] == "no_change"
    assert decision["reason_code"] == "workout_not_praxys_generated"
    assert decision["after"] is None


def test_multiple_praxys_workouts_fail_closed() -> None:
    second = {
        **_hard_workout(),
        "canonical_id": "22222222-2222-4222-8222-222222222222",
    }
    decision = _evaluate(workouts=[_hard_workout(), second])

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == "ambiguous_plan_slot"


@pytest.mark.parametrize(
    ("recovery", "expected_reason"),
    [
        (_recovery(stale=True), "recovery_evidence_unavailable"),
        (_recovery(include_hrv=False), "recovery_evidence_unavailable"),
        (_recovery(status="insufficient_data"), "recovery_evidence_unavailable"),
    ],
)
def test_missing_or_stale_recovery_fails_closed(
    recovery: dict[str, Any],
    expected_reason: str,
) -> None:
    decision = _evaluate(recovery_analysis=recovery)

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == expected_reason
    assert decision["after"] is None


@pytest.mark.parametrize("target_state", ["missing", "stale", "pending", "conflict"])
def test_uncertain_target_state_fails_closed(target_state: str) -> None:
    decision = _evaluate(target_evidence_state=target_state)

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == f"target_{target_state}"


def test_recorded_activity_blocks_the_change() -> None:
    decision = _evaluate(has_completed_activity=True)

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == "activity_already_recorded"


def test_non_hrv_cautions_remain_suggestions() -> None:
    decision = _evaluate(
        training_signal=_signal(
            reason_code="high_load_hard",
            recommendation="modify",
        ),
        recovery_analysis=_recovery(status="normal"),
    )

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == "outside_automatic_rule"


def test_signal_without_matching_hrv_values_fails_closed() -> None:
    recovery = _recovery()
    recovery["hrv"] = {
        **recovery["hrv"],
        "today_ln": recovery["hrv"]["threshold_ln"],
    }

    decision = _evaluate(recovery_analysis=recovery)

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == "recovery_evidence_mismatch"


@pytest.mark.parametrize(
    "hrv_update",
    [
        {"baseline_mean_ln": None},
        {"baseline_sd_ln": None},
        {"today_ln": 3.50},
        {"threshold_ln": 3.60},
    ],
)
def test_incomplete_or_inconsistent_hrv_math_fails_closed(
    hrv_update: dict[str, float | None],
) -> None:
    recovery = _recovery()
    recovery["hrv"] = {**recovery["hrv"], **hrv_update}

    decision = _evaluate(recovery_analysis=recovery)

    assert decision["status"] == "suggestion"
    assert decision["after"] is None


def test_hrv_must_be_recorded_on_the_workout_date() -> None:
    recovery = _recovery()
    recovery["hrv_latest_date"] = (TODAY - timedelta(days=1)).isoformat()

    decision = _evaluate(recovery_analysis=recovery)

    assert decision["status"] == "suggestion"
    assert decision["reason_code"] == "recovery_evidence_not_same_day"


def test_hrv_rule_makes_one_bounded_rest_replacement() -> None:
    before = _hard_workout()
    decision = _evaluate(workouts=[before])

    assert decision["status"] == "adjust"
    assert decision["reason_code"] == "hrv_below_hard"
    assert decision["before"] == before
    assert decision["after"]["canonical_id"] == before["canonical_id"]
    assert decision["after"]["date"] == before["date"]
    assert decision["after"]["source"] == "praxys"
    assert decision["after"]["workout_type"] == "rest"
    assert decision["after"]["planned_duration_min"] is None
    assert decision["after"]["target_power_min"] is None
    assert decision["bounds"] == {
        "date_shift_days": 0,
        "workouts_changed": 1,
        "result_workout_type": "rest",
        "external_workouts_changed": 0,
    }
    assert decision["citations"]
    assert decision["idempotency_key"].endswith(TODAY.isoformat())


@pytest.fixture
def adjustment_db(tmp_path):
    """Yield an isolated enabled policy database with deterministic evidence."""
    engine = create_engine(f"sqlite:///{tmp_path / 'plan-adjustments.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    db.add_all([
        User(
            id=USER_ID,
            email="adjustment@example.test",
            hashed_password="test",
        ),
        User(
            id=OTHER_USER_ID,
            email="other-adjustment@example.test",
            hashed_password="test",
        ),
        UserConfig(
            user_id=USER_ID,
            source_options={"athlete_timezone": "Asia/Shanghai"},
            plan_management={
                "mode": "praxys",
                "execution_target": None,
                "delivery_enabled": False,
                "adjustment_policy": "auto_conservative",
            },
        ),
        UserConfig(
            user_id=OTHER_USER_ID,
            source_options={"athlete_timezone": "Asia/Shanghai"},
            plan_management={
                "mode": "praxys",
                "execution_target": None,
                "delivery_enabled": False,
                "adjustment_policy": "auto_conservative",
            },
        ),
    ])
    for offset, hrv in enumerate((52, 51, 53, 50, 52, 51, 53, 38)):
        db.add(RecoveryData(
            user_id=USER_ID,
            date=TODAY - timedelta(days=7 - offset),
            hrv_avg=hrv,
            source="oura",
        ))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _add_plan(
    db: Session,
    *,
    user_id: str = USER_ID,
    source: str = "praxys",
    workout_type: str = "threshold",
    description: str = "Threshold repeats",
    workout_origin: str | None = None,
    workout_date: date = TODAY,
    start_time: datetime | None = None,
) -> TrainingPlan:
    plan = TrainingPlan(
        user_id=user_id,
        canonical_id=str(uuid4()),
        date=workout_date,
        workout_type=workout_type,
        planned_duration_min=50,
        planned_distance_km=10,
        target_power_min=260,
        target_power_max=280,
        workout_description=description,
        source=source,
        workout_origin=workout_origin or (
            "generated" if source in {"praxys", "ai"} else "imported"
        ),
        start_time=start_time,
    )
    db.add(plan)
    db.commit()
    return plan


def _add_matching_delivery(
    db: Session,
    plan: TrainingPlan,
    *,
    synced_at: datetime,
    window_start: date = TODAY,
    window_end: date = TODAY + timedelta(days=13),
    observation_at: datetime | None = None,
    legacy_identity: bool = False,
) -> None:
    snapshot = plan_snapshot(plan)
    plan_version = workout_version(snapshot)
    db.add_all([
        PlanDelivery(
            user_id=USER_ID,
            canonical_key=(
                f"ai:{plan.date.isoformat()}"
                if legacy_identity
                else canonical_workout_key(snapshot)
            ),
            canonical_id=None if legacy_identity else plan.canonical_id,
            workout_date=plan.date,
            workout_version="provider-payload-v1",
            plan_version=None if legacy_identity else plan_version,
            provider_content_version="provider-content-v1",
            target="stryd",
            state="synced",
            external_id="stryd-workout-1",
            provider_account_id="stryd-account",
            delivered_at=synced_at - timedelta(minutes=5),
        ),
        PlanTargetCalendarSync(
            user_id=USER_ID,
            target="stryd",
            provider_account_id="stryd-account",
            window_start=window_start,
            window_end=window_end,
            synced_at=synced_at,
        ),
        PlanTargetWorkout(
            user_id=USER_ID,
            target="stryd",
            provider_account_id="stryd-account",
            external_id="stryd-workout-1",
            workout_date=plan.date,
            normalized_workout={
                "date": plan.date.isoformat(),
                "workout_type": plan.workout_type,
            },
            content_fingerprint="provider-content-v1",
            payload_fingerprint="provider-payload-v1",
            present=True,
            observed_at=observation_at or synced_at,
        ),
    ])
    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "execution_target": "stryd",
        "delivery_enabled": True,
    }
    db.commit()


def test_adjustment_loader_accepts_immutable_profile_account_alias(
    adjustment_db: Session,
) -> None:
    from analysis.data_loader import load_plan_adjustment_inputs

    db = adjustment_db
    plan = _add_plan(db)
    snapshot = plan_snapshot(plan)
    profile_references = {"profile_account_id": "stable-profile"}
    db.add_all([
        PlanDelivery(
            user_id=USER_ID,
            canonical_key=canonical_workout_key(snapshot),
            canonical_id=plan.canonical_id,
            workout_date=plan.date,
            workout_version="provider-payload-v1",
            plan_version=workout_version(snapshot),
            provider_content_version="provider-content-v1",
            target="garmin",
            state="synced",
            external_id="schedule-1",
            provider_account_id="international:old-display",
            provider_references=profile_references,
        ),
        PlanTargetCalendarSync(
            user_id=USER_ID,
            target="garmin",
            provider_account_id="international:new-display",
            provider_references=profile_references,
            window_start=TODAY,
            window_end=TODAY + timedelta(days=13),
            synced_at=datetime.utcnow(),
        ),
        PlanTargetWorkout(
            user_id=USER_ID,
            target="garmin",
            provider_account_id="international:old-display",
            external_id="schedule-1",
            provider_references=profile_references,
            workout_date=plan.date,
            normalized_workout={"date": plan.date.isoformat()},
            content_fingerprint="provider-content-v1",
            payload_fingerprint="provider-payload-v1",
            present=True,
            observed_at=datetime.utcnow(),
        ),
    ])
    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "execution_target": "garmin",
        "delivery_enabled": True,
    }
    db.commit()

    *_, target_workouts = load_plan_adjustment_inputs(
        USER_ID,
        db,
        current_date=TODAY,
        recovery_source="oura",
        target="garmin",
    )

    assert [row.external_id for row in target_workouts] == ["schedule-1"]


def test_lifecycle_changes_only_the_praxys_row(adjustment_db: Session) -> None:
    db = adjustment_db
    praxys = _add_plan(db)
    external = _add_plan(
        db,
        source="stryd",
        description="Coach-authored threshold",
    )

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "adjusted"
    db.expire_all()
    assert db.get(TrainingPlan, praxys.id).workout_type == "rest"
    unchanged = db.get(TrainingPlan, external.id)
    assert unchanged.workout_type == "threshold"
    assert unchanged.workout_description == "Coach-authored threshold"
    revision = db.scalar(
        select(PlanRevision).where(
            PlanRevision.id == result["revision_id"],
        )
    )
    assert revision.operation == "auto_adjustment"
    assert revision.actor_type == "system"
    assert revision.details["reason_code"] == "hrv_below_hard"


def test_lifecycle_never_changes_a_manual_praxys_workout(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    manual = _add_plan(db, workout_origin="manual")

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "no_change"
    assert result["decision"]["reason_code"] == "workout_not_praxys_generated"
    db.expire_all()
    assert db.get(TrainingPlan, manual.id).workout_type == "threshold"


def test_persisted_timezone_drives_the_athlete_local_date(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        # Still September 13 in UTC, already September 14 in Shanghai.
        now=datetime(2026, 9, 13, 16, 30),
    )

    assert result["status"] == "adjusted"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "rest"


def test_local_midnight_never_mutates_the_prior_plan_day(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        # September 15 in Shanghai, while UTC is still September 14.
        now=datetime(2026, 9, 14, 16, 30),
    )

    assert result["status"] == "no_change"
    assert result["decision"]["reason_code"] == "no_workout"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_target_calendar_must_cover_the_adjusted_day(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    _add_matching_delivery(
        db,
        plan,
        synced_at=datetime(2026, 9, 14, 7, 45),
        window_start=TODAY + timedelta(days=1),
        window_end=TODAY + timedelta(days=14),
    )

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "suggestion"
    assert result["decision"]["reason_code"] == "target_stale"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_legacy_delivery_identity_still_requires_current_target_evidence(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    _add_matching_delivery(
        db,
        plan,
        synced_at=datetime(2026, 9, 14, 7, 45),
        window_start=TODAY + timedelta(days=1),
        window_end=TODAY + timedelta(days=14),
        legacy_identity=True,
    )

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "suggestion"
    assert result["decision"]["reason_code"] == "target_stale"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_newest_delivery_version_controls_target_evidence(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    _add_matching_delivery(
        db,
        plan,
        synced_at=datetime(2026, 9, 14, 7, 45),
    )
    snapshot = plan_snapshot(plan)
    db.add(PlanDelivery(
        user_id=USER_ID,
        canonical_key=canonical_workout_key(snapshot),
        canonical_id=plan.canonical_id,
        workout_date=plan.date,
        workout_version="obsolete-provider-payload",
        plan_version="obsolete-plan-version",
        target="stryd",
        state="synced",
        external_id="obsolete-stryd-workout",
        provider_account_id="stryd-account",
        delivered_at=datetime(2020, 1, 1),
        created_at=datetime(2020, 1, 1),
        updated_at=datetime(2020, 1, 1),
    ))
    db.commit()

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "adjusted"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "rest"


def test_target_observation_must_come_from_the_latest_calendar_sync(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    _add_matching_delivery(
        db,
        plan,
        synced_at=datetime(2026, 9, 14, 7, 45),
        observation_at=datetime(2026, 9, 14, 6),
    )

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "suggestion"
    assert result["decision"]["reason_code"] == "target_stale"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_west_of_utc_adjustment_delivers_the_athlete_local_day(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    config = db.get(UserConfig, USER_ID)
    config.source_options = {"athlete_timezone": "America/Los_Angeles"}
    db.commit()
    plan = _add_plan(db)
    _add_matching_delivery(
        db,
        plan,
        synced_at=datetime(2026, 9, 15, 0, 15),
    )
    factory = sessionmaker(bind=db.get_bind())
    monkeypatch.setattr("db.session.init_db", lambda: None)
    monkeypatch.setattr("db.session.SessionLocal", factory)
    delivery_calls: list[tuple[str, date | None]] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: (
            delivery_calls.append((trigger, window_start)) or None
        ),
    )

    result = run_plan_adjustment_for_user(
        USER_ID,
        trigger="test",
        # September 15 UTC, but still September 14 for the athlete.
        now=datetime(2026, 9, 15, 0, 30, tzinfo=timezone.utc),
    )

    assert result["status"] == "adjusted"
    assert delivery_calls == [("automatic_plan_adjustment", TODAY)]
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "rest"


def test_missing_athlete_timezone_fails_closed(
    adjustment_db: Session,
) -> None:
    db = adjustment_db
    config = db.get(UserConfig, USER_ID)
    config.source_options = {}
    db.commit()
    plan = _add_plan(db)

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        now=datetime(2026, 9, 14, 8),
    )

    assert result["status"] == "suggestion"
    assert result["decision"]["reason_code"] == "athlete_timezone_unavailable"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_database_activity_guard_blocks_mutation(adjustment_db: Session) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    db.add(Activity(
        user_id=USER_ID,
        activity_id="already-trained",
        date=TODAY,
    ))
    db.commit()

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )

    assert result["status"] == "suggestion"
    assert result["decision"]["reason_code"] == "activity_already_recorded"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_disabled_policy_skips_dashboard_work(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    config = db.get(UserConfig, USER_ID)
    config.plan_management = {
        **config.plan_management,
        "adjustment_policy": "suggest_only",
    }
    db.commit()
    monkeypatch.setattr(
        "api.plan_adjustments.load_plan_adjustment_inputs",
        lambda *args, **kwargs: pytest.fail("disabled policy loaded evidence"),
    )

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )

    assert result["status"] == "disabled"


def test_evidence_is_rechecked_under_the_write_fence(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    from api import plan_adjustments as adjustment_service

    real_loader = adjustment_service.load_plan_adjustment_inputs
    calls = 0

    def shifting_evidence(*args, **kwargs):
        nonlocal calls
        calls += 1
        loaded = list(real_loader(*args, **kwargs))
        if calls == 2:
            recovery = loaded[2]
            loaded[2] = recovery.loc[recovery["date"] < TODAY].copy()
        return tuple(loaded)

    monkeypatch.setattr(
        "api.plan_adjustments.load_plan_adjustment_inputs",
        shifting_evidence,
    )

    result = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )

    assert result["status"] == "suggestion"
    assert result["decision"]["reason_code"] == "recovery_evidence_unavailable"
    db.expire_all()
    assert db.get(TrainingPlan, plan.id).workout_type == "threshold"


def test_exact_snapshot_undo_and_idempotency(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    original_start = datetime(2026, 9, 14, 7, 30)
    plan = _add_plan(db, start_time=original_start)
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: None,
    )
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )

    undone = undo_plan_adjustment(
        db,
        user_id=USER_ID,
        revision_id=applied["revision_id"],
    )
    repeated_undo = undo_plan_adjustment(
        db,
        user_id=USER_ID,
        revision_id=applied["revision_id"],
    )
    repeated_evidence = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )

    assert undone["status"] == "undone"
    assert repeated_undo["status"] == "already_undone"
    assert repeated_evidence["status"] == "already_evaluated"
    db.expire_all()
    restored = db.get(TrainingPlan, plan.id)
    assert restored.workout_type == "threshold"
    assert restored.planned_duration_min == 50
    assert restored.start_time == original_start
    history = list_plan_adjustments(db, user_id=USER_ID)
    assert history["items"][0]["status"] == "undone"
    assert history["items"][0]["can_undo"] is False


def test_undo_rejects_metadata_only_supersession(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: None,
    )
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )
    db.expire_all()
    changed = db.get(TrainingPlan, plan.id)
    changed.meta = {**(changed.meta or {}), "edited_after_adjustment": True}
    db.commit()

    with pytest.raises(PlanAdjustmentConflictError):
        undo_plan_adjustment(
            db,
            user_id=USER_ID,
            revision_id=applied["revision_id"],
        )

    db.expire_all()
    assert db.get(TrainingPlan, plan.id).meta["edited_after_adjustment"] is True


def test_undo_restores_legacy_source_and_origin_exactly(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    legacy = _add_plan(db, source="ai", workout_origin="generated")
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: None,
    )
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )
    db.expire_all()
    assert db.get(TrainingPlan, legacy.id).source == "praxys"

    undo_plan_adjustment(
        db,
        user_id=USER_ID,
        revision_id=applied["revision_id"],
    )

    db.expire_all()
    restored = db.get(TrainingPlan, legacy.id)
    assert restored.source == "ai"
    assert restored.workout_origin == "generated"


def test_undo_rejects_a_superseded_workout(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    plan = _add_plan(db)
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: None,
    )
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )
    db.expire_all()
    changed = db.get(TrainingPlan, plan.id)
    changed.workout_description = "User edited this after adjustment"
    db.commit()

    with pytest.raises(PlanAdjustmentConflictError):
        undo_plan_adjustment(
            db,
            user_id=USER_ID,
            revision_id=applied["revision_id"],
        )

    history = list_plan_adjustments(db, user_id=USER_ID)
    assert history["items"][0]["status"] == "superseded"
    assert history["items"][0]["can_undo"] is False


def test_history_and_undo_are_user_isolated(adjustment_db: Session) -> None:
    db = adjustment_db
    _add_plan(db)
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )

    assert list_plan_adjustments(db, user_id=OTHER_USER_ID) == {"items": []}
    with pytest.raises(PlanAdjustmentNotFoundError):
        undo_plan_adjustment(
            db,
            user_id=OTHER_USER_ID,
            revision_id=applied["revision_id"],
        )


def test_delivery_consequence_is_append_only(adjustment_db: Session) -> None:
    db = adjustment_db
    _add_plan(db)
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )
    revision_before = get_revisions(db, USER_ID, ["plans"])["plans"]

    _record_delivery_consequence(
        db,
        user_id=USER_ID,
        adjustment_revision_id=applied["revision_id"],
        operation="auto_adjustment_delivery",
        snapshot=applied["snapshot"],
        delivery_result=None,
    )
    revision_after = get_revisions(db, USER_ID, ["plans"])["plans"]
    _record_delivery_consequence(
        db,
        user_id=USER_ID,
        adjustment_revision_id=applied["revision_id"],
        operation="auto_adjustment_delivery",
        snapshot=applied["snapshot"],
        delivery_result=None,
    )
    revision_after_retry = get_revisions(db, USER_ID, ["plans"])["plans"]

    revisions = db.scalars(
        select(PlanRevision)
        .where(PlanRevision.user_id == USER_ID)
        .order_by(PlanRevision.created_at, PlanRevision.id)
    ).all()
    assert [revision.operation for revision in revisions] == [
        "auto_adjustment",
        "auto_adjustment_delivery",
    ]
    assert revisions[0].details["delivery"]["status"] == "pending"
    assert revisions[1].details["delivery"]["status"] == "unavailable"
    assert revision_after == revision_before + 1
    assert revision_after_retry == revision_after


def test_pending_delivery_audit_retries_while_adjustment_is_current(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    _add_plan(db)
    factory = sessionmaker(bind=db.get_bind())
    monkeypatch.setattr("db.session.init_db", lambda: None)
    monkeypatch.setattr("db.session.SessionLocal", factory)
    delivery_calls: list[tuple[str, date | None]] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: (
            delivery_calls.append((trigger, window_start)) or None
        ),
    )
    from api import plan_adjustments as adjustment_service

    real_record = adjustment_service._record_delivery_consequence
    record_calls = 0

    def fail_first_record(*args, **kwargs):
        nonlocal record_calls
        record_calls += 1
        if record_calls == 1:
            raise RuntimeError("temporary audit failure")
        return real_record(*args, **kwargs)

    monkeypatch.setattr(
        adjustment_service,
        "_record_delivery_consequence",
        fail_first_record,
    )

    first = run_plan_adjustment_for_user(
        USER_ID,
        trigger="test",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 8),
    )
    second = run_plan_adjustment_for_user(
        USER_ID,
        trigger="retry",
        current_date=TODAY,
        now=datetime(2026, 9, 14, 9),
    )

    assert first["status"] == "adjusted"
    assert first["delivery_audit_status"] == "pending"
    assert second["status"] == "no_change"
    assert second["decision"]["reason_code"] == "workout_not_hard"
    assert delivery_calls == [
        ("automatic_plan_adjustment", TODAY),
        ("automatic_plan_adjustment_audit_recovery", TODAY),
    ]
    with factory() as verification:
        delivery_revision = verification.scalar(
            select(PlanRevision).where(
                PlanRevision.user_id == USER_ID,
                PlanRevision.operation == "auto_adjustment_delivery",
            )
        )
        assert delivery_revision is not None


def test_exact_undo_retry_recovers_pending_delivery_audit(
    adjustment_db: Session,
    monkeypatch,
) -> None:
    db = adjustment_db
    _add_plan(db)
    applied = apply_conservative_plan_adjustment(
        db,
        user_id=USER_ID,
        trigger="test",
        current_date=TODAY,
    )
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: None,
    )
    from api import plan_adjustments as adjustment_service

    real_record = adjustment_service._record_delivery_consequence
    record_calls = 0

    def fail_first_record(*args, **kwargs):
        nonlocal record_calls
        record_calls += 1
        if record_calls == 1:
            raise RuntimeError("temporary audit failure")
        return real_record(*args, **kwargs)

    monkeypatch.setattr(
        adjustment_service,
        "_record_delivery_consequence",
        fail_first_record,
    )

    first = undo_plan_adjustment(
        db,
        user_id=USER_ID,
        revision_id=applied["revision_id"],
    )
    second = undo_plan_adjustment(
        db,
        user_id=USER_ID,
        revision_id=applied["revision_id"],
    )

    assert first["status"] == "undone"
    assert first["delivery_audit_status"] == "pending"
    assert second["status"] == "already_undone"
    assert second["delivery_audit_status"] == "recorded"
    delivery_revision = db.scalar(
        select(PlanRevision).where(
            PlanRevision.user_id == USER_ID,
            PlanRevision.operation == "auto_adjustment_undo_delivery",
        )
    )
    assert delivery_revision is not None
