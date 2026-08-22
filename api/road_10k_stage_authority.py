"""Read-only, fail-closed Road 10K stage-authority consumer.

The application never creates or edits this artifact.  A deployment may
provide a path to an independently issued artifact, but absence remains the
normal dormant state and no environment value can turn the feature on by
itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from analysis.road_10k_contract import ROAD_10K_CAPABILITY
from api.version import get_api_version, is_valid_build_version

ROAD_10K_OBJECT_ID = "road-10k-controlled-opt-in-foundation-v1"
ROAD_10K_WORK_CONTRACT_DIGEST = (
    "sha256:b2c668dc304e44407a743c8b8c2710cc6c133ac4106045986bfd1726d2a7725e"
)
ROAD_10K_ROUTE_DIGEST = (
    "sha256:a916feab2d029de3d6996933a7aece668670facc016f6abf8b932aa747af8214"
)
ROAD_10K_AUTHORITY_SCHEMA_VERSION = "road-10k-stage-authority-v1"
ROAD_10K_CONTROL_SCHEMA_VERSION = 2
ROAD_10K_COMPILED_INVITATION_CEILING = 60
ROAD_10K_COMPILED_EXPOSURE_CEILING = 30
ROAD_10K_MAX_HEARTBEAT_AGE_SECONDS = 300
ROAD_10K_LIFECYCLE_STATES = frozenset(
    {"paused", "killed", "hold", "rollback", "stopped", "revision"}
)


class StageAuthorityError(ValueError):
    """Raised only while parsing an invalid external authority artifact."""


@dataclass(frozen=True)
class Road10KStageAuthority:
    stage_id: str
    authority_digest: str
    capability_id: str
    object_id: str
    work_contract_digest: str
    route_digest: str
    schema_version: str
    control_schema_version: int
    state: str
    invitation_ceiling: int
    exposure_ceiling: int
    notice_digest: str
    cohort_rule_digest: str
    sampling_run_evidence_digest: str
    valid_from: datetime
    valid_until: datetime
    heartbeat_at: datetime
    heartbeat_max_age_seconds: int
    readiness: str
    provider_fence: str
    pause: bool
    kill: bool
    build_id: str

    @property
    def is_fresh(self) -> bool:
        now = datetime.now(timezone.utc)
        return (
            self.valid_from <= now <= self.valid_until
            and self.heartbeat_at <= now
            and (now - self.heartbeat_at).total_seconds()
            <= self.heartbeat_max_age_seconds
        )

    @property
    def is_usable(self) -> bool:
        """Return false: this repository revision has no activation path.

        Artifacts remain parseable solely for migration and malformed-input
        fixtures.  Neither an environment locator nor a complete, fresh
        authority may make a stage capability usable in this revision.
        """
        return False

    @property
    def lifecycle_status(self) -> None:
        """No lifecycle is owner-visible while the revision is hard-off."""
        return None



def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise StageAuthorityError(f"{field} must be an RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageAuthorityError(f"{field} is malformed") from exc
    if parsed.tzinfo is None:
        raise StageAuthorityError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise StageAuthorityError(f"{field} must be a sha256 digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise StageAuthorityError(f"{field} must be a sha256 digest") from exc
    return value


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    without_digest = {
        key: value for key, value in payload.items() if key != "authority_digest"
    }
    encoded = json.dumps(
        without_digest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_stage_authority(payload: Mapping[str, Any]) -> Road10KStageAuthority:
    """Parse and validate one externally supplied authority mapping.

    Unknown fields are rejected to make mixed-version artifacts fail closed.
    """
    if not isinstance(payload, Mapping):
        raise StageAuthorityError("authority must be an object")
    allowed = {
        "authority_digest",
        "stage_id",
        "capability_id",
        "object_id",
        "work_contract_digest",
        "route_digest",
        "schema_version",
        "control_schema_version",
        "state",
        "invitation_ceiling",
        "exposure_ceiling",
        "notice_digest",
        "cohort_rule_digest",
        "sampling_run_evidence_digest",
        "valid_from",
        "valid_until",
        "heartbeat_at",
        "heartbeat_max_age_seconds",
        "readiness",
        "provider_fence",
        "pause",
        "kill",
        "build_id",
    }
    if set(payload) != allowed:
        raise StageAuthorityError("authority fields are mixed-version or incomplete")
    authority_digest = _digest(payload["authority_digest"], "authority_digest")
    if _canonical_digest(payload) != authority_digest:
        raise StageAuthorityError("authority digest mismatch")
    stage_id = payload["stage_id"]
    if not isinstance(stage_id, str) or not stage_id or len(stage_id) > 80:
        raise StageAuthorityError("stage_id is malformed")
    if payload["capability_id"] != str(ROAD_10K_CAPABILITY["capability_id"]):
        raise StageAuthorityError("capability mismatch")
    if payload["object_id"] != ROAD_10K_OBJECT_ID:
        raise StageAuthorityError("object mismatch")
    if payload["work_contract_digest"] != ROAD_10K_WORK_CONTRACT_DIGEST:
        raise StageAuthorityError("work contract mismatch")
    if payload["route_digest"] != ROAD_10K_ROUTE_DIGEST:
        raise StageAuthorityError("route mismatch")
    if payload["schema_version"] != ROAD_10K_AUTHORITY_SCHEMA_VERSION:
        raise StageAuthorityError("authority schema mismatch")
    if payload["control_schema_version"] != ROAD_10K_CONTROL_SCHEMA_VERSION:
        raise StageAuthorityError("control schema mismatch")
    if payload["state"] not in {
        "active",
        "off",
        "paused",
        "killed",
        "hold",
        "rollback",
        "stopped",
        "revision",
    }:
        raise StageAuthorityError("unknown authority state")
    invitation_ceiling = payload["invitation_ceiling"]
    exposure_ceiling = payload["exposure_ceiling"]
    if (
        type(invitation_ceiling) is not int
        or type(exposure_ceiling) is not int
        or invitation_ceiling != ROAD_10K_COMPILED_INVITATION_CEILING
        or exposure_ceiling != ROAD_10K_COMPILED_EXPOSURE_CEILING
    ):
        raise StageAuthorityError("authority ceilings must match fixed policy")
    heartbeat_max_age = payload["heartbeat_max_age_seconds"]
    if (
        type(heartbeat_max_age) is not int
        or heartbeat_max_age <= 0
        or heartbeat_max_age > ROAD_10K_MAX_HEARTBEAT_AGE_SECONDS
    ):
        raise StageAuthorityError("heartbeat bound is malformed")
    if payload["readiness"] not in {"ready", "not_ready"}:
        raise StageAuthorityError("readiness is malformed")
    if payload["provider_fence"] not in {"closed", "open", "unknown"}:
        raise StageAuthorityError("provider fence is malformed")
    if type(payload["pause"]) is not bool or type(payload["kill"]) is not bool:
        raise StageAuthorityError("pause and kill must be booleans")
    build_id = payload["build_id"]
    if not isinstance(build_id, str) or not build_id or len(build_id) > 120:
        raise StageAuthorityError("build_id is malformed")
    running_build = get_api_version()
    if (
        running_build == "develop"
        or not is_valid_build_version(running_build)
        or build_id != running_build
    ):
        raise StageAuthorityError("build mismatch")
    valid_from = _utc(payload["valid_from"], "valid_from")
    valid_until = _utc(payload["valid_until"], "valid_until")
    heartbeat_at = _utc(payload["heartbeat_at"], "heartbeat_at")
    if valid_until <= valid_from:
        raise StageAuthorityError("authority validity window is malformed")
    return Road10KStageAuthority(
        stage_id=stage_id,
        authority_digest=authority_digest[7:],
        capability_id=payload["capability_id"],
        object_id=payload["object_id"],
        work_contract_digest=payload["work_contract_digest"],
        route_digest=payload["route_digest"],
        schema_version=payload["schema_version"],
        control_schema_version=payload["control_schema_version"],
        state=payload["state"],
        invitation_ceiling=invitation_ceiling,
        exposure_ceiling=exposure_ceiling,
        notice_digest=_digest(payload["notice_digest"], "notice_digest")[7:],
        cohort_rule_digest=_digest(
            payload["cohort_rule_digest"], "cohort_rule_digest"
        )[7:],
        sampling_run_evidence_digest=_digest(
            payload["sampling_run_evidence_digest"],
            "sampling_run_evidence_digest",
        )[7:],
        valid_from=valid_from,
        valid_until=valid_until,
        heartbeat_at=heartbeat_at,
        heartbeat_max_age_seconds=heartbeat_max_age,
        readiness=payload["readiness"],
        provider_fence=payload["provider_fence"],
        pause=payload["pause"],
        kill=payload["kill"],
        build_id=build_id,
    )


def _authority_path() -> Path | None:
    raw = os.environ.get("PRAXYS_ROAD_10K_STAGE_AUTHORITY_PATH", "").strip()
    return Path(raw) if raw else None


def load_stage_authority() -> Road10KStageAuthority | None:
    """Read the external artifact once per request; malformed state is absent."""
    path = _authority_path()
    if path is None:
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return parse_stage_authority(raw)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def authority_denial_reason(
    authority: Road10KStageAuthority | None,
) -> str:
    """Return a low-cardinality status for restricted diagnostics."""
    if authority is None:
        return "missing_or_malformed"
    # A structurally valid artifact is deliberately not activation authority.
    if not authority.is_usable:
        return "inactive_revision"
    if authority.state != "active":
        return authority.state
    if authority.pause:
        return "paused"
    if authority.kill:
        return "killed"
    if not authority.is_fresh:
        return "heartbeat_or_validity_stale"
    if authority.readiness != "ready":
        return "not_ready"
    if authority.provider_fence != "closed":
        return "provider_fence_open"
    return "allowed"
