"""Legacy Stryd push-status import and per-user isolation."""
import glob
import json
import os
from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def ledger_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    db = db_session.SessionLocal()
    from db.models import User

    for user_id in (
        "alice",
        "corrupt-user",
        "invalid-user",
        "rolling-user",
        "repeat-user",
        "verified-rolling-user",
        "fenced-remove-user",
    ):
        db.add(User(
            id=user_id,
            email=f"{user_id}@example.test",
            hashed_password="test",
        ))
    db.commit()
    status_dir = tmp_path / "ai" / "stryd_push_status"
    status_dir.mkdir(parents=True)
    try:
        yield db, status_dir
    finally:
        db.close()
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


def _write_status(status_dir, user_id: str, payload) -> str:
    from db.plan_ledger import legacy_stryd_status_path

    path = legacy_stryd_status_path(str(status_dir), user_id)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def test_path_is_unique_per_user(ledger_db):
    _, status_dir = ledger_db
    from db.plan_ledger import legacy_stryd_status_path

    a = legacy_stryd_status_path(str(status_dir), "user-a")
    b = legacy_stryd_status_path(str(status_dir), "user-b")
    assert a != b
    assert a.endswith("user-a.json")
    assert b.endswith("user-b.json")


def test_modern_delivery_rekeys_active_legacy_slot_before_replacement(
    ledger_db,
):
    db, _ = ledger_db
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
    )
    from db.models import TrainingPlan

    legacy, _ = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot={
            "date": "2026-05-01",
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Version A",
        },
    )
    legacy, attempt, disposition = begin_delivery_attempt(
        db,
        legacy,
        operation="deliver",
    )
    assert disposition == "started"
    assert attempt is not None
    complete_delivery_attempt(
        db,
        user_id="rolling-user",
        delivery_id=legacy.id,
        attempt_id=attempt.id,
        attempt_state="synced",
        external_id="legacy-version-a",
    )
    db.commit()

    canonical_id = "11111111-1111-1111-1111-111111111111"
    db.add(TrainingPlan(
        user_id="rolling-user",
        canonical_id=canonical_id,
        date=date(2026, 5, 1),
        source="ai",
        workout_type="easy",
        workout_description="Version B",
    ))
    db.flush()

    replacement, created = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot={
            "canonical_id": canonical_id,
            "date": "2026-05-01",
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Version B",
        },
    )
    assert created is True
    db.refresh(legacy)
    assert legacy.canonical_key == replacement.canonical_key

    _, retry_attempt, retry_disposition = begin_delivery_attempt(
        db,
        replacement,
        operation="deliver",
    )
    assert retry_attempt is None
    assert retry_disposition == "replacement_required"


def test_new_worker_adopts_old_worker_delivery_identity(ledger_db):
    db, _ = ledger_db
    from db.models import PlanDelivery
    from db.plan_ledger import (
        canonical_workout_key,
        get_or_create_delivery,
        workout_version,
    )

    canonical_id = "11111111-1111-1111-1111-111111111111"
    legacy_snapshot = {
        "canonical_id": canonical_id,
        "date": "2026-05-02",
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Compatibility",
    }
    version = workout_version(legacy_snapshot)
    old_delivery = PlanDelivery(
        user_id="rolling-user",
        canonical_key=canonical_workout_key(legacy_snapshot),
        canonical_id=None,
        workout_date=date(2026, 5, 2),
        workout_version=version,
        plan_version=version,
        target="stryd",
        state="pending",
    )
    db.add(old_delivery)
    db.commit()

    delivery, created = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot={
            **legacy_snapshot,
            "source": "praxys",
            "workout_origin": "generated",
        },
    )

    assert created is False
    assert delivery.id == old_delivery.id
    assert delivery.canonical_id == canonical_id
    assert delivery.canonical_key == f"ai:{canonical_id}"


