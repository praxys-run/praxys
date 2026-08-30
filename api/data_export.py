"""Privacy-safe self-service export of caller-owned training data."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from analysis.config import load_config_from_db
from api.views import utc_isoformat
from db.models import (
    AdaptivePlan,
    AdaptivePlanGoalSnapshot,
    Activity,
    ActivitySample,
    ActivitySplit,
    AiInsight,
    AiInsightFeedback,
    Feedback,
    FitnessData,
    GoalBaselineAssessment,
    GoalBaselineConfirmation,
    GoalBaselineSnapshot,
    GoalBaselineTestRecord,
    Outdoor5KPlanGeneration,
    Road10KBaselineConfirmation,
    Road10KBaselineSnapshot,
    Road10KPlanGeneration,
    Road10KTrainingPatternSnapshot,
    RecoveryData,
    PlanProposal,
    TermsAcceptanceReceipt,
    TrainingPlan,
    User,
    UserConnection,
)


_SENSITIVE_KEY_PARTS = frozenset({
    "credential",
    "token",
    "password",
    "secret",
    "encrypted",
    "wrapped",
    "authorization",
    "private_key",
})

_ACCOUNT_FIELDS = (
    "id",
    "email",
    "is_active",
    "is_superuser",
    "is_verified",
    "created_at",
    "last_seen_at",
    "terms_version",
    "terms_digest",
    "terms_accepted_at",
    "wechat_openid",
    "wechat_unionid",
    "wechat_nickname",
    "wechat_avatar_url",
)
_CONNECTION_FIELDS = (
    "platform",
    "preferences",
    "last_sync",
    "status",
    "consecutive_failures",
    "next_retry_at",
    "last_error",
    "tokens_updated_at",
)
_ACTIVITY_FIELDS = (
    "activity_id",
    "date",
    "activity_type",
    "distance_km",
    "duration_sec",
    "temperature_c",
    "relative_humidity_pct",
    "environment_source",
    "avg_power",
    "max_power",
    "avg_hr",
    "max_hr",
    "avg_pace_min_km",
    "avg_pace_sec_km",
    "elevation_gain_m",
    "avg_cadence",
    "training_effect",
    "rss",
    "trimp",
    "rtss",
    "cp_estimate",
    "load_score",
    "start_time",
    "source",
)
_ACTIVITY_SAMPLE_FIELDS = (
    "activity_id",
    "source",
    "t_sec",
    "power_watts",
    "hr_bpm",
    "speed_ms",
    "pace_sec_km",
    "cadence_spm",
    "altitude_m",
    "distance_m",
    "lat",
    "lng",
    "grade_pct",
    "temperature_c",
    "ground_time_ms",
    "oscillation_mm",
    "leg_spring_kn_m",
    "vertical_ratio",
    "form_power_watts",
    "respiration_rate",
)
_ACTIVITY_SPLIT_FIELDS = (
    "activity_id",
    "split_num",
    "distance_km",
    "duration_sec",
    "avg_power",
    "power_source",
    "avg_hr",
    "max_hr",
    "avg_pace_min_km",
    "avg_pace_sec_km",
    "avg_cadence",
    "elevation_change_m",
)
_RECOVERY_FIELDS = (
    "date",
    "readiness_score",
    "hrv_avg",
    "resting_hr",
    "sleep_score",
    "total_sleep_sec",
    "deep_sleep_sec",
    "rem_sleep_sec",
    "body_temp_delta",
    "source",
)
_FITNESS_FIELDS = (
    "date",
    "metric_type",
    "value",
    "value_str",
    "source",
    "power_source",
)
_TRAINING_PLAN_FIELDS = (
    "canonical_id",
    "adaptive_plan_id",
    "date",
    "activity_type",
    "workout_type",
    "planned_duration_min",
    "planned_distance_km",
    "target_power_min",
    "target_power_max",
    "target_hr_min",
    "target_hr_max",
    "target_pace_min",
    "target_pace_max",
    "workout_description",
    "workout_structure_version",
    "workout_structure",
    "source",
    "workout_origin",
    "external_id",
    "start_time",
    "meta",
)
_AI_INSIGHT_FIELDS = (
    "insight_type",
    "headline",
    "summary",
    "findings",
    "recommendations",
    "meta",
    "translations",
    "generated_at",
)
_AI_INSIGHT_FEEDBACK_FIELDS = (
    "insight_type",
    "dataset_hash",
    "vote",
    "submitted_at",
)
_TERMS_RECEIPT_FIELDS = (
    "id",
    "action",
    "terms_version",
    "terms_digest",
    "locale",
    "channel",
    "client_version",
    "source_sha",
    "notice_version",
    "release_id",
    "accepted_at",
)

_ADAPTIVE_GOAL_SNAPSHOT_FIELDS = (
    "id",
    "version",
    "state",
    "purpose_source",
    "source_goal_id",
    "source_goal_revision",
    "goal_kind",
    "target",
    "horizon_start",
    "horizon_end",
    "snapshot",
    "acknowledged_at",
    "created_at",
)
_ADAPTIVE_PLAN_FIELDS = (
    "id",
    "goal_snapshot_id",
    "discipline",
    "lifecycle",
    "version",
    "active_proposal_id",
    "created_at",
    "updated_at",
)
_PLAN_PROPOSAL_FIELDS = (
    "id",
    "adaptive_plan_id",
    "goal_snapshot_id",
    "discipline",
    "version",
    "state",
    "origin",
    "actor_type",
    "actor_id",
    "base_plan_version",
    "supersedes_proposal_id",
    "policy_version",
    "model_version",
    "science_version",
    "assumptions",
    "unknowns",
    "warnings",
    "alternatives",
    "expires_at",
    "created_at",
    "decided_at",
    "workout_snapshot",
)
_OUTDOOR_5K_PLAN_GENERATION_FIELDS = (
    "id",
    "proposal_id",
    "policy_version",
    "generator_version",
    "science_decision_id",
    "evidence_review_ids",
    "evidence_claim_ids",
    "ai_explanation_present",
    "baseline_snapshot_id",
    "source_revision",
    "deterministic_input_hash",
    "request_kind",
    "request_fingerprint",
    "predecessor_proposal_id",
    "predecessor_version",
    "observed_input_snapshot",
    "constraint_snapshot",
    "derived_history_statistics",
    "validation_results",
    "created_at",
)
_ROAD_10K_BASELINE_CONFIRMATION_FIELDS = (
    "id",
    "lineage_id",
    "version",
    "supersedes_id",
    "goal_signature",
    "goal_snapshot",
    "activity_id",
    "response",
    "measured_10k",
    "elapsed_timing_confirmed",
    "completed_at",
    "elapsed_time_sec",
    "surface_or_protocol",
    "route_or_venue_identifier",
    "assistance_status",
    "source_provider",
    "created_at",
)
_ROAD_10K_BASELINE_SNAPSHOT_FIELDS = (
    "id",
    "lineage_id",
    "version",
    "supersedes_id",
    "goal_signature",
    "goal_snapshot",
    "source_kind",
    "source_id",
    "provenance",
    "observed_date",
    "completed_at",
    "distance_km",
    "elapsed_time_sec",
    "measured_10k",
    "elapsed_timing_confirmed",
    "surface_or_protocol",
    "route_or_venue_identifier",
    "assistance_status",
    "source_provider",
    "qualification_status",
    "change_comparability",
    "invalidators",
    "created_at",
)
_ROAD_10K_PLAN_GENERATION_FIELDS = (
    "id",
    "proposal_id",
    "capability_id",
    "policy_version",
    "generator_version",
    "science_decision_id",
    "source_decision_digest",
    "contract_digest",
    "baseline_snapshot_id",
    "baseline_source",
    "source_goal_id",
    "source_goal_revision",
    "history_cutoff_completed_days",
    "training_pattern_snapshot_version",
    "event_context_snapshot_version",
    "active_zone_model_id",
    "active_zone_model_version",
    "normalized_constraints",
    "selected_template_ids",
    "source_revision",
    "deterministic_input_hash",
    "request_kind",
    "request_fingerprint",
    "predecessor_proposal_id",
    "predecessor_version",
    "result_code",
    "validation_reason_code",
    "created_at",
)
_ROAD_10K_TRAINING_PATTERN_SNAPSHOT_FIELDS = (
    "version",
    "schema_version",
    "policy_version",
    "usable_completed_weeks",
    "recent_modal_running_frequency",
    "recent_median_usable_weekly_minutes",
    "recent_maximum_usable_weekly_minutes",
    "recent_maximum_session_minutes",
    "recent_maximum_session_distance_km",
    "latest_run_date",
    "history_observation_count",
    "history_provenance_fingerprint",
    "intensity_observation_count",
    "intensity_provenance_fingerprint",
    "reserved_date_count",
    "reservation_fingerprint",
    "canonical_fingerprint",
    "created_at",
)

_GOAL_BASELINE_CONFIRMATION_FIELDS = (
    "id",
    "lineage_id",
    "version",
    "supersedes_id",
    "goal_signature",
    "goal_snapshot",
    "activity_id",
    "response",
    "measured_5k",
    "elapsed_timing_confirmed",
    "created_at",
)
_GOAL_BASELINE_TEST_FIELDS = (
    "id",
    "lineage_id",
    "version",
    "supersedes_id",
    "goal_signature",
    "goal_snapshot",
    "purpose_source",
    "source_goal_id",
    "source_goal_revision",
    "state",
    "protocol_id",
    "scheduled_date",
    "plan_canonical_id",
    "activity_id",
    "observed_date",
    "measured_5k",
    "elapsed_timing_confirmed",
    "protocol_followed",
    "reason_code",
    "safety_stop",
    "created_at",
)
_GOAL_BASELINE_SNAPSHOT_FIELDS = (
    "id",
    "lineage_id",
    "version",
    "supersedes_id",
    "goal_signature",
    "goal_snapshot",
    "source_kind",
    "source_id",
    "provenance",
    "observed_date",
    "distance_km",
    "elapsed_time_sec",
    "measured_5k",
    "elapsed_timing_confirmed",
    "qualification_status",
    "change_comparability",
    "invalidators",
    "created_at",
)
_GOAL_BASELINE_ASSESSMENT_FIELDS = (
    "id",
    "lineage_id",
    "version",
    "supersedes_id",
    "goal_signature",
    "goal_snapshot",
    "policy_version",
    "science_decision_id",
    "status",
    "readiness",
    "evidence_snapshot_id",
    "test_record_id",
    "candidate_count",
    "created_at",
)


def _json_value(value: Any) -> Any:
    """Convert database scalar values to JSON-safe export values."""
    if isinstance(value, datetime):
        return utc_isoformat(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _without_credentials(value: Any) -> Any:
    """Remove credential-shaped keys from flexible JSON configuration fields."""
    if isinstance(value, dict):
        return {
            key: _without_credentials(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_without_credentials(item) for item in value]
    return _json_value(value)


def _serialize_rows(
    rows: Iterable[Any],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Serialize explicit export fields without internal ownership columns."""
    return [
        {field: _without_credentials(getattr(row, field)) for field in fields}
        for row in rows
    ]


