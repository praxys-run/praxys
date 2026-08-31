"""Pure identity and admission policy for agent invocation control."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Mapping


SCHEMA_VERSION = 2
POLICY_VERSION = "agent-invocation-control-v1"
APPROVED_MODES = ("instrument", "shadow")
DISPATCH_PROFILES = {
    "sync": "sync_inline",
    "background": "background_independent_immediate_no_poll",
}
POLICY_REASONS = (
    "admit",
    "kill_switch_active",
    "duplicate_active",
    "ancestry_cycle",
    "ancestry_depth_limit",
    "active_contract_limit",
    "logical_contract_limit",
    "retry_fingerprint_limit",
    "attempt_limit",
    "no_progress",
)
DECISION_REASONS = (
    "admit",
    "work_contract_invalid",
    "kill_switch_active",
    "duplicate_active",
    "ancestry_cycle",
    "ancestry_depth_limit",
    "active_contract_limit",
    "logical_contract_limit",
    "retry_fingerprint_limit",
    "attempt_limit",
    "no_progress",
    "state_missing",
    "state_corrupt",
    "state_unsupported",
)
MACHINE_REASON_CODES = (
    "instrument_recorded",
    "shadow_would_admit",
    "shadow_would_deny_cycle",
    "shadow_would_deny_policy_limit",
    "invalid_request",
    "invalid_identity",
    "work_contract_unavailable",
    "work_contract_mismatch",
    "policy_unavailable",
    "recovery_required",
    "ledger_unavailable",
    "enforcement_unavailable",
    "kill_switch_active",
    "ledger_initialized",
    "ledger_ready",
    "identity_created",
    "finish_recorded",
    "finish_idempotent",
    "recovery_recorded",
    "kill_switch_updated",
    "status_reported",
    "lifecycle_transition_rejected",
    "native_bound",
    "native_notification_recorded",
    "completion_notification_required",
    "native_notifications_unavailable",
    "native_read_authorized",
    "native_read_refused",
    "native_observation_recorded",
    "progress_recorded",
    "progress_idempotent",
    "tree_termination_recorded",
    "tree_termination_idempotent",
    "direct_sibling_active",
    "execution_provenance_invalid",
    "native_binding_mismatch",
    "native_binding_invalidated",
    "native_invalidated",
)
ID_PREFIXES = {
    "contract": "ctr",
    "slot": "slt",
    "generation": "gen",
    "logical": "log",
    "attempt": "att",
    "decision": "dec",
    "native": "nat",
    "read_claim": "rcl",
}
_IDENTITY_RE = re.compile(r"^[a-z]{3}_[0-9a-f]{32}$")
_FINGERPRINT_RE = re.compile(r"^fpr_[0-9a-f]{64}$")
_ARTIFACT_REVISION_RE = re.compile(
    r"^(?:sha256:[0-9a-f]{64}|git:[0-9a-f]{40}|git:[0-9a-f]{64})$"
)
_REPOSITORY_IDENTITY_RE = re.compile(
    r"^(?:ctr|slt|gen|log|att|dec|nat|rcl)_[0-9a-f]{32}$"
)
_PUBLIC_AGENT_ID_MAX_LENGTH = 512
_PUBLIC_AGENT_ID_PLACEHOLDERS = {
    "agent",
    "agent-id",
    "agent_id",
    "changeme",
    "dummy",
    "example",
    "nonexistent",
    "none",
    "null",
    "pending",
    "placeholder",
    "public-agent-id",
    "public_agent_id",
    "task-result",
    "task_result",
    "todo",
    "unknown",
    "x",
}


@dataclass(frozen=True)
class InvocationLimits:
    """Accepted starting bounds for the candidate policy."""

    maximum_ancestry_depth: int
    maximum_active_per_contract: int
    maximum_logical_per_contract: int
    maximum_attempts_per_logical: int
    maximum_retries_per_failure_fingerprint: int
    no_progress_identical_terminals: int

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, object]
    ) -> "InvocationLimits":
        """Validate and construct the exact v1 limit set."""
        expected = {
            "maximum_ancestry_depth",
            "maximum_active_per_contract",
            "maximum_logical_per_contract",
            "maximum_attempts_per_logical",
            "maximum_retries_per_failure_fingerprint",
            "no_progress_identical_terminals",
        }
        if set(payload) != expected:
            raise ValueError("limit keys do not match schema v1")
        values: dict[str, int] = {}
        for key in expected:
            value = payload[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("limits must be integers")
            if value < 1:
                raise ValueError("limits must be positive")
            values[key] = value
        return cls(**values)


@dataclass(frozen=True)
class AdmissionFacts:
    """Privacy-safe facts for one atomic admission decision."""

    kill_switch_active: bool
    duplicate_active: bool
    ancestor_slot_ids: tuple[str, ...]
    proposed_slot_id: str
    proposed_depth: int
    active_count: int
    logical_count: int
    is_new_logical: bool
    retry_fingerprint: str | None
    retries_for_fingerprint: int
    attempt_count: int
    recent_terminal_fingerprints: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionDecision:
    """One stable candidate-policy result."""

    policy_reason: str
    would_reject: bool
    launch_authorized: bool


def format_identity(kind: str, opaque_hex: str) -> str:
    """Format a caller-generated, 128-bit opaque identity."""
    prefix = ID_PREFIXES.get(kind)
    if prefix is None or re.fullmatch(r"[0-9a-f]{32}", opaque_hex) is None:
        raise ValueError("invalid opaque identity material")
    return f"{prefix}_{opaque_hex}"


def is_valid_identity(value: object, kind: str) -> bool:
    """Return whether value is a valid opaque invocation identity."""
    prefix = ID_PREFIXES.get(kind)
    return (
        prefix is not None
        and isinstance(value, str)
        and _IDENTITY_RE.fullmatch(value) is not None
        and value.startswith(f"{prefix}_")
    )


def is_valid_fingerprint(value: object) -> bool:
    """Return whether value is a versioned opaque fingerprint."""
    return isinstance(value, str) and _FINGERPRINT_RE.fullmatch(value) is not None


def is_valid_artifact_revision(value: object) -> bool:
    """Return whether value is an immutable artifact digest or Git head."""
    return (
        isinstance(value, str)
        and _ARTIFACT_REVISION_RE.fullmatch(value) is not None
    )


def is_valid_public_agent_id(value: object) -> bool:
    """Validate a task-returned public agent ID without assuming its format."""
    if not isinstance(value, str):
        return False
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if (
        not encoded
        or len(encoded) > _PUBLIC_AGENT_ID_MAX_LENGTH
        or value != value.strip()
        or value.casefold() in _PUBLIC_AGENT_ID_PLACEHOLDERS
        or value.casefold().startswith("call_")
        or _REPOSITORY_IDENTITY_RE.fullmatch(value) is not None
    ):
        return False
    return not any(
        character.isspace()
        or unicodedata.category(character).startswith("C")
        for character in value
    )


def evaluate_admission(
    facts: AdmissionFacts,
    limits: InvocationLimits,
) -> AdmissionDecision:
    """Evaluate the accepted guards in stable v1 precedence."""
    reason = "admit"
    if facts.kill_switch_active:
        reason = "kill_switch_active"
    elif facts.duplicate_active:
        reason = "duplicate_active"
    elif facts.proposed_slot_id in facts.ancestor_slot_ids:
        reason = "ancestry_cycle"
    elif facts.proposed_depth > limits.maximum_ancestry_depth:
        reason = "ancestry_depth_limit"
    elif facts.active_count >= limits.maximum_active_per_contract:
        reason = "active_contract_limit"
    elif (
        facts.is_new_logical
        and facts.logical_count >= limits.maximum_logical_per_contract
    ):
        reason = "logical_contract_limit"
    elif (
        facts.retry_fingerprint is not None
        and facts.retries_for_fingerprint
        >= limits.maximum_retries_per_failure_fingerprint
    ):
        reason = "retry_fingerprint_limit"
    elif facts.attempt_count >= limits.maximum_attempts_per_logical:
        reason = "attempt_limit"
    elif (
        len(facts.recent_terminal_fingerprints)
        >= limits.no_progress_identical_terminals
        and len(
            set(facts.recent_terminal_fingerprints[: limits.no_progress_identical_terminals])
        )
        == 1
    ):
        reason = "no_progress"

    would_reject = reason != "admit"
    return AdmissionDecision(
        policy_reason=reason,
        would_reject=would_reject,
        launch_authorized=reason != "kill_switch_active",
    )