def test_legacy_delivery_rekeys_to_unique_same_slot_content_match(ledger_db):
    db, _ = ledger_db
    from db.models import TrainingPlan
    from db.plan_ledger import get_or_create_delivery

    legacy_snapshot = {
        "date": "2026-05-01",
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Version A",
    }
    legacy, _ = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot=legacy_snapshot,
    )
    first_id = "11111111-1111-1111-1111-111111111111"
    second_id = "22222222-2222-2222-2222-222222222222"
    db.add_all([
        TrainingPlan(
            user_id="rolling-user",
            canonical_id=first_id,
            date=date(2026, 5, 1),
            source="ai",
            workout_type="easy",
            workout_description="Version A",
        ),
        TrainingPlan(
            user_id="rolling-user",
            canonical_id=second_id,
            date=date(2026, 5, 1),
            source="ai",
            workout_type="easy",
            workout_description="Version B",
        ),
    ])
    db.flush()

    second, created = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot={
            **legacy_snapshot,
            "canonical_id": second_id,
            "workout_description": "Version B",
        },
    )
    assert created is True
    db.refresh(legacy)
    assert legacy.canonical_key == f"ai:{first_id}"
    assert legacy.canonical_id == first_id
    assert second.canonical_key == f"ai:{second_id}"
    assert second.canonical_id == second_id

    first, created = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot={**legacy_snapshot, "canonical_id": first_id},
    )
    assert created is False
    assert first.id == legacy.id


def test_legacy_delivery_rekey_fails_closed_for_ambiguous_same_slot(ledger_db):
    db, _ = ledger_db
    from db.models import TrainingPlan
    from db.plan_ledger import get_or_create_delivery

    legacy, _ = get_or_create_delivery(
        db,
        user_id="rolling-user",
        target="stryd",
        snapshot={
            "date": "2026-05-01",
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Legacy only",
        },
    )
    legacy_key = legacy.canonical_key
    db.add_all([
        TrainingPlan(
            user_id="rolling-user",
            canonical_id="11111111-1111-1111-1111-111111111111",
            date=date(2026, 5, 1),
            source="ai",
            workout_type="easy",
            workout_description="Morning",
        ),
        TrainingPlan(
            user_id="rolling-user",
            canonical_id="22222222-2222-2222-2222-222222222222",
            date=date(2026, 5, 1),
            source="ai",
            workout_type="easy",
            workout_description="Evening",
        ),
    ])
    db.flush()

    with pytest.raises(
        ValueError,
        match="ambiguous legacy delivery identity requires reconciliation",
    ):
        get_or_create_delivery(
            db,
            user_id="rolling-user",
            target="stryd",
            snapshot={
                "canonical_id": "11111111-1111-1111-1111-111111111111",
                "date": "2026-05-01",
                "source": "ai",
                "workout_type": "easy",
                "workout_description": "Morning",
            },
        )
    db.refresh(legacy)
    assert legacy.canonical_key == legacy_key


def test_import_is_idempotent_and_preserves_status_shape(ledger_db):
    db, status_dir = ledger_db
    from db.models import PlanDelivery, PlanDeliveryAttempt, PlanRevision
    from db.plan_ledger import (
        delivery_status_for_snapshots,
        import_legacy_stryd_status,
    )

    path = _write_status(
        status_dir,
        "alice",
        {
            "2026-05-01": {
                "workout_id": "alice-w1",
                "pushed_at": "2026-04-30T12:00:00+00:00",
                "status": "pushed",
            }
        },
    )
    assert import_legacy_stryd_status(
        db,
        user_id="alice",
        status_dir=str(status_dir),
    ) == "imported"
    assert os.path.exists(path)
    assert glob.glob(f"{path}.imported-*") == []

    status = delivery_status_for_snapshots(
        db,
        user_id="alice",
        target="stryd",
        current_snapshots={},
    )
    assert status["2026-05-01"]["workout_id"] == "alice-w1"
    assert status["2026-05-01"]["status"] == "pushed"
    assert db.query(PlanDelivery).filter_by(user_id="alice").count() == 1
    assert db.query(PlanDeliveryAttempt).count() == 1
    assert db.query(PlanRevision).filter_by(
        user_id="alice",
        operation="legacy_import",
    ).count() == 1
    assert os.path.exists(path)

    _write_status(
        status_dir,
        "alice",
        {
            "2026-05-01": {
                "workout_id": "alice-w1",
                "pushed_at": "2026-04-30T12:00:00+00:00",
                "status": "pushed",
            }
        },
    )
    assert import_legacy_stryd_status(
        db,
        user_id="alice",
        status_dir=str(status_dir),
    ) == "already_imported"
    assert db.query(PlanDelivery).filter_by(user_id="alice").count() == 1
    assert db.query(PlanDeliveryAttempt).count() == 1
    assert db.query(PlanRevision).filter_by(
        user_id="alice",
        operation="legacy_import",
    ).count() == 1


