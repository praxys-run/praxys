"""Road 10K private marker and screenshot-fence tests."""
from datetime import datetime, timedelta, timezone

import pytest

from api import road_10k_deletion_storage as storage
from api.road_10k_screenshot_storage import (
    Road10KScreenshotUnavailable,
    delete_object,
)


def test_marker_is_payload_free_and_replayed_before_traffic(tmp_path, monkeypatch):
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    requested_at = datetime.now(timezone.utc)
    marker = storage.stage_manifest(
        owner_id="native-owner",
        stage_id="road-10k-controlled-opt-in-v1",
        reason="account_deletion",
        evaluation_ids=["evaluation-1"],
        screenshot_keys=[],
        requested_at=requested_at,
    )
    assert not storage.marker_contains_payload(marker)
    deleted = []
    replayed = storage.replay_manifests(
        delete_object=deleted.append,
        delete_evaluation=lambda evaluation_id, _manifest: deleted.append(evaluation_id),
        now=requested_at + timedelta(hours=1),
    )
    assert replayed == 1
    assert deleted == ["evaluation-1"]


def test_old_marker_is_expired_only_after_restore_window(tmp_path, monkeypatch):
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    old = datetime.now(timezone.utc) - timedelta(
        days=storage.MARKER_RETENTION_DAYS + 1
    )
    storage.stage_manifest(
        owner_id="native-owner",
        stage_id="road-10k-controlled-opt-in-v1",
        reason="retention",
        evaluation_ids=[],
        screenshot_keys=[],
        requested_at=old,
    )
    assert list(storage.iter_active(now=datetime.now(timezone.utc))) == []


def test_retention_marker_targets_only_the_expired_record(tmp_path, monkeypatch):
    from api.road_10k_control import _owner_deletion_manifest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from db.models import Base, Road10KEvaluation, User

    monkeypatch.setattr("db.session.get_data_dir", lambda: str(tmp_path))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id="owner", email="owner@example.test", hashed_password="x"))
        db.add_all(
            [
                Road10KEvaluation(
                    id="expired",
                    user_id="owner",
                    stage_id="road-10k-controlled-opt-in-v1",
                    result_code="validation_failed",
                    payload={"private": "old"},
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(days=31),
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(days=1),
                ),
                Road10KEvaluation(
                    id="fresh",
                    user_id="owner",
                    stage_id="road-10k-controlled-opt-in-v1",
                    result_code="validation_failed",
                    payload={"private": "new"},
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    + timedelta(days=29),
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
    assert marker["evaluation_ids"] == ["expired"]


def test_screenshot_object_delete_rejects_non_road_key():
    with pytest.raises(ValueError):
        delete_object("feedback/1/0.png")
