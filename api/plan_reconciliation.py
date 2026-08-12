"""Read-only plan reconciliation between Praxys and execution targets."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import PRAXYS_PLAN_SOURCES
from api.plan_delivery.base import (
    provider_account_references_match,
    provider_snapshot_references_match,
)
from api.plan_workout_structure import (
    default_activity_type,
    inspect_workout_structure,
    normalize_activity_type,
    validate_structured_workout,
)
from db.models import (
    PlanDelivery,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    TrainingPlan,
)
from db.plan_reconciliation import target_observation_matches_calendar
from db.plan_ledger import (
    canonical_workout_key,
    delivery_canonical_id,
    plan_snapshot,
    workout_version,
)

_CONFLICT_STATES = {
    "target_edited",
    "target_deleted",
    "canonical_changed",
    "delivery_failed",
}


def plan_target_calendar_generation(
    calendar_sync: PlanTargetCalendarSync,
    observations: list[PlanTargetWorkout],
    *,
    presence_overrides: Mapping[str, bool] | None = None,
) -> str:
    """Return a stable semantic generation for one target-calendar snapshot."""
    overrides = presence_overrides or {}
    payload = {
        "sync": {
            "id": calendar_sync.id,
            "provider_account_id": calendar_sync.provider_account_id,
            "provider_references": calendar_sync.provider_references,
            "window_start": calendar_sync.window_start.isoformat(),
            "window_end": calendar_sync.window_end.isoformat(),
        },
        "observations": [
            {
                "id": observation.id,
                "provider_account_id": observation.provider_account_id,
                "provider_references": observation.provider_references,
                "external_id": observation.external_id,
                "workout_date": observation.workout_date.isoformat(),
                "start_time": (
                    observation.start_time.isoformat()
                    if observation.start_time is not None
                    else None
                ),
                "normalized_workout": observation.normalized_workout,
                "content_fingerprint": observation.content_fingerprint,
                "payload_fingerprint": observation.payload_fingerprint,
                "present": overrides.get(
                    observation.id,
                    bool(observation.present),
                ),
            }
            for observation in sorted(
                observations,
                key=lambda row: (row.external_id, row.id),
            )
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def observation_matches_calendar(
    calendar_sync: PlanTargetCalendarSync,
    observation: PlanTargetWorkout,
) -> bool:
    """Return whether an observation belongs to this account snapshot."""
    return target_observation_matches_calendar(
        calendar_sync,
        observation,
    )


def _resolution_identity(
    *,
    canonical: TrainingPlan | None,
    observation: PlanTargetWorkout | None,
    delivery: PlanDelivery | None,
    calendar_generation: str | None,
) -> str:
    payload = {
        "canonical_version": (
            workout_version(plan_snapshot(canonical))
            if canonical is not None
            else None
        ),
        "delivery_id": delivery.id if delivery is not None else None,
        "delivery_external_id": (
            delivery.external_id if delivery is not None else None
        ),
        "delivery_plan_version": (
            delivery.plan_version or delivery.workout_version
            if delivery is not None
            else None
        ),
        "observation_id": (
            observation.id if observation is not None else None
        ),
        "observation_external_id": (
            observation.external_id if observation is not None else None
        ),
        "observation_content_version": (
            observation.content_fingerprint
            or observation.payload_fingerprint
            if observation is not None
            else None
        ),
        "observation_snapshot": (
            observation.normalized_workout
            if observation is not None
            else None
        ),
        "calendar_generation": calendar_generation,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _observation_can_be_accepted(
    observation: PlanTargetWorkout | None,
) -> bool:
    if observation is None or not observation.present:
        return False
    # Existing Garmin observations predate explicit representation status.
    # Their calendar summaries never contained authoritative template steps,
    # so they must remain unacceptably lossy after an in-place upgrade too.
    if str(observation.target or "").strip().casefold() == "garmin":
        return False
    snapshot = observation.normalized_workout or {}
    status = str(
        snapshot.get("workout_structure_status") or ""
    ).strip()
    if status not in {"", "absent", "supported"}:
        return False
    inspection = inspect_workout_structure(
        workout_structure_version=snapshot.get(
            "workout_structure_version"
        ),
        workout_structure=snapshot.get("workout_structure"),
    )
    if status == "absent" and inspection.state != "absent":
        return False
    if status == "supported" and inspection.state != "supported":
        return False
    workout_type = str(snapshot.get("workout_type") or "")
    activity_type = str(
        snapshot.get("activity_type")
        or default_activity_type(workout_type)
    )
    try:
        if inspection.state == "absent":
            normalize_activity_type(workout_type, activity_type)
            return True
        if inspection.state != "supported" or inspection.structure is None:
            return False
        validate_structured_workout(
            workout_type=workout_type,
            activity_type=activity_type,
            workout_structure_version="v1",
            workout_structure=inspection.structure,
        )
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class PlanReconciliationItem:
    """One canonical or target-only workout reconciliation result."""

    id: str
    state: str
    target: str
    canonical: TrainingPlan | None
    observation: PlanTargetWorkout | None
    delivery: PlanDelivery | None
    match_basis: str | None = None
    reason: str | None = None
    calendar_generation: str | None = None
    calendar_observation_present: bool | None = field(
        default=None,
        repr=False,
    )
    observation_present: bool | None = field(init=False, repr=False)
    resolution_identity: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        current_observation_present = (
            bool(self.observation.present)
            if self.observation is not None
            else None
        )
        if self.calendar_observation_present is None:
            object.__setattr__(
                self,
                "calendar_observation_present",
                current_observation_present,
            )
        object.__setattr__(
            self,
            "observation_present",
            current_observation_present,
        )
        object.__setattr__(
            self,
            "resolution_identity",
            _resolution_identity(
                canonical=self.canonical,
                observation=self.observation,
                delivery=self.delivery,
                calendar_generation=self.calendar_generation,
            ),
        )

    def matches_current(
        self,
        *,
        canonical: TrainingPlan | None,
        observation: PlanTargetWorkout | None,
        delivery: PlanDelivery | None,
        calendar_generation: str | None = None,
    ) -> bool:
        """Return whether locked rows still represent this conflict."""
        return self.resolution_identity == _resolution_identity(
            canonical=canonical,
            observation=observation,
            delivery=delivery,
            calendar_generation=calendar_generation,
        )

    @property
    def opaque_id(self) -> str:
        """Return the stable client-visible identity for this conflict generation."""
        return f"{self.id}@{self.resolution_identity}"

    @property
    def resolutions(self) -> list[str]:
        can_accept = _observation_can_be_accepted(self.observation)
        if self.state == "target_only":
            return ["accept_target"] if can_accept else []
        if self.reason == "external_id_changed":
            return ["accept_target"] if can_accept else []
        if self.state in {"target_edited", "canonical_changed"}:
            resolutions = ["restore_praxys"]
            if can_accept:
                resolutions.append("accept_target")
            return resolutions
        if self.state in {"target_deleted", "delivery_failed"}:
            return ["restore_praxys"]
        return []

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.opaque_id,
            "state": self.state,
            "conflict": self.state in _CONFLICT_STATES,
            "target": self.target,
            "resolutions": self.resolutions,
        }
        if self.canonical is not None:
            result["canonical_id"] = self.canonical.canonical_id
        if self.delivery is not None:
            result["delivery_id"] = self.delivery.id
            if self.delivery.last_error:
                result["last_error"] = self.delivery.last_error
        if self.observation is not None:
            result["target_workout_id"] = self.observation.id
            result["external_id"] = self.observation.external_id
            if self.observation.present:
                result["target_workout"] = dict(
                    self.observation.normalized_workout or {}
                )
        elif self.delivery is not None and self.delivery.external_id:
            result["external_id"] = self.delivery.external_id
        if self.match_basis:
            result["match_basis"] = self.match_basis
        if self.reason:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class PlanReconciliationView:
    """Reconciliation results indexed by durable canonical identity."""

    canonical_items: Mapping[str, PlanReconciliationItem]
    target_only_items: tuple[PlanReconciliationItem, ...]
    calendar_sync: PlanTargetCalendarSync
    calendar_generation: str
    consumed_observation_ids: frozenset[str]

    def item_by_id(self, reconciliation_id: str) -> PlanReconciliationItem | None:
        for item in self.canonical_items.values():
            if reconciliation_id in {item.id, item.opaque_id}:
                return item
        return next(
            (
                item
                for item in self.target_only_items
                if reconciliation_id in {item.id, item.opaque_id}
            ),
            None,
        )


def reconciliation_sync_state(state: str) -> str:
    """Map detailed reconciliation to the legacy three-state API contract."""
    if state in {"matching", "pending_observation"}:
        return "synced"
    if state == "not_delivered":
        return "not_synced"
    return "mismatch"


def _normalized_type(value: Any) -> str:
    return str(value or "").strip().casefold()


def _has_modern_canonical_key(canonical_key: str) -> bool:
    _, separator, candidate = str(canonical_key or "").partition(":")
    if not separator:
        return False
    try:
        UUID(candidate)
    except (ValueError, AttributeError):
        return False
    return True


def _delivery_content_matches(
    delivery: PlanDelivery,
    observation: PlanTargetWorkout,
) -> bool | None:
    if delivery.provider_content_version:
        if observation.content_fingerprint:
            return (
                delivery.provider_content_version
                == observation.content_fingerprint
            )
        return None
    if (
        not delivery.workout_version.startswith("legacy-unknown:")
        and observation.payload_fingerprint
    ):
        return delivery.workout_version == observation.payload_fingerprint
    return None


def _classify_delivery(
    *,
    canonical: TrainingPlan,
    observation: PlanTargetWorkout | None,
    delivery: PlanDelivery,
    calendar_sync: PlanTargetCalendarSync,
    match_basis: str | None,
) -> tuple[str, str | None]:
    if (
        delivery.provider_account_id
        and not provider_account_references_match(
            stored_account_id=delivery.provider_account_id,
            current_account_id=calendar_sync.provider_account_id,
            stored_references=delivery.provider_references or {},
            current_references=(
                observation.provider_references
                if observation is not None
                else calendar_sync.provider_references or {}
            ),
        )
    ):
        return "delivery_failed", "provider_account_changed"
    if delivery.state in {"failed", "conflict"}:
        return "delivery_failed", delivery.state
    if delivery.state in {"pending", "delivering"}:
        return "pending_observation", delivery.state

    current_plan_version = workout_version(plan_snapshot(canonical))
    delivery_plan_version = delivery.plan_version or delivery.workout_version
    canonical_matches = current_plan_version == delivery_plan_version

    if observation is not None:
        if not observation.present:
            reference_time = delivery.delivered_at or delivery.updated_at
            if observation.observed_at >= reference_time:
                return "target_deleted", "external_id_absent"
            return "pending_observation", "awaiting_newer_calendar_sync"
        content_matches = _delivery_content_matches(delivery, observation)
        if match_basis == "fingerprint":
            return (
                "target_edited",
                (
                    "external_id_changed_same_content"
                    if content_matches is True
                    else "external_id_changed"
                ),
            )
        if content_matches is None:
            return "pending_observation", "content_unverified"
        if content_matches is False:
            return (
                "target_edited",
                "content_changed",
            )
        if observation.workout_date != delivery.workout_date:
            return "target_edited", "scheduled_date_changed"
        if not canonical_matches:
            return "canonical_changed", "praxys_content_changed"
        return "matching", None

    reference_time = delivery.delivered_at or delivery.updated_at
    if (
        provider_snapshot_references_match(
            stored_account_id=str(delivery.provider_account_id or ""),
            current_account_id=calendar_sync.provider_account_id,
            stored_references=delivery.provider_references or {},
            current_references=calendar_sync.provider_references or {},
        )
        and calendar_sync.window_start
        <= delivery.workout_date
        <= calendar_sync.window_end
        and calendar_sync.synced_at >= reference_time
    ):
        return "target_deleted", "external_id_absent"
    return "pending_observation", "awaiting_calendar_sync"


def classify_plan_delivery_snapshot(
    *,
    canonical: TrainingPlan,
    delivery: PlanDelivery,
    calendar_sync: PlanTargetCalendarSync,
    observations: list[PlanTargetWorkout],
) -> tuple[str, str | None, PlanTargetWorkout | None]:
    """Classify one delivery from already-loaded target-calendar evidence."""
    observation = next(
        (
            row
            for row in observations
            if delivery.external_id
            and row.external_id == delivery.external_id
        ),
        None,
    )
    match_basis = "external_id" if observation is not None else None
    if (
        (observation is None or not observation.present)
        and delivery.provider_content_version
    ):
        fingerprint_matches = [
            row
            for row in observations
            if row.present
            and row.workout_date == delivery.workout_date
            and row.content_fingerprint
            == delivery.provider_content_version
        ]
        if len(fingerprint_matches) == 1:
            observation = fingerprint_matches[0]
            match_basis = "fingerprint"
    state, reason = _classify_delivery(
        canonical=canonical,
        observation=observation,
        delivery=delivery,
        calendar_sync=calendar_sync,
        match_basis=match_basis,
    )
    return state, reason, observation


def _select_canonical(
    delivery: PlanDelivery,
    observation: PlanTargetWorkout | None,
    canonicals: list[TrainingPlan],
) -> TrainingPlan | None:
    canonical_id = delivery_canonical_id(delivery)
    if canonical_id is not None:
        id_matches = [
            row for row in canonicals if row.canonical_id == canonical_id
        ]
        return id_matches[0] if len(id_matches) == 1 else None

    key_matches = [
        row
        for row in canonicals
        if canonical_workout_key(plan_snapshot(row)) == delivery.canonical_key
    ]
    if len(key_matches) == 1:
        return key_matches[0]
    if _has_modern_canonical_key(delivery.canonical_key):
        return None

    plan_version_matches = [
        row
        for row in canonicals
        if workout_version(plan_snapshot(row))
        == (delivery.plan_version or delivery.workout_version)
    ]
    if len(plan_version_matches) == 1:
        return plan_version_matches[0]

    target_type = (
        _normalized_type(
            (observation.normalized_workout or {}).get("workout_type")
        )
        if observation is not None
        else ""
    )
    date_type_matches = [
        row
        for row in canonicals
        if row.date == delivery.workout_date
        and (
            not target_type
            or _normalized_type(row.workout_type) == target_type
        )
    ]
    if len(date_type_matches) == 1:
        return date_type_matches[0]
    return None


def build_plan_reconciliation(
    db: Session,
    *,
    user_id: str,
    target: str,
    start: date | None = None,
    end: date | None = None,
) -> PlanReconciliationView | None:
    """Build a stable reconciliation view without mutating either side."""
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync).where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
        )
    ).scalar_one_or_none()
    if calendar_sync is None:
        return None

    canonical_query = select(TrainingPlan).where(
        TrainingPlan.user_id == user_id,
        TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
    )
    canonicals = db.execute(
        canonical_query.order_by(TrainingPlan.date, TrainingPlan.id)
    ).scalars().all()

    observations = db.execute(
        select(PlanTargetWorkout)
        .where(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
        )
        .order_by(
            PlanTargetWorkout.workout_date,
            PlanTargetWorkout.external_id,
        )
    ).scalars().all()
    observations = [
        row for row in observations
        if observation_matches_calendar(calendar_sync, row)
    ]
    calendar_generation = plan_target_calendar_generation(
        calendar_sync,
        observations,
    )
    observations_by_external = {
        row.external_id: row for row in observations
    }
    present_observations = [row for row in observations if row.present]

    deliveries = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.state != "removed",
        )
        .order_by(
            PlanDelivery.updated_at.desc(),
            PlanDelivery.created_at.desc(),
        )
    ).scalars().all()

    canonical_items: dict[str, PlanReconciliationItem] = {}
    consumed_observations: set[str] = set()
    consumed_canonicals: set[str] = set()

    for delivery in deliveries:
        observation = None
        match_basis = None
        if (
            delivery.external_id
        ):
            candidate_observation = observations_by_external.get(
                delivery.external_id
            )
            if (
                candidate_observation is not None
                and (
                    delivery.provider_account_id is None
                    or provider_account_references_match(
                        stored_account_id=delivery.provider_account_id,
                        current_account_id=(
                            calendar_sync.provider_account_id
                        ),
                        stored_references=(
                            delivery.provider_references or {}
                        ),
                        current_references=(
                            candidate_observation.provider_references
                            or {}
                        ),
                    )
                )
            ):
                observation = candidate_observation
                match_basis = "external_id"

        if (
            (observation is None or not observation.present)
            and delivery.provider_content_version
        ):
            fingerprint_matches = [
                row
                for row in present_observations
                if row.id not in consumed_observations
                and row.workout_date == delivery.workout_date
                and row.content_fingerprint
                == delivery.provider_content_version
            ]
            if len(fingerprint_matches) == 1:
                observation = fingerprint_matches[0]
                match_basis = "fingerprint"

        available_canonicals = [
            row
            for row in canonicals
            if row.canonical_id not in consumed_canonicals
        ]
        canonical = _select_canonical(
            delivery,
            observation,
            available_canonicals,
        )
        if canonical is None:
            if observation is not None:
                consumed_observations.add(observation.id)
            continue

        state, reason = _classify_delivery(
            canonical=canonical,
            observation=observation,
            delivery=delivery,
            calendar_sync=calendar_sync,
            match_basis=match_basis,
        )
        item = PlanReconciliationItem(
            id=f"delivery:{delivery.id}",
            state=state,
            target=target,
            canonical=canonical,
            observation=observation,
            delivery=delivery,
            match_basis=match_basis,
            reason=reason,
            calendar_generation=calendar_generation,
        )
        canonical_items[canonical.canonical_id] = item
        consumed_canonicals.add(canonical.canonical_id)
        if observation is not None:
            consumed_observations.add(observation.id)

    for canonical in canonicals:
        if canonical.canonical_id in consumed_canonicals:
            continue
        canonical_items[canonical.canonical_id] = PlanReconciliationItem(
            id=f"canonical:{canonical.canonical_id}",
            state="not_delivered",
            target=target,
            canonical=canonical,
            observation=None,
            delivery=None,
            calendar_generation=calendar_generation,
        )

    target_only: list[PlanReconciliationItem] = []
    for observation in present_observations:
        if observation.id in consumed_observations:
            continue
        if start is not None and observation.workout_date < start:
            continue
        if end is not None and observation.workout_date > end:
            continue
        target_only.append(
            PlanReconciliationItem(
                id=f"target:{observation.id}",
                state="target_only",
                target=target,
                canonical=None,
                observation=observation,
                delivery=None,
                calendar_generation=calendar_generation,
            )
        )

    visible_canonical_items = {
        canonical_id: item
        for canonical_id, item in canonical_items.items()
        if item.canonical is not None
        and (start is None or item.canonical.date >= start)
        and (end is None or item.canonical.date <= end)
    }

    return PlanReconciliationView(
        canonical_items=visible_canonical_items,
        target_only_items=tuple(target_only),
        calendar_sync=calendar_sync,
        calendar_generation=calendar_generation,
        consumed_observation_ids=frozenset(consumed_observations),
    )


def load_plan_reconciliation_item(
    db: Session,
    *,
    user_id: str,
    target: str,
    reconciliation_id: str,
    allow_owned_removal_retry: bool = False,
) -> PlanReconciliationItem | None:
    """Load a current item, retaining removed deliveries for safe retries."""
    view = build_plan_reconciliation(
        db,
        user_id=user_id,
        target=target,
    )
    if view is None:
        return None
    base_id, separator, expected_identity = reconciliation_id.partition("@")
    current = view.item_by_id(reconciliation_id)
    if current is not None:
        return current

    if base_id.startswith("target:"):
        observation_id = base_id.removeprefix("target:")
        observation = db.execute(
            select(PlanTargetWorkout).where(
                PlanTargetWorkout.id == observation_id,
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.target == target,
            )
        ).scalar_one_or_none()
        if (
            observation is None
            or not observation_matches_calendar(
                view.calendar_sync,
                observation,
            )
        ):
            return None
        if observation.id in view.consumed_observation_ids:
            return None
        item = PlanReconciliationItem(
            id=base_id,
            state="target_only",
            target=target,
            canonical=None,
            observation=observation,
            delivery=None,
            calendar_generation=view.calendar_generation,
        )
        if separator and item.resolution_identity != expected_identity:
            return None
        return item

    if not base_id.startswith("delivery:"):
        return None
    delivery_id = base_id.removeprefix("delivery:")
    delivery = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.id == delivery_id,
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
        )
    ).scalar_one_or_none()
    if delivery is None:
        return None
    if delivery.external_id:
        observation_candidates = db.execute(
            select(PlanTargetWorkout).where(
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.target == target,
                PlanTargetWorkout.external_id == delivery.external_id,
            )
        ).scalars().all()
        matching_observations = [
            row for row in observation_candidates
            if observation_matches_calendar(view.calendar_sync, row)
        ]
        observation = next(
            (
                row for row in matching_observations
                if row.provider_account_id
                == view.calendar_sync.provider_account_id
            ),
            matching_observations[0] if matching_observations else None,
        )
    else:
        observation = None
    canonicals = db.execute(
        select(TrainingPlan).where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        )
    ).scalars().all()
    canonical = _select_canonical(delivery, observation, canonicals)
    if canonical is None:
        return None
    state, reason = _classify_delivery(
        canonical=canonical,
        observation=observation,
        delivery=delivery,
        calendar_sync=view.calendar_sync,
        match_basis="external_id" if observation is not None else None,
    )
    item = PlanReconciliationItem(
        id=base_id,
        state=state,
        target=target,
        canonical=canonical,
        observation=observation,
        delivery=delivery,
        match_basis="external_id" if observation is not None else None,
        reason=reason,
        calendar_generation=view.calendar_generation,
    )
    if separator and item.resolution_identity != expected_identity:
        if (
            not allow_owned_removal_retry
            or observation is None
            or observation.present
            or delivery.state not in {"removed", "failed"}
        ):
            return None
        observations = db.execute(
            select(PlanTargetWorkout).where(
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.target == target,
            )
        ).scalars().all()
        observations = [
            row for row in observations
            if observation_matches_calendar(view.calendar_sync, row)
        ]
        retry_item = PlanReconciliationItem(
            id=base_id,
            state=state,
            target=target,
            canonical=canonical,
            observation=observation,
            delivery=delivery,
            match_basis="external_id",
            reason=reason,
            calendar_generation=plan_target_calendar_generation(
                view.calendar_sync,
                observations,
                presence_overrides={observation.id: True},
            ),
            calendar_observation_present=True,
        )
        if retry_item.resolution_identity != expected_identity:
            return None
        return retry_item
    return item
