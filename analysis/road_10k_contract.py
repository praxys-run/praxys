"""Reviewed machine-contract helpers for the inactive road 10K capability."""
from __future__ import annotations

from analysis.science_artifacts import load_policy_contract


ROAD_10K_SCIENCE_DECISION_ID = "sdr-road-10k-plan-generation-policy-v2"
ROAD_10K_GENERATOR_VERSION = "road-10k-deterministic-generator-v1"
ROAD_10K_CONTRACT_DIGEST = (
    "sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496"
)
ROAD_10K_SOURCE_DECISION_DIGEST = (
    "sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad"
)
ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION = "road-10k-training-pattern-v1"
ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION = "road-10k-event-context-v1"
ROAD_10K_BASELINE_SNAPSHOT_VERSION = "road-10k-direct-baseline-v1"

ROAD_10K_CONTRACT = load_policy_contract(
    ROAD_10K_SCIENCE_DECISION_ID,
    require_active=False,
)
if ROAD_10K_CONTRACT.contract_digest != ROAD_10K_CONTRACT_DIGEST:
    raise ValueError("road 10K contract digest mismatch")
if ROAD_10K_CONTRACT.source_decision_digest != ROAD_10K_SOURCE_DECISION_DIGEST:
    raise ValueError("road 10K source decision digest mismatch")

ROAD_10K_POLICY_VERSION = ROAD_10K_CONTRACT.model_version
ROAD_10K_PARAMETER_VALUES = ROAD_10K_CONTRACT.parameter_values
ROAD_10K_CAPABILITY = ROAD_10K_PARAMETER_VALUES["road_10k_v2_capability_tuple"]
ROAD_10K_REQUIRED_INPUTS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_required_inputs"
]
ROAD_10K_READINESS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_readiness_and_missingness"
]
ROAD_10K_EXECUTION = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_execution_window_and_reassessment"
]
ROAD_10K_SCHEDULE = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_schedule_construction"
]
ROAD_10K_TEMPLATES = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_workout_templates"
]
ROAD_10K_INTENSITY = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_intensity_quality_and_spacing"
]
ROAD_10K_EVENTS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_event_benchmark_and_taper"
]
ROAD_10K_TYPED_OUTCOMES = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_typed_outcomes"
]["outcomes"]
ROAD_10K_DEMOGRAPHICS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_demographic_and_claim_limits"
]
ROAD_10K_ACTIVATION = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_activation_and_dependencies"
]
ROAD_10K_AUDIT = ROAD_10K_PARAMETER_VALUES["road_10k_v2_privacy_and_audit"]
