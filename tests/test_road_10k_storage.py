"""Road 10K private marker and screenshot-fence tests."""
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DatabaseError

from api import road_10k_deletion_storage as storage
from api import feedback_storage
from api.account_deletion import delete_user_account
from api.road_10k_screenshot_storage import (
    Road10KScreenshotUnavailable,
    delete_object,
    delete_manifest_object,
)


class _MemoryManifestStore:
    def __init__(self):
        self.items: dict[str, bytes] = {}

    def put(self, key: str, payload: bytes) -> None:
        self.items[key] = payload

    def iter(self, prefix: str):
        for key, payload in list(self.items.items()):
            if key.startswith(prefix):
                yield key, payload

    def delete(self, key: str) -> None:
        self.items.pop(key, None)


def test_road_10k_account_deletion_logs_are_not_owner_dimensional():
    source = inspect.getsource(delete_user_account)
    assert "Road 10K deletion manifest failed for user" not in source
    assert "marker completion failed for user" not in source


def test_marker_is_payload_free_and_replayed_before_traffic(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    requested_at = datetime.now(timezone.utc)
    marker = storage.stage_manifest(
        owner_id="native-owner",
        stage_id="road-10k-controlled-opt-in-v1",
        reason="account_deletion",
        evaluation_ids=["evaluation-1"],
        screenshot_keys=[],
        requested_at=requested_at,
    )
    marker = storage.mark_committed(marker, requested_at)
    assert not storage.marker_contains_payload(marker)
    deleted = []
    replayed = storage.replay_manifests(
        delete_object=deleted.append,
        delete_evaluation=lambda evaluation_id, _manifest: deleted.append(evaluation_id),
        now=requested_at + timedelta(hours=1),
    )
    assert replayed == 1
    assert deleted == ["evaluation-1"]


def test_old_completed_marker_is_expired_after_restore_window(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    old = datetime.now(timezone.utc) - timedelta(
        days=storage.MARKER_RETENTION_DAYS + 1
    )
    marker = storage.stage_manifest(
        owner_id="native-owner",
        stage_id="road-10k-controlled-opt-in-v1",
        reason="retention",
        evaluation_ids=[],
        screenshot_keys=[],
        requested_at=old,
    )
    storage.mark_completed(marker, old)
    assert list(storage.iter_active(now=datetime.now(timezone.utc))) == []


def test_unreplayed_marker_survives_restore_window_until_replay(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    old = datetime.now(timezone.utc) - timedelta(
        days=storage.MARKER_RETENTION_DAYS + 1
    )
    marker = storage.stage_manifest(
        owner_id="native-owner",
        stage_id="road-10k-controlled-opt-in-v1",
        reason="account_deletion",
        evaluation_ids=["evaluation-1"],
        screenshot_keys=[],
        requested_at=old,
    )
    storage.mark_committed(marker, old)
    deleted: list[str] = []

    assert storage.replay_manifests(
        delete_object=lambda _key: None,
        delete_evaluation=lambda evaluation_id, _manifest: deleted.append(
            evaluation_id
        ),
        now=datetime.now(timezone.utc),
    ) == 1
    assert deleted == ["evaluation-1"]
    assert list(storage.iter_active(now=datetime.now(timezone.utc))) == []


def test_retention_marker_targets_only_the_expired_record(tmp_path, monkeypatch):
    from api.road_10k_control import _owner_deletion_manifest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from db.models import Base, Road10KEvaluation, Road10KOwnerStageReceipt, User

    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        db.add_all(
            [
                Road10KEvaluation(
                    id="expired",
                    user_id="owner",
                    stage_id="road-10k-controlled-opt-in-v1",
                    result_code="validation_failed",
                    payload={"private": "old"},
                    created_at=now - timedelta(days=31),
                    expires_at=now - timedelta(days=1),
                ),
                Road10KEvaluation(
                    id="fresh",
                    user_id="owner",
                    stage_id="road-10k-controlled-opt-in-v1",
                    result_code="validation_failed",
                    payload={"private": "new"},
                    created_at=now,
                    expires_at=now + timedelta(days=29),
                ),
            ]
        )
        db.commit()
        marker = _owner_deletion_manifest(
            db,
            user_id="owner",
            stage_id="road-10k-controlled-opt-in-v1",
            reason="retention",
            now=datetime.now(timezone.utc).replace(tzinfo=None),
            evaluation_ids=["expired"],
        )
    assert marker is not None
    assert marker["evaluation_ids"] == ["expired"]


def test_screenshot_object_delete_rejects_non_road_key():
    with pytest.raises(ValueError):
        delete_object("feedback/1/0.png")


def test_local_private_feedback_and_road_objects_are_deleted_without_credentials(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    for key in ("feedback/7/0.png", "road-10k/screenshots/11111111-1111-4111-8111-111111111111.png"):
        path = Path(tmp_path) / "feedback_images" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"private")
        delete_manifest_object(key)
        assert not path.exists()


def test_blob_fake_deletes_base_snapshots_and_versions_for_each_object_form(
    monkeypatch,
):
    calls: list[tuple[str, dict[str, object]]] = []

    class Blob:
        def __init__(self, key: str, kwargs: dict[str, object]):
            self.key = key
            self.kwargs = kwargs

        def delete_blob(self, **kwargs):
            if "delete_snapshots" in kwargs:
                assert kwargs["delete_snapshots"] in {"include", "only"}
            calls.append((self.key, {**self.kwargs, **kwargs}))

    class Client:
        def get_blob_client(self, key: str, **kwargs):
            return Blob(key, kwargs)

        def list_blob_versions(self, *, name: str):
            return [
                SimpleNamespace(version_id="version-1", snapshot=None),
                SimpleNamespace(version_id=None, snapshot="snapshot-1"),
            ]

    monkeypatch.setattr("api.feedback_storage._use_blob", lambda: True)
    monkeypatch.setattr("api.feedback_storage._blob_container_client", lambda: Client())
    delete_manifest_object("feedback/7/0.png")
    delete_manifest_object(
        "road-10k/screenshots/11111111-1111-4111-8111-111111111111.webp"
    )

    assert len(calls) == 6
    assert any(
        kwargs.get("delete_snapshots") == "include"
        for _key, kwargs in calls
    )
    assert any(kwargs.get("version_id") == "version-1" for _key, kwargs in calls)
    assert any(kwargs.get("snapshot") == "snapshot-1" for _key, kwargs in calls)


def test_partial_replay_keeps_committed_marker_until_all_targets_are_deleted(
    monkeypatch,
):
    store = _MemoryManifestStore()
    monkeypatch.setattr(storage, "_test_store", store)
    marker = storage.stage_manifest(
        owner_id="owner",
        stage_id="road-10k-controlled-opt-in-v1",
        reason="account_deletion",
        evaluation_ids=[],
        screenshot_keys=[
            "road-10k/screenshots/11111111-1111-4111-8111-111111111111.png",
            "road-10k/screenshots/22222222-2222-4222-8222-222222222222.png",
        ],
        requested_at=datetime.now(timezone.utc),
    )
    marker = storage.mark_committed(marker, datetime.now(timezone.utc))
    attempts = {"count": 0}

    def flaky_delete(_key: str) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return
        raise OSError("object store unavailable")

    with pytest.raises(storage.Road10KDeletionStorageError):
        storage.replay_manifests(
            delete_object=flaky_delete,
            delete_evaluation=lambda _id, _manifest: None,
        )
    assert storage.replay_status() == "blocked"
    assert list(storage.iter_active())
    storage.replay_manifests(
        delete_object=lambda _key: None,
        delete_evaluation=lambda _id, _manifest: None,
    )
    active = list(storage.iter_active())
    assert active and active[0]["status"] == "completed"
    assert storage.replay_status() == "ready"


def test_account_deletion_manifest_captures_orphan_road_evaluations(
    tmp_path,
    monkeypatch,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.road_10k_control import prepare_account_deletion
    from db.models import Base, Road10KEvaluation, User

    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    engine = create_engine(f"sqlite:///{tmp_path / 'orphan.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        db.add(
            Road10KEvaluation(
                id="orphan-evaluation",
                user_id="owner",
                stage_id="road-10k-controlled-opt-in-v1",
                result_code="validation_failed",
                payload={"private": True},
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        db.commit()
        manifests = prepare_account_deletion(db, user_id="owner")

    assert manifests[0]["evaluation_ids"] == ["orphan-evaluation"]


def test_prepared_account_deletion_marker_does_not_replay_before_db_commit(
    tmp_path,
    monkeypatch,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.road_10k_control import replay_road_10k_deletion_manifests
    from db.models import Base, Feedback, User

    manifest_store = _MemoryManifestStore()
    monkeypatch.setattr(storage, "_test_store", manifest_store)
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    engine = create_engine(f"sqlite:///{tmp_path / 'prepared-ignore.db'}")
    Base.metadata.create_all(engine)
    key = "feedback/7/0.png"
    object_path = Path(tmp_path) / "feedback_images" / key
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(b"live-screenshot")

    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        db.add(
            Feedback(
                user_id="owner",
                kind="other",
                message="private",
                image_keys=[key],
            )
        )
        db.commit()
        storage.stage_manifest(
            owner_id="owner",
            stage_id="road-10k-controlled-opt-in-v1",
            reason="account_deletion",
            evaluation_ids=[],
            screenshot_keys=[key],
            requested_at=datetime.now(timezone.utc),
        )

        assert replay_road_10k_deletion_manifests(db) == 0
        assert db.query(Feedback).filter(Feedback.user_id == "owner").count() == 1
        assert object_path.exists()


def test_prepared_account_deletion_marker_replays_after_db_commit_without_commit_ack(
    tmp_path,
    monkeypatch,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.road_10k_control import (
        initialize_road_10k_runtime,
        prepare_account_deletion,
        record_deletion_obligations,
        road_10k_requires_replay_ready,
    )
    from db.models import Base, Feedback, Road10KDeletionObligation, User

    manifest_store = _MemoryManifestStore()
    monkeypatch.setattr(storage, "_test_store", manifest_store)
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    engine = create_engine(f"sqlite:///{tmp_path / "prepared-replay.db"}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        feedback = Feedback(
            user_id="owner",
            kind="other",
            message="private",
        )
        db.add(feedback)
        db.flush()
        key = f"feedback/{feedback.id}/0.png"
        feedback.image_keys = [key]
        db.commit()
        object_path = Path(tmp_path) / "feedback_images" / key
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(b"restored-screenshot")
        manifests = prepare_account_deletion(db, user_id="owner")
        record_deletion_obligations(db, manifests)
        # Simulate a crash after the account transaction commits but before the
        # private marker receives its best-effort committed acknowledgement.
        db.query(Feedback).delete()
        db.query(User).delete()
        db.commit()

        assert road_10k_requires_replay_ready(db) is True
        assert db.query(Road10KDeletionObligation).one().status == "committed"
        assert initialize_road_10k_runtime(db) == 1
        assert not object_path.exists()
        assert db.query(Road10KDeletionObligation).one().status == "completed"
        active = list(storage.iter_active())
        assert active and active[0]["status"] == "completed"


def test_committed_obligation_rejects_tampered_or_missing_marker(
    tmp_path,
    monkeypatch,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.road_10k_control import (
        Road10KDeletionFailed,
        initialize_road_10k_runtime,
        prepare_account_deletion,
        record_deletion_obligations,
    )
    from db.models import Base, Feedback, User

    manifest_store = _MemoryManifestStore()
    monkeypatch.setattr(storage, "_test_store", manifest_store)
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    engine = create_engine(f"sqlite:///{tmp_path / 'tampered-marker.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        feedback = Feedback(
            user_id="owner",
            kind="other",
            message="private",
        )
        db.add(feedback)
        db.flush()
        key = f"feedback/{feedback.id}/0.png"
        feedback.image_keys = [key]
        db.commit()
        object_path = Path(tmp_path) / "feedback_images" / key
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(b"private")
        manifests = prepare_account_deletion(db, user_id="owner")
        record_deletion_obligations(db, manifests)
        db.commit()

        marker_key = next(iter(manifest_store.items))
        tampered = json.loads(manifest_store.items[marker_key])
        tampered["screenshot_keys"] = ["feedback/8/0.png"]
        manifest_store.items[marker_key] = json.dumps(tampered).encode()

        with pytest.raises(Road10KDeletionFailed, match="marker_mismatch"):
            initialize_road_10k_runtime(db)
        assert object_path.exists()

        manifest_store.items.clear()
        with pytest.raises(Road10KDeletionFailed, match="marker_missing"):
            initialize_road_10k_runtime(db)
        assert object_path.exists()


def test_private_manifest_storage_unavailable_fails_closed(
    monkeypatch,
):
    monkeypatch.setattr(feedback_storage, "_use_blob", lambda: True)
    monkeypatch.setattr(
        feedback_storage,
        "_blob_container_client",
        lambda: None,
    )
    with pytest.raises(storage.Road10KDeletionStorageError, match="unavailable"):
        storage.stage_manifest(
            owner_id="owner",
            stage_id="road-10k-controlled-opt-in-v1",
            reason="account_deletion",
            evaluation_ids=[],
            screenshot_keys=[],
            requested_at=datetime.now(timezone.utc),
        )
    with pytest.raises(storage.Road10KDeletionStorageError, match="failed"):
        storage.replay_manifests(
            delete_object=lambda _key: None,
            delete_evaluation=lambda _id, _manifest: None,
        )


def test_account_deletion_stages_feedback_image_keys_before_row_removal(
    tmp_path, monkeypatch
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api.road_10k_control import prepare_account_deletion
    from db.models import Base, Feedback, User

    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    engine = create_engine(f"sqlite:///{tmp_path / 'feedback-delete.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        feedback = Feedback(
            user_id="owner",
            kind="other",
            message="private",
        )
        db.add(feedback)
        db.flush()
        key = f"feedback/{feedback.id}/0.png"
        feedback.image_keys = [key]
        db.commit()

        manifests = prepare_account_deletion(db, user_id="owner")
        assert [manifest["screenshot_keys"] for manifest in manifests] == [[key]]
        assert db.query(Feedback).filter(Feedback.user_id == "owner").one().image_keys == [key]


@pytest.mark.parametrize(
    "object_key",
    [
        "feedback/8/0.png",
        "feedback/7/../../other.png",
        "road-10k/screenshots/11111111-1111-4111-8111-111111111111.png",
    ],
)
def test_account_deletion_rejects_unbound_feedback_locator(
    tmp_path,
    monkeypatch,
    object_key,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from api.road_10k_control import (
        Road10KDeletionFailed,
        prepare_account_deletion,
    )
    from db.models import Base, Feedback, User

    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    engine = create_engine(f"sqlite:///{tmp_path / 'unbound-feedback.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        row = Feedback(
            user_id="owner",
            kind="other",
            message="private",
        )
        db.add(row)
        db.flush()
        assert row.id == 1
        row.image_keys = [object_key]
        db.commit()

        with pytest.raises(
            Road10KDeletionFailed,
            match="invalid_feedback_locator",
        ):
            prepare_account_deletion(db, user_id="owner")
        assert storage._test_store.items == {}


def test_evaluation_retention_is_creation_based_until_explicit_purge(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from api import road_10k_control
    from db.models import Base, Road10KEvaluation, Road10KOwnerStageReceipt, User

    monkeypatch.setattr(storage, "_test_store", _MemoryManifestStore())
    monkeypatch.setattr(
        road_10k_control,
        "_authority",
        lambda lifecycle=True: SimpleNamespace(
            stage_id="road-10k-controlled-opt-in-v1",
            authority_digest="retention-test-authority",
        ),
    )
    monkeypatch.setattr(
        road_10k_control,
        "require_road_10k_participation",
        lambda *args, **kwargs: None,
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expired_created = now - timedelta(days=31)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        receipt_at = now - timedelta(days=32)
        withdrawn_at = now - timedelta(days=1)
        db.add(
            Road10KOwnerStageReceipt(
                id="retention-owner-receipt",
                user_id="owner",
                stage_id="road-10k-controlled-opt-in-v1",
                capability_id="outdoor_road_10k_performance_v1",
                schema_version=2,
                policy_version="road-10k-plan-generation-policy-v2",
                authority_digest="a" * 64,
                notice_digest="b" * 64,
                cohort_rule_digest="c" * 64,
                sampling_run_evidence_digest="d" * 64,
                invitation_idempotency_key="retention-owner-invitation",
                state="withdrawn",
                invitation_issued_at=receipt_at,
                withdrawn_at=withdrawn_at,
                created_at=receipt_at,
                updated_at=withdrawn_at,
            )
        )
        db.add_all(
            [
                Road10KEvaluation(
                    id="expired",
                    user_id="owner",
                    stage_id="road-10k-controlled-opt-in-v1",
                    result_code="validation_failed",
                    payload={"private": "expired"},
                    created_at=expired_created,
                    # A caller/restore must not be able to slide this deadline.
                    expires_at=expired_created + timedelta(days=30),
                ),
                Road10KEvaluation(
                    id="fresh",
                    user_id="owner",
                    stage_id="road-10k-controlled-opt-in-v1",
                    result_code="validation_failed",
                    payload={"private": "fresh"},
                    created_at=now,
                    expires_at=now + timedelta(days=30),
                ),
            ]
        )
        db.commit()

        exported = road_10k_control.export_owner_records(db, user_id="owner")
        assert [item["id"] for item in exported["evaluations"]] == ["fresh"]

        # Reads do not rewrite the original authoritative deadline.
        expired = db.get(Road10KEvaluation, "expired")
        assert expired is not None
        assert expired.expires_at == expired_created + timedelta(days=30)
        assert road_10k_control._evaluation_expiry(expired) == expired.expires_at

        # A direct update or restore-like creation-time rewrite cannot move the
        # retention anchor while leaving the deadline untouched.
        expired.created_at = now
        with pytest.raises(
            DatabaseError,
            match="evaluation retention deadline immutable",
        ):
            db.commit()
        db.rollback()

        assert road_10k_control.purge_expired_evaluations(
            db,
            now=now,
        ) == 1
        assert db.get(Road10KEvaluation, "expired") is None
        assert db.get(Road10KEvaluation, "fresh") is not None


def test_configured_blob_delete_also_removes_legacy_local_bytes(
    tmp_path,
    monkeypatch,
):
    key = "feedback/7/0.png"
    local_path = tmp_path / "feedback_images" / key
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(b"legacy-private")
    deleted: list[str] = []

    class Blob:
        def delete_blob(self, **_kwargs) -> None:
            deleted.append(key)

    class Client:
        def get_blob_client(self, _key: str, **_kwargs):
            return Blob()

        def list_blob_versions(self, *, name: str):
            assert name == key
            return []

    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(feedback_storage, "_use_blob", lambda: True)
    monkeypatch.setattr(
        feedback_storage,
        "_blob_container_client",
        lambda: Client(),
    )

    feedback_storage.delete_private_object(key)

    assert deleted == [key]
    assert not local_path.exists()


def test_unavailable_configured_blob_delete_keeps_legacy_local_bytes(
    tmp_path,
    monkeypatch,
):
    key = "feedback/7/0.png"
    local_path = tmp_path / "feedback_images" / key
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(b"legacy-private")

    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(feedback_storage, "_use_blob", lambda: True)
    monkeypatch.setattr(
        feedback_storage,
        "_blob_container_client",
        lambda: None,
    )

    with pytest.raises(OSError, match="blob storage unavailable"):
        feedback_storage.delete_private_object(key)

    assert local_path.read_bytes() == b"legacy-private"


def test_feedback_manifest_storage_error_is_normalized(
    tmp_path,
    monkeypatch,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from api import road_10k_control
    from db.models import Base, Feedback, User

    engine = create_engine(f"sqlite:///{tmp_path / 'feedback-stage-error.db'}")
    Base.metadata.create_all(engine)

    def fail_stage(**_kwargs):
        raise storage.Road10KDeletionStorageError("store unavailable")

    monkeypatch.setattr(road_10k_control, "stage_manifest", fail_stage)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        feedback = Feedback(
            user_id="owner",
            kind="other",
            message="private",
        )
        db.add(feedback)
        db.flush()
        feedback.image_keys = [f"feedback/{feedback.id}/0.png"]
        db.commit()

        with pytest.raises(
            road_10k_control.Road10KDeletionFailed,
            match="deletion_storage_unavailable",
        ):
            road_10k_control.prepare_account_deletion(db, user_id="owner")
