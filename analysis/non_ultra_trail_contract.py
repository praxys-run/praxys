"""Accepted machine-contract helpers for inactive non-ultra Trail planning.

The contracts loaded here are intentionally inactive.  Importing this module
does not register a capability, expose an API, or authorize runtime use.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from analysis.science_artifacts import load_policy_contract


NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID = "sdr-trail-running-goal-ontology-v2"
NON_ULTRA_TRAIL_SCIENCE_DECISION_ID = (
    "sdr-non-ultra-trail-plan-generation-policy-v2"
)
NON_ULTRA_TRAIL_GENERATOR_VERSION = (
    "non-ultra-trail-deterministic-generator-v2"
)
NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST = (
    "sha256:363d5970c2ad6f7d4a18ced426d4a2996aef3ff116e6a6b112232c9eccaeeca1"
)
NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST = (
    "sha256:0d3e4056e081e07bb52cbda15fc161ff9584a50f25f97f39fd513e1dad404c9c"
)
NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST = (
    "sha256:9e4eef184a94d3f646b9483b569a4751ab2a9939ac509e55b888af6548c888fe"
)
NON_ULTRA_TRAIL_CONTRACT_DIGEST = (
    "sha256:1952421299cb59ddfea00115b6824d3116bd6e5f9175741916aa6f1015f8f9f9"
)


NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT = load_policy_contract(
    NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    require_active=False,
)
NON_ULTRA_TRAIL_CONTRACT = load_policy_contract(
    NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    require_active=False,
)


def _assert_exact_contract(
    *,
    contract: Any,
    decision_id: str,
    source_decision_digest: str,
    contract_digest: str,
    model_version: str,
) -> None:
    if contract.decision_id != decision_id:
        raise ValueError(f"{decision_id} contract decision ID mismatch")
    if str(contract.decision_status) not in {"accepted", "RecordStatus.ACCEPTED"}:
        raise ValueError(f"{decision_id} is not accepted")
    if str(contract.runtime_state) not in {"inactive", "ArtifactRuntimeState.INACTIVE"}:
        raise ValueError(f"{decision_id} must remain inactive")
    if contract.source_decision_digest != source_decision_digest:
        raise ValueError(f"{decision_id} source decision digest mismatch")
    if contract.contract_digest != contract_digest:
        raise ValueError(f"{decision_id} contract digest mismatch")
    if contract.model_version != model_version:
        raise ValueError(f"{decision_id} model version mismatch")


_assert_exact_contract(
    contract=NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT,
    decision_id=NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    source_decision_digest=NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
    contract_digest=NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
    model_version="trail-course-demand-v2",
)
_assert_exact_contract(
    contract=NON_ULTRA_TRAIL_CONTRACT,
    decision_id=NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    source_decision_digest=NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
    contract_digest=NON_ULTRA_TRAIL_CONTRACT_DIGEST,
    model_version="non-ultra-trail-plan-generation-policy-v2",
)

NON_ULTRA_TRAIL_POLICY_VERSION = NON_ULTRA_TRAIL_CONTRACT.model_version
NON_ULTRA_TRAIL_ONTOLOGY_VERSION = (
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.model_version
)
NON_ULTRA_TRAIL_PARAMETER_VALUES = NON_ULTRA_TRAIL_CONTRACT.parameter_values
NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES = (
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.parameter_values
)

NON_ULTRA_TRAIL_SCOPE = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_scope_and_dependencies"
]
NON_ULTRA_TRAIL_REQUIRED_INPUTS = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_required_inputs"
]
NON_ULTRA_TRAIL_EXECUTION = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_execution_and_reassessment"
]
NON_ULTRA_TRAIL_HISTORY = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_history_guardrails"
]
NON_ULTRA_TRAIL_SCHEDULE = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_schedule_construction"
]
NON_ULTRA_TRAIL_TEMPLATES = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_workout_templates"
]
NON_ULTRA_TRAIL_INTENSITY = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_intensity_and_spacing"
]
NON_ULTRA_TRAIL_EXPOSURE_CAPS = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_course_exposure_caps"
]
NON_ULTRA_TRAIL_EVENTS = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_event_and_taper"
]
NON_ULTRA_TRAIL_TYPED_OUTCOMES = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_typed_outcomes"
]
NON_ULTRA_TRAIL_HARD_BOUNDARIES = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_hard_boundaries"
]
NON_ULTRA_TRAIL_MODULE_STRUCTURE = NON_ULTRA_TRAIL_PARAMETER_VALUES[
    "trail_policy_modular_structure"
]

NON_ULTRA_TRAIL_COURSE_SCHEMA = NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES[
    "trail_course_demand_schema"
]
NON_ULTRA_TRAIL_PROVENANCE_POLICY = (
    NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES["trail_field_provenance"]
)
NON_ULTRA_TRAIL_GRADE_DISTRIBUTION = (
    NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES["trail_grade_distribution"]
)
NON_ULTRA_TRAIL_FOOTING_AND_HAZARDS = (
    NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES[
        "trail_footing_and_hazard_contract"
    ]
)
NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA = (
    NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES[
        "trail_training_constraints_schema"
    ]
)
NON_ULTRA_TRAIL_OPTIONAL_CONTEXT = (
    NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES[
        "trail_optional_context_shapes"
    ]
)
NON_ULTRA_TRAIL_UNKNOWN_POLICY = NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES[
    "trail_unknown_and_materiality_policy"
]
NON_ULTRA_TRAIL_REVISION_POLICY = (
    NON_ULTRA_TRAIL_ONTOLOGY_PARAMETER_VALUES[
        "trail_revision_and_confirmation"
    ]
)

NON_ULTRA_TRAIL_CAPABILITY_ID = "non_ultra_trail_performance_v2"
NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID = str(
    NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA["schema_id"]
)
NON_ULTRA_TRAIL_COURSE_SCHEMA_ID = str(
    NON_ULTRA_TRAIL_COURSE_SCHEMA["schema_id"]
)

if (
    NON_ULTRA_TRAIL_SCOPE["requires_accepted_ontology"]
    != NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID
):
    raise ValueError("non-ultra Trail ontology dependency mismatch")
if (
    NON_ULTRA_TRAIL_SCOPE["requires_course_demand_schema"]
    != NON_ULTRA_TRAIL_COURSE_SCHEMA_ID
):
    raise ValueError("non-ultra Trail course schema dependency mismatch")
if (
    NON_ULTRA_TRAIL_SCOPE["requires_constraint_schema"]
    != NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID
):
    raise ValueError("non-ultra Trail constraint schema dependency mismatch")

NON_ULTRA_TRAIL_PROPOSAL_DAYS = int(
    NON_ULTRA_TRAIL_EXECUTION["committed_proposal_days"]
)
NON_ULTRA_TRAIL_REASSESSMENT_DAYS = int(
    NON_ULTRA_TRAIL_EXECUTION["advisory_reassessment_after_completed_days"]
)
NON_ULTRA_TRAIL_HISTORY_LOOKBACK_COMPLETED_WEEKS = int(
    NON_ULTRA_TRAIL_HISTORY["recent_history_lookback_completed_weeks"]
)
NON_ULTRA_TRAIL_STATUS_PRECEDENCE = tuple(
    str(value)
    for value in NON_ULTRA_TRAIL_TYPED_OUTCOMES["status_precedence"]
)
NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG = {
    str(status): tuple(str(reason) for reason in reasons)
    for status, reasons in NON_ULTRA_TRAIL_TYPED_OUTCOMES[
        "detail_reason_catalog"
    ].items()
}
NON_ULTRA_TRAIL_REASON_PAIRS = frozenset(
    (status, reason)
    for status, reasons in NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG.items()
    for reason in reasons
)
NON_ULTRA_TRAIL_MODULE_KEYS = tuple(
    str(value)
    for value in NON_ULTRA_TRAIL_TYPED_OUTCOMES["module_availability"][
        "required_keys_in_fixed_order"
    ]
)
NON_ULTRA_TRAIL_MODULE_STATES = frozenset(
    str(value)
    for value in NON_ULTRA_TRAIL_TYPED_OUTCOMES["module_availability"][
        "allowed_states"
    ]
)
NON_ULTRA_TRAIL_LIMITED_MODULE_ORDER = tuple(
    str(value)
    for value in NON_ULTRA_TRAIL_TYPED_OUTCOMES["limited_modules"][
        "allowed_sorted_order"
    ]
)
NON_ULTRA_TRAIL_RESULT_CODES = frozenset(NON_ULTRA_TRAIL_STATUS_PRECEDENCE)
NON_ULTRA_TRAIL_ALLOWED_PROVENANCE = frozenset(
    str(value)
    for value in NON_ULTRA_TRAIL_PROVENANCE_POLICY[
        "server_stamped_provenance_allowed"
    ]
)

if len(NON_ULTRA_TRAIL_REASON_PAIRS) != 21:
    raise ValueError("non-ultra Trail v2 must expose exactly 21 closed reasons")
if NON_ULTRA_TRAIL_STATUS_PRECEDENCE[-1] != "eligible_proposal":
    raise ValueError("non-ultra Trail eligible status precedence mismatch")
if NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG["eligible_proposal"]:
    raise ValueError("eligible Trail proposals cannot carry a detail reason")
if set(NON_ULTRA_TRAIL_MODULE_KEYS) != set(
    NON_ULTRA_TRAIL_LIMITED_MODULE_ORDER
):
    raise ValueError("non-ultra Trail module projections disagree")


@dataclass(frozen=True)
class NonUltraTrailGuardrailProjection:
    """Read-only accepted values used by pure generation and explanation."""

    committed_proposal_days: int
    advisory_reassessment_after_completed_days: int
    recent_history_lookback_completed_weeks: int
    minimum_usable_completed_weeks: int
    minimum_running_sessions_per_usable_week: int
    latest_run_within_completed_days: int
    minimum_planned_low_intensity_running_minutes_fraction: float
    maximum_quality_exposures_per_7_day_unit: int

    def public_payload(self) -> dict[str, int | float]:
        """Return the response-safe exact-value projection."""
        return asdict(self)


NON_ULTRA_TRAIL_GUARDRAILS = NonUltraTrailGuardrailProjection(
    committed_proposal_days=NON_ULTRA_TRAIL_PROPOSAL_DAYS,
    advisory_reassessment_after_completed_days=(
        NON_ULTRA_TRAIL_REASSESSMENT_DAYS
    ),
    recent_history_lookback_completed_weeks=(
        NON_ULTRA_TRAIL_HISTORY_LOOKBACK_COMPLETED_WEEKS
    ),
    minimum_usable_completed_weeks=int(
        NON_ULTRA_TRAIL_HISTORY["minimum_usable_completed_weeks"]
    ),
    minimum_running_sessions_per_usable_week=int(
        NON_ULTRA_TRAIL_HISTORY[
            "minimum_running_sessions_per_usable_week"
        ]
    ),
    latest_run_within_completed_days=int(
        NON_ULTRA_TRAIL_HISTORY["latest_run_within_completed_days"]
    ),
    minimum_planned_low_intensity_running_minutes_fraction=float(
        NON_ULTRA_TRAIL_INTENSITY[
            "minimum_planned_low_intensity_running_minutes_fraction"
        ]
    ),
    maximum_quality_exposures_per_7_day_unit=int(
        NON_ULTRA_TRAIL_INTENSITY[
            "maximum_quality_exposures_per_7_day_unit"
        ]
    ),
)
