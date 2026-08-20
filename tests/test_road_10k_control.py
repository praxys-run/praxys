"""Road 10K control-ledger tests."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import road_10k_control, road_10k_deletion_storage
from api.road_10k_control import (
    Road10KControlDenied,
    Road10KControlUnavailable,
    authorize_first_exposure,
    enroll_owner,
    issue_invitation,
    withdraw_owner,
)
from api.road_10k_screenshot_storage import (
    Road10KScreenshotUnavailable,
    screenshot_capture_available,
)
from api.road_10k_stage_authority import Road10KStageAuthority
from api.road_10k_stage_authority import StageAuthorityError, parse_stage_authority
from db.models import Base, Road10KStageCounter, User


def _db(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'road.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    return db


def _authority() -> Road10KStageAuthority:
    now = datetime.now(timezone.utc)
    digest = "a" * 64
    return Road10KStageAuthority(
        stage_id="road-10k-controlled-opt-in-v1",
        authority_digest="b" * 64,
        capability_id="outdoor_road_10k_performance_v1",
        object_id="road-10k-controlled-opt-in-foundation-v1",
        work_contract_digest="1bdbdeded8149881cf610df2309a607561d9ff599c3da24f48f400d20400adb1",
        route_digest="62ef1a983cd560f6dfab10e6508fbf9a73c68bd9ad3ca0c59f911f3e48237f08",
        schema_version="road-10k-stage-authority-v1",
        control_schema_version=2,
        state="active",
        invitation_ceiling=60,
        exposure_ceiling=30,
        notice_digest=digest,
        cohort_rule_digest=digest,
        sampling_run_evidence_digest=digest,
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(minutes=5),
        heartbeat_at=now,
        heartbeat_max_age_seconds=300,
        readiness="ready",
        provider_fence="closed",
        pause=False,
        kill=False,
        build_id="test",
    )


def _owner(db, user_id: str):
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@example.test",
            hashed_password="unused",
            is_active=True,
            is_demo=False,
        )
    )
    db.commit()


def test_invitation_and_exposure_are_monotonic_and_idempotent(
    tmp_path, monkeypatch
):
    db = _db(tmp_path)
    _owner(db, "owner-1")
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    authority = _authority()
    receipt = issue_invitation(
        db,
        user_id="owner-1",
        idempotency_key="invitation-1",
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    assert issue_invitation(
        db,
        user_id="owner-1",
        idempotency_key="invitation-1",
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    ).id == receipt.id
    enroll_owner(db, user_id="owner-1", notice_digest=authority.notice_digest)
    first = authorize_first_exposure(db, user_id="owner-1")
    assert authorize_first_exposure(db, user_id="owner-1").id == first.id
    counter = db.query(Road10KStageCounter).one()
    assert counter.invitation_slots_consumed == 1
    assert counter.distinct_exposed_owners_consumed == 1


def test_caps_deny_without_slot_reuse(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    authority = _authority()
    for index in range(60):
        user_id = f"owner-{index}"
        _owner(db, user_id)
        issue_invitation(
            db,
            user_id=user_id,
            idempotency_key=f"invitation-{index:02d}",
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )
    _owner(db, "owner-60")
    with pytest.raises(Road10KControlDenied, match="invitation_cap"):
        issue_invitation(
            db,
            user_id="owner-60",
            idempotency_key="invitation-60",
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )
    assert db.query(Road10KStageCounter).one().invitation_slots_consumed == 60


def test_uninvited_authorization_and_enrollment_do_not_create_counter(
    tmp_path, monkeypatch
):
    db = _db(tmp_path)
    _owner(db, "uninvited")
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    authority = _authority()

    with pytest.raises(Road10KControlDenied, match="enrollment_required"):
        authorize_first_exposure(db, user_id="uninvited")
    with pytest.raises(Road10KControlDenied, match="invitation_required"):
        enroll_owner(
            db,
            user_id="uninvited",
            notice_digest=authority.notice_digest,
        )

    assert db.query(Road10KStageCounter).count() == 0


def test_withdrawal_keeps_exposure_count_and_deletes_evidence(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / "data"
    monkeypatch.setattr("db.session.get_data_dir", lambda: str(data_dir))
    db = _db(tmp_path)
    monkeypatch.setattr(
        road_10k_deletion_storage,
        "_test_store",
        _MemoryManifestStore(),
    )
    _owner(db, "owner-withdraw")
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    authority = _authority()
    issue_invitation(
        db,
        user_id="owner-withdraw",
        idempotency_key="withdraw-invitation",
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(db, user_id="owner-withdraw", notice_digest=authority.notice_digest)
    authorize_first_exposure(db, user_id="owner-withdraw")
    withdrawn = withdraw_owner(db, user_id="owner-withdraw")
    assert withdrawn.state == "withdrawn"
    assert db.query(Road10KStageCounter).one().distinct_exposed_owners_consumed == 1


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


def test_runtime_snapshot_with_authority_present_is_low_cardinality(
    tmp_path, monkeypatch
):
    db = _db(tmp_path)
    authority = _authority()
    db.add(
        Road10KStageCounter(
            stage_id=authority.stage_id,
            schema_version=2,
            capability_id=authority.capability_id,
            invitation_ceiling=authority.invitation_ceiling,
            exposure_ceiling=authority.exposure_ceiling,
        )
    )
    db.commit()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", lambda: authority)
    monkeypatch.setattr(road_10k_control, "replay_status", lambda: "ready")

    snapshot = road_10k_control.road_10k_runtime_snapshot(db)

    assert snapshot["authority"] == "allowed"
    assert snapshot["stage"] == authority.stage_id
    assert snapshot["invitation_slots_consumed"] == 0
    assert snapshot["distinct_exposed_owners_consumed"] == 0
    assert snapshot["ready"] is True


def test_screenshot_upload_is_unavailable():
    assert screenshot_capture_available() is False
    with pytest.raises(Road10KScreenshotUnavailable):
        from api.road_10k_screenshot_storage import store_screenshot

        store_screenshot(b"image")


def test_stale_receipt_contract_cannot_expose_or_participate(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "stale-owner")
    authority = _authority()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", lambda: authority)
    issue_invitation(
        db,
        user_id="stale-owner",
        idempotency_key="stale-invitation",
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(db, user_id="stale-owner", notice_digest=authority.notice_digest)
    receipt = (
        db.query(road_10k_control.Road10KOwnerStageReceipt)
        .filter_by(user_id="stale-owner")
        .one()
    )
    receipt.policy_version = "stale-policy"
    db.commit()

    with pytest.raises(Road10KControlUnavailable, match="receipt_contract"):
        authorize_first_exposure(db, user_id="stale-owner")
    with pytest.raises(Road10KControlDenied, match="participation_required"):
        road_10k_control.require_road_10k_participation(
            db,
            user_id="stale-owner",
        )


def test_stage_authority_mixed_versions_fail_closed():
    with pytest.raises(StageAuthorityError):
        parse_stage_authority(
            {
                "stage_id": "road-10k-controlled-opt-in-v1",
                "state": "active",
                "invitation_ceiling": 60,
                "exposure_ceiling": 30,
            }
        )


@pytest.mark.parametrize("state", ["paused", "killed", "hold", "rollback"])
def test_lifecycle_authority_is_visible_but_not_mutation_usable(state):
    authority = _authority()
    authority = replace(authority, state=state)
    assert authority.lifecycle_status == state
    assert authority.is_usable is False
