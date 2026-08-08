"""Consent, aggregate persistence, and private processing for Labs V1."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from analysis.environment_response import (
    LABS_ENVIRONMENT_MODEL_VERSION,
    POWER_REGIME,
    build_environment_response_result,
)
from analysis.heat_response_validation import build_research_dataset_bundle
from analysis.metrics import ACTIVITY_RESEARCH_SCHEMA_VERSION
from api.etag import ENDPOINT_SCOPES, compute_revision_token
from api.packs import (
    RequestContext,
    get_activity_research_pack,
    get_analysis_response_version,
)
from api.views import utc_isoformat
from api import labs_tombstone_storage
from db.models import (
    LabsDeletionTombstone,
    LabsExperimentEnrollment,
    LabsExperimentResult,
    User,
)
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

EXPERIMENT_ID = "environment-response-v1"
CONSENT_VERSION = "environment-response-consent-v1"
_SNAPSHOT_SALT = (
    "analysis-export&v="
    f"{get_analysis_response_version(ACTIVITY_RESEARCH_SCHEMA_VERSION)}"
)


class StaleSourceRevision(RuntimeError):
    """Raised when source data changes during private snapshot construction."""


def _locked_enrollment(
    db: Session,
    user_id: str,
    experiment_id: str,
) -> LabsExperimentEnrollment | None:
    return (
        db.query(LabsExperimentEnrollment)
        .filter(
            LabsExperimentEnrollment.user_id == user_id,
            LabsExperimentEnrollment.experiment_id == experiment_id,
        )
        .with_for_update()
        .one_or_none()
    )


def source_revision(db: Session, user_id: str) -> str:
    """Return the owner-bound source revision used to fence one computation."""
    return compute_revision_token(
        db,
        user_id,
        ENDPOINT_SCOPES["analysis"],
        salt=_SNAPSHOT_SALT,
    )


def enroll(
    db: Session,
    user_id: str,
    *,
    adult_attested: bool,
    consent_version: str,
) -> LabsExperimentEnrollment:
    """Create or replace explicit consent and queue aggregate computation."""
    if not adult_attested:
        raise ValueError("adult_eligibility_not_confirmed")
    if consent_version != CONSENT_VERSION:
        raise ValueError("consent_version_stale")
    begin_serialized_write(db)
    now = datetime.utcnow()
    revision = source_revision(db, user_id)
    row = _locked_enrollment(db, user_id, EXPERIMENT_ID)
    if row is None:
        row = LabsExperimentEnrollment(
            user_id=user_id,
            experiment_id=EXPERIMENT_ID,
            consent_version=CONSENT_VERSION,
            consented_at=now,
            adult_attested_at=now,
            status="queued",
            model_version=LABS_ENVIRONMENT_MODEL_VERSION,
            source_revision=revision,
            correlation_id=str(uuid4()),
            queued_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.consent_version = CONSENT_VERSION
        row.consented_at = now
        row.adult_attested_at = now
        row.status = "queued"
        row.model_version = LABS_ENVIRONMENT_MODEL_VERSION
        row.source_revision = revision
        row.correlation_id = str(uuid4())
        row.availability_reason = None
        row.queued_at = now
        row.started_at = None
        row.completed_at = None
        row.updated_at = now
    db.query(LabsExperimentResult).filter(
        LabsExperimentResult.user_id == user_id,
        LabsExperimentResult.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(row)
    return row


def queue_recompute(
    db: Session,
    user_id: str,
) -> LabsExperimentEnrollment | None:
    """Queue a fresh computation without changing the active consent time."""
    begin_serialized_write(db)
    row = _locked_enrollment(db, user_id, EXPERIMENT_ID)
    if row is None:
        db.rollback()
        return None
    now = datetime.utcnow()
    row.status = "queued"
    row.model_version = LABS_ENVIRONMENT_MODEL_VERSION
    row.source_revision = source_revision(db, user_id)
    row.correlation_id = str(uuid4())
    row.availability_reason = None
    row.queued_at = now
    row.started_at = None
    row.completed_at = None
    row.updated_at = now
    db.query(LabsExperimentResult).filter(
        LabsExperimentResult.user_id == user_id,
        LabsExperimentResult.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(row)
    return row


def recover_interrupted_jobs(
    db: Session,
    *,
    user_id: str | None = None,
    all_processing: bool = False,
) -> int:
    """Return abandoned in-process work to the durable queued state."""
    begin_serialized_write(db)
    query = db.query(LabsExperimentEnrollment).filter(
        LabsExperimentEnrollment.status == "processing",
    )
    if not all_processing:
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        query = query.filter(
            (LabsExperimentEnrollment.started_at.is_(None))
            | (LabsExperimentEnrollment.started_at <= cutoff)
        )
    if user_id is not None:
        query = query.filter(LabsExperimentEnrollment.user_id == user_id)
    rows = query.with_for_update().all()
    now = datetime.utcnow()
    for row in rows:
        row.status = "queued"
        row.correlation_id = str(uuid4())
        row.availability_reason = None
        row.queued_at = now
        row.started_at = None
        row.completed_at = None
        row.updated_at = now
    db.commit()
    return len(rows)


def withdraw(db: Session, user_id: str) -> bool:
    """Delete active consent and aggregate result, retaining only a tombstone."""
    begin_serialized_write(db)
    enrollment = _locked_enrollment(db, user_id, EXPERIMENT_ID)
    deleted_at = datetime.utcnow()
    labs_tombstone_storage.store(
        user_id,
        EXPERIMENT_ID,
        deleted_at,
    )
    existed = enrollment is not None or (
        db.get(LabsExperimentResult, (user_id, EXPERIMENT_ID)) is not None
    )
    db.query(LabsExperimentResult).filter(
        LabsExperimentResult.user_id == user_id,
        LabsExperimentResult.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    db.query(LabsExperimentEnrollment).filter(
        LabsExperimentEnrollment.user_id == user_id,
        LabsExperimentEnrollment.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    tombstone = db.get(LabsDeletionTombstone, (user_id, EXPERIMENT_ID))
    if tombstone is None:
        db.add(LabsDeletionTombstone(
            user_id=user_id,
            experiment_id=EXPERIMENT_ID,
            deleted_at=deleted_at,
        ))
    else:
        tombstone.deleted_at = deleted_at
    db.commit()
    return existed


def replay_deletion_tombstones(db: Session) -> int:
    """Reapply withdrawals after a point-in-time database restore."""
    for external in labs_tombstone_storage.iter_active():
        identity = (
            str(external["user_id"]),
            str(external["experiment_id"]),
        )
        if db.get(User, identity[0]) is None:
            continue
        tombstone = db.get(LabsDeletionTombstone, identity)
        deleted_at = external["deleted_at"]
        if tombstone is None:
            db.add(LabsDeletionTombstone(
                user_id=identity[0],
                experiment_id=identity[1],
                deleted_at=deleted_at,
            ))
        elif tombstone.deleted_at < deleted_at:
            tombstone.deleted_at = deleted_at
    db.flush()
    deleted = 0
    for tombstone in db.query(LabsDeletionTombstone).all():
        deleted += db.query(LabsExperimentResult).filter(
            LabsExperimentResult.user_id == tombstone.user_id,
            LabsExperimentResult.experiment_id == tombstone.experiment_id,
            LabsExperimentResult.computed_at <= tombstone.deleted_at,
        ).delete(synchronize_session=False)
        deleted += db.query(LabsExperimentEnrollment).filter(
            LabsExperimentEnrollment.user_id == tombstone.user_id,
            LabsExperimentEnrollment.experiment_id == tombstone.experiment_id,
            LabsExperimentEnrollment.consented_at <= tombstone.deleted_at,
        ).delete(synchronize_session=False)
    db.commit()
    return deleted


def process_environment_response_job(
    user_id: str,
    experiment_id: str,
    model_version: str,
    expected_source_revision: str,
) -> None:
    """Compute one queued job using only privacy-minimized identifiers."""
    from db import session as db_session

    db = db_session.SessionLocal()
    correlation_id = "unknown"
    try:
        begin_serialized_write(db)
        row = _locked_enrollment(db, user_id, experiment_id)
        if (
            row is None
            or row.status != "queued"
            or row.model_version != model_version
            or row.source_revision != expected_source_revision
        ):
            return
        correlation_id = row.correlation_id
        row.status = "processing"
        row.started_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        db.commit()

        try:
            bundle = _build_private_dataset_bundle(
                db,
                user_id,
                expected_source_revision,
            )
        except StaleSourceRevision:
            _persist_unavailable(
                db,
                user_id,
                experiment_id,
                model_version,
                expected_source_revision,
                correlation_id,
                "stale_source_revision",
                "stale",
            )
            return
        if source_revision(db, user_id) != expected_source_revision:
            _persist_unavailable(
                db,
                user_id,
                experiment_id,
                model_version,
                expected_source_revision,
                correlation_id,
                "stale_source_revision",
                "stale",
            )
            return
        aggregate = build_environment_response_result(bundle)
        if source_revision(db, user_id) != expected_source_revision:
            _persist_unavailable(
                db,
                user_id,
                experiment_id,
                model_version,
                expected_source_revision,
                correlation_id,
                "stale_source_revision",
                "stale",
            )
            return

        db.rollback()
        db.expire_all()
        begin_serialized_write(db)
        row = _locked_enrollment(db, user_id, experiment_id)
        if (
            row is None
            or row.status != "processing"
            or row.model_version != model_version
            or row.source_revision != expected_source_revision
            or row.correlation_id != correlation_id
        ):
            return
        tombstone = db.get(LabsDeletionTombstone, (user_id, experiment_id))
        if tombstone is not None and tombstone.deleted_at >= row.consented_at:
            return
        result = db.get(LabsExperimentResult, (user_id, experiment_id))
        if result is None:
            result = LabsExperimentResult(
                user_id=user_id,
                experiment_id=experiment_id,
            )
            db.add(result)
        result.model_version = model_version
        result.source_revision = expected_source_revision
        result.result_state = aggregate["result_state"]
        result.eligibility_counts = aggregate["eligibility_counts"]
        result.aggregate_curve_points = aggregate["aggregate_curve_points"]
        result.aggregate_uncertainty = aggregate["aggregate_uncertainty"]
        result.gate_statuses = aggregate["gate_statuses"]
        result.prediction_status = aggregate["prediction_status"]
        result.power_regime = aggregate["power_regime"]
        result.computed_at = datetime.utcnow()
        row.status = (
            "available"
            if aggregate["aggregate_curve_points"]
            else "unavailable"
        )
        row.availability_reason = (
            None
            if row.status == "available"
            else availability_reason(
                aggregate,
                correlation_id=correlation_id,
            )
        )
        row.completed_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Labs environment-response processing failed "
            "correlation_id=%s stage=analysis model=%s regime=%s",
            correlation_id,
            model_version,
            POWER_REGIME,
        )
        try:
            _persist_unavailable(
                db,
                user_id,
                experiment_id,
                model_version,
                expected_source_revision,
                correlation_id,
                "analysis_failed",
                "failed",
            )
        except Exception:
            db.rollback()
            logger.exception(
                "Labs failure state persistence failed correlation_id=%s",
                correlation_id,
            )
    finally:
        db.close()


def _build_private_dataset_bundle(
    db: Session,
    user_id: str,
    expected_source_revision: str,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    offset = 0
    limit = 50
    ctx = RequestContext(user_id=user_id, db=db)
    while True:
        if source_revision(db, user_id) != expected_source_revision:
            raise StaleSourceRevision
        page = get_activity_research_pack(
            ctx,
            export_snapshot_id=expected_source_revision,
            limit=limit,
            offset=offset,
        )
        pages.append(page)
        offset += limit
        if offset >= page["total"]:
            break
    return build_research_dataset_bundle(pages)


def _persist_unavailable(
    db: Session,
    user_id: str,
    experiment_id: str,
    model_version: str,
    expected_source_revision: str,
    correlation_id: str,
    code: str,
    status: str,
) -> None:
    db.rollback()
    db.expire_all()
    begin_serialized_write(db)
    row = _locked_enrollment(db, user_id, experiment_id)
    if (
        row is None
        or row.model_version != model_version
        or row.source_revision != expected_source_revision
        or row.correlation_id != correlation_id
        or row.status != "processing"
    ):
        return
    row.status = status
    row.availability_reason = _reason(
        code,
        correlation_id=correlation_id,
    )
    row.completed_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()


def availability_reason(
    aggregate: dict[str, Any],
    *,
    correlation_id: str,
) -> dict[str, Any]:
    """Map aggregate gate failures to the stable public diagnostic taxonomy."""
    gates = aggregate["gate_statuses"]
    exclusions = aggregate.get("eligibility_counts", {}).get(
        "exclusion_reason_counts",
        {},
    )
    exclusion_priority = (
        (
            (
                "power_missing_or_invalid",
                "split_fallback_excluded",
                "stable_segments_unavailable",
            ),
            "missing_continuous_sample_power",
        ),
        (
            ("mean_hr_missing_or_invalid", "heart_rate_provider_missing"),
            "missing_continuous_heart_rate",
        ),
        (
            ("temperature_missing_or_invalid",),
            "missing_temperature",
        ),
        (
            ("relative_humidity_missing_or_invalid",),
            "missing_relative_humidity",
        ),
        (
            (
                "critical_power_contract_missing",
                "critical_power_unavailable",
                "critical_power_value_missing_or_invalid",
                "critical_power_provider_missing",
            ),
            "missing_provider_aligned_critical_power",
        ),
        (
            (
                "critical_power_provider_mismatch",
                "mean_pct_cp_critical_power_mismatch",
                "provider_mismatch_reason_code",
            ),
            "critical_power_provider_mismatch",
        ),
        (
            (
                "activity_sample_coverage_missing",
                "activity_sample_coverage_low",
                "segment_sample_coverage_missing",
                "segment_sample_coverage_low",
            ),
            "insufficient_sample_coverage",
        ),
    )
    priority = (
        ("complete_export", "incomplete_export"),
        ("minimum_activities", "insufficient_activities"),
        ("minimum_segments", "insufficient_segments"),
        ("environmental_spread", "insufficient_environmental_spread"),
        ("chronological_holdout", "insufficient_holdout"),
        ("holdout_environmental_spread", "insufficient_holdout"),
        ("curve_bin_support", "insufficient_curve_bin_support"),
        ("reference_power_overlap", "insufficient_reference_power_overlap"),
        ("provider_regime_consistency", "mixed_power_regime"),
        ("bootstrap_interval_excludes_zero", "bootstrap_unstable"),
        ("bootstrap_interval_width", "bootstrap_unstable"),
        ("sensitivity_analysis_coverage", "sensitivity_unstable"),
        ("coefficient_stability", "sensitivity_unstable"),
        ("leave_one_activity_out_influence", "influential_activity"),
    )
    exclusion_code = next(
        (
            mapped
            for reason_names, mapped in exclusion_priority
            if any(exclusions.get(name, 0) for name in reason_names)
        ),
        None,
    )
    minimum_support_failed = any(
        gates.get(gate_name) != "pass"
        for gate_name in ("minimum_activities", "minimum_segments")
    )
    if exclusion_code is not None and minimum_support_failed:
        code = exclusion_code
    elif gates.get("stryd_power_regime") == "fail":
        combinations = aggregate.get("eligibility_counts", {}).get(
            "provider_regimes",
            [],
        )
        code = (
            "unverified_garmin_wrist_power"
            if any("power=garmin|" in str(item) for item in combinations)
            else "unsupported_power_provider"
        )
    elif aggregate["result_state"] == "prediction_unavailable":
        code = "prediction_unavailable"
    else:
        code = next(
            (
                mapped
                for gate_name, mapped in priority
                if gates.get(gate_name) != "pass"
            ),
            "analysis_failed",
        )
    counts = aggregate.get("eligibility_counts", {})
    observed = {
        key: counts[key]
        for key in (
            "eligible_activity_count",
            "eligible_segment_count",
            "observed_wet_bulb_domain_c",
        )
        if key in counts
    }
    return _reason(
        code,
        correlation_id=correlation_id,
        observed_aggregate=observed or None,
    )


def _reason(
    code: str,
    *,
    correlation_id: str,
    observed_aggregate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    category = (
        "processing"
        if code == "analysis_failed"
        else "eligibility"
        if code == "adult_eligibility_not_confirmed"
        else "data_support"
    )
    return {
        "code": code,
        "category": category,
        "public_message_key": f"labs.environment.reason.{code}",
        "observed_aggregate": observed_aggregate,
        "required_guardrail": code,
        "user_actionable": code not in {
            "analysis_failed",
            "bootstrap_unstable",
            "sensitivity_unstable",
            "influential_activity",
        },
        "suggested_action_key": f"labs.environment.action.{code}",
        "analysis_stage": "environment_response",
        "power_regime": POWER_REGIME,
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "correlation_id": correlation_id,
    }


def adult_eligibility_reason() -> dict[str, Any]:
    """Return a structured diagnostic for a rejected adult attestation."""
    return _reason(
        "adult_eligibility_not_confirmed",
        correlation_id=str(uuid4()),
    )


def public_state(db: Session, user_id: str) -> dict[str, Any]:
    """Return the authenticated, aggregate-only experiment state."""
    row = db.get(LabsExperimentEnrollment, (user_id, EXPERIMENT_ID))
    base = {
        "experiment_id": EXPERIMENT_ID,
        "consent_version": CONSENT_VERSION,
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "enrolled": row is not None,
        "status": "not_enrolled" if row is None else row.status,
        "adult_attestation_required": True,
        "power_regime": POWER_REGIME,
        "availability_reason": None if row is None else row.availability_reason,
        "result": None,
    }
    if row is None:
        return base
    base.update({
        "consented_at": utc_isoformat(row.consented_at),
        "adult_attested_at": utc_isoformat(row.adult_attested_at),
        "source_revision": row.source_revision,
        "correlation_id": row.correlation_id,
        "queued_at": utc_isoformat(row.queued_at),
        "started_at": utc_isoformat(row.started_at),
        "completed_at": utc_isoformat(row.completed_at),
    })
    result = db.get(LabsExperimentResult, (user_id, EXPERIMENT_ID))
    if result is not None:
        base["result"] = {
            "result_state": result.result_state,
            "prediction_status": result.prediction_status,
            "eligibility_counts": result.eligibility_counts,
            "aggregate_curve_points": result.aggregate_curve_points,
            "aggregate_uncertainty": result.aggregate_uncertainty,
            "gate_statuses": result.gate_statuses,
            "computed_at": utc_isoformat(result.computed_at),
            "source_revision": result.source_revision,
            "model_version": result.model_version,
            "power_regime": result.power_regime,
        }
    return base
