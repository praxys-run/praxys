"""Road 10K control-ledger tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from threading import Barrier, Event

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from api import road_10k_control, road_10k_deletion_storage
from api.road_10k_control import (
    Road10KControlDenied,
    Road10KControlUnavailable,
    authorize_first_exposure,
    enroll_owner,
    issue_invitation,
    prepare_account_deletion,
    record_result,
    withdraw_owner,
)
from api.road_10k_screenshot_storage import (
    Road10KScreenshotUnavailable,
    screenshot_capture_available,
)
from api.road_10k_stage_authority import Road10KStageAuthority
from api.road_10k_stage_authority import StageAuthorityError, parse_stage_authority
from db.models import (
    Base,
    Road10KExposureReceipt,
    Road10KEvaluation,
    Road10KOwnerStageReceipt,
    Road10KStageCounter,
    User,
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


@pytest.fixture(autouse=True)
def _runtime_ready(monkeypatch):
    monkeypatch.setattr(
        road_10k_deletion_storage,
        "_test_store",
        _MemoryManifestStore(),
    )
    monkeypatch.setattr(road_10k_control, "replay_status", lambda: "ready")


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


def _invitation_key(label: str) -> str:
    return "inv_" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:32]


def _parsed_authority(
    monkeypatch,
    **updates,
) -> Road10KStageAuthority:
    authority = _authority()
    monkeypatch.setenv("PRAXYS_API_VERSION", "2026.08.735")
    payload = {
        "authority_digest": "",
        "stage_id": authority.stage_id,
        "capability_id": authority.capability_id,
        "object_id": authority.object_id,
        "work_contract_digest": f"sha256:{authority.work_contract_digest}",
        "route_digest": f"sha256:{authority.route_digest}",
        "schema_version": authority.schema_version,
        "control_schema_version": authority.control_schema_version,
        "state": authority.state,
        "invitation_ceiling": authority.invitation_ceiling,
        "exposure_ceiling": authority.exposure_ceiling,
        "notice_digest": f"sha256:{authority.notice_digest}",
        "cohort_rule_digest": f"sha256:{authority.cohort_rule_digest}",
        "sampling_run_evidence_digest": (
            f"sha256:{authority.sampling_run_evidence_digest}"
        ),
        "valid_from": authority.valid_from.isoformat(),
        "valid_until": authority.valid_until.isoformat(),
        "heartbeat_at": authority.heartbeat_at.isoformat(),
        "heartbeat_max_age_seconds": authority.heartbeat_max_age_seconds,
        "readiness": authority.readiness,
        "provider_fence": authority.provider_fence,
        "pause": authority.pause,
        "kill": authority.kill,
        "build_id": "2026.08.735",
    }
    payload.update(updates)
    encoded = json.dumps(
        {
            key: value
            for key, value in payload.items()
            if key != "authority_digest"
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    payload["authority_digest"] = (
        "sha256:" + hashlib.sha256(encoded).hexdigest()
    )
    return parse_stage_authority(payload)


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


def test_invitation_key_must_be_opaque_random_material(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "opaque-key-owner")
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    authority = _authority()

    for identifying_key in (
        "opaque-key-owner",
        "runner@example.test",
        "inv_not-hexadecimal-owner-material",
    ):
        with pytest.raises(
            Road10KControlDenied,
            match="invalid_idempotency_key",
        ):
            issue_invitation(
                db,
                user_id="opaque-key-owner",
                idempotency_key=identifying_key,
                notice_digest=authority.notice_digest,
                cohort_rule_digest=authority.cohort_rule_digest,
            )

    assert db.query(Road10KOwnerStageReceipt).count() == 0


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
        idempotency_key=_invitation_key("invitation-1"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    assert (
        receipt.sampling_run_evidence_digest
        == authority.sampling_run_evidence_digest
    )
    assert issue_invitation(
        db,
        user_id="owner-1",
        idempotency_key=_invitation_key("invitation-1"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    ).id == receipt.id
    enroll_owner(db, user_id="owner-1", notice_digest=authority.notice_digest)
    first = authorize_first_exposure(db, user_id="owner-1")
    assert authorize_first_exposure(db, user_id="owner-1").id == first.id
    counter = db.query(Road10KStageCounter).one()
    assert counter.invitation_slots_consumed == 1
    assert counter.distinct_exposed_owners_consumed == 1
    assert "request_fingerprint" not in Road10KOwnerStageReceipt.__table__.columns


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
            idempotency_key=_invitation_key(f"invitation-{index:02d}"),
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )
    _owner(db, "owner-60")
    with pytest.raises(Road10KControlDenied, match="invitation_cap"):
        issue_invitation(
            db,
            user_id="owner-60",
            idempotency_key=_invitation_key("invitation-60"),
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )
    assert db.query(Road10KStageCounter).one().invitation_slots_consumed == 60


def test_sqlite_concurrent_attempts_cannot_consume_slot_61_or_exposure_31(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "road-concurrency.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    authority = _authority()
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: authority,
    )
    with SessionLocal() as db:
        for index in range(61):
            _owner(db, f"concurrent-owner-{index}")
        for index in range(59):
            issue_invitation(
                db,
                user_id=f"concurrent-owner-{index}",
                idempotency_key=_invitation_key(
                    f"concurrent-invitation-{index:02d}"
                ),
                notice_digest=authority.notice_digest,
                cohort_rule_digest=authority.cohort_rule_digest,
            )

    invitation_barrier = Barrier(2)

    def invite(index: int) -> str:
        with SessionLocal() as db:
            invitation_barrier.wait()
            try:
                issue_invitation(
                    db,
                    user_id=f"concurrent-owner-{index}",
                    idempotency_key=_invitation_key(
                        f"concurrent-invitation-{index:02d}"
                    ),
                    notice_digest=authority.notice_digest,
                    cohort_rule_digest=authority.cohort_rule_digest,
                )
                return "invited"
            except Road10KControlDenied as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        invitation_results = list(executor.map(invite, (59, 60)))
    assert sorted(invitation_results) == ["invitation_cap", "invited"]

    with SessionLocal() as db:
        invited_owner_ids = [
            user_id
            for (user_id,) in db.query(Road10KOwnerStageReceipt.user_id)
            .filter(Road10KOwnerStageReceipt.user_id.is_not(None))
            .order_by(Road10KOwnerStageReceipt.user_id)
            .all()
        ]
        for user_id in invited_owner_ids:
            assert user_id is not None
            enroll_owner(
                db,
                user_id=user_id,
                notice_digest=authority.notice_digest,
            )
        for user_id in invited_owner_ids[:29]:
            authorize_first_exposure(db, user_id=user_id)

    exposure_barrier = Barrier(2)

    def expose(user_id: str) -> str:
        with SessionLocal() as db:
            exposure_barrier.wait()
            try:
                authorize_first_exposure(db, user_id=user_id)
                return "exposed"
            except Road10KControlDenied as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        exposure_results = list(
            executor.map(expose, invited_owner_ids[29:31])
        )
    assert sorted(exposure_results) == ["exposed", "exposure_cap"]

    with SessionLocal() as db:
        counter = db.query(Road10KStageCounter).one()
        assert counter.invitation_slots_consumed == 60
        assert counter.distinct_exposed_owners_consumed == 30


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
        idempotency_key=_invitation_key("withdraw-invitation"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(db, user_id="owner-withdraw", notice_digest=authority.notice_digest)
    authorize_first_exposure(db, user_id="owner-withdraw")
    withdrawn = withdraw_owner(db, user_id="owner-withdraw")
    assert withdrawn.state == "withdrawn"
    assert db.query(Road10KStageCounter).one().distinct_exposed_owners_consumed == 1


def test_withdrawn_owner_reopts_into_existing_receipt_and_counters(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    authority = _authority()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    _owner(db, "owner-reopt")
    receipt = issue_invitation(
        db,
        user_id="owner-reopt",
        idempotency_key=_invitation_key("owner-reopt-invitation"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(db, user_id="owner-reopt", notice_digest=authority.notice_digest)
    exposure = authorize_first_exposure(db, user_id="owner-reopt")
    withdraw_owner(db, user_id="owner-reopt")

    reenrolled = enroll_owner(
        db,
        user_id="owner-reopt",
        notice_digest=authority.notice_digest,
    )

    assert reenrolled.id == receipt.id
    assert reenrolled.state == "exposed"
    assert reenrolled.withdrawn_at is None
    assert db.query(Road10KExposureReceipt).one().id == exposure.id
    counter = db.query(Road10KStageCounter).one()
    assert counter.invitation_slots_consumed == 1
    assert counter.distinct_exposed_owners_consumed == 1

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


def test_dormant_runtime_snapshot_keeps_retained_consumption_visible(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "dormant-snapshot-owner")
    authority = _authority()
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: authority,
    )
    issue_invitation(
        db,
        user_id="dormant-snapshot-owner",
        idempotency_key=_invitation_key("dormant-snapshot"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: None,
    )

    snapshot = road_10k_control.road_10k_runtime_snapshot(db)

    assert snapshot["authority"] == "missing_or_malformed"
    assert snapshot["stage"] == authority.stage_id
    assert snapshot["invitation_slots_consumed"] == 1
    assert snapshot["distinct_exposed_owners_consumed"] == 0
    assert snapshot["ready"] is False


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
        idempotency_key=_invitation_key("stale-invitation"),
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


def test_account_deletion_unlinks_native_owner_without_pseudonym_or_slot_reuse(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    authority = _authority()
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: authority,
    )
    _owner(db, "deleted-native-owner")
    issue_invitation(
        db,
        user_id="deleted-native-owner",
        idempotency_key=_invitation_key("deleted-owner-invitation"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(
        db,
        user_id="deleted-native-owner",
        notice_digest=authority.notice_digest,
    )
    authorize_first_exposure(db, user_id="deleted-native-owner")

    prepare_account_deletion(db, user_id="deleted-native-owner")
    db.commit()
    db.delete(db.get(User, "deleted-native-owner"))
    db.commit()

    deleted_receipt = db.query(Road10KOwnerStageReceipt).one()
    assert db.get(User, "deleted-native-owner") is None
    assert deleted_receipt.user_id is None
    assert (
        deleted_receipt.invitation_idempotency_key
        == _invitation_key("deleted-owner-invitation")
    )
    assert deleted_receipt.state == "deleted"
    assert db.query(Road10KExposureReceipt).one().user_id is None

    _owner(db, "new-native-owner")
    with pytest.raises(
        road_10k_control.Road10KControlConflict,
        match="idempotency_conflict",
    ):
        issue_invitation(
            db,
            user_id="new-native-owner",
            idempotency_key=_invitation_key("deleted-owner-invitation"),
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )

    counter = db.query(Road10KStageCounter).one()
    assert counter.invitation_slots_consumed == 1
    assert counter.distinct_exposed_owners_consumed == 1


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


def test_authority_is_rechecked_after_the_serialized_write_begins(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "owner-authority-race")
    active = _authority()
    paused = replace(active, state="paused", pause=True)
    authorities = iter((active, paused))
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: next(authorities),
    )

    with pytest.raises(Road10KControlUnavailable, match="paused"):
        issue_invitation(
            db,
            user_id="owner-authority-race",
            idempotency_key=_invitation_key("authority-race-invitation"),
            notice_digest=active.notice_digest,
            cohort_rule_digest=active.cohort_rule_digest,
        )

    assert db.query(Road10KStageCounter).count() == 0
    assert db.query(Road10KOwnerStageReceipt).count() == 0


def test_counter_and_receipt_disagreement_fails_closed(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "owner-counter-mismatch")
    authority = _authority()
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: authority,
    )
    issue_invitation(
        db,
        user_id="owner-counter-mismatch",
        idempotency_key=_invitation_key("counter-mismatch-invitation"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    db.execute(text("DROP TRIGGER trg_road_10k_stage_counters_monotonic"))
    db.execute(
        text(
            "UPDATE road_10k_stage_counters "
            "SET invitation_slots_consumed = 0"
        )
    )
    db.commit()

    with pytest.raises(Road10KControlUnavailable, match="counter_mismatch"):
        enroll_owner(
            db,
            user_id="owner-counter-mismatch",
            notice_digest=authority.notice_digest,
        )


@pytest.mark.parametrize(
    "state",
    ["paused", "killed", "hold", "rollback", "stopped", "revision"],
)
def test_lifecycle_authority_is_visible_but_not_mutation_usable(state):
    authority = _authority()
    authority = replace(authority, state=state)
    assert authority.lifecycle_status == state
    assert authority.is_usable is False


def test_parsed_heartbeat_and_lifecycle_refresh_preserve_consumed_evidence(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "authority-refresh-owner")
    initial = _parsed_authority(monkeypatch)
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: initial,
    )
    issue_invitation(
        db,
        user_id="authority-refresh-owner",
        idempotency_key=_invitation_key("authority-refresh-invitation"),
        notice_digest=initial.notice_digest,
        cohort_rule_digest=initial.cohort_rule_digest,
    )
    enroll_owner(
        db,
        user_id="authority-refresh-owner",
        notice_digest=initial.notice_digest,
    )
    authorize_first_exposure(db, user_id="authority-refresh-owner")

    refreshed = _parsed_authority(
        monkeypatch,
        heartbeat_at=datetime.now(timezone.utc).isoformat(),
    )
    assert refreshed.authority_digest != initial.authority_digest
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: refreshed,
    )
    assert road_10k_control.require_road_10k_gate(
        db,
        user_id="authority-refresh-owner",
        expose=False,
    ).authority_digest == refreshed.authority_digest

    for lifecycle in (
        _parsed_authority(
            monkeypatch,
            state="paused",
            pause=True,
        ),
        _parsed_authority(
            monkeypatch,
            state="killed",
            kill=True,
        ),
    ):
        monkeypatch.setattr(
            road_10k_control,
            "load_stage_authority",
            lambda lifecycle=lifecycle: lifecycle,
        )
        assert road_10k_control.require_road_10k_participation(
            db,
            user_id="authority-refresh-owner",
            lifecycle=True,
        ).lifecycle_status in {"paused", "killed"}
        with pytest.raises(Road10KControlUnavailable):
            road_10k_control.require_road_10k_gate(
                db,
                user_id="authority-refresh-owner",
                expose=False,
            )


def test_create_all_ledger_blocks_decrements_and_receipt_deletes(
    tmp_path,
):
    db = _db(tmp_path)
    _owner(db, "durable-owner")
    db.add(
        Road10KStageCounter(
            stage_id="road-10k-controlled-opt-in-v1",
            schema_version=2,
            capability_id="outdoor_road_10k_performance_v1",
            invitation_slots_consumed=1,
            distinct_exposed_owners_consumed=1,
            invitation_ceiling=60,
            exposure_ceiling=30,
        )
    )
    receipt = Road10KOwnerStageReceipt(
        id="durable-owner-receipt",
        user_id="durable-owner",
        stage_id="road-10k-controlled-opt-in-v1",
        capability_id="outdoor_road_10k_performance_v1",
        schema_version=2,
        policy_version="road-10k-plan-generation-policy-v2",
        authority_digest="a" * 64,
        notice_digest="b" * 64,
        cohort_rule_digest="c" * 64,
        sampling_run_evidence_digest="d" * 64,
        invitation_idempotency_key="durable-owner-invitation",
        state="exposed",
        invitation_issued_at=datetime.utcnow(),
        first_exposed_at=datetime.utcnow(),
    )
    exposure = Road10KExposureReceipt(
        id="durable-owner-exposure",
        stage_id=receipt.stage_id,
        user_id="durable-owner",
        owner_stage_receipt_id=receipt.id,
        authority_digest="a" * 64,
        exposed_at=datetime.utcnow(),
    )
    db.add_all([receipt, exposure])
    db.commit()

    receipt.state = "withdrawn"
    receipt.withdrawn_at = datetime.utcnow()
    db.commit()

    counter = db.query(Road10KStageCounter).one()
    counter.invitation_slots_consumed = 0
    with pytest.raises(DatabaseError, match="counters cannot decrement"):
        db.commit()
    db.rollback()

    db.delete(db.get(Road10KOwnerStageReceipt, receipt.id))
    with pytest.raises(DatabaseError, match="owner receipts cannot be deleted"):
        db.commit()
    db.rollback()

    native_exposure = db.get(Road10KExposureReceipt, exposure.id)
    native_exposure.user_id = None
    db.commit()
    native_exposure.authority_digest = "e" * 64
    with pytest.raises(DatabaseError, match="exposure receipts are immutable"):
        db.commit()
    db.rollback()

    db.delete(db.get(Road10KExposureReceipt, exposure.id))
    with pytest.raises(
        DatabaseError,
        match="exposure receipts cannot be deleted",
    ):
        db.commit()


def test_withdrawal_serialization_cannot_omit_concurrent_result(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "withdrawal-race.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    authority = _authority()
    monkeypatch.setattr(
        road_10k_control,
        "load_stage_authority",
        lambda: authority,
    )
    with SessionLocal() as db:
        _owner(db, "withdrawal-race-owner")
        issue_invitation(
            db,
            user_id="withdrawal-race-owner",
            idempotency_key=_invitation_key("withdrawal-race-invitation"),
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )
        enroll_owner(
            db,
            user_id="withdrawal-race-owner",
            notice_digest=authority.notice_digest,
        )
        authorize_first_exposure(db, user_id="withdrawal-race-owner")
        existing = record_result(
            db,
            user_id="withdrawal-race-owner",
            result_code="validation_failed",
            payload={"boundary": "readiness"},
        )
        existing_id = existing.id

    staged = Event()
    release = Event()
    evaluation_started = Event()
    original_stage_manifest = road_10k_control.stage_manifest

    def blocking_stage_manifest(**kwargs):
        marker = original_stage_manifest(**kwargs)
        staged.set()
        assert release.wait(timeout=10)
        return marker

    monkeypatch.setattr(
        road_10k_control,
        "stage_manifest",
        blocking_stage_manifest,
    )

    def withdraw() -> str:
        with SessionLocal() as db:
            return withdraw_owner(
                db,
                user_id="withdrawal-race-owner",
            ).state

    def evaluate() -> str:
        evaluation_started.set()
        with SessionLocal() as db:
            try:
                record_result(
                    db,
                    user_id="withdrawal-race-owner",
                    result_code="validation_failed",
                    payload={"boundary": "concurrent"},
                )
                return "recorded"
            except road_10k_control.Road10KControlError as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        withdrawal_future = executor.submit(withdraw)
        assert staged.wait(timeout=10)
        evaluation_future = executor.submit(evaluate)
        assert evaluation_started.wait(timeout=10)
        release.set()
        assert withdrawal_future.result(timeout=10) == "withdrawn"
        assert evaluation_future.result(timeout=10) != "recorded"

    with SessionLocal() as db:
        assert db.query(Road10KEvaluation).count() == 0
    manifests = [
        json.loads(raw)
        for raw in road_10k_deletion_storage._test_store.items.values()
    ]
    assert any(existing_id in marker["evaluation_ids"] for marker in manifests)
