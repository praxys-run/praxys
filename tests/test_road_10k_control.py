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
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import sessionmaker

from api import road_10k_control, road_10k_deletion_storage
from api.road_10k_control import (
    Road10KControlDenied,
    Road10KControlUnavailable,
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
from api.road_10k_runtime import ROAD_10K_BOUNDARIES, evaluate_boundary, provider_fence_is_closed
from db.models import (
    Base,
    Road10KDeletionObligation,
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
def _runtime_ready(monkeypatch, request):
    monkeypatch.setattr(
        road_10k_deletion_storage,
        "_test_store",
        _MemoryManifestStore(),
    )
    # Ledger tests use an explicit in-memory authority seam. Production callers
    # always pass through the hard-off authority reader.
    excluded = {
        "test_valid_looking_non_off_authority_cannot_enable_any_boundary",
        "test_invitation_and_exposure_are_monotonic_and_idempotent",
        "test_authority_is_rechecked_after_the_serialized_write_begins",
    }
    if request.node.name not in excluded:
        monkeypatch.setattr(
            road_10k_control,
            "_authority",
            lambda lifecycle=False: road_10k_control.load_stage_authority(),
        )




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
        work_contract_digest="b2c668dc304e44407a743c8b8c2710cc6c133ac4106045986bfd1726d2a7725e",
        route_digest="a916feab2d029de3d6996933a7aece668670facc016f6abf8b932aa747af8214",
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


def test_valid_looking_non_off_authority_cannot_enable_any_boundary(monkeypatch):
    """This revision is mechanically hard-off, even for a complete artifact."""
    authority = _authority()
    monkeypatch.setattr(
        "api.road_10k_runtime.load_stage_authority",
        lambda: authority,
    )

    assert authority.is_usable is False
    assert authority.lifecycle_status is None
    for boundary in (*ROAD_10K_BOUNDARIES, "unknown-boundary"):
        decision = evaluate_boundary(boundary)
        assert decision.allowed is False
        assert decision.provider_calls_allowed is False
    assert provider_fence_is_closed() is True


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


@pytest.mark.parametrize(
    "updates",
    [
        {"invitation_ceiling": 59},
        {"exposure_ceiling": 29},
    ],
)
def test_stage_authority_rejects_nonfixed_ceiling(monkeypatch, updates):
    with pytest.raises(StageAuthorityError, match="fixed policy"):
        _parsed_authority(monkeypatch, **updates)


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
    # This isolates the legacy ledger fixture from the production hard-off
    # authority gate; it is not a runtime activation mechanism.
    monkeypatch.setattr(
        road_10k_control,
        "_authority",
        lambda lifecycle=False: authority,
    )
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
    with pytest.raises(
        Road10KControlDenied,
        match="first_exposure_requires_durable_result",
    ):
        road_10k_control.authorize_first_exposure(db, user_id="owner-1")
    assert db.query(Road10KExposureReceipt).count() == 0
    assert db.query(Road10KStageCounter).one().distinct_exposed_owners_consumed == 0

    first = record_result(
        db,
        user_id="owner-1",
        result_code="validation_failed",
        payload={"boundary": "test"},
    )
    retry = record_result(
        db,
        user_id="owner-1",
        result_code="validation_failed",
        payload={"boundary": "test-retry"},
    )
    assert first.id != retry.id
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
            record_result(db, user_id=user_id, result_code="validation_failed", payload={"scope": "ledger-unit"})

    exposure_barrier = Barrier(2)

    def expose(user_id: str) -> str:
        with SessionLocal() as db:
            exposure_barrier.wait()
            try:
                record_result(db, user_id=user_id, result_code="validation_failed", payload={"scope": "ledger-unit"})
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
        record_result(db, user_id="uninvited", result_code="validation_failed", payload={"scope": "ledger-unit"})
    with pytest.raises(Road10KControlDenied, match="invitation_required"):
        enroll_owner(
            db,
            user_id="uninvited",
            notice_digest=authority.notice_digest,
        )

    assert db.query(Road10KStageCounter).count() == 0


def test_withdrawal_without_payload_does_not_require_private_storage(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    authority = _authority()
    monkeypatch.setattr(road_10k_deletion_storage, "_test_store", None)
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    _owner(db, "owner-empty-withdrawal")
    issue_invitation(
        db,
        user_id="owner-empty-withdrawal",
        idempotency_key=_invitation_key("empty-withdrawal-invitation"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(
        db,
        user_id="owner-empty-withdrawal",
        notice_digest=authority.notice_digest,
    )

    withdrawn = withdraw_owner(db, user_id="owner-empty-withdrawal")

    assert withdrawn.state == "withdrawn"
    assert db.query(road_10k_control.Road10KDeletionObligation).count() == 0


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
    record_result(db, user_id="owner-withdraw", result_code="validation_failed", payload={"scope": "withdrawal"})
    withdrawn = withdraw_owner(db, user_id="owner-withdraw")
    assert withdrawn.state == "withdrawn"
    assert db.query(Road10KStageCounter).one().distinct_exposed_owners_consumed == 1


def test_withdrawn_owner_cannot_reopt_or_reuse_a_slot(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    authority = _authority()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", _authority)
    _owner(db, "owner-reopt")
    issue_invitation(
        db,
        user_id="owner-reopt",
        idempotency_key=_invitation_key("owner-reopt-invitation"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    enroll_owner(db, user_id="owner-reopt", notice_digest=authority.notice_digest)
    record_result(db, user_id="owner-reopt", result_code="validation_failed", payload={"scope": "withdrawal"})
    withdraw_owner(db, user_id="owner-reopt")

    with pytest.raises(Road10KControlDenied, match="same_stage_reenrollment_denied"):
        enroll_owner(db, user_id="owner-reopt", notice_digest=authority.notice_digest)
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

    snapshot = road_10k_control.road_10k_runtime_snapshot(db)

    assert snapshot["authority"] == "inactive_revision"
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

    assert snapshot["authority"] == "inactive_revision"
    assert snapshot["stage"] == authority.stage_id
    assert snapshot["invitation_slots_consumed"] == 1
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
    with pytest.raises(IntegrityError, match="owner receipt (immutable|lifecycle invalid)"):
        db.commit()
    db.rollback()


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
    record_result(db, user_id="deleted-native-owner", result_code="validation_failed", payload={"scope": "account-deletion"})

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
    """An apparently active artifact fails before the first ledger write."""
    db = _db(tmp_path)
    _owner(db, "owner-authority-race")
    authority = _authority()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", lambda: authority)

    with pytest.raises(Road10KControlUnavailable, match="inactive_revision"):
        issue_invitation(
            db,
            user_id="owner-authority-race",
            idempotency_key=_invitation_key("authority-race"),
            notice_digest=authority.notice_digest,
            cohort_rule_digest=authority.cohort_rule_digest,
        )
    assert db.query(Road10KStageCounter).count() == 0

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
def test_lifecycle_authority_is_hidden_and_not_mutation_usable(state):
    authority = replace(_authority(), state=state)
    assert authority.lifecycle_status is None
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
    record_result(db, user_id="authority-refresh-owner", result_code="validation_failed", payload={"scope": "receipt-refresh"})

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
        ).lifecycle_status is None


def test_sqlite_ledger_constraints_freeze_ceilings_timestamps_and_expiry(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "invariant-owner")
    authority = _authority()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", lambda: authority)
    issue_invitation(
        db,
        user_id="invariant-owner",
        idempotency_key=_invitation_key("invariant"),
        notice_digest=authority.notice_digest,
        cohort_rule_digest=authority.cohort_rule_digest,
    )
    counter = db.query(Road10KStageCounter).one()
    counter.invitation_ceiling = 59
    with pytest.raises(IntegrityError, match="counters cannot decrement"):
        db.commit()
    db.rollback()

    receipt = db.query(Road10KOwnerStageReceipt).one()
    receipt.updated_at = receipt.updated_at + timedelta(seconds=1)
    with pytest.raises(IntegrityError, match="owner receipt lifecycle invalid"):
        db.commit()
    db.rollback()

    created = datetime.utcnow()
    db.add(
        Road10KEvaluation(
            id="invalid-expiry",
            user_id="invariant-owner",
            stage_id=authority.stage_id,
            result_code="validation_failed",
            payload={},
            created_at=created,
            expires_at=created + timedelta(days=31),
        )
    )
    with pytest.raises(IntegrityError, match="evaluation expiry invalid"):
        db.commit()
    db.rollback()

    obligation_time = datetime.utcnow()
    obligation = Road10KDeletionObligation(
        id="00000000-0000-4000-8000-000000000735",
        manifest_digest="a" * 64,
        stage_id=authority.stage_id,
        reason="withdrawal",
        status="committed",
        requested_at=obligation_time,
        committed_at=obligation_time,
    )
    db.add(obligation)
    db.commit()
    obligation.reason = "retention"
    with pytest.raises(IntegrityError, match="deletion obligation immutable"):
        db.commit()
    db.rollback()

    obligation = db.get(Road10KDeletionObligation, obligation.id)
    obligation.status = "completed"
    obligation.completed_at = obligation_time + timedelta(seconds=1)
    db.commit()
    obligation.status = "committed"
    obligation.completed_at = None
    with pytest.raises(IntegrityError, match="deletion obligation immutable"):
        db.commit()
    db.rollback()

    obligation = db.get(Road10KDeletionObligation, obligation.id)
    db.delete(obligation)
    with pytest.raises(IntegrityError, match="cannot be deleted"):
        db.commit()
    db.rollback()


def test_ledger_migration_declares_postgresql_and_sqlite_invariants():
    migration = Path(
        "alembic/versions/d2e3f4a5b6c7_add_road_10k_control_ledger.py"
    ).read_text(encoding="utf-8")

    for required in (
        "invitation_ceiling = 60 AND exposure_ceiling = 30",
        "trg_road_10k_owner_stage_receipts_lifecycle",
        "road_10k_owner_stage_receipts_immutable",
        "NEW.enrolled_at IS OLD.enrolled_at",
        "trg_road_10k_deletion_obligations_immutable",
        "road_10k_deletion_obligations_immutable",
        "trg_road_10k_evaluations_expiry_immutable",
        "road_10k_evaluation_expiry_insert",
        "DROP FUNCTION IF EXISTS road_10k_evaluation_expiry_update()",
    ):
        assert required in migration


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
    receipt_time = datetime.utcnow()
    exposed_time = receipt_time + timedelta(seconds=1)
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
        invitation_issued_at=receipt_time,
        enrolled_at=receipt_time,
        first_exposed_at=exposed_time,
        created_at=receipt_time,
        updated_at=exposed_time,
    )
    exposure = Road10KExposureReceipt(
        id="durable-owner-exposure",
        stage_id=receipt.stage_id,
        user_id="durable-owner",
        owner_stage_receipt_id=receipt.id,
        authority_digest="a" * 64,
        exposed_at=exposed_time,
    )
    db.add(receipt)
    db.flush()
    db.add(exposure)
    db.commit()

    receipt.state = "withdrawn"
    receipt.withdrawn_at = exposed_time + timedelta(seconds=1)
    receipt.updated_at = receipt.withdrawn_at
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


def test_invalid_runtime_snapshot_keeps_fixed_ceiling_fields(tmp_path):
    db = _db(tmp_path)
    db.add(
        Road10KStageCounter(
            stage_id=road_10k_control.ROAD_10K_STAGE_ID,
            schema_version=2,
            capability_id="outdoor_road_10k_performance_v1",
            invitation_slots_consumed=1,
            distinct_exposed_owners_consumed=0,
            invitation_ceiling=60,
            exposure_ceiling=30,
        )
    )
    db.commit()

    snapshot = road_10k_control.road_10k_runtime_snapshot(db)

    assert snapshot["authority"] == "counter_mismatch"
    assert snapshot["invitation_ceiling"] == 60
    assert snapshot["exposure_ceiling"] == 30
    assert snapshot["deletion_replay_status"] == "blocked"
    assert snapshot["ready"] is False


def test_fixed_owner_receipt_rejects_withdrawal_before_latest_lifecycle(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "validator-owner")
    invited_at = datetime(2026, 8, 1, 10, 0, 0)
    enrolled_at = invited_at + timedelta(minutes=1)
    exposed_at = invited_at + timedelta(minutes=2)
    withdrawn_at = invited_at + timedelta(minutes=1, seconds=30)
    receipt = Road10KOwnerStageReceipt(
        id="validator-receipt",
        user_id="validator-owner",
        stage_id=road_10k_control.ROAD_10K_STAGE_ID,
        capability_id="outdoor_road_10k_performance_v1",
        schema_version=2,
        policy_version=road_10k_control.ROAD_10K_POLICY_VERSION,
        authority_digest="a" * 64,
        notice_digest="b" * 64,
        cohort_rule_digest="c" * 64,
        sampling_run_evidence_digest="d" * 64,
        invitation_idempotency_key="validator-invitation",
        state="withdrawn",
        invitation_issued_at=invited_at,
        enrolled_at=enrolled_at,
        first_exposed_at=exposed_at,
        withdrawn_at=withdrawn_at,
        created_at=invited_at,
        updated_at=withdrawn_at,
    )
    monkeypatch.setattr(road_10k_control, "_receipt", lambda *args, **kwargs: receipt)

    with pytest.raises(Road10KControlDenied, match="receipt_contract_mismatch"):
        road_10k_control._fixed_owner_receipt(db, user_id="validator-owner")


def test_create_all_rejects_withdrawal_before_first_exposure(tmp_path):
    db = _db(tmp_path)
    _owner(db, "chronology-withdraw-owner")
    invited_at = datetime(2026, 8, 1, 10, 0, 0)
    enrolled_at = invited_at + timedelta(minutes=1)
    exposed_at = invited_at + timedelta(minutes=2)
    receipt = Road10KOwnerStageReceipt(
        id="chronology-withdraw-receipt",
        user_id="chronology-withdraw-owner",
        stage_id=road_10k_control.ROAD_10K_STAGE_ID,
        capability_id="outdoor_road_10k_performance_v1",
        schema_version=2,
        policy_version=road_10k_control.ROAD_10K_POLICY_VERSION,
        authority_digest="a" * 64,
        notice_digest="b" * 64,
        cohort_rule_digest="c" * 64,
        sampling_run_evidence_digest="d" * 64,
        invitation_idempotency_key="chronology-withdraw-invitation",
        state="exposed",
        invitation_issued_at=invited_at,
        enrolled_at=enrolled_at,
        first_exposed_at=exposed_at,
        created_at=invited_at,
        updated_at=exposed_at,
    )
    db.add(receipt)
    db.commit()

    receipt.state = "withdrawn"
    receipt.withdrawn_at = enrolled_at + timedelta(seconds=30)
    receipt.updated_at = receipt.withdrawn_at
    with pytest.raises(IntegrityError):
        db.commit()


def test_create_all_rejects_deletion_before_withdrawal(tmp_path):
    db = _db(tmp_path)
    _owner(db, "chronology-delete-owner")
    invited_at = datetime(2026, 8, 1, 10, 0, 0)
    enrolled_at = invited_at + timedelta(minutes=1)
    exposed_at = invited_at + timedelta(minutes=2)
    withdrawn_at = invited_at + timedelta(minutes=3)
    receipt = Road10KOwnerStageReceipt(
        id="chronology-delete-receipt",
        user_id="chronology-delete-owner",
        stage_id=road_10k_control.ROAD_10K_STAGE_ID,
        capability_id="outdoor_road_10k_performance_v1",
        schema_version=2,
        policy_version=road_10k_control.ROAD_10K_POLICY_VERSION,
        authority_digest="a" * 64,
        notice_digest="b" * 64,
        cohort_rule_digest="c" * 64,
        sampling_run_evidence_digest="d" * 64,
        invitation_idempotency_key="chronology-delete-invitation",
        state="withdrawn",
        invitation_issued_at=invited_at,
        enrolled_at=enrolled_at,
        first_exposed_at=exposed_at,
        withdrawn_at=withdrawn_at,
        created_at=invited_at,
        updated_at=withdrawn_at,
    )
    db.add(receipt)
    db.commit()

    receipt.user_id = None
    receipt.state = "deleted"
    receipt.deleted_at = exposed_at + timedelta(seconds=30)
    receipt.updated_at = receipt.deleted_at
    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize(
    "mismatch",
    ["receipt_id", "stage", "user", "authority", "state", "timestamp"],
)
def test_create_all_exposure_insert_requires_exact_owner_receipt(
    tmp_path,
    mismatch,
):
    db = _db(tmp_path)
    _owner(db, "exposure-owner")
    _owner(db, "other-exposure-owner")
    invited_at = datetime(2026, 8, 1, 10, 0, 0)
    enrolled_at = invited_at + timedelta(minutes=1)
    exposed_at = invited_at + timedelta(minutes=2)
    state = "enrolled_unexposed" if mismatch == "state" else "exposed"
    receipt = Road10KOwnerStageReceipt(
        id="exact-owner-receipt",
        user_id="exposure-owner",
        stage_id=road_10k_control.ROAD_10K_STAGE_ID,
        capability_id="outdoor_road_10k_performance_v1",
        schema_version=2,
        policy_version=road_10k_control.ROAD_10K_POLICY_VERSION,
        authority_digest="a" * 64,
        notice_digest="b" * 64,
        cohort_rule_digest="c" * 64,
        sampling_run_evidence_digest="d" * 64,
        invitation_idempotency_key=f"exact-exposure-{mismatch}",
        state=state,
        invitation_issued_at=invited_at,
        enrolled_at=enrolled_at,
        first_exposed_at=None if mismatch == "state" else exposed_at,
        created_at=invited_at,
        updated_at=enrolled_at if mismatch == "state" else exposed_at,
    )
    db.add(receipt)
    db.commit()

    values = {
        "owner_stage_receipt_id": receipt.id,
        "stage_id": receipt.stage_id,
        "user_id": receipt.user_id,
        "authority_digest": receipt.authority_digest,
        "exposed_at": exposed_at,
    }
    if mismatch == "receipt_id":
        values["owner_stage_receipt_id"] = "different-receipt"
    elif mismatch == "stage":
        values["stage_id"] = "different-stage"
    elif mismatch == "user":
        values["user_id"] = "other-exposure-owner"
    elif mismatch == "authority":
        values["authority_digest"] = "e" * 64
    elif mismatch == "timestamp":
        values["exposed_at"] = exposed_at + timedelta(microseconds=1)

    db.add(
        Road10KExposureReceipt(
            id=f"mismatched-exposure-{mismatch}",
            **values,
        )
    )
    with pytest.raises(IntegrityError, match="exposure receipt mismatch"):
        db.commit()


def test_first_exposure_after_authority_refresh_uses_receipt_authority(
    tmp_path,
    monkeypatch,
):
    db = _db(tmp_path)
    _owner(db, "authority-refresh-first-exposure")
    initial = _authority()
    monkeypatch.setattr(road_10k_control, "load_stage_authority", lambda: initial)
    receipt = issue_invitation(
        db,
        user_id="authority-refresh-first-exposure",
        idempotency_key=_invitation_key("authority-refresh-first-exposure"),
        notice_digest=initial.notice_digest,
        cohort_rule_digest=initial.cohort_rule_digest,
    )
    enroll_owner(
        db,
        user_id="authority-refresh-first-exposure",
        notice_digest=initial.notice_digest,
    )
    refreshed = replace(initial, authority_digest="e" * 64)
    monkeypatch.setattr(road_10k_control, "load_stage_authority", lambda: refreshed)

    record_result(
        db,
        user_id="authority-refresh-first-exposure",
        result_code="validation_failed",
        payload={"scope": "authority-refresh"},
    )

    exposure = db.query(Road10KExposureReceipt).one()
    assert exposure.authority_digest == receipt.authority_digest
    assert exposure.exposed_at == db.get(
        Road10KOwnerStageReceipt, receipt.id
    ).first_exposed_at


def test_ledger_migration_source_covers_chronology_and_exposure_match():
    migration = Path(
        "alembic/versions/d2e3f4a5b6c7_add_road_10k_control_ledger.py"
    ).read_text(encoding="utf-8")

    for required in (
        "(enrolled_at IS NULL OR withdrawn_at >= enrolled_at)",
        "(withdrawn_at IS NULL OR deleted_at >= withdrawn_at)",
        "NEW.withdrawn_at >= OLD.updated_at",
        "NEW.deleted_at >= OLD.updated_at",
        "trg_road_10k_exposure_receipts_insert_match",
        "road_10k_exposure_receipts_insert_match()",
        "owner_receipt.user_id IS NOT DISTINCT FROM NEW.user_id",
        "owner_receipt.first_exposed_at = NEW.exposed_at",
        "DROP FUNCTION IF EXISTS road_10k_exposure_receipts_insert_match()",
    ):
        assert required in migration


def test_road_10k_ops_docs_keep_hard_off_and_storage_boundaries_exact():
    deploy = Path("docs/ops/deploy.md").read_text(encoding="utf-8")
    setup = Path("docs/deployment.md").read_text(encoding="utf-8")
    monitoring = Path("docs/ops/monitoring-and-alerts.md").read_text(
        encoding="utf-8"
    )

    assert "Only a committed Road 10K database deletion obligation" in deploy
    assert "visible Road 10K authority or committed replay obligation" not in deploy
    road_setup = setup.split("### Road 10K foundation", 1)[1].split("## CI/CD", 1)[0]
    normalized_road_setup = " ".join(road_setup.split())
    assert (
        "unconditionally hard-off before stage-authority evaluation"
        in normalized_road_setup
    )
    assert "paused" not in road_setup
    assert "killed" not in road_setup
    assert "fixed ceiling fields are always present" in monitoring
    assert "pending, not_required, or blocked" in monitoring
