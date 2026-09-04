"""Focused service tests for the inactive migration-free Trail v2 slice."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import os
import tempfile

import pytest
from sqlalchemy import event

from api.trail_plan_service import (
    ABSENT_TRAIL_PLAN_REVISION,
    TRAIL_EDITABLE_SECTION_KEYS,
    TRAIL_PLAN_GOAL_NAMESPACE,
    TrailPlanServiceError,
    confirm_trail_plan_section,
    delete_trail_plan_draft,
    evaluate_trail_plan_readiness,
    read_trail_plan_draft,
    reset_trail_plan_draft,
    save_trail_plan_draft,
    validate_trail_draft_request,
)


TODAY = date(2026, 9, 4)
NOW = datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def trail_db(monkeypatch):
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", os.path.join(tmpdir.name, "data"))
    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()
    from db.models import User, UserConfig

    with db_session.SessionLocal() as db:
        db.add(User(
            id="trail-owner",
            email="trail-owner@test.local",
            hashed_password="x",
            is_active=True,
        ))
        db.add(UserConfig(
            user_id="trail-owner",
            goal={
                "goal_kind": "race",
                "distance": "24.7k",
                "race_date": "2026-11-15",
                "target_time_sec": 0,
            },
            source_options={"athlete_timezone": "Asia/Shanghai"},
        ))
        db.commit()
    try:
        yield db_session
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        if db_session.async_engine is not None:
            import asyncio

            try:
                asyncio.run(db_session.async_engine.dispose())
            except RuntimeError:
                pass
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _known(value):
    return {"state": "known", "value": value}


def _unknown():
    return {"state": "unknown"}


def _valid_request() -> dict:
    return {
        "course_demand": {
            "schema_id": "trail_course_demand_v2",
            "fields": {
                "event_date": _known("2026-11-15"),
                "distance_meters": _known(24700),
                "total_ascent_m": _known(618),
                "total_descent_m": _known(620),
                "planning_duration_range": _known({
                    "minimum_min": 180,
                    "maximum_min": 300,
                }),
                "event_format": _known("single_day"),
                "distance_family": _known("non_ultra"),
                "planning_intent": _known("performance"),
                "grade_distribution": _known({
                    "below_neg_10": 500,
                    "neg_10_to_below_neg_3": 1500,
                    "neg_3_to_below_pos_3": 4000,
                    "pos_3_to_below_pos_10": 3000,
                    "pos_10_and_above": 1000,
                }),
                "course_footing": _known([
                    "firm_smooth",
                    "rocks_or_roots",
                ]),
                "hands_assist": _known(False),
                "fixed_rope": _known(False),
                "optional_context": {
                    "environment": {
                        "maximum_altitude_m": _unknown(),
                        "temperature_min_c": _unknown(),
                        "temperature_max_c": _unknown(),
                        "humidity_min_pct": _unknown(),
                        "humidity_max_pct": _unknown(),
                        "sun_exposure": _unknown(),
                        "wind_exposure": _unknown(),
                        "conditions_basis": _unknown(),
                    },
                    "support": {
                        "aid_support_mode": _unknown(),
                        "aid_station_count": _unknown(),
                        "max_aid_station_gap_m": _known(None),
                        "water_availability": _unknown(),
                        "food_availability": _unknown(),
                        "mandatory_gear": _known([]),
                    },
                    "fueling": {
                        "longest_practiced_duration_min": _unknown(),
                        "practice_sessions_last_42_days": _unknown(),
                        "intake_form": _unknown(),
                        "gastrointestinal_experience": _unknown(),
                    },
                },
            },
        },
        "constraints": {
            "schema_id": "non_ultra_trail_constraints_v2",
            "available_weekdays": _known([2, 4, 6]),
            "weekly_time_limit_min": _known(240),
            "maximum_session_duration_min": _known(70),
            "unavailable_dates": _known([]),
            "preferred_longest_weekday": 6,
            "nontechnical_three_minute_uphill_access": _known(True),
            "controlled_downhill_access": _known(True),
            "accessible_footing": _known([
                "firm_smooth",
                "rocks_or_roots",
            ]),
            "adult_nonclinical_scope_confirmed": _known(True),
            "performance_intent_confirmed": _known(True),
            "current_symptom_stop": _known(False),
        },
    }


def _confirm_all(db, state: dict) -> dict:
    current = state
    for section_key in TRAIL_EDITABLE_SECTION_KEYS:
        section = next(
            item
            for item in current["revision_bindings"]["section_confirmations"]
            if item["section_key"] == section_key
        )
        current = confirm_trail_plan_section(
            db,
            user_id="trail-owner",
            section_key=section_key,
            section_revision=section["current_revision"],
            expected_revision=current["composite_revision"],
            athlete_today=TODAY,
        )
    return current


def test_strict_request_contract_rejects_coercion_duplicates_and_extra_keys():
    request = _valid_request()
    assert validate_trail_draft_request(request)["constraints"][
        "available_weekdays"
    ]["value"] == (2, 4, 6)

    extra = deepcopy(request)
    extra["actor_id"] = "forged"
    with pytest.raises(TrailPlanServiceError, match="Invalid Trail"):
        validate_trail_draft_request(extra)

    coerced = deepcopy(request)
    coerced["course_demand"]["fields"]["distance_meters"] = _known("24700")
    with pytest.raises(TrailPlanServiceError):
        validate_trail_draft_request(coerced)

    duplicate = deepcopy(request)
    duplicate["constraints"]["available_weekdays"] = _known([2, 2, 6])
    with pytest.raises(TrailPlanServiceError):
        validate_trail_draft_request(duplicate)

    bad_grade = deepcopy(request)
    bad_grade["course_demand"]["fields"]["grade_distribution"]["value"][
        "below_neg_10"
    ] = 501
    with pytest.raises(TrailPlanServiceError):
        validate_trail_draft_request(bad_grade)

    forged = deepcopy(request)
    forged["course_demand"]["fields"]["event_date"]["provenance"] = (
        "course_verified"
    )
    with pytest.raises(TrailPlanServiceError):
        validate_trail_draft_request(forged)

    explicit_null = deepcopy(request)
    explicit_null["constraints"]["preferred_longest_weekday"] = None
    with pytest.raises(TrailPlanServiceError):
        validate_trail_draft_request(explicit_null)

    omitted = deepcopy(request)
    omitted["constraints"].pop("preferred_longest_weekday")
    assert validate_trail_draft_request(omitted)["constraints"][
        "preferred_longest_weekday"
    ] is None


def test_save_rejects_unavailable_dates_outside_current_14_day_horizon(trail_db):
    request = _valid_request()
    request["constraints"]["unavailable_dates"] = _known([
        (TODAY + timedelta(days=14)).isoformat(),
    ])
    with trail_db.SessionLocal() as db:
        with pytest.raises(TrailPlanServiceError) as invalid:
            save_trail_plan_draft(
                db,
                user_id="trail-owner",
                request=request,
                expected_revision=ABSENT_TRAIL_PLAN_REVISION,
                athlete_today=TODAY,
                now=NOW,
            )
        assert invalid.value.code == "TRAIL_INVALID_FIELD_VALUE"


def test_draft_confirmation_edit_reset_and_delete_are_revision_fenced(trail_db):
    with trail_db.SessionLocal() as db:
        absent = read_trail_plan_draft(
            db, user_id="trail-owner", athlete_today=TODAY
        )
        assert absent == {
            "state": "absent",
            "composite_revision": ABSENT_TRAIL_PLAN_REVISION,
        }
        saved = save_trail_plan_draft(
            db,
            user_id="trail-owner",
            request=_valid_request(),
            expected_revision=absent["composite_revision"],
            athlete_today=TODAY,
            now=NOW,
        )
        assert saved["state"] == "current"
        assert saved["course_demand"]["event_id"]
        assert all(
            item["confirmed_revision"] is None
            for item in saved["revision_bindings"]["section_confirmations"]
        )
        confirmed = _confirm_all(db, saved)
        assert all(
            item["confirmed_revision"] == item["current_revision"]
            for item in confirmed["revision_bindings"]["section_confirmations"]
        )

        changed_request = _valid_request()
        changed_request["course_demand"]["fields"]["distance_meters"] = _known(24701)
        changed = save_trail_plan_draft(
            db,
            user_id="trail-owner",
            request=changed_request,
            expected_revision=confirmed["composite_revision"],
            athlete_today=TODAY,
            now=NOW + timedelta(minutes=1),
        )
        confirmations = {
            item["section_key"]: item
            for item in changed["revision_bindings"]["section_confirmations"]
        }
        assert confirmations["section.event-duration"]["confirmed_revision"] is None
        assert all(
            confirmations[key]["confirmed_revision"]
            == confirmations[key]["current_revision"]
            for key in TRAIL_EDITABLE_SECTION_KEYS
            if key != "section.event-duration"
        )

        with pytest.raises(TrailPlanServiceError) as stale:
            reset_trail_plan_draft(
                db,
                user_id="trail-owner",
                expected_revision=confirmed["composite_revision"],
                athlete_today=TODAY,
                now=NOW,
            )
        assert stale.value.status_code == 412

        reset = reset_trail_plan_draft(
            db,
            user_id="trail-owner",
            expected_revision=changed["composite_revision"],
            athlete_today=TODAY,
            now=NOW + timedelta(minutes=2),
        )
        assert reset["reset_is_erasure"] is False
        assert reset["course_demand"]["fields"]["event_date"]["state"] == "unknown"
        assert all(
            item["confirmed_revision"] is None
            for item in reset["revision_bindings"]["section_confirmations"]
        )

        deleted = delete_trail_plan_draft(
            db,
            user_id="trail-owner",
            expected_revision=reset["composite_revision"],
            athlete_today=TODAY,
        )
        assert deleted == {
            "status": "deleted",
            "composite_revision": ABSENT_TRAIL_PLAN_REVISION,
        }
        from db.models import UserConfig

        row = db.get(UserConfig, "trail-owner")
        assert TRAIL_PLAN_GOAL_NAMESPACE not in row.goal
        assert row.goal["race_date"] == "2026-11-15"


def test_confirmation_rejects_malformed_revision_before_stale_disclosure(
    trail_db,
):
    with trail_db.SessionLocal() as db:
        saved = save_trail_plan_draft(
            db,
            user_id="trail-owner",
            request=_valid_request(),
            expected_revision=ABSENT_TRAIL_PLAN_REVISION,
            athlete_today=TODAY,
            now=NOW,
        )
        with pytest.raises(TrailPlanServiceError) as malformed:
            confirm_trail_plan_section(
                db,
                user_id="trail-owner",
                section_key="section.event-duration",
                section_revision="bogus",
                expected_revision=saved["composite_revision"],
                athlete_today=TODAY,
            )
        assert malformed.value.status_code == 400
        assert malformed.value.code == "TRAIL_INVALID_FIELD_VALUE"
        assert "current_section_revision" not in malformed.value.details


def test_assumption_confirmation_binds_the_exact_visible_section_revision(
    trail_db,
):
    request = _valid_request()
    request["course_demand"]["fields"]["optional_context"]["environment"][
        "conditions_basis"
    ] = _known("athlete_assumption")

    with trail_db.SessionLocal() as db:
        saved = save_trail_plan_draft(
            db,
            user_id="trail-owner",
            request=request,
            expected_revision=ABSENT_TRAIL_PLAN_REVISION,
            athlete_today=TODAY,
            now=NOW,
        )
        before = next(
            item
            for item in saved["revision_bindings"]["section_confirmations"]
            if item["section_key"] == "section.optional-context"
        )
        confirmed = confirm_trail_plan_section(
            db,
            user_id="trail-owner",
            section_key="section.optional-context",
            section_revision=before["current_revision"],
            expected_revision=saved["composite_revision"],
            athlete_today=TODAY,
        )
        after = next(
            item
            for item in confirmed["revision_bindings"][
                "section_confirmations"
            ]
            if item["section_key"] == "section.optional-context"
        )
        basis = confirmed["course_demand"]["fields"]["optional_context"][
            "environment"
        ]["conditions_basis"]

        assert after["current_revision"] == before["current_revision"]
        assert after["confirmed_revision"] == before["current_revision"]
        assert basis["assumption_confirmed_revision"] == basis[
            "source_revision"
        ]


def test_unknown_namespace_round_trips_but_only_reset_or_delete_can_replace_it(trail_db):
    from db.models import UserConfig

    opaque = {
        "namespace_version": 99,
        "future": {"keep": ["exact", {"value": 7}]},
    }
    with trail_db.SessionLocal() as db:
        row = db.get(UserConfig, "trail-owner")
        row.goal = {**row.goal, TRAIL_PLAN_GOAL_NAMESPACE: opaque}
        db.commit()
        state = read_trail_plan_draft(db, user_id="trail-owner", athlete_today=TODAY)
        assert state["state"] == "unknown_schema"
        assert state["namespace"] == opaque
        with pytest.raises(TrailPlanServiceError) as mismatch:
            save_trail_plan_draft(
                db,
                user_id="trail-owner",
                request=_valid_request(),
                expected_revision=state["composite_revision"],
                athlete_today=TODAY,
                now=NOW,
            )
        assert mismatch.value.code == "TRAIL_SCHEMA_VERSION_MISMATCH"
        assert db.get(UserConfig, "trail-owner").goal[TRAIL_PLAN_GOAL_NAMESPACE] == opaque

        reset = reset_trail_plan_draft(
            db,
            user_id="trail-owner",
            expected_revision=state["composite_revision"],
            athlete_today=TODAY,
            now=NOW,
        )
        assert reset["state"] == "current"
        assert db.get(UserConfig, "trail-owner").goal[TRAIL_PLAN_GOAL_NAMESPACE][
            "namespace_version"
        ] == 1


def test_readiness_is_no_write_uses_actual_inactive_core_and_invents_no_descent_or_footing(trail_db):
    from db.models import Activity, PlanProposal, UserConfig

    with trail_db.SessionLocal() as db:
        db.add(Activity(
            user_id="trail-owner",
            activity_id="trail-observation",
            date=TODAY - timedelta(days=3),
            activity_type="trail_running",
            duration_sec=3600.0,
            distance_km=10.0,
            elevation_gain_m=500.0,
            avg_power=9999.0,
            start_time=(NOW - timedelta(days=3)).isoformat(),
            source="garmin",
        ))
        db.commit()
        saved = save_trail_plan_draft(
            db,
            user_id="trail-owner",
            request=_valid_request(),
            expected_revision=ABSENT_TRAIL_PLAN_REVISION,
            athlete_today=TODAY,
            now=NOW,
        )
        confirmed = _confirm_all(db, saved)
        before_goal = deepcopy(db.get(UserConfig, "trail-owner").goal)
        statements: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.strip().upper())

        event.listen(trail_db.engine, "before_cursor_execute", capture)
        try:
            result = evaluate_trail_plan_readiness(
                db,
                user_id="trail-owner",
                athlete_today=TODAY,
            )
        finally:
            event.remove(trail_db.engine, "before_cursor_execute", capture)

        readiness = result["readiness"]
        assert readiness["status"] == "policy_unavailable"
        assert readiness["detail_reason"] == "policy_inactive"
        assert readiness["plan"] is None
        assert readiness["inactive_dry_run"] is False
        reasons = {
            f"{item['status']}.{item['detail_reason']}"
            for item in readiness["matching_reasons"]
        }
        assert "policy_unavailable.policy_inactive" in reasons
        assert "readiness_blocked.insufficient_descent_history" in reasons
        assert "readiness_blocked.insufficient_comparable_trail_history" in reasons
        assert readiness["history_statistics"]["recent_maximum_session_descent_meters"] == 0
        assert readiness["history_statistics"]["recently_observed_footing"] == []
        assert db.get(UserConfig, "trail-owner").goal == before_goal
        assert db.query(PlanProposal).count() == 0
        assert not any(
            statement.startswith(("INSERT", "UPDATE", "DELETE"))
            for statement in statements
        )
        assert confirmed["composite_revision"] == result["draft"]["composite_revision"]


def test_garmin_local_times_and_outdoor_runs_support_running_continuity(
    trail_db,
):
    from db.models import Activity

    current_week_start = TODAY - timedelta(days=TODAY.weekday())
    with trail_db.SessionLocal() as db:
        for week in range(1, 5):
            week_start = current_week_start - timedelta(weeks=week)
            for index, offset in enumerate((0, 2, 4)):
                observed = week_start + timedelta(days=offset)
                activity_type = "trail_running" if index == 2 else "running"
                db.add(Activity(
                    user_id="trail-owner",
                    activity_id=f"garmin-{week}-{index}",
                    date=observed,
                    activity_type=activity_type,
                    duration_sec=3600.0,
                    distance_km=10.0,
                    elevation_gain_m=300.0 if index == 2 else 50.0,
                    start_time=f"{observed.isoformat()} 07:00:00",
                    source="garmin",
                ))
        db.commit()
        saved = save_trail_plan_draft(
            db,
            user_id="trail-owner",
            request=_valid_request(),
            expected_revision=ABSENT_TRAIL_PLAN_REVISION,
            athlete_today=TODAY,
            now=NOW,
        )
        _confirm_all(db, saved)

        result = evaluate_trail_plan_readiness(
            db,
            user_id="trail-owner",
            athlete_today=TODAY,
        )["readiness"]
        reasons = {
            f"{item['status']}.{item['detail_reason']}"
            for item in result["matching_reasons"]
        }

        assert result["history_statistics"]["usable_completed_weeks"] == 4
        assert result["history_statistics"][
            "recent_modal_running_frequency"
        ] == 3
        assert (
            "readiness_blocked.insufficient_recent_running_history"
            not in reasons
        )
        assert "readiness_blocked.insufficient_descent_history" in reasons