def test_one_users_import_is_invisible_to_another(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        delivery_status_for_snapshots,
        import_legacy_stryd_status,
    )

    _write_status(
        status_dir,
        "alice",
        {"2026-05-01": {"workout_id": "alice-w1"}},
    )
    import_legacy_stryd_status(db, user_id="alice", status_dir=str(status_dir))

    assert delivery_status_for_snapshots(
        db,
        user_id="alice",
        target="stryd",
        current_snapshots={},
    )["2026-05-01"]["workout_id"] == "alice-w1"
    assert delivery_status_for_snapshots(
        db,
        user_id="bob",
        target="stryd",
        current_snapshots={},
    ) == {}


def test_missing_user_returns_empty_status(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        delivery_status_for_snapshots,
        import_legacy_stryd_status,
    )

    assert import_legacy_stryd_status(
        db,
        user_id="never-pushed",
        status_dir=str(status_dir),
    ) == "missing"
    assert delivery_status_for_snapshots(
        db,
        user_id="never-pushed",
        target="stryd",
        current_snapshots={},
    ) == {}


def test_deleted_user_legacy_file_cannot_recreate_ledger_state(ledger_db):
    db, status_dir = ledger_db
    from db.models import PlanDelivery, PlanRevision
    from db.plan_ledger import (
        import_legacy_stryd_status,
        write_legacy_stryd_status,
    )

    path = _write_status(
        status_dir,
        "deleted-user",
        {"2026-05-01": {"workout_id": "deleted-id"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id="deleted-user",
        status_dir=str(status_dir),
    ) == "missing_user"
    assert db.query(PlanDelivery).filter_by(user_id="deleted-user").count() == 0
    assert db.query(PlanRevision).filter_by(user_id="deleted-user").count() == 0

    with pytest.raises(LookupError):
        write_legacy_stryd_status(
            db,
            status_dir=str(status_dir),
            user_id="deleted-user",
            workout_date="2026-05-02",
            external_id="new-id",
            pushed_at="2026-05-01T12:00:00+00:00",
        )
    with open(path, encoding="utf-8") as handle:
        assert json.load(handle) == {
            "2026-05-01": {"workout_id": "deleted-id"}
        }


def test_corrupt_file_is_quarantined_without_inventing_success(ledger_db):
    db, status_dir = ledger_db
    from db.models import PlanDelivery
    from db.plan_ledger import (
        has_unresolved_legacy_stryd_corruption,
        import_legacy_stryd_status,
        legacy_stryd_status_path,
    )

    path = legacy_stryd_status_path(str(status_dir), "corrupt-user")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{this is not json")

    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    assert not os.path.exists(path)
    assert len(glob.glob(f"{path}.corrupt-*")) == 1
    assert db.query(PlanDelivery).filter_by(user_id="corrupt-user").count() == 0
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )

    _write_status(status_dir, "corrupt-user", {})
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
        authoritative_recovery=True,
    ) == "imported"
    assert not has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )


