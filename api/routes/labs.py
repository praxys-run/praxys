"""Authenticated lifecycle endpoints for Praxys Labs experiments."""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Response,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from analysis.metrics import estimate_wet_bulb_c
from api.auth import get_current_user_id, require_write_access
from api.labs_environment import (
    CONSENT_VERSION,
    EXPERIMENT_ID,
    RecomputeLimitError,
    adult_eligibility_reason,
    enroll,
    environment_response_preflight,
    public_state,
    queue_recompute,
    withdraw,
)
from api.labs_dispatch import dispatch_job, notify_dispatcher
from api.labs_tombstone_storage import TombstoneStorageError
from api.views import utc_isoformat
from db.session import get_db

router = APIRouter()
IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$",
    ),
]


class EnvironmentEnrollmentRequest(BaseModel):
    """Explicit consent submitted against the currently displayed text."""

    model_config = ConfigDict(extra="forbid")

    adult_attested: Annotated[bool, Field(strict=True)]
    consent_version: str


class EnvironmentWetBulbRequest(BaseModel):
    """Temperature and humidity inputs for the non-persisted calculator."""

    model_config = ConfigDict(extra="forbid")

    temperature_c: Annotated[
        float,
        Field(strict=True, allow_inf_nan=False),
    ]
    relative_humidity_pct: Annotated[
        float,
        Field(strict=True, allow_inf_nan=False),
    ]


class EnvironmentWetBulbResponse(BaseModel):
    """Versioned Stull estimate with an explicit method boundary."""

    model_config = ConfigDict(extra="forbid")

    temperature_c: float
    relative_humidity_pct: float
    wet_bulb_c: float | None
    within_method_domain: bool
    method: Literal["stull_psychrometric"]
    source_url: str
    limitation_code: Literal[
        "psychrometric_proxy_not_wbgt",
        "outside_method_domain",
    ]


class EnvironmentObservedAggregate(BaseModel):
    """Small non-identifying counts included in availability diagnostics."""

    model_config = ConfigDict(extra="forbid")

    eligible_activity_count: int | None = None
    eligible_segment_count: int | None = None
    observed_wet_bulb_domain_c: list[float] | None = None


class EnvironmentAvailabilityReason(BaseModel):
    """Privacy-safe diagnostic returned when no curve is available."""

    model_config = ConfigDict(extra="forbid")

    code: str
    category: str
    public_message_key: str
    observed_aggregate: EnvironmentObservedAggregate | None
    required_guardrail: str
    user_actionable: bool
    suggested_action_key: str
    analysis_stage: str
    power_regime: str
    model_version: str
    correlation_id: str


class EnvironmentCurvePoint(BaseModel):
    """One aggregate modeled point within observed environmental support."""

    model_config = ConfigDict(extra="forbid")

    wet_bulb_c: float
    modeled_hr_bpm: float
    relative_hr_bpm: float
    relative_lower_bpm: float
    relative_upper_bpm: float
    reference_wet_bulb_c: float
    support_bin_index: int
    section_index: int


class EnvironmentProviderRegime(BaseModel):
    """Aggregate provider combination count, never an activity identity."""

    model_config = ConfigDict(extra="forbid")

    label: str
    activity_count: int
    segment_count: int


class EnvironmentReferencePowerFunnel(BaseModel):
    """Aggregate activity counts through comparable-power support stages."""

    model_config = ConfigDict(extra="forbid")

    environment_activity_count: int
    any_valid_sample_activity_count: int
    continuous_coverage_activity_count: int
    stable_segment_mean_activity_count: int
    training_partition_activity_count: int
    final_reference_power_activity_count: int


class EnvironmentCurveSupportBin(BaseModel):
    """Aggregate display-domain support for one prespecified bin."""

    model_config = ConfigDict(extra="forbid")

    bin_index: int
    lower_wet_bulb_c: float
    upper_wet_bulb_c: float
    activity_count: int
    segment_count: int
    reference_power_activity_count: int
    required_activity_count: int
    required_segment_count: int
    required_reference_power_activity_count: int
    supported: bool
    support_failure_reasons: list[str]
    reference_power_funnel: EnvironmentReferencePowerFunnel


class EnvironmentEligibilityCounts(BaseModel):
    """Aggregate-only coverage retained for audit and explanation."""

    model_config = ConfigDict(extra="forbid")

    input_activity_count: int
    input_segment_count: int
    eligible_activity_count: int
    eligible_segment_count: int
    exclusion_reason_counts: dict[str, int]
    provider_regimes: list[EnvironmentProviderRegime]
    observed_wet_bulb_domain_c: list[float] | None = None
    curve_support_bins: list[EnvironmentCurveSupportBin] | None = None
    displayed_wet_bulb_domains_c: list[list[float]] | None = None


