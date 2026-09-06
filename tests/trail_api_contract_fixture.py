"""Generate reviewed Trail readiness fixtures from the actual Python service."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterator

from sqlalchemy import event

from api.trail_plan_service import (
    ABSENT_TRAIL_PLAN_REVISION,
    evaluate_trail_plan_readiness,
    read_trail_plan_draft,
    save_trail_plan_draft,
)
from tests.test_trail_plan_service import NOW, TODAY, _confirm_all, _known, _valid_request


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "web"
    / "tests"
    / "fixtures"
    / "trail-readiness-service-contract.json"
)


@contextmanager
def _fresh_fixture_database() -> Iterator[Any]:
    previous_data_dir = os.environ.get("DATA_DIR")
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    os.environ["DATA_DIR"] = os.path.join(tmpdir.name, "data")
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
            try:
                asyncio.run(db_session.async_engine.dispose())
            except RuntimeError:
                pass
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        if previous_data_dir is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = previous_data_dir
        tmpdir.cleanup()


def _json_round_trip(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _canonicalize_dynamic_digests(case_name: str, value: Any) -> Any:
    """Keep actual shape/bindings while removing the save-time mutation nonce."""
    dynamic_prefixed_keys = {
        "source_revision",
        "course_revision",
        "planning_context_revision",
        "history_revision",
        "composite_revision",
        "current_revision",
        "confirmed_revision",
        "readiness_receipt_digest",
    }
    replacements: dict[str, str] = {}

    def replacement(original: str) -> str:
        if original not in replacements:
            seed = f"{case_name}:dynamic-digest:{len(replacements)}"
            replacements[original] = f"sha256:{hashlib.sha256(seed.encode()).hexdigest()}"
        return replacements[original]

    def visit(item: Any) -> Any:
        if isinstance(item, list):
            return [visit(child) for child in item]
        if not isinstance(item, dict):
            return item
        normalized: dict[str, Any] = {}
        for key, child in item.items():
            if key == "deterministic_input_hash":
                normalized[key] = hashlib.sha256(
                    f"{case_name}:deterministic-input".encode()
                ).hexdigest()
            elif (
                key in dynamic_prefixed_keys
                and isinstance(child, str)
                and child.startswith("sha256:")
            ):
                normalized[key] = replacement(child)
            else:
                normalized[key] = visit(child)
        return normalized

    return visit(value)


def _build_case(name: str) -> dict[str, Any]:
    from db.models import Activity, PlanProposal, UserConfig

    request = _valid_request()
    evaluation_day = TODAY
    activity: Activity | None = None
    if name == "expired_unavailable_date":
        request["constraints"]["unavailable_dates"] = _known([TODAY.isoformat()])
        evaluation_day = TODAY + timedelta(days=1)
    elif name == "old_loaded_activity":
        activity = Activity(
            user_id="trail-owner",
            activity_id="old-loaded-run",
            date=date(2026, 7, 1),
            activity_type="trail_running",
            duration_sec=3600.0,
            distance_km=10.0,
            elevation_gain_m=500.0,
            start_time="2026-07-01T07:00:00+08:00",
            source="garmin",
        )
    elif name == "empty_history_fallback":
        activity = Activity(
            user_id="trail-owner",
            activity_id="",
            date=date(2026, 9, 1),
            activity_type="trail_running",
            duration_sec=3600.0,
            distance_km=10.0,
            elevation_gain_m=500.0,
            start_time="2026-09-01T07:00:00+08:00",
            source="garmin",
        )
    elif name == "contradictory_preferred_weekday":
        request["constraints"]["available_weekdays"] = _known([2, 4])
        request["constraints"]["preferred_longest_weekday"] = 6
    elif name != "ordinary_confirmed":
        raise ValueError(f"unknown Trail fixture case: {name}")

    with _fresh_fixture_database() as db_session:
        with db_session.SessionLocal() as db:
            if activity is not None:
                db.add(activity)
                db.commit()
            saved = save_trail_plan_draft(
                db,
                user_id="trail-owner",
                request=request,
                expected_revision=ABSENT_TRAIL_PLAN_REVISION,
                athlete_today=TODAY,
                now=NOW,
            )
            _confirm_all(db, saved)
            fresh = read_trail_plan_draft(
                db,
                user_id="trail-owner",
                athlete_today=evaluation_day,
            )
            before_goal = deepcopy(db.get(UserConfig, "trail-owner").goal)
            statements: list[str] = []

            def capture(_conn, _cursor, statement, _parameters, _context, _many):
                statements.append(statement.strip().upper())

            event.listen(db_session.engine, "before_cursor_execute", capture)
            try:
                first = evaluate_trail_plan_readiness(
                    db,
                    user_id="trail-owner",
                    athlete_today=evaluation_day,
                )
                second = evaluate_trail_plan_readiness(
                    db,
                    user_id="trail-owner",
                    athlete_today=evaluation_day,
                )
            finally:
                event.remove(db_session.engine, "before_cursor_execute", capture)

            serialized = _json_round_trip(first)
            assert serialized == _json_round_trip(second)
            assert fresh["composite_revision"] == serialized["draft"]["composite_revision"]
            assert len(statements) == 4
            assert not any(
                statement.startswith(("INSERT", "UPDATE", "DELETE"))
                for statement in statements
            )
            assert db.get(UserConfig, "trail-owner").goal == before_goal
            assert db.query(PlanProposal).count() == 0
            canonical = _canonicalize_dynamic_digests(name, serialized)
            return {
                "evaluation_date": evaluation_day.isoformat(),
                "expected_composite_revision": canonical["draft"]["composite_revision"],
                "evaluation_statement_count": len(statements),
                "response": canonical,
            }


def build_trail_readiness_contract_fixture() -> dict[str, Any]:
    names = (
        "ordinary_confirmed",
        "expired_unavailable_date",
        "old_loaded_activity",
        "empty_history_fallback",
        "contradictory_preferred_weekday",
    )
    return {
        "schema_version": 1,
        "provenance": (
            "Actual save, four confirmations, fresh read, and repeated inactive "
            "evaluation through api.trail_plan_service using fresh synthetic SQLite; "
            "only save-nonce-dependent digests are canonically substituted while "
            "preserving format, equality, bindings, and all semantic values."
        ),
        "reference_date": TODAY.isoformat(),
        "reference_now": NOW.isoformat(),
        "cases": {name: _build_case(name) for name in names},
    }


def write_trail_readiness_contract_fixture() -> None:
    payload = build_trail_readiness_contract_fixture()
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_trail_readiness_contract_fixture()