def test_dual_write_cannot_resolve_corrupt_legacy_state(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        has_unresolved_legacy_stryd_corruption,
        import_legacy_stryd_status,
        legacy_stryd_status_path,
        write_legacy_stryd_status,
    )

    path = _write_status(
        status_dir,
        "corrupt-user",
        {"2026-05-01": {"workout_id": "legacy-owned-id"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "imported"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{truncated")
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"

    delivery, _ = get_or_create_delivery(
        db,
        user_id="corrupt-user",
        target="stryd",
        snapshot={
            "date": "2026-05-02",
            "source": "ai",
            "workout_type": "easy",
        },
    )
    delivery, attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )
    assert disposition == "started"
    assert attempt is not None
    complete_delivery_attempt(
        db,
        user_id="corrupt-user",
        delivery_id=delivery.id,
        attempt_id=attempt.id,
        attempt_state="synced",
        external_id="new-owned-id",
    )
    db.commit()

    write_legacy_stryd_status(
        db,
        status_dir=str(status_dir),
        user_id="corrupt-user",
        workout_date="2026-05-02",
        external_id="new-owned-id",
        pushed_at="2026-05-01T12:00:00+00:00",
    )

    assert not os.path.exists(
        legacy_stryd_status_path(str(status_dir), "corrupt-user")
    )
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )
    legacy = db.query(type(delivery)).filter_by(
        user_id="corrupt-user",
        external_id="legacy-owned-id",
    ).one()
    assert legacy.state == "synced"

    _write_status(
        status_dir,
        "corrupt-user",
        {"2026-05-02": {"workout_id": "new-owned-id"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    db.refresh(legacy)
    assert legacy.state == "synced"
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )


def test_preexisting_corrupt_archive_is_backfilled_before_cleanup(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        has_unresolved_legacy_stryd_corruption,
        import_legacy_stryd_status,
        legacy_stryd_status_path,
    )

    path = legacy_stryd_status_path(str(status_dir), "corrupt-user")
    archive_path = f"{path}.corrupt-20260731T120000Z"
    with open(archive_path, "w", encoding="utf-8") as handle:
        handle.write("{quarantined by an older worker")

    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )

    _write_status(status_dir, "corrupt-user", {})
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
        authoritative_recovery=True,
    ) == "imported"
    os.remove(path)
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "missing"
    assert not has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )


def test_unmarked_valid_import_cannot_resolve_corrupt_archive(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        has_unresolved_legacy_stryd_corruption,
        import_legacy_stryd_status,
        legacy_stryd_status_path,
    )

    path = _write_status(
        status_dir,
        "corrupt-user",
        {"2026-05-02": {"workout_id": "partial-old-worker-id"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "imported"
    with open(
        f"{path}.corrupt-20260731T120000Z",
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write("{older quarantined state")

    assert import_legacy_stryd_status(
        db,
        user_id="corrupt-user",
        status_dir=str(status_dir),
    ) == "corrupt"
    assert has_unresolved_legacy_stryd_corruption(
        db,
        user_id="corrupt-user",
    )
    assert os.path.exists(
        legacy_stryd_status_path(str(status_dir), "corrupt-user")
    )


def test_invalid_entries_are_skipped_without_success_rows(ledger_db):
    db, status_dir = ledger_db
    from db.models import PlanDelivery, PlanRevision
    from db.plan_ledger import import_legacy_stryd_status

    _write_status(
        status_dir,
        "invalid-user",
        {
            "not-a-date": {"workout_id": "x"},
            "2026-05-01": {"status": "failed"},
            "2026-05-02": "not-an-object",
            "2026-05-03": {"workout_id": "unsafe?id"},
        },
    )
    assert import_legacy_stryd_status(
        db,
        user_id="invalid-user",
        status_dir=str(status_dir),
    ) == "imported"
    assert db.query(PlanDelivery).filter_by(user_id="invalid-user").count() == 0
    revision = db.query(PlanRevision).filter_by(user_id="invalid-user").one()
    assert revision.details == {"imported": 0, "skipped": 4, "entries": {}}


def test_changed_legacy_snapshot_reconciles_replacements_and_removals(ledger_db):
    db, status_dir = ledger_db
    from db.models import PlanDelivery, PlanDeliveryAttempt
    from db.plan_ledger import (
        delivery_status_for_snapshots,
        import_legacy_stryd_status,
    )

    _write_status(
        status_dir,
        "rolling-user",
        {
            "2026-05-01": {"workout_id": "old-a"},
            "2026-05-02": {"workout_id": "old-b"},
        },
    )
    assert import_legacy_stryd_status(
        db,
        user_id="rolling-user",
        status_dir=str(status_dir),
    ) == "imported"

    _write_status(
        status_dir,
        "rolling-user",
        {"2026-05-01": {"workout_id": "new-a"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id="rolling-user",
        status_dir=str(status_dir),
    ) == "imported"

    status = delivery_status_for_snapshots(
        db,
        user_id="rolling-user",
        target="stryd",
        current_snapshots={},
    )
    assert status == {
        "2026-05-01": {
            "workout_id": "new-a",
            "status": "pushed",
            "pushed_at": status["2026-05-01"]["pushed_at"],
        }
    }
    rows = db.query(PlanDelivery).filter_by(user_id="rolling-user").order_by(
        PlanDelivery.workout_date,
    ).all()
    assert [(row.external_id, row.state) for row in rows] == [
        ("new-a", "synced"),
        ("old-b", "removed"),
    ]
    attempts = db.query(PlanDeliveryAttempt).order_by(
        PlanDeliveryAttempt.delivery_id,
        PlanDeliveryAttempt.attempt_number,
    ).all()
    assert sum(attempt.state == "removed" for attempt in attempts) == 2
    assert sum(attempt.state == "synced" for attempt in attempts) == 3


def test_legacy_snapshot_cursor_handles_historical_digest_repeats(ledger_db):
    db, status_dir = ledger_db
    from db.models import PlanDelivery
    from db.plan_ledger import import_legacy_stryd_status

    snapshot_a = {"2026-05-01": {"workout_id": "a"}}
    snapshot_ab = {
        **snapshot_a,
        "2026-05-02": {"workout_id": "b"},
    }
    for payload in (snapshot_a, snapshot_ab, snapshot_a):
        _write_status(status_dir, "repeat-user", payload)
        assert import_legacy_stryd_status(
            db,
            user_id="repeat-user",
            status_dir=str(status_dir),
        ) == "imported"

    rows = db.query(PlanDelivery).filter_by(user_id="repeat-user").order_by(
        PlanDelivery.workout_date,
    ).all()
    assert [(row.external_id, row.state) for row in rows] == [
        ("a", "synced"),
        ("b", "removed"),
    ]


def test_old_worker_delete_marks_verified_delivery_removed(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        import_legacy_stryd_status,
        write_legacy_stryd_status,
    )

    delivery, _ = get_or_create_delivery(
        db,
        user_id="verified-rolling-user",
        target="stryd",
        snapshot={
            "date": "2026-05-03",
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Verified version",
        },
    )
    delivery, attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )
    assert disposition == "started"
    assert attempt is not None
    complete_delivery_attempt(
        db,
        user_id="verified-rolling-user",
        delivery_id=delivery.id,
        attempt_id=attempt.id,
        attempt_state="synced",
        external_id="verified-id",
    )
    db.commit()
    write_legacy_stryd_status(
        db,
        status_dir=str(status_dir),
        user_id="verified-rolling-user",
        workout_date="2026-05-03",
        external_id="verified-id",
        pushed_at="2026-05-02T12:00:00+00:00",
    )
    assert import_legacy_stryd_status(
        db,
        user_id="verified-rolling-user",
        status_dir=str(status_dir),
    ) == "already_imported"

    _write_status(status_dir, "verified-rolling-user", {})
    assert import_legacy_stryd_status(
        db,
        user_id="verified-rolling-user",
        status_dir=str(status_dir),
    ) == "imported"
    db.refresh(delivery)
    assert delivery.state == "removed"

    _write_status(
        status_dir,
        "verified-rolling-user",
        {"2026-05-03": {"workout_id": "verified-id"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id="verified-rolling-user",
        status_dir=str(status_dir),
    ) == "imported"
    db.refresh(delivery)
    assert delivery.state == "removed"
    rows = db.query(type(delivery)).filter_by(
        user_id="verified-rolling-user",
    ).all()
    assert sorted(
        (row.workout_version.startswith("legacy-unknown:"), row.state)
        for row in rows
    ) == [(False, "removed")]


def test_superseded_removal_cannot_overwrite_successful_retry(ledger_db):
    db, _ = ledger_db
    from db.plan_ledger import (
        DELIVERY_ATTEMPT_LEASE,
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
    )

    delivery, _ = get_or_create_delivery(
        db,
        user_id="fenced-remove-user",
        target="stryd",
        snapshot={
            "date": "2026-05-04",
            "source": "ai",
            "workout_type": "easy",
        },
    )
    delivery, deliver_attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )
    assert disposition == "started"
    assert deliver_attempt is not None
    assert complete_delivery_attempt(
        db,
        user_id="fenced-remove-user",
        delivery_id=delivery.id,
        attempt_id=deliver_attempt.id,
        attempt_state="synced",
        external_id="fenced-id",
    )
    db.commit()

    delivery, first_remove, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="remove",
    )
    assert disposition == "started"
    assert first_remove is not None
    first_remove.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()

    delivery, retry_remove, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="remove",
    )
    assert disposition == "started"
    assert retry_remove is not None
    db.commit()
    assert complete_delivery_attempt(
        db,
        user_id="fenced-remove-user",
        delivery_id=delivery.id,
        attempt_id=retry_remove.id,
        attempt_state="removed",
        external_id="fenced-id",
    )
    db.commit()

    assert not complete_delivery_attempt(
        db,
        user_id="fenced-remove-user",
        delivery_id=delivery.id,
        attempt_id=first_remove.id,
        attempt_state="failed",
        delivery_state="synced",
        error="late failure",
    )
    db.commit()
    db.refresh(delivery)
    assert delivery.state == "removed"


def test_late_removal_success_dominates_retry_failure(ledger_db):
    db, _ = ledger_db
    from db.plan_ledger import (
        DELIVERY_ATTEMPT_LEASE,
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
    )

    user_id = "fenced-remove-user"
    delivery, _ = get_or_create_delivery(
        db,
        user_id=user_id,
        target="stryd",
        snapshot={
            "date": "2026-05-05",
            "source": "ai",
            "workout_type": "easy",
        },
    )
    delivery, deliver_attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )
    assert disposition == "started"
    assert deliver_attempt is not None
    assert complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=deliver_attempt.id,
        attempt_state="synced",
        external_id="late-success-id",
    )
    db.commit()

    delivery, first_remove, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="remove",
    )
    assert disposition == "started"
    assert first_remove is not None
    first_remove.started_at = (
        datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
    )
    db.commit()

    delivery, retry_remove, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="remove",
    )
    assert disposition == "started"
    assert retry_remove is not None
    db.commit()

    assert not complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=first_remove.id,
        attempt_state="removed",
        external_id="late-success-id",
    )
    db.commit()
    assert not complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=retry_remove.id,
        attempt_state="failed",
        delivery_state="synced",
        error="retry failed after prior success",
    )
    db.commit()

    db.refresh(delivery)
    assert delivery.state == "removed"


