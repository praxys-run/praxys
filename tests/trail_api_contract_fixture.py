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
import re
import tempfile
from typing import Any, Iterator

from sqlalchemy import event

from api.trail_plan_service import (
    ABSENT_TRAIL_PLAN_REVISION,
    TRAIL_EDITABLE_SECTION_KEYS,
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
_NONCE_PREFIXED_DIGEST_KEYS = {
    "source_revision",
    "course_revision",
    "planning_context_revision",
    "composite_revision",
    "current_revision",
    "confirmed_revision",
    "assumption_confirmed_revision",
    "readiness_receipt_digest",
}
_PREFIXED_DIGEST_KEYS = _NONCE_PREFIXED_DIGEST_KEYS | {
    "history_revision",
    "source_revision_fingerprint",
    "contract_digest",
    "source_decision_digest",
    "ontology_contract_digest",
    "ontology_source_decision_digest",
}
_BARE_DIGEST = re.compile(r"[0-9a-f]{64}")
_PREFIXED_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


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


def _require_raw_digest(key: str, value: Any) -> None:
    pattern = _BARE_DIGEST if key == "deterministic_input_hash" else _PREFIXED_DIGEST
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"Invalid raw Trail digest format: {key}")


def _validate_raw_digest_formats(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _validate_raw_digest_formats(item)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key == "deterministic_input_hash" or key in _PREFIXED_DIGEST_KEYS:
                _require_raw_digest(key, child)
            _validate_raw_digest_formats(child)


def _validate_raw_readiness_bindings(response: Any) -> None:
    if not isinstance(response, dict) or set(response) != {"draft", "readiness"}:
        raise ValueError("Expected a complete raw Trail readiness response")
    draft = response["draft"]
    readiness = response["readiness"]
    if not isinstance(draft, dict) or not isinstance(readiness, dict):
        raise ValueError("Expected raw Trail draft and readiness objects")
    _require_raw_digest("composite_revision", draft.get("composite_revision"))
    _require_raw_digest("deterministic_input_hash", readiness.get("deterministic_input_hash"))
    _require_raw_digest("readiness_receipt_digest", readiness.get("readiness_receipt_digest"))
    bindings = draft.get("revision_bindings")
    if not isinstance(bindings, dict) or set(bindings) != {
        "course_revision", "planning_context_revision", "history_revision",
        "composite_revision", "section_confirmations",
    }:
        raise ValueError("Expected complete raw Trail revision bindings")
    if (
        bindings != readiness.get("revision_bindings")
        or bindings["composite_revision"] != draft["composite_revision"]
    ):
        raise ValueError("Raw Trail revision bindings do not match")
    confirmations = bindings["section_confirmations"]
    if (
        not isinstance(confirmations, list)
        or any(
            not isinstance(item, dict)
            or set(item) != {"section_key", "current_revision", "confirmed_revision"}
            for item in confirmations
        )
        or [item["section_key"] for item in confirmations] != list(TRAIL_EDITABLE_SECTION_KEYS)
        or any(item["confirmed_revision"] != item["current_revision"] for item in confirmations)
    ):
        raise ValueError("Expected four current raw Trail section confirmations")


def _canonicalize_dynamic_digests(case_name: str, value: Any) -> Any:
    """Validate raw receipts before substituting only save-nonce-derived hashes."""
    _validate_raw_digest_formats(value)
    for response in value if isinstance(value, list) else [value]:
        _validate_raw_readiness_bindings(response)
    replacements: dict[str, str] = {}

    def replacement(original: str) -> str:
        if original not in replacements:
            seed = f"{case_name}:dynamic-digest:{len(replacements)}"
            prefix = "sha256:" if original.startswith("sha256:") else ""
            replacements[original] = prefix + hashlib.sha256(seed.encode()).hexdigest()
        return replacements[original]

    def visit(item: Any) -> Any:
        if isinstance(item, list):
            return [visit(child) for child in item]
        if not isinstance(item, dict):
            return item
        normalized: dict[str, Any] = {}
        for key, child in item.items():
            if key == "deterministic_input_hash" or key in _NONCE_PREFIXED_DIGEST_KEYS:
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
            confirmed = _confirm_all(db, saved)
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
            if fresh != serialized["draft"]:
                raise ValueError("Raw fresh Trail read differs from the readiness draft")
            assert fresh["revision_bindings"]["section_confirmations"] == (
                confirmed["revision_bindings"]["section_confirmations"]
            )
            if evaluation_day != TODAY:
                assert fresh["constraints"]["unavailable_dates"]["value"] == [TODAY.isoformat()]
                assert fresh["composite_revision"] != confirmed["composite_revision"]
            else:
                assert fresh["composite_revision"] == confirmed["composite_revision"]
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
        "generator": "tests/trail_api_contract_fixture.py",
        "provenance": (
            "Actual save, four confirmations, fresh read, and repeated inactive "
            "evaluation through api.trail_plan_service using fresh synthetic SQLite; "
            "raw digest formats, fresh-read equality, mirrored revision bindings, "
            "and four current section confirmations are checked before substitution."
        ),
        "dynamic_digest_normalization": (
            "Only source, editable/section/composite revision, input, and receipt "
            "digests derived from _stamp's mutation nonce receive consistent, "
            "noncollapsing test-only replacements. Bare versus sha256-prefixed "
            "formats and all semantic values are preserved. history_revision "
            "(derived from history statistics), source_revision_fingerprint, "
            "and frozen contract digests retain their exact raw service values."
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
