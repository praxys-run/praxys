"""Durable external cleanup obligations for deleted accounts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from api.account_deletion_cleanup import (
    AccountDeletionCleanupError,
    CLEANUP_KINDS,
    _mark_completed,
    pending_cleanup_exists,
    record_cleanup_obligations,
    replay_cleanup_obligations,
    require_cleanup_owners_absent,
    run_startup_cleanup,
)
from db.models import AccountDeletionCleanupObligation, Base, User


def _sessions(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cleanup.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def test_cleanup_obligations_are_payload_free_and_replay_after_restart(
    tmp_path,
):
    engine, SessionLocal = _sessions(tmp_path)
    requested_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    try:
        with SessionLocal() as db:
            record_cleanup_obligations(
                db,
                ["deleted-owner"],
                now=requested_at,
            )
            db.commit()
        calls: list[tuple[str, str]] = []
        handlers = {
            kind: (lambda user_id, kind=kind: calls.append((kind, user_id)))
            for kind in CLEANUP_KINDS
        }
        with SessionLocal() as restarted_db:
            assert replay_cleanup_obligations(
                restarted_db,
                handlers=handlers,
            ) == 2
            rows = restarted_db.query(
                AccountDeletionCleanupObligation
            ).all()
            assert {row.status for row in rows} == {"completed"}
            assert all(row.completed_at is not None for row in rows)
            assert pending_cleanup_exists(restarted_db) is False
        assert set(calls) == {
            ("garmin_tokens", "deleted-owner"),
            ("legacy_plan_status", "deleted-owner"),
        }
        assert set(AccountDeletionCleanupObligation.__table__.columns.keys()) == {
            "id",
            "user_id",
            "cleanup_kind",
            "status",
            "requested_at",
            "completed_at",
        }
    finally:
        engine.dispose()


def test_failed_cleanup_remains_pending_until_later_replay(tmp_path):
    engine, SessionLocal = _sessions(tmp_path)
    try:
        with SessionLocal() as db:
            record_cleanup_obligations(db, ["deleted-owner"])
            db.commit()
            with pytest.raises(AccountDeletionCleanupError, match="remain pending"):
                replay_cleanup_obligations(
                    db,
                    handlers={
                        kind: lambda _user_id: (_ for _ in ()).throw(
                            OSError("storage unavailable")
                        )
                        for kind in CLEANUP_KINDS
                    },
                    raise_on_failure=True,
                )
            assert pending_cleanup_exists(db) is True
        with SessionLocal() as restarted_db:
            assert replay_cleanup_obligations(
                restarted_db,
                handlers={kind: lambda _user_id: None for kind in CLEANUP_KINDS},
            ) == 2
            assert pending_cleanup_exists(restarted_db) is False
    finally:
        engine.dispose()


def test_two_cleanup_completers_preserve_first_completion(tmp_path):
    engine, SessionLocal = _sessions(tmp_path)
    try:
        requested_at = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(seconds=10)
        )
        with SessionLocal() as db:
            record_cleanup_obligations(
                db, ["deleted-owner"], now=requested_at
            )
            db.commit()
            obligation_id = db.query(
                AccountDeletionCleanupObligation.id
            ).filter(
                AccountDeletionCleanupObligation.user_id == "deleted-owner",
                AccountDeletionCleanupObligation.cleanup_kind == "garmin_tokens",
            ).scalar()
        barrier = Barrier(2)
        completion_times = [
            requested_at + timedelta(seconds=1),
            requested_at + timedelta(seconds=2),
        ]

        def complete(index: int) -> datetime:
            with SessionLocal() as db:
                row = db.get(
                    AccountDeletionCleanupObligation,
                    obligation_id,
                )
                assert row is not None and row.status == "pending"
                barrier.wait(timeout=10)
                _mark_completed(
                    db, row, completed_at=completion_times[index]
                )
                current = db.get(
                    AccountDeletionCleanupObligation,
                    obligation_id,
                )
                assert current is not None
                db.refresh(current)
                return current.completed_at

        with ThreadPoolExecutor(max_workers=2) as executor:
            observed = list(executor.map(complete, range(2)))
        assert observed[0] == observed[1]
        assert observed[0] in completion_times
    finally:
        engine.dispose()


def test_cleanup_obligations_are_immutable_and_reject_unsafe_locators(
    tmp_path,
):
    engine, SessionLocal = _sessions(tmp_path)
    try:
        with SessionLocal() as db:
            with pytest.raises(AccountDeletionCleanupError, match="invalid"):
                record_cleanup_obligations(db, ["../other-user"])
            record_cleanup_obligations(db, ["deleted-owner"])
            db.commit()
            row = db.get(
                AccountDeletionCleanupObligation,
                db.query(AccountDeletionCleanupObligation.id).filter(
                    AccountDeletionCleanupObligation.user_id == "deleted-owner",
                    AccountDeletionCleanupObligation.cleanup_kind == "garmin_tokens",
                ).scalar(),
            )
            assert row is not None
            row.requested_at = row.requested_at + timedelta(seconds=1)
            with pytest.raises(IntegrityError, match="obligation immutable"):
                db.commit()
            db.rollback()
            row = db.get(
                AccountDeletionCleanupObligation,
                db.query(AccountDeletionCleanupObligation.id).filter(
                    AccountDeletionCleanupObligation.user_id == "deleted-owner",
                    AccountDeletionCleanupObligation.cleanup_kind == "garmin_tokens",
                ).scalar(),
            )
            db.delete(row)
            with pytest.raises(IntegrityError, match="cannot be deleted"):
                db.commit()
    finally:
        engine.dispose()


def test_reused_user_locator_creates_fresh_cleanup_authority(tmp_path):
    engine, SessionLocal = _sessions(tmp_path)
    try:
        with SessionLocal() as db:
            record_cleanup_obligations(db, ["reused-owner"])
            db.commit()
            replay_cleanup_obligations(
                db,
                handlers={kind: lambda _user_id: None for kind in CLEANUP_KINDS},
            )
            assert pending_cleanup_exists(db) is False

            # A later account lifecycle with the same external locator must not
            # inherit the completed state of the earlier deletion.
            record_cleanup_obligations(db, ["reused-owner"])
            db.commit()
            rows = db.query(AccountDeletionCleanupObligation).filter(
                AccountDeletionCleanupObligation.user_id == "reused-owner"
            ).all()
            assert len(rows) == 4
            assert sum(row.status == "pending" for row in rows) == 2
            assert sum(row.status == "completed" for row in rows) == 2
    finally:
        engine.dispose()


def test_pending_cleanup_refuses_a_live_reused_owner(tmp_path):
    engine, SessionLocal = _sessions(tmp_path)
    try:
        with SessionLocal() as db:
            record_cleanup_obligations(db, ["reused-owner"])
            db.add(User(
                id="reused-owner",
                email="new-owner@example.test",
                hashed_password="x",
            ))
            db.commit()
            with pytest.raises(AccountDeletionCleanupError, match="owner_present"):
                require_cleanup_owners_absent(db)
            touched: list[str] = []
            replay_cleanup_obligations(
                db,
                handlers={
                    kind: lambda _user_id, kind=kind: touched.append(kind)
                    for kind in CLEANUP_KINDS
                },
            )
            assert touched == []
            assert pending_cleanup_exists(db) is True
    finally:
        engine.dispose()


def test_startup_cleanup_fails_closed_then_replays_on_next_start(
    tmp_path,
    monkeypatch,
):
    engine, SessionLocal = _sessions(tmp_path)
    try:
        with SessionLocal() as db:
            record_cleanup_obligations(db, ["deleted-owner"])
            db.commit()
        monkeypatch.setattr("db.session.SessionLocal", SessionLocal)
        monkeypatch.setattr(
            "api.routes.sync.migrate_legacy_garmin_tokenstores",
            lambda: {"migrated": 0, "removed": 0},
        )
        fail = {"value": True}

        def handlers():
            def cleanup(_user_id: str) -> None:
                if fail["value"]:
                    raise OSError("external storage unavailable")

            return {kind: cleanup for kind in CLEANUP_KINDS}

        monkeypatch.setattr(
            "api.account_deletion_cleanup._cleanup_handlers",
            handlers,
        )
        with pytest.raises(AccountDeletionCleanupError, match="remain pending"):
            run_startup_cleanup()
        with SessionLocal() as db:
            assert pending_cleanup_exists(db) is True

        fail["value"] = False
        run_startup_cleanup()
        with SessionLocal() as db:
            assert pending_cleanup_exists(db) is False
    finally:
        engine.dispose()