class EnvironmentLeaveOneOut(BaseModel):
    """Aggregate activity-influence diagnostic."""

    model_config = ConfigDict(extra="forbid")

    evaluated_activity_count: int
    sign_agreement: float
    maximum_relative_change: float | None


class EnvironmentUncertainty(BaseModel):
    """Descriptive coefficient uncertainty; fields are absent when unevaluable."""

    model_config = ConfigDict(extra="forbid")

    estimate_bpm_per_c: float | None = None
    interval_bpm_per_c: list[float | None] | None = None
    interval_method: str | None = None
    interval_width_to_absolute_estimate_ratio: float | None = None
    leave_one_activity_out: EnvironmentLeaveOneOut | None = None


class EnvironmentResult(BaseModel):
    """Aggregate-only persisted result."""

    model_config = ConfigDict(extra="forbid")

    result_state: Literal[
        "historical_association_only",
        "insufficient_data",
        "unstable_association",
        "prediction_unavailable",
    ]
    prediction_status: Literal[
        "unavailable",
        "passed_research_diagnostics",
        "failed_research_diagnostics",
    ]
    eligibility_counts: EnvironmentEligibilityCounts
    aggregate_curve_points: list[EnvironmentCurvePoint]
    aggregate_uncertainty: EnvironmentUncertainty
    gate_statuses: dict[str, Literal["pass", "fail", "unavailable"]]
    computed_at: str
    source_revision: str
    model_version: str
    power_regime: str


class EnvironmentResponseState(BaseModel):
    """Stable state contract shared by read and mutation responses."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    consent_version: str
    model_version: str
    enrolled: bool
    status: Literal[
        "not_enrolled",
        "queued",
        "processing",
        "available",
        "unavailable",
        "failed",
        "stale",
    ]
    adult_attestation_required: bool
    power_regime: str
    availability_reason: EnvironmentAvailabilityReason | None
    result: EnvironmentResult | None
    consented_at: str | None = None
    adult_attested_at: str | None = None
    source_revision: str | None = None
    correlation_id: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    execution: "EnvironmentExecutionState"


class EnvironmentRecomputePolicy(BaseModel):
    """Server-authoritative manual recompute policy."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reason: Literal[
        "not_enrolled",
        "active_job",
        "cooldown",
        "daily_limit",
    ] | None
    available_at: str | None
    retry_after_seconds: int | None
    remaining_requests: int
    window_hours: int
    cooldown_hours: int


class EnvironmentExecutionState(BaseModel):
    """Durable queue/worker state for the current or latest generation."""

    model_config = ConfigDict(extra="forbid")

    job_status: Literal[
        "queued",
        "dispatched",
        "processing",
        "retrying",
        "succeeded",
        "failed",
        "cancelled",
        "dead_lettered",
    ] | None
    attempt_count: int
    retryable_failure: bool
    requested_at: str | None
    dispatched_at: str | None
    recompute: EnvironmentRecomputePolicy


EnvironmentResponseState.model_rebuild()


class EnvironmentPreflightObserved(BaseModel):
    """Aggregate prerequisite counts; no activity identities or samples."""

    model_config = ConfigDict(extra="forbid")

    candidate_activity_count: int
    temperature_activity_count: int
    humidity_activity_count: int
    environment_activity_count: int
    power_activity_count: int
    heart_rate_activity_count: int
    complete_any_provider_activity_count: int
    stryd_power_activity_count: int
    complete_stryd_activity_count: int
    provider_aligned_cp_activity_count: int