def build_user_data_export(user_id: str, db: Session) -> dict[str, Any]:
    """Return the requested user's portable training data without credentials."""
    from api.personal_context import build_personal_context_export

    user = db.query(User).filter(User.id == user_id).one()
    config = _without_credentials(asdict(load_config_from_db(user_id, db)))
    return {
        "schema_version": 6,
        "exported_at": utc_isoformat(datetime.now(timezone.utc)),
        "account": {
            field: _without_credentials(getattr(user, field))
            for field in _ACCOUNT_FIELDS
        },
        "user_config": config,
        "connections": _serialize_rows(
            db.query(UserConnection)
            .filter(UserConnection.user_id == user_id)
            .order_by(UserConnection.platform, UserConnection.id)
            .all(),
            _CONNECTION_FIELDS,
        ),
        "activities": _serialize_rows(
            db.query(Activity)
            .filter(Activity.user_id == user_id)
            .order_by(Activity.date, Activity.id)
            .all(),
            _ACTIVITY_FIELDS,
        ),
        "activity_splits": _serialize_rows(
            db.query(ActivitySplit)
            .filter(ActivitySplit.user_id == user_id)
            .order_by(ActivitySplit.activity_id, ActivitySplit.split_num, ActivitySplit.id)
            .all(),
            _ACTIVITY_SPLIT_FIELDS,
        ),
        "activity_samples": _serialize_rows(
            db.query(ActivitySample)
            .filter(ActivitySample.user_id == user_id)
            .order_by(
                ActivitySample.activity_id,
                ActivitySample.t_sec,
                ActivitySample.id,
            )
            .all(),
            _ACTIVITY_SAMPLE_FIELDS,
        ),
        "recovery": _serialize_rows(
            db.query(RecoveryData)
            .filter(RecoveryData.user_id == user_id)
            .order_by(RecoveryData.date, RecoveryData.source, RecoveryData.id)
            .all(),
            _RECOVERY_FIELDS,
        ),
        "fitness": _serialize_rows(
            db.query(FitnessData)
            .filter(FitnessData.user_id == user_id)
            .order_by(FitnessData.date, FitnessData.metric_type, FitnessData.source, FitnessData.id)
            .all(),
            _FITNESS_FIELDS,
        ),
        "training_plans": _serialize_rows(
            db.query(TrainingPlan)
            .filter(TrainingPlan.user_id == user_id)
            .order_by(TrainingPlan.date, TrainingPlan.id)
            .all(),
            _TRAINING_PLAN_FIELDS,
        ),
        "ai_insights": _serialize_rows(
            db.query(AiInsight)
            .filter(AiInsight.user_id == user_id)
            .order_by(AiInsight.insight_type, AiInsight.generated_at)
            .all(),
            _AI_INSIGHT_FIELDS,
        ),
        "ai_insight_feedback": _serialize_rows(
            db.query(AiInsightFeedback)
            .filter(AiInsightFeedback.user_id == user_id)
            .order_by(AiInsightFeedback.submitted_at, AiInsightFeedback.id)
            .all(),
            _AI_INSIGHT_FEEDBACK_FIELDS,
        ),
        "feedback": [
            {
                "id": row.id,
                "kind": row.kind,
                "message": row.message,
                "context": _without_credentials(row.context_json),
                "locale": row.locale,
                "status": row.status,
                "ai_title": row.ai_title,
                "ai_body": row.ai_body,
                "ai_labels": _without_credentials(row.ai_labels),
                "priority": row.priority,
                "github_issue_number": row.github_issue_number,
                "github_issue_url": row.github_issue_url,
                "error": row.error,
                "private_image_count": len(row.image_keys or []),
                "private_image_downloads": [
                    f"/api/me/feedback/{row.id}/image/{index}"
                    for index, _key in enumerate(row.image_keys or [])
                ],
                "image_description": row.image_description,
                "image_sensitive": row.image_sensitive,
                "created_at": _json_value(row.created_at),
                "updated_at": _json_value(row.updated_at),
            }
            for row in (
                db.query(Feedback)
                .filter(Feedback.user_id == user_id)
                .order_by(Feedback.created_at, Feedback.id)
                .all()
            )
        ],
        "terms_acceptance_receipts": _serialize_rows(
            db.query(TermsAcceptanceReceipt)
            .filter(TermsAcceptanceReceipt.user_id == user_id)
            .order_by(
                TermsAcceptanceReceipt.accepted_at,
                TermsAcceptanceReceipt.id,
            )
            .all(),
            _TERMS_RECEIPT_FIELDS,
        ),
        "adaptive_plan_proposals": {
            "schema_version": 1,
            "exported_at": utc_isoformat(datetime.now(timezone.utc)),
            "goal_snapshots": _serialize_rows(
                db.query(AdaptivePlanGoalSnapshot)
                .filter(AdaptivePlanGoalSnapshot.user_id == user_id)
                .order_by(AdaptivePlanGoalSnapshot.created_at, AdaptivePlanGoalSnapshot.version)
                .all(),
                _ADAPTIVE_GOAL_SNAPSHOT_FIELDS,
            ),
            "plans": _serialize_rows(
                db.query(AdaptivePlan)
                .filter(AdaptivePlan.user_id == user_id)
                .order_by(AdaptivePlan.created_at, AdaptivePlan.id)
                .all(),
                _ADAPTIVE_PLAN_FIELDS,
            ),
            "proposals": _serialize_rows(
                db.query(PlanProposal)
                .filter(PlanProposal.user_id == user_id)
                .order_by(PlanProposal.created_at, PlanProposal.version)
                .all(),
                _PLAN_PROPOSAL_FIELDS,
            ),
        },
        "goal_baseline": {
            "schema_version": 1,
            "exported_at": utc_isoformat(datetime.now(timezone.utc)),
            "confirmations": _serialize_rows(
                db.query(GoalBaselineConfirmation)
                .filter(GoalBaselineConfirmation.user_id == user_id)
                .order_by(GoalBaselineConfirmation.created_at, GoalBaselineConfirmation.version)
                .all(),
                _GOAL_BASELINE_CONFIRMATION_FIELDS,
            ),
            "tests": _serialize_rows(
                db.query(GoalBaselineTestRecord)
                .filter(GoalBaselineTestRecord.user_id == user_id)
                .order_by(GoalBaselineTestRecord.created_at, GoalBaselineTestRecord.version)
                .all(),
                _GOAL_BASELINE_TEST_FIELDS,
            ),
            "snapshots": _serialize_rows(
                db.query(GoalBaselineSnapshot)
                .filter(GoalBaselineSnapshot.user_id == user_id)
                .order_by(GoalBaselineSnapshot.created_at, GoalBaselineSnapshot.version)
                .all(),
                _GOAL_BASELINE_SNAPSHOT_FIELDS,
            ),
            "assessments": _serialize_rows(
                db.query(GoalBaselineAssessment)
                .filter(GoalBaselineAssessment.user_id == user_id)
                .order_by(GoalBaselineAssessment.created_at, GoalBaselineAssessment.version)
                .all(),
                _GOAL_BASELINE_ASSESSMENT_FIELDS,
            ),
        },
        "outdoor_5k_plan_generation": {
            "schema_version": 1,
            "exported_at": utc_isoformat(datetime.now(timezone.utc)),
            "records": _serialize_rows(
                db.query(Outdoor5KPlanGeneration)
                .filter(Outdoor5KPlanGeneration.user_id == user_id)
                .order_by(Outdoor5KPlanGeneration.created_at, Outdoor5KPlanGeneration.id)
                .all(),
                _OUTDOOR_5K_PLAN_GENERATION_FIELDS,
            ),
        },
        "road_10k_baseline": {
            "schema_version": 1,
            "exported_at": utc_isoformat(datetime.now(timezone.utc)),
            "confirmations": _serialize_rows(
                db.query(Road10KBaselineConfirmation)
                .filter(Road10KBaselineConfirmation.user_id == user_id)
                .order_by(
                    Road10KBaselineConfirmation.created_at,
                    Road10KBaselineConfirmation.version,
                )
                .all(),
                _ROAD_10K_BASELINE_CONFIRMATION_FIELDS,
            ),
            "snapshots": _serialize_rows(
                db.query(Road10KBaselineSnapshot)
                .filter(Road10KBaselineSnapshot.user_id == user_id)
                .order_by(
                    Road10KBaselineSnapshot.created_at,
                    Road10KBaselineSnapshot.version,
                )
                .all(),
                _ROAD_10K_BASELINE_SNAPSHOT_FIELDS,
            ),
        },
        "road_10k_plan_generation": {
            "schema_version": 1,
            "exported_at": utc_isoformat(datetime.now(timezone.utc)),
            "training_pattern_snapshots": _serialize_rows(
                db.query(Road10KTrainingPatternSnapshot)
                .filter(Road10KTrainingPatternSnapshot.user_id == user_id)
                .order_by(
                    Road10KTrainingPatternSnapshot.created_at,
                    Road10KTrainingPatternSnapshot.version,
                )
                .all(),
                _ROAD_10K_TRAINING_PATTERN_SNAPSHOT_FIELDS,
            ),
            "records": _serialize_rows(
                db.query(Road10KPlanGeneration)
                .filter(Road10KPlanGeneration.user_id == user_id)
                .order_by(
                    Road10KPlanGeneration.created_at,
                    Road10KPlanGeneration.id,
                )
                .all(),
                _ROAD_10K_PLAN_GENERATION_FIELDS,
            ),
        },
        "personal_context": build_personal_context_export(
            db,
            user_id=user_id,
        ),
    }