def test_stale_legacy_success_does_not_resurrect_removed_delivery(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        legacy_stryd_status_path,
        write_legacy_stryd_status,
    )

    user_id = "rolling-user"
    delivery, _ = get_or_create_delivery(
        db,
        user_id=user_id,
        target="stryd",
        snapshot={
            "date": "2026-05-06",
            "source": "ai",
            "workout_type": "easy",
        },
    )
    delivery, deliver_attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )
    assert disposition == "started"
    assert deliver_attempt is not None
    assert complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=deliver_attempt.id,
        attempt_state="synced",
        external_id="removed-before-legacy-id",
    )
    db.commit()

    delivery, remove_attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="remove",
    )
    assert disposition == "started"
    assert remove_attempt is not None
    assert complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=remove_attempt.id,
        attempt_state="removed",
        external_id="removed-before-legacy-id",
    )
    db.commit()

    write_legacy_stryd_status(
        db,
        status_dir=str(status_dir),
        user_id=user_id,
        workout_date="2026-05-06",
        external_id="removed-before-legacy-id",
        pushed_at="2026-05-05T12:00:00+00:00",
    )

    assert not os.path.exists(
        legacy_stryd_status_path(str(status_dir), user_id)
    )
    rows = db.query(type(delivery)).filter_by(user_id=user_id).all()
    assert [(row.workout_version.startswith("legacy-unknown:"), row.state) for row in rows] == [
        (False, "removed")
    ]