class EnvironmentPreflightResponse(BaseModel):
    """Fast prerequisite estimate before the full scientific analysis."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "likely_eligible",
        "ineligible",
        "needs_full_analysis",
    ]
    can_start_analysis: bool
    reason_code: str | None
    minimum_activity_count: int
    observed: EnvironmentPreflightObserved
    full_analysis_still_required: Literal[True]


@router.post(
    "/labs/environment-response/wet-bulb",
    response_model=EnvironmentWetBulbResponse,
)
def calculate_environment_wet_bulb(
    body: EnvironmentWetBulbRequest,
    _user_id: str = Depends(get_current_user_id),
) -> dict:
    """Calculate the non-persisted Stull psychrometric wet-bulb proxy."""
    estimate = estimate_wet_bulb_c(
        body.temperature_c,
        body.relative_humidity_pct,
    )
    return {
        "temperature_c": body.temperature_c,
        "relative_humidity_pct": body.relative_humidity_pct,
        "wet_bulb_c": estimate,
        "within_method_domain": estimate is not None,
        "method": "stull_psychrometric",
        "source_url": "https://doi.org/10.1175/JAMC-D-11-0143.1",
        "limitation_code": (
            "psychrometric_proxy_not_wbgt"
            if estimate is not None
            else "outside_method_domain"
        ),
    }


@router.get(
    "/labs/environment-response/preflight",
    response_model=EnvironmentPreflightResponse,
)
def get_environment_response_preflight(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Return fast definite blockers without running or storing analysis."""
    return environment_response_preflight(db, user_id)


def _require_preflight_eligibility(db: Session, user_id: str) -> None:
    preflight = environment_response_preflight(db, user_id)
    if not preflight["can_start_analysis"]:
        raise HTTPException(
            409,
            detail={
                "code": "LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE",
                "preflight": preflight,
            },
        )


def _schedule(
    background_tasks: BackgroundTasks,
    job_id: str | None,
) -> None:
    if job_id is None:
        return
    background_tasks.add_task(dispatch_job, job_id)
    notify_dispatcher()


@router.get(
    "/labs/environment-response",
    response_model=EnvironmentResponseState,
)
def get_environment_response(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Return consent, processing, diagnostics, and aggregate result state."""
    return public_state(db, user_id)


@router.post(
    "/labs/environment-response",
    status_code=202,
    response_model=EnvironmentResponseState,
)
def enroll_environment_response(
    body: EnvironmentEnrollmentRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: IdempotencyKey = None,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Record explicit consent and queue private aggregate computation."""
    try:
        decision = enroll(
            db,
            user_id,
            adult_attested=body.adult_attested,
            consent_version=body.consent_version,
            idempotency_key=idempotency_key,
            eligibility_check=lambda: _require_preflight_eligibility(
                db,
                user_id,
            ),
        )
    except ValueError as exc:
        code = str(exc)
        if code == "adult_eligibility_not_confirmed":
            raise HTTPException(
                422,
                detail=adult_eligibility_reason(),
            ) from exc
        if code == "consent_version_stale":
            raise HTTPException(
                409,
                detail={
                    "code": code,
                    "current_consent_version": CONSENT_VERSION,
                },
            ) from exc
        raise
    _schedule(
        background_tasks,
        None if decision.job is None else decision.job.id,
    )
    return public_state(db, user_id)


@router.post(
    "/labs/environment-response/recompute",
    status_code=202,
    response_model=EnvironmentResponseState,
)
def recompute_environment_response(
    background_tasks: BackgroundTasks,
    idempotency_key: IdempotencyKey = None,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Queue a fresh result under the existing explicit consent."""
    try:
        decision = queue_recompute(
            db,
            user_id,
            idempotency_key=idempotency_key,
            eligibility_check=lambda: _require_preflight_eligibility(
                db,
                user_id,
            ),
        )
    except RecomputeLimitError as exc:
        retry_after = max(
            1,
            int((exc.available_at - datetime.utcnow()).total_seconds() + 0.999),
        )
        code = (
            "LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN"
            if exc.code == "cooldown"
            else "LABS_ENVIRONMENT_RECOMPUTE_DAILY_LIMIT"
        )
        raise HTTPException(
            429,
            detail={
                "code": code,
                "message": (
                    "This experiment can be recomputed after the current "
                    "cooldown."
                    if exc.code == "cooldown"
                    else "The rolling daily recompute limit has been reached."
                ),
                "available_at": utc_isoformat(exc.available_at),
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        ) from exc
    if decision is None:
        raise HTTPException(
            409,
            detail={
                "code": "LABS_ENVIRONMENT_NOT_ENROLLED",
                "message": "Current experiment consent is required.",
            },
        )
    _schedule(
        background_tasks,
        None if decision.job is None else decision.job.id,
    )
    return public_state(db, user_id)


@router.delete("/labs/environment-response", status_code=204)
def withdraw_environment_response(
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> Response:
    """Withdraw consent and immediately delete the aggregate result."""
    try:
        withdraw(db, user_id)
    except TombstoneStorageError as exc:
        db.rollback()
        raise HTTPException(
            503,
            detail="LABS_WITHDRAWAL_STORAGE_UNAVAILABLE",
        ) from exc
    return Response(status_code=204)
