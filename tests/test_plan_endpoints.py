"""Integration tests for the AI plan endpoints in api/routes/ai.py.

Covers:
- POST /api/plan/upload — replace (default) and merge modes
- PUT /api/plan/{date} — upsert single workout
- DELETE /api/plan/{date} — delete single day

These guard the contract change in #128 (delete-and-recreate replaced by
explicit modes + per-day operations) so a future refactor can't quietly
revert to "wipe everything on every push" semantics.
"""
import tempfile
from datetime import date, datetime, timedelta

import pytest

from analysis.config import (
    PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCES,
    PRAXYS_PLAN_WRITE_SOURCE,
)


@pytest.fixture
def api_client(monkeypatch):
    """FastAPI TestClient with an isolated SQLite DB and a stable test user."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY", "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o="
    )

    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.main import app
    from api.auth import (
        get_current_user_id,
        get_data_user_id,
        require_write_access,
    )
    from db.session import get_db

    test_user_id = "test-user-plan-endpoints"
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name == "stryd_connection_enabled",
    )

    from db.models import User
    seed = db_session.SessionLocal()
    try:
        seed.add(User(
            id=test_user_id,
            email="plan-endpoints@test.local",
            hashed_password="x",
            is_active=True,
        ))
        seed.commit()
    finally:
        seed.close()

    def _override_user():
        return test_user_id

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[require_write_access] = _override_user
    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[get_data_user_id] = _override_user
    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app)
    try:
        yield client, test_user_id
    finally:
        app.dependency_overrides.clear()
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


def _seed_plan(user_id: str, days: list[tuple[str, str, str]]):
    """Insert legacy Praxys rows to verify rolling-read compatibility."""
    from datetime import datetime
    from db import session as db_session
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        for date_iso, wt, desc in days:
            db.add(TrainingPlan(
                user_id=user_id,
                date=datetime.strptime(date_iso, "%Y-%m-%d").date(),
                workout_type=wt,
                workout_description=desc,
                source="ai",
            ))
        db.commit()
    finally:
        db.close()


def _seed_external_plan(
    user_id: str,
    *,
    date_iso: str,
    workout_type: str = "easy",
    activity_type: str | None = None,
) -> str:
    """Insert one provider-owned row and return its non-editable UUID."""
    from datetime import datetime
    from db import session as db_session
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        row = TrainingPlan(
            user_id=user_id,
            date=datetime.strptime(date_iso, "%Y-%m-%d").date(),
            workout_type=workout_type,
            activity_type=activity_type,
            workout_description="External coach workout",
            source="stryd",
            workout_origin="imported",
            external_id="external-workout-1",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.canonical_id
    finally:
        db.close()


def _list_plan_rows(user_id: str) -> list[dict]:
    from db import session as db_session
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        rows = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).order_by(TrainingPlan.date).all()
        return [
            {
                "canonical_id": r.canonical_id,
                "date": r.date.isoformat(),
                "workout_type": r.workout_type,
                "workout_description": r.workout_description,
                "source": r.source,
                "workout_origin": r.workout_origin,
            }
            for r in rows
        ]
    finally:
        db.close()


def _list_revisions(user_id: str) -> list[dict]:
    from db import session as db_session
    from db.models import PlanRevision

    db = db_session.SessionLocal()
    try:
        rows = db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
        ).order_by(PlanRevision.created_at, PlanRevision.id).all()
        return [
            {
                "operation": row.operation,
                "actor_type": row.actor_type,
                "actor_id": row.actor_id,
                "origin": row.origin,
                "before": row.before_snapshot,
                "after": row.after_snapshot,
                "details": row.details,
            }
            for row in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/plan/upload — replace mode (default, backwards-compat)
# ---------------------------------------------------------------------------


class TestUploadReplaceMode:
    def test_empty_csv_returns_http_error(self, api_client):
        client, _ = api_client

        response = client.post("/api/plan/upload", json={
            "csv": "date,workout_type\n",
        })

        assert response.status_code == 400
        assert response.json()["detail"] == "No rows in CSV"

    def test_replace_is_default(self, api_client):
        client, user_id = api_client
        future = (date.today() + timedelta(days=2)).isoformat()
        far = (date.today() + timedelta(days=20)).isoformat()
        _seed_plan(user_id, [
            (future, "easy", "stale entry, must be deleted"),
            (far, "rest", "also stale"),
        ])

        new_date = (date.today() + timedelta(days=5)).isoformat()
        res = client.post("/api/plan/upload", json={
            "csv": "date,workout_type,workout_description\n"
                   f"{new_date},long_run,Fresh row\n",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == "saved"
        assert body["rows"] == 1
        assert body["mode"] == "replace"

        rows = _list_plan_rows(user_id)
        assert len(rows) == 1, "replace mode wiped existing future rows"
        assert rows[0]["date"] == new_date
        assert rows[0]["source"] == PRAXYS_PLAN_WRITE_SOURCE
        assert rows[0]["workout_origin"] == "generated"
        from db import session as db_session
        from db.models import TrainingPlan

        db = db_session.SessionLocal()
        try:
            uploaded = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.date == date.fromisoformat(new_date),
            ).one()
            assert uploaded.activity_type == "running"
            assert uploaded.workout_structure_version is None
            assert uploaded.workout_structure is None
        finally:
            db.close()

    def test_replace_preserves_past_rows(self, api_client):
        client, user_id = api_client
        past = (date.today() - timedelta(days=3)).isoformat()
        future = (date.today() + timedelta(days=3)).isoformat()
        _seed_plan(user_id, [
            (past, "easy", "history"),
            (future, "easy", "to be replaced"),
        ])

        new_date = (date.today() + timedelta(days=5)).isoformat()
        res = client.post("/api/plan/upload?mode=replace", json={
            "csv": f"date,workout_type\n{new_date},rest\n",
        })
        assert res.status_code == 200, res.text

        rows = _list_plan_rows(user_id)
        dates = [r["date"] for r in rows]
        assert past in dates, "past rows must survive a replace"
        assert future not in dates
        assert new_date in dates


# ---------------------------------------------------------------------------
# POST /api/plan/upload — merge mode (the new behavior)
# ---------------------------------------------------------------------------


class TestUploadMergeMode:
    def test_merge_only_touches_payload_dates(self, api_client):
        client, user_id = api_client
        d1 = (date.today() + timedelta(days=1)).isoformat()
        d2 = (date.today() + timedelta(days=2)).isoformat()
        d3 = (date.today() + timedelta(days=3)).isoformat()
        _seed_plan(user_id, [
            (d1, "easy", "keep me"),
            (d2, "easy", "stale, will be replaced"),
            (d3, "rest", "keep me too"),
        ])

        res = client.post("/api/plan/upload?mode=merge", json={
            "csv": "date,workout_type,workout_description\n"
                   f"{d2},threshold,Updated\n",
        })
        assert res.status_code == 200, res.text
        assert res.json()["mode"] == "merge"

        rows = {r["date"]: r for r in _list_plan_rows(user_id)}
        assert rows[d1]["workout_description"] == "keep me"
        assert rows[d2]["workout_type"] == "threshold"
        assert rows[d2]["workout_description"] == "Updated"
        assert rows[d3]["workout_description"] == "keep me too"

    def test_merge_inserts_new_dates(self, api_client):
        client, user_id = api_client
        d_existing = (date.today() + timedelta(days=1)).isoformat()
        _seed_plan(user_id, [(d_existing, "easy", "existing")])

        d_new = (date.today() + timedelta(days=10)).isoformat()
        res = client.post("/api/plan/upload?mode=merge", json={
            "csv": f"date,workout_type\n{d_new},long_run\n",
        })
        assert res.status_code == 200, res.text

        rows = _list_plan_rows(user_id)
        assert len(rows) == 2
        assert {r["date"] for r in rows} == {d_existing, d_new}

    def test_merge_preserves_canonical_identity_across_type_edit(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=2)).isoformat()
        _seed_plan(user_id, [(target, "easy", "before")])
        before = _list_plan_rows(user_id)[0]["canonical_id"]

        response = client.post("/api/plan/upload?mode=merge", json={
            "csv": "date,workout_type,workout_description\n"
                   f"{target},threshold,after\n",
        })

        assert response.status_code == 200, response.text
        after = _list_plan_rows(user_id)[0]
        assert after["canonical_id"] == before
        assert after["workout_type"] == "threshold"

    def test_upload_allows_multiple_same_type_workouts_on_one_date(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=3)).isoformat()

        response = client.post("/api/plan/upload?mode=merge", json={
            "csv": "date,workout_type,workout_description\n"
                   f"{target},easy,Morning\n"
                   f"{target},easy,Evening\n",
        })

        assert response.status_code == 200, response.text
        rows = _list_plan_rows(user_id)
        assert len(rows) == 2
        assert len({row["canonical_id"] for row in rows}) == 2

    def test_merge_does_not_transfer_identity_by_same_type_row_order(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=3)).isoformat()
        _seed_plan(user_id, [
            (target, "easy", "Morning"),
            (target, "easy", "Evening"),
        ])
        before = {
            row["workout_description"]: row["canonical_id"]
            for row in _list_plan_rows(user_id)
        }

        response = client.post("/api/plan/upload?mode=merge", json={
            "csv": "date,workout_type,workout_description\n"
                   f"{target},easy,Evening\n",
        })

        assert response.status_code == 200, response.text
        rows = _list_plan_rows(user_id)
        assert len(rows) == 1
        assert rows[0]["workout_description"] == "Evening"
        assert rows[0]["canonical_id"] == before["Evening"]


# ---------------------------------------------------------------------------
# PUT /api/plan/{date}
# ---------------------------------------------------------------------------


class TestUpsertPlanDay:
    def test_put_inserts_new_day(self, api_client):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        res = client.put(f"/api/plan/{target}", json={
            "workout_type": "easy",
            "planned_duration_min": 45,
            "target_power_min": 150,
            "target_power_max": 200,
            "workout_description": "Easy aerobic run",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["date"] == target
        assert body["workout_type"] == "easy"
        assert body["planned_duration_min"] == 45
        assert body["source"] == "ai"
        assert body["owner"] == PRAXYS_PLAN_SOURCE
        assert body["origin"] == "manual"

    def test_put_replaces_existing_day_only(self, api_client):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        other = (date.today() + timedelta(days=5)).isoformat()
        _seed_plan(user_id, [
            (target, "easy", "old"),
            (other, "rest", "untouched"),
        ])
        canonical_id = next(
            row["canonical_id"]
            for row in _list_plan_rows(user_id)
            if row["date"] == target
        )

        res = client.put(f"/api/plan/{target}", json={
            "workout_type": "threshold",
            "workout_description": "New workout",
        })
        assert res.status_code == 200, res.text

        rows = {r["date"]: r for r in _list_plan_rows(user_id)}
        assert rows[target]["workout_type"] == "threshold"
        assert rows[target]["workout_description"] == "New workout"
        assert rows[target]["canonical_id"] == canonical_id
        assert rows[other]["workout_description"] == "untouched"

    def test_put_reuses_only_unique_exact_identity_on_ambiguous_day(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        _seed_plan(user_id, [
            (target, "easy", "Morning"),
            (target, "easy", "Evening"),
        ])
        before = {
            row["workout_description"]: row["canonical_id"]
            for row in _list_plan_rows(user_id)
        }

        response = client.put(f"/api/plan/{target}", json={
            "workout_type": "easy",
            "workout_description": "Evening",
        })

        assert response.status_code == 200, response.text
        assert response.json()["canonical_id"] == before["Evening"]
        rows = _list_plan_rows(user_id)
        assert len(rows) == 1
        assert rows[0]["canonical_id"] == before["Evening"]

    def test_put_rejects_bad_date(self, api_client):
        client, _ = api_client
        res = client.put("/api/plan/not-a-date", json={"workout_type": "easy"})
        assert res.status_code == 400

    def test_put_rejects_completed_history(self, api_client):
        client, user_id = api_client
        target = (date.today() - timedelta(days=1)).isoformat()
        _seed_plan(user_id, [(target, "easy", "completed")])

        response = client.put(f"/api/plan/{target}", json={
            "workout_type": "threshold",
        })

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "PLAN_HISTORY_IMMUTABLE"
        assert detail["minimum_date"] == date.today().isoformat()
        assert _list_plan_rows(user_id)[0]["workout_description"] == "completed"


# ---------------------------------------------------------------------------
# DELETE /api/plan/{date}
# ---------------------------------------------------------------------------


class TestDeletePlanDay:
    def test_delete_removes_only_target_day(self, api_client):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        other = (date.today() + timedelta(days=5)).isoformat()
        _seed_plan(user_id, [
            (target, "easy", "to be deleted"),
            (other, "rest", "must survive"),
        ])

        res = client.delete(f"/api/plan/{target}")
        assert res.status_code == 200, res.text
        assert res.json()["rows"] == 1

        rows = _list_plan_rows(user_id)
        dates = [r["date"] for r in rows]
        assert target not in dates
        assert other in dates

    def test_delete_missing_day_is_noop(self, api_client):
        client, _ = api_client
        target = (date.today() + timedelta(days=99)).isoformat()
        res = client.delete(f"/api/plan/{target}")
        assert res.status_code == 200, res.text
        assert res.json()["rows"] == 0

    def test_delete_rejects_bad_date(self, api_client):
        client, _ = api_client
        res = client.delete("/api/plan/2026-99-99")
        assert res.status_code == 400

    def test_delete_rejects_completed_history(self, api_client):
        client, user_id = api_client
        target = (date.today() - timedelta(days=1)).isoformat()
        _seed_plan(user_id, [(target, "easy", "completed")])

        response = client.delete(f"/api/plan/{target}")

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "PLAN_HISTORY_IMMUTABLE"
        assert detail["minimum_date"] == date.today().isoformat()
        assert len(_list_plan_rows(user_id)) == 1


# ---------------------------------------------------------------------------
# Canonical-ID workout management API
# ---------------------------------------------------------------------------


class TestCanonicalWorkoutManagement:
    def test_mutation_history_boundary_uses_athlete_date(
        self,
        api_client,
        monkeypatch,
    ):
        client, _ = api_client
        athlete_today = date.today() + timedelta(days=1)
        monkeypatch.setattr(
            "api.routes.ai._current_athlete_date",
            lambda db, user_id: athlete_today,
        )

        response = client.post("/api/plan/workouts", json={
            "date": date.today().isoformat(),
            "workout_type": "easy",
        })

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "PLAN_HISTORY_IMMUTABLE"
        assert detail["minimum_date"] == athlete_today.isoformat()

    def test_create_returns_version_revision_and_delivery_state(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=3)).isoformat()

        response = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "easy",
            "planned_duration_min": 45,
            "workout_description": "Aerobic run",
        })

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "created"
        assert body["date"] == target
        assert body["owner"] == "praxys"
        assert body["origin"] == "manual"
        assert body["editable"] is True
        assert len(body["workout_version"]) == 64
        assert body["revision_id"]
        assert body["delivery"]["status"] in {
            "blocked",
            "complete",
            "partial",
            "skipped",
            "unavailable",
        }
        revisions = _list_revisions(user_id)
        assert revisions[-1]["operation"] == "create"
        assert revisions[-1]["after"][0]["canonical_id"] == body["canonical_id"]

    def test_list_exposes_version_and_only_praxys_rows_are_editable(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=3)).isoformat()
        external_target = (date.today() + timedelta(days=4)).isoformat()
        _seed_plan(user_id, [(target, "easy", "Praxys")])
        _seed_external_plan(
            user_id,
            date_iso=external_target,
            workout_type="tempo",
            activity_type="ultra_trail",
        )

        response = client.get(
            f"/api/plan?start={target}&end={external_target}",
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["management"]["mutation_api_version"] == 1
        assert body["management"]["can_write"] is True
        assert body["management"]["minimum_date"] == date.today().isoformat()
        assert body["management"]["external_overlap_dates"] == []
        praxys = next(
            workout
            for workout in body["workouts"]
            if workout["owner"] == "praxys"
        )
        external = next(
            workout
            for workout in body["workouts"]
            if workout["owner"] == "external"
        )
        assert praxys["editable"] is True
        assert len(praxys["workout_version"]) == 64
        assert praxys["workout_structure_status"] == "absent"
        assert external["editable"] is False
        assert external["activity_type"] == "other"
        assert external["workout_structure_status"] == "absent"
        assert "workout_version" not in external

    def test_list_window_and_editability_use_athlete_date(
        self,
        api_client,
        monkeypatch,
    ):
        client, user_id = api_client
        server_today = date.today()
        athlete_today = server_today + timedelta(days=1)
        _seed_plan(user_id, [
            (server_today.isoformat(), "easy", "athlete history"),
            (athlete_today.isoformat(), "tempo", "athlete today"),
        ])
        monkeypatch.setattr(
            "api.routes.plan.effective_athlete_date",
            lambda config: athlete_today,
        )

        response = client.get(
            "/api/plan",
            params={
                "start": server_today.isoformat(),
                "end": athlete_today.isoformat(),
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["management"]["minimum_date"] == athlete_today.isoformat()
        editable_by_date = {
            workout["date"]: workout["editable"]
            for workout in body["workouts"]
        }
        assert editable_by_date == {
            server_today.isoformat(): False,
            athlete_today.isoformat(): True,
        }

        default_window = client.get("/api/plan")
        assert default_window.status_code == 200, default_window.text
        assert default_window.json()["window"]["start"] == athlete_today.isoformat()

    def test_demo_view_is_explicitly_read_only(self, api_client):
        client, user_id = api_client
        target = (date.today() + timedelta(days=3)).isoformat()
        _seed_plan(user_id, [(target, "easy", "Praxys")])

        from api.auth import get_current_user_id
        from api.main import app

        app.dependency_overrides[get_current_user_id] = lambda: "demo-viewer"
        response = client.get(f"/api/plan?start={target}&end={target}")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["management"]["can_write"] is False
        assert body["workouts"][0]["editable"] is False
        assert "stryd_status" not in body

        app.dependency_overrides[get_current_user_id] = lambda: user_id

    def test_plan_etag_salts_date_and_write_capability(
        self,
        api_client,
        monkeypatch,
    ):
        client, user_id = api_client
        salts: list[str] = []

        def capture_etag(
            db: object,
            called_user_id: str,
            scopes: object,
            *,
            salt: str | None = None,
        ) -> str:
            assert called_user_id == user_id
            salts.append(salt)
            return f'W/"etag-{len(salts)}"'

        monkeypatch.setattr("api.routes.plan.compute_etag", capture_etag)
        first = client.get("/api/plan")

        from api.auth import get_current_user_id
        from api.main import app

        app.dependency_overrides[get_current_user_id] = lambda: "demo-viewer"
        second = client.get("/api/plan")

        assert first.status_code == 200
        assert second.status_code == 200
        assert f"today={date.today().isoformat()}" in salts[0]
        assert "writable=1" in salts[0]
        assert "writable=0" in salts[1]
        assert first.headers["etag"] != second.headers["etag"]

        app.dependency_overrides[get_current_user_id] = lambda: user_id

    def test_edit_reschedules_in_place_and_stale_retry_fails_closed(
        self,
        api_client,
    ):
        client, user_id = api_client
        original_date = (date.today() + timedelta(days=3)).isoformat()
        next_date = (date.today() + timedelta(days=5)).isoformat()
        created = client.post("/api/plan/workouts", json={
            "date": original_date,
            "workout_type": "easy",
            "planned_duration_min": 40,
        }).json()

        response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": created["workout_version"],
                "date": next_date,
                "workout_type": "threshold",
                "planned_duration_min": 50,
            },
        )

        assert response.status_code == 200, response.text
        updated = response.json()
        assert updated["canonical_id"] == created["canonical_id"]
        assert updated["date"] == next_date
        assert updated["workout_type"] == "threshold"
        assert updated["workout_version"] != created["workout_version"]

        stale = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": created["workout_version"],
                "workout_description": "Overwrite newer edit",
            },
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "PLAN_VERSION_CONFLICT"
        rows = _list_plan_rows(user_id)
        assert rows == [{
            "canonical_id": created["canonical_id"],
            "date": next_date,
            "workout_type": "threshold",
            "workout_description": "",
            "source": PRAXYS_PLAN_WRITE_SOURCE,
            "workout_origin": "manual",
        }]
        assert [row["operation"] for row in _list_revisions(user_id)] == [
            "create",
            "update",
        ]

    def test_structured_workout_fields_round_trip_through_create_read_and_update(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        created = client.post("/api/plan/workouts", json={
            "date": target,
            "activity_type": "trail_running",
            "workout_type": "tempo",
            "workout_description": "Trail tempo",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [
                    {
                        "type": "step",
                        "phase": "warmup",
                        "label": "Easy opening",
                        "instructions": "Relax and settle before the main set.",
                        "termination": {"type": "time", "seconds": 600},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 65,
                            "max": 75,
                        },
                    },
                    {
                        "type": "step",
                        "phase": "work",
                        "termination": {"type": "time", "seconds": 1200},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 88,
                            "max": 92,
                        },
                    },
                    {
                        "type": "step",
                        "phase": "cooldown",
                        "termination": {"type": "time", "seconds": 300},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 60,
                            "max": 70,
                        },
                    },
                ]
            },
        })
        assert created.status_code == 201, created.text
        created_body = created.json()
        assert created_body["activity_type"] == "trail_running"
        assert created_body["workout_structure_version"] == "v1"
        assert created_body["workout_structure"]["steps"][1]["phase"] == "work"

        listed = client.get(f"/api/plan?start={target}&end={target}")
        assert listed.status_code == 200, listed.text
        listed_workout = listed.json()["workouts"][0]
        assert listed_workout["activity_type"] == "trail_running"
        assert listed_workout["workout_structure"] == created_body["workout_structure"]

        updated = client.put(
            f"/api/plan/workouts/{created_body['canonical_id']}",
            json={
                "expected_version": created_body["workout_version"],
                "workout_structure_version": "v1",
                "workout_structure": {
                    "steps": [
                        {
                            "type": "step",
                            "phase": "warmup",
                            "termination": {"type": "time", "seconds": 600},
                            "target": {
                                "metric": "power",
                                "unit": "percent_cp",
                                "reference": "critical_power",
                                "min": 65,
                                "max": 75,
                            },
                        },
                        {
                            "type": "step",
                            "phase": "work",
                            "termination": {"type": "time", "seconds": 1500},
                            "target": {
                                "metric": "power",
                                "unit": "percent_cp",
                                "reference": "critical_power",
                                "min": 90,
                                "max": 94,
                            },
                        },
                    ]
                },
            },
        )
        assert updated.status_code == 200, updated.text
        updated_body = updated.json()
        assert updated_body["activity_type"] == "trail_running"
        assert updated_body["workout_structure"]["steps"][1]["termination"]["seconds"] == 1500
        assert updated_body["workout_version"] != created_body["workout_version"]

        from db import session as db_session
        from db.models import TrainingPlan

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created_body["canonical_id"],
            ).one()
            assert row.activity_type == "trail_running"
            assert row.workout_structure_version == "v1"
            assert row.workout_structure == updated_body["workout_structure"]
        finally:
            db.close()

    def test_flat_editor_preserves_authoritative_repeat_structure(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        structure = {
            "steps": [
                {
                    "type": "step",
                    "phase": "warmup",
                    "termination": {"type": "time", "seconds": 600},
                    "target": {
                        "metric": "power",
                        "unit": "percent_cp",
                        "reference": "critical_power",
                        "min": 65,
                        "max": 75,
                    },
                },
                {
                    "type": "repeat",
                    "label": "Main set",
                    "repetitions": 4,
                    "steps": [
                        {
                            "type": "step",
                            "phase": "work",
                            "label": "On",
                            "instructions": "Run tall; hold the prescribed power.",
                            "termination": {
                                "type": "time",
                                "seconds": 240,
                            },
                            "target": {
                                "metric": "power",
                                "unit": "percent_cp",
                                "reference": "critical_power",
                                "min": 105,
                                "max": 110,
                            },
                        },
                        {
                            "type": "step",
                            "phase": "recovery",
                            "label": "Float",
                            "instructions": "Keep moving without forcing pace.",
                            "termination": {
                                "type": "time",
                                "seconds": 180,
                            },
                            "target": {
                                "metric": "power",
                                "unit": "percent_cp",
                                "reference": "critical_power",
                                "min": 55,
                                "max": 65,
                            },
                        },
                    ],
                },
                {
                    "type": "step",
                    "phase": "cooldown",
                    "label": "Easy finish",
                    "instructions": "Let the effort fall naturally.",
                    "termination": {"type": "time", "seconds": 600},
                    "target": {
                        "metric": "power",
                        "unit": "percent_cp",
                        "reference": "critical_power",
                        "min": 60,
                        "max": 70,
                    },
                },
            ],
        }
        created_response = client.post("/api/plan/workouts", json={
            "date": target,
            "activity_type": "trail_running",
            "workout_type": "interval",
            "workout_description": "Four repeats",
            "workout_structure_version": "v1",
            "workout_structure": structure,
        })
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()
        assert created["planned_duration_min"] == 48

        # Web and miniapp send every flat projection on a note-only save.
        updated_response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": created["workout_version"],
                "date": target,
                "workout_type": "interval",
                "planned_duration_min": 48,
                "planned_distance_km": None,
                "target_power_min": None,
                "target_power_max": None,
                "target_hr_min": None,
                "target_hr_max": None,
                "target_pace_min": None,
                "target_pace_max": None,
                "workout_description": "Notes only",
            },
        )

        assert updated_response.status_code == 200, updated_response.text
        updated = updated_response.json()
        assert updated["activity_type"] == "trail_running"
        assert updated["workout_structure"] == structure
        assert updated["workout_description"] == "Notes only"

        conflict = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": updated["workout_version"],
                "planned_duration_min": 49,
            },
        )
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["detail"] == {
            "code": "PLAN_STRUCTURE_PROJECTION_CONFLICT",
            "message": (
                "Flat workout fields cannot change an authoritative "
                "workout structure."
            ),
            "fields": ["planned_duration_min"],
        }

        upsert_response = client.put(
            f"/api/plan/{target}",
            json={
                "workout_type": "interval",
                "planned_duration_min": 48,
                "planned_distance_km": None,
                "target_power_min": None,
                "target_power_max": None,
                "target_hr_min": None,
                "target_hr_max": None,
                "target_pace_min": None,
                "target_pace_max": None,
                "workout_description": "Legacy editor notes",
            },
        )
        assert upsert_response.status_code == 200, upsert_response.text
        upserted = upsert_response.json()
        assert upserted["canonical_id"] == created["canonical_id"]
        assert upserted["activity_type"] == "trail_running"
        assert upserted["workout_structure"] == structure

        from db import session as db_session
        from db.models import TrainingPlan

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created["canonical_id"],
            ).one()
            assert row.workout_structure == structure
            assert row.planned_duration_min == 48
            assert row.activity_type == "trail_running"
        finally:
            db.close()

    def test_newer_structure_allows_note_edit_without_rewriting_tree(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=5)).isoformat()
        _seed_plan(user_id, [(target, "interval", "Future structure")])
        future_structure = {
            "steps": [{
                "type": "repeat",
                "repetitions": 3,
                "steps": [{
                    "type": "ramp",
                    "from": 70,
                    "to": 90,
                }],
            }],
        }

        from db import session as db_session
        from db.models import TrainingPlan

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.date == datetime.strptime(
                    target,
                    "%Y-%m-%d",
                ).date(),
            ).one()
            row.activity_type = "trail_running"
            row.workout_structure_version = "v2"
            row.workout_structure = future_structure
            db.commit()
            canonical_id = row.canonical_id
        finally:
            db.close()

        listed = client.get(
            f"/api/plan?start={target}&end={target}",
        ).json()["workouts"][0]
        assert listed["workout_structure_status"] == "unsupported"
        assert listed["workout_structure_version"] == "v2"
        assert listed["workout_structure"] == future_structure

        updated_response = client.put(
            f"/api/plan/workouts/{canonical_id}",
            json={
                "expected_version": listed["workout_version"],
                "date": target,
                "workout_description": "Notes stay safe",
            },
        )

        assert updated_response.status_code == 200, updated_response.text
        updated = updated_response.json()
        assert updated["workout_structure_status"] == "unsupported"
        assert updated["workout_structure_version"] == "v2"
        assert updated["workout_structure"] == future_structure
        assert updated["workout_description"] == "Notes stay safe"

        rejected = client.put(
            f"/api/plan/workouts/{canonical_id}",
            json={
                "expected_version": updated["workout_version"],
                "activity_type": "running",
            },
        )
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["detail"]["code"] == (
            "PLAN_WORKOUT_STRUCTURE_UNSUPPORTED"
        )

    def test_rest_transitions_reset_activity_and_structure_without_500(
        self,
        api_client,
    ):
        client, _ = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        created = client.post("/api/plan/workouts", json={
            "date": target,
            "activity_type": "trail_running",
            "workout_type": "interval",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [{
                    "type": "step",
                    "phase": "work",
                    "termination": {"type": "time", "seconds": 1200},
                    "target": {
                        "metric": "power",
                        "unit": "percent_cp",
                        "reference": "critical_power",
                        "min": 95,
                        "max": 100,
                    },
                }],
            },
        }).json()

        rest_response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": created["workout_version"],
                "workout_type": "rest",
                "planned_duration_min": None,
                "planned_distance_km": None,
                "target_power_min": None,
                "target_power_max": None,
                "target_hr_min": None,
                "target_hr_max": None,
                "target_pace_min": None,
                "target_pace_max": None,
            },
        )
        assert rest_response.status_code == 200, rest_response.text
        rest = rest_response.json()
        assert rest["activity_type"] == "rest"
        assert rest["workout_structure_version"] == "v1"
        assert rest["workout_structure"] == {"steps": []}

        # A cached client may echo the former rest activity while changing
        # purpose. The server owns the transition default and must not throw.
        easy_response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": rest["workout_version"],
                "activity_type": "rest",
                "workout_type": "easy",
                "planned_duration_min": 30,
            },
        )
        assert easy_response.status_code == 200, easy_response.text
        easy = easy_response.json()
        assert easy["activity_type"] == "running"
        assert easy["workout_structure_version"] == "v1"
        assert easy["workout_structure"]["steps"][0]["termination"] == {
            "type": "time",
            "seconds": 1800,
        }

    def test_legacy_flat_crud_stays_flat_and_invalid_transition_is_typed(
        self,
        api_client,
    ):
        client, _ = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        flat_response = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "easy",
            "planned_duration_min": 40,
        })
        assert flat_response.status_code == 201, flat_response.text
        flat = flat_response.json()
        assert flat["activity_type"] == "running"
        assert flat["workout_structure_version"] is None
        assert flat["workout_structure"] is None

        rest_response = client.put(
            f"/api/plan/workouts/{flat['canonical_id']}",
            json={
                "expected_version": flat["workout_version"],
                "workout_type": "rest",
            },
        )
        assert rest_response.status_code == 200, rest_response.text
        rest = rest_response.json()
        assert rest["activity_type"] == "rest"
        assert rest["workout_structure_version"] is None
        assert rest["workout_structure"] is None

        # Explicitly opting a rest row into v1 makes the transition synthesis
        # path authoritative; values that round to an invalid step fail safely.
        structured_rest = client.put(
            f"/api/plan/workouts/{flat['canonical_id']}",
            json={
                "expected_version": rest["workout_version"],
                "workout_structure_version": "v1",
                "workout_structure": {"steps": []},
            },
        ).json()
        invalid = client.put(
            f"/api/plan/workouts/{flat['canonical_id']}",
            json={
                "expected_version": structured_rest["workout_version"],
                "workout_type": "easy",
                "planned_duration_min": 0.001,
            },
        )
        assert invalid.status_code == 422, invalid.text
        assert invalid.json()["detail"]["code"] == (
            "PLAN_WORKOUT_STRUCTURE_INVALID"
        )

        ambiguous_termination = client.put(
            f"/api/plan/workouts/{flat['canonical_id']}",
            json={
                "expected_version": structured_rest["workout_version"],
                "workout_type": "easy",
                "planned_duration_min": 30,
                "planned_distance_km": 5,
            },
        )
        assert ambiguous_termination.status_code == 422, (
            ambiguous_termination.text
        )
        assert ambiguous_termination.json()["detail"]["code"] == (
            "PLAN_WORKOUT_STRUCTURE_INVALID"
        )

    def test_convert_to_rest_and_delete_require_current_version(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        created = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "tempo",
            "planned_duration_min": 55,
            "planned_distance_km": 10,
        }).json()

        converted_response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": created["workout_version"],
                "workout_type": "rest",
                "planned_duration_min": None,
                "planned_distance_km": None,
                "target_power_min": None,
                "target_power_max": None,
                "workout_description": "",
            },
        )
        assert converted_response.status_code == 200, converted_response.text
        converted = converted_response.json()
        assert converted["workout_type"] == "rest"
        assert converted["planned_duration_min"] is None

        stale_delete = client.delete(
            f"/api/plan/workouts/{created['canonical_id']}",
            params={"expected_version": created["workout_version"]},
        )
        assert stale_delete.status_code == 409
        assert stale_delete.json()["detail"]["code"] == "PLAN_VERSION_CONFLICT"

        deleted = client.delete(
            f"/api/plan/workouts/{created['canonical_id']}",
            params={"expected_version": converted["workout_version"]},
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["status"] == "deleted"
        assert _list_plan_rows(user_id) == []
        assert [row["operation"] for row in _list_revisions(user_id)] == [
            "create",
            "update",
            "delete",
        ]

    def test_rest_conversion_clears_every_hidden_training_target(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        created = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "tempo",
            "planned_duration_min": 55,
            "planned_distance_km": 10,
            "target_power_min": 250,
            "target_power_max": 280,
            "target_hr_min": 155,
            "target_hr_max": 170,
            "target_pace_min": "04:00",
            "target_pace_max": "04:20",
        }).json()

        from db import session as db_session
        from db.models import TrainingPlan

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created["canonical_id"],
            ).one()
            row.start_time = datetime(2030, 1, 1, 8)
            db.commit()
        finally:
            db.close()

        current = client.get(
            f"/api/plan?start={target}&end={target}",
        ).json()["workouts"][0]
        assert current["hr_min"] == 155
        assert current["hr_max"] == 170
        assert current["pace_min"] == "04:00"
        assert current["pace_max"] == "04:20"

        response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": current["workout_version"],
                "workout_type": "rest",
            },
        )

        assert response.status_code == 200, response.text
        converted = response.json()
        for field in (
            "planned_duration_min",
            "planned_distance_km",
            "target_power_min",
            "target_power_max",
            "target_hr_min",
            "target_hr_max",
            "target_pace_min",
            "target_pace_max",
        ):
            assert converted[field] is None

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created["canonical_id"],
            ).one()
            assert row.start_time is None
        finally:
            db.close()

    def test_same_date_edit_preserves_start_time_but_reschedule_clears_it(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = date.today() + timedelta(days=4)
        created = client.post("/api/plan/workouts", json={
            "date": target.isoformat(),
            "workout_type": "easy",
            "workout_description": "Morning run",
        }).json()

        from db import session as db_session
        from db.models import TrainingPlan

        scheduled_time = datetime.combine(target, datetime.min.time()).replace(
            hour=7,
            minute=30,
        )
        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created["canonical_id"],
            ).one()
            row.start_time = scheduled_time
            db.commit()
        finally:
            db.close()

        current = client.get(
            f"/api/plan?start={target}&end={target}",
        ).json()["workouts"][0]
        edited = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": current["workout_version"],
                "workout_description": "Updated notes",
            },
        )
        assert edited.status_code == 200, edited.text

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created["canonical_id"],
            ).one()
            assert row.start_time == scheduled_time
        finally:
            db.close()

        moved_date = target + timedelta(days=1)
        moved = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": edited.json()["workout_version"],
                "date": moved_date.isoformat(),
            },
        )
        assert moved.status_code == 200, moved.text

        db = db_session.SessionLocal()
        try:
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == created["canonical_id"],
            ).one()
            assert row.start_time is None
        finally:
            db.close()

    def test_mutation_response_normalizes_strings_and_delivery_shape(
        self,
        api_client,
    ):
        client, _ = api_client
        target = (date.today() + timedelta(days=3)).isoformat()

        response = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "  custom session  ",
            "workout_description": "  Keep exact intent  ",
        })

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["workout_type"] == "custom session"
        assert body["workout_description"] == "Keep exact intent"
        assert set(body["delivery"]) == {
            "status",
            "target",
            "reason",
            "items",
        }

    def test_target_range_errors_are_structured_after_partial_merge(
        self,
        api_client,
    ):
        client, _ = api_client
        target = (date.today() + timedelta(days=3)).isoformat()

        invalid_create = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "tempo",
            "target_power_min": 280,
            "target_power_max": 250,
        })
        assert invalid_create.status_code == 400
        assert invalid_create.json()["detail"]["code"] == (
            "PLAN_TARGET_RANGE_INVALID"
        )

        created = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "tempo",
            "target_hr_max": 165,
        }).json()
        invalid_update = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={
                "expected_version": created["workout_version"],
                "target_hr_min": 170,
            },
        )
        assert invalid_update.status_code == 400
        assert invalid_update.json()["detail"]["code"] == (
            "PLAN_TARGET_RANGE_INVALID"
        )

    def test_empty_update_returns_structured_no_changes(
        self,
        api_client,
    ):
        client, _ = api_client
        target = (date.today() + timedelta(days=3)).isoformat()
        created = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "easy",
        }).json()

        response = client.put(
            f"/api/plan/workouts/{created['canonical_id']}",
            json={"expected_version": created["workout_version"]},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "PLAN_NO_CHANGES"

    def test_compatibility_preview_is_typed_and_never_delivers(
        self,
        api_client,
    ):
        """Draft compatibility names lossy fields without writing a workout."""
        client, user_id = api_client
        target = (date.today() + timedelta(days=3)).isoformat()
        response = client.post("/api/plan/workouts/compatibility", json={
            "date": target,
            "activity_type": "trail_running",
            "workout_type": "hill_repeat",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [{
                    "type": "repeat",
                    "label": "Hill set",
                    "repetitions": 2,
                    "steps": [{
                        "type": "step",
                        "phase": "rest",
                        "label": "Walk",
                        "instructions": "Wait for breathing to settle.",
                        "termination": {"type": "manual"},
                        "target": {
                            "metric": "rpe",
                            "unit": "scale_10",
                            "reference": "perceived_exertion",
                            "min": 3,
                        },
                    }],
                }],
            },
        })

        assert response.status_code == 200, response.text
        by_target = {
            item["target"]: item
            for item in response.json()["providers"]
        }
        assert by_target["garmin"]["compatible"] is False
        assert by_target["garmin"]["mode"] == "unsupported"
        assert by_target["stryd"]["compatible"] is False
        assert {
            reason["code"] for reason in by_target["stryd"]["reasons"]
        } == {
            "wording_not_supported",
            "termination_not_supported",
            "target_not_supported",
        }
        assert _list_plan_rows(user_id) == []

    def test_compatibility_preview_accepts_fractional_stryd_percent_cp(
        self,
        api_client,
    ):
        client, _ = api_client
        target = (date.today() + timedelta(days=3)).isoformat()
        response = client.post("/api/plan/workouts/compatibility", json={
            "date": target,
            "activity_type": "running",
            "workout_type": "threshold",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [{
                    "type": "step",
                    "phase": "work",
                    "termination": {"type": "time", "seconds": 300},
                    "target": {
                        "metric": "power",
                        "unit": "percent_cp",
                        "reference": "critical_power",
                        "min": 95.5,
                        "max": 96.5,
                    },
                }],
            },
        })

        assert response.status_code == 200, response.text
        stryd = next(
            item
            for item in response.json()["providers"]
            if item["target"] == "stryd"
        )
        assert stryd["compatible"] is True
        assert stryd["reasons"] == []

    def test_compatibility_preview_hides_stryd_when_gate_is_off(
        self,
        api_client,
        monkeypatch,
    ):
        client, _ = api_client
        monkeypatch.setattr(
            "api.statsig_client.check_gate",
            lambda gate_name, _user: (
                gate_name == "garmin_plan_delivery_eligible"
            ),
        )

        response = client.post(
            "/api/plan/workouts/compatibility",
            json={
                "date": (date.today() + timedelta(days=3)).isoformat(),
                "activity_type": "running",
                "workout_type": "easy",
                "planned_duration_min": 45,
            },
        )

        assert response.status_code == 200, response.text
        assert [
            provider["target"]
            for provider in response.json()["providers"]
        ] == ["garmin"]

    def test_compatibility_preview_uses_viewer_eligibility(
        self,
        api_client,
        monkeypatch,
    ):
        client, _ = api_client
        from api.auth import get_current_user_id
        from api.main import app
        from db import session as db_session
        from db.models import User

        db = db_session.SessionLocal()
        try:
            db.add(User(
                id="demo-compatibility-viewer",
                email="demo-compatibility@test.local",
                hashed_password="x",
                is_active=True,
                is_demo=True,
            ))
            db.commit()
        finally:
            db.close()

        app.dependency_overrides[get_current_user_id] = (
            lambda: "demo-compatibility-viewer"
        )
        monkeypatch.setattr(
            "api.statsig_client.check_gate",
            lambda _gate_name, _user: True,
        )

        response = client.post(
            "/api/plan/workouts/compatibility",
            json={
                "date": (date.today() + timedelta(days=3)).isoformat(),
                "activity_type": "running",
                "workout_type": "easy",
                "planned_duration_min": 45,
            },
        )

        assert response.status_code == 200, response.text
        assert [
            provider["target"]
            for provider in response.json()["providers"]
        ] == ["garmin"]

    def test_external_and_other_user_workouts_are_not_mutable(
        self,
        api_client,
    ):
        client, user_id = api_client
        target = (date.today() + timedelta(days=4)).isoformat()
        external_id = _seed_external_plan(user_id, date_iso=target)
        _seed_plan("another-user", [(target, "easy", "Private")])
        other_id = _list_plan_rows("another-user")[0]["canonical_id"]
        expected = "0" * 64

        for canonical_id in (external_id, other_id):
            response = client.put(
                f"/api/plan/workouts/{canonical_id}",
                json={
                    "expected_version": expected,
                    "workout_type": "rest",
                },
            )
            assert response.status_code == 404
            assert response.json()["detail"]["code"] == "PLAN_WORKOUT_NOT_FOUND"

        assert _list_plan_rows("another-user")[0]["workout_description"] == "Private"

    def test_completed_workout_is_listed_but_immutable(self, api_client):
        client, user_id = api_client
        target = (date.today() - timedelta(days=1)).isoformat()
        _seed_plan(user_id, [(target, "easy", "Completed")])
        row = _list_plan_rows(user_id)[0]

        listed = client.get(f"/api/plan?start={target}&end={target}")
        assert listed.status_code == 200
        workout = listed.json()["workouts"][0]
        assert workout["editable"] is False

        updated = client.put(
            f"/api/plan/workouts/{row['canonical_id']}",
            json={
                "expected_version": workout["workout_version"],
                "workout_type": "rest",
            },
        )
        deleted = client.delete(
            f"/api/plan/workouts/{row['canonical_id']}",
            params={"expected_version": workout["workout_version"]},
        )
        created = client.post("/api/plan/workouts", json={
            "date": target,
            "workout_type": "easy",
        })

        assert updated.status_code == 409
        assert deleted.status_code == 409
        assert created.status_code == 409
        assert _list_plan_rows(user_id)[0]["workout_description"] == "Completed"


# ---------------------------------------------------------------------------
# Mode validation guard
# ---------------------------------------------------------------------------


def test_upload_rejects_invalid_mode(api_client):
    client, _ = api_client
    res = client.post("/api/plan/upload?mode=bogus", json={
        "csv": "date,workout_type\n2026-12-31,easy\n",
    })
    # FastAPI returns 422 for query validation failures
    assert res.status_code == 422


def test_plan_mutation_hooks_run_after_commit(api_client, monkeypatch):
    client, user_id = api_client
    target = (date.today() + timedelta(days=8)).isoformat()
    observed: list[tuple[str, int, str | None]] = []

    def capture_hook(called_user_id: str, *, trigger: str) -> None:
        from db import session as db_session
        from db.models import PlanRevision, TrainingPlan

        db = db_session.SessionLocal()
        try:
            revisions = db.query(PlanRevision).filter(
                PlanRevision.user_id == called_user_id,
            ).count()
            row = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == called_user_id,
                TrainingPlan.date == date.fromisoformat(target),
            ).first()
            observed.append((
                trigger,
                revisions,
                row.workout_description if row is not None else None,
            ))
        finally:
            db.close()

    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        capture_hook,
    )

    upload = client.post("/api/plan/upload?mode=merge", json={
        "csv": "date,workout_type,workout_description\n"
               f"{target},easy,Uploaded\n",
    })
    upsert = client.put(f"/api/plan/{target}", json={
        "workout_type": "threshold",
        "workout_description": "Updated",
    })
    deleted = client.delete(f"/api/plan/{target}")

    assert upload.status_code == 200, upload.text
    assert upsert.status_code == 200, upsert.text
    assert deleted.status_code == 200, deleted.text
    assert observed == [
        ("plan_upload", 1, "Uploaded"),
        ("plan_upsert", 2, "Updated"),
        ("plan_delete", 3, None),
    ]


def test_plan_mutations_append_before_and_after_revisions(api_client):
    client, user_id = api_client
    target = (date.today() + timedelta(days=8)).isoformat()

    upload = client.post("/api/plan/upload?mode=merge", json={
        "csv": "date,workout_type,workout_description\n"
               f"{target},easy,Initial workout\n",
    })
    assert upload.status_code == 200, upload.text
    uploaded_canonical_id = _list_plan_rows(user_id)[0]["canonical_id"]

    upsert = client.put(f"/api/plan/{target}", json={
        "workout_type": "threshold",
        "workout_description": "Adjusted workout",
    })
    assert upsert.status_code == 200, upsert.text

    delete = client.delete(f"/api/plan/{target}")
    assert delete.status_code == 200, delete.text

    revisions = _list_revisions(user_id)
    assert [row["operation"] for row in revisions] == [
        "upload",
        "upsert",
        "delete",
    ]
    assert all(row["actor_type"] == "user" for row in revisions)
    assert all(row["actor_id"] == user_id for row in revisions)
    assert revisions[0]["origin"] == "api.plan.upload"
    assert revisions[0]["before"] == []
    assert revisions[0]["after"][0]["canonical_id"] == uploaded_canonical_id
    assert revisions[0]["after"][0]["workout_description"] == "Initial workout"
    assert revisions[1]["before"][0]["canonical_id"] == uploaded_canonical_id
    assert revisions[1]["after"][0]["canonical_id"] == uploaded_canonical_id
    assert revisions[1]["before"][0]["workout_type"] == "easy"
    assert revisions[1]["after"][0]["workout_type"] == "threshold"
    assert revisions[2]["before"][0]["workout_description"] == "Adjusted workout"
    assert revisions[2]["before"][0]["canonical_id"] == uploaded_canonical_id
    assert revisions[2]["after"] == []


def test_revision_failure_rolls_back_plan_change(api_client, monkeypatch):
    client, user_id = api_client
    target = (date.today() + timedelta(days=9)).isoformat()
    _seed_plan(user_id, [(target, "easy", "Keep this row")])
    canonical_id = _list_plan_rows(user_id)[0]["canonical_id"]

    def _fail_revision(*args, **kwargs):
        raise RuntimeError("revision write failed")

    monkeypatch.setattr("api.routes.ai.record_plan_revision", _fail_revision)
    with pytest.raises(RuntimeError, match="revision write failed"):
        client.put(f"/api/plan/{target}", json={
            "workout_type": "threshold",
            "workout_description": "Must roll back",
        })

    assert _list_plan_rows(user_id) == [{
        "canonical_id": canonical_id,
        "date": target,
        "workout_type": "easy",
        "workout_description": "Keep this row",
        "source": "ai",
        "workout_origin": "legacy",
    }]
    assert _list_revisions(user_id) == []