def test_raw_stale_legacy_snapshot_does_not_resurrect_removed_delivery(ledger_db):
    db, status_dir = ledger_db
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        import_legacy_stryd_status,
    )

    user_id = "repeat-user"
    delivery, _ = get_or_create_delivery(
        db,
        user_id=user_id,
        target="stryd",
        snapshot={
            "date": "2026-05-07",
            "source": "ai",
            "workout_type": "easy",
        },
    )
    delivery, deliver_attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="deliver",
    )
    assert disposition == "started"
    assert deliver_attempt is not None
    assert complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=deliver_attempt.id,
        attempt_state="synced",
        external_id="raw-stale-id",
    )
    db.commit()
    delivery, remove_attempt, disposition = begin_delivery_attempt(
        db,
        delivery,
        operation="remove",
    )
    assert disposition == "started"
    assert remove_attempt is not None
    assert complete_delivery_attempt(
        db,
        user_id=user_id,
        delivery_id=delivery.id,
        attempt_id=remove_attempt.id,
        attempt_state="removed",
        external_id="raw-stale-id",
    )
    db.commit()

    _write_status(
        status_dir,
        user_id,
        {"2026-05-07": {"workout_id": "raw-stale-id", "status": "pushed"}},
    )
    assert import_legacy_stryd_status(
        db,
        user_id=user_id,
        status_dir=str(status_dir),
    ) == "imported"

    rows = db.query(type(delivery)).filter_by(user_id=user_id).all()
    assert [(row.workout_version.startswith("legacy-unknown:"), row.state) for row in rows] == [
        (False, "removed")
    ]
