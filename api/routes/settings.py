"""User settings endpoints.

Supports both file-based (backward compat) and DB-based config persistence.
When user_id and db are available (from auth), uses DB; otherwise falls back to files.
"""
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
import logging
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit
from dataclasses import asdict
from typing import Any, Literal
from zoneinfo import ZoneInfo

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from analysis.config import (
    ATHLETE_TIMEZONE_OPTION,
    load_config,
    save_config,
    load_config_from_db,
    save_config_to_db,
    normalize_plan_management,
    normalize_persisted_plan_management,
    normalize_athlete_timezone,
    PlatformName,
    TrainingBase,
    UserConfig,
    PLATFORM_CAPABILITIES,
)
from analysis.providers import available_providers
from analysis.thresholds import detect_thresholds
from analysis.training_base import get_display_config
from api import telemetry
from api.auth import (
    get_current_user_id,
    get_data_user_id,
    require_write_access,
)
from api.env_compat import getenv_compat
from api.plan_delivery import is_plan_delivery_target_registered
from api.plan_delivery.capabilities import (
    effective_platform_capabilities,
    garmin_plan_delivery_eligible,
    garmin_region,
    plan_delivery_account_fence_token,
    plan_delivery_options,
    plan_delivery_target_selectable,
)
from api.stryd_access import (
    is_stryd_provider,
    require_stryd_connection_enabled,
    stryd_connection_enabled,
)
from api.views import utc_isoformat
from db.models import UserConnection
from db.session import get_db
from db.sync_scheduler import (
    ALLOWED_SYNC_INTERVAL_HOURS,
    DEFAULT_SYNC_INTERVAL_HOURS,
    normalize_sync_interval_hours,
)

router = APIRouter()


SUPPORTED_LANGUAGES = {"en", "zh"}
_STRAVA_STATE_TTL_MINUTES = 10


def _garmin_delivery_eligibility(
    user_id: str,
    db: Session,
    config: UserConfig,
) -> bool:
    """Evaluate authoritative per-user Garmin rollout eligibility."""
    from api.statsig_client import get_statsig_user_for_account

    statsig_user = get_statsig_user_for_account(
        db,
        user_id=user_id,
        training_base=config.training_base,
        language=config.language,
    )
    return garmin_plan_delivery_eligible(statsig_user)


def _backfill_garmin_region_for_selection(
    user_id: str,
    db: Session,
    config: UserConfig,
) -> bool:
    """Migrate a connected legacy Garmin account's credential region."""
    if garmin_region(config.source_options) is not None:
        return False
    from db.connection_credentials import (
        CredentialAccessError,
        load_connection_credentials,
    )

    try:
        credentials = load_connection_credentials(
            db,
            user_id=user_id,
            platform="garmin",
        )
    except CredentialAccessError:
        return False
    if credentials is None or not isinstance(credentials.get("is_cn"), bool):
        return False
    config.source_options = {
        **config.source_options,
        "garmin_region": (
            "cn" if credentials["is_cn"] else "international"
        ),
    }
    return True


def _plan_management_transition(
    before: dict[str, Any],
    after: dict[str, Any],
) -> str | None:
    """Return the operator-facing lifecycle transition, if one occurred."""
    if before["mode"] != "praxys" and after["mode"] == "praxys":
        return "adopt"
    if before["mode"] == "praxys" and after["mode"] != "praxys":
        return "leave"
    if before["mode"] != "praxys" or after["mode"] != "praxys":
        return None
    if before["delivery_enabled"] and not after["delivery_enabled"]:
        return "pause"
    if not before["delivery_enabled"] and after["delivery_enabled"]:
        return "resume"
    if before["execution_target"] != after["execution_target"]:
        return "change_target"
    return None


class PlanManagementUpdate(BaseModel):
    """Partial managed-plan ownership update."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["external", "praxys"] | None = None
    execution_target: str | None = None
    delivery_enabled: bool | None = None
    adjustment_policy: Literal[
        "suggest_only",
        "auto_conservative",
    ] | None = None

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, value: str | None) -> str | None:
        """Validate targets without publishing private provider names."""
        if value is not None and value not in PLATFORM_CAPABILITIES:
            raise ValueError("Unsupported plan execution target")
        return value


class SettingsUpdate(BaseModel):
    """Partial update for user settings."""

    display_name: str | None = None
    unit_system: str | None = None
    connections: list[str] | None = None
    # dict[str, Any] so the nested `threshold_sources` mapping
    # (e.g. {"threshold_sources": {"cp_estimate": "stryd"}}) flows through.
    preferences: dict[str, Any] | None = None
    plan_management: PlanManagementUpdate | None = None
    managed_plan_preview_start: date | None = None
    training_base: TrainingBase | None = None
    thresholds: dict[str, Any] | None = None
    zones: dict[str, list[float]] | None = None
    goal: dict[str, Any] | None = None
    source_options: dict[str, Any] | None = None
    language: str | None = None


def _legacy_execution_target(plan_source: object) -> str | None:
    """Return a plan-capable provider from a legacy preference value."""
    if not isinstance(plan_source, str):
        return None
    target = plan_source.strip().casefold()
    caps = PLATFORM_CAPABILITIES.get(target)
    return target if caps and caps.get("plan") else None


def _valid_managed_preview_dates(
    config: UserConfig,
    *,
    now: datetime,
) -> set[date]:
    """Return current UTC and athlete-local dates accepted from clients."""
    utc_now = now.astimezone(timezone.utc)
    valid_dates = {utc_now.date()}
    timezone_name = normalize_athlete_timezone(
        config.source_options.get(ATHLETE_TIMEZONE_OPTION)
    )
    if timezone_name is not None:
        valid_dates.add(utc_now.astimezone(ZoneInfo(timezone_name)).date())
    return valid_dates


def _apply_plan_management_update(
    config: UserConfig,
    update: PlanManagementUpdate,
    *,
    user_id: str,
    db: Session,
    garmin_eligible: bool,
    stryd_eligible: bool,
) -> None:
    """Validate and merge an explicit managed-plan settings update."""
    changes = update.model_dump(exclude_unset=True)
    for required_field in ("mode", "delivery_enabled", "adjustment_policy"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(
                status_code=400,
                detail=f"plan_management.{required_field} cannot be null",
            )

    prior_management = config.plan_management
    if (
        prior_management["mode"] == "praxys"
        and not prior_management["delivery_enabled"]
        and prior_management["adjustment_policy"] == "auto_conservative"
        and changes.get("mode", "praxys") == "praxys"
        and changes.get("delivery_enabled") is True
        and changes.get("adjustment_policy") == "suggest_only"
    ):
        # Older clients sent their pre-feature placeholder on every resume.
        # Consent is independent from delivery, so that payload must not
        # silently revoke a policy the user enabled with a newer client.
        changes["adjustment_policy"] = "auto_conservative"

    candidate = {**config.plan_management, **changes}
    target_changed = (
        "execution_target" in changes
        and changes["execution_target"]
        != prior_management["execution_target"]
    )
    if (
        target_changed
        and prior_management["mode"] == "praxys"
        and prior_management["delivery_enabled"]
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Pause managed delivery before changing execution targets"
            ),
        )
    if (
        target_changed
        and prior_management["mode"] == "praxys"
        and candidate.get("delivery_enabled")
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Change the execution target and resume managed delivery "
                "in separate requests"
            ),
        )
    if (
        changes.get("mode") == "external"
        and "delivery_enabled" not in changes
    ):
        candidate["delivery_enabled"] = False
    if (
        changes.get("mode") == "external"
        and "adjustment_policy" not in changes
    ):
        candidate["adjustment_policy"] = "suggest_only"
    if (
        candidate.get("adjustment_policy") == "auto_conservative"
        and candidate.get("mode") != "praxys"
    ):
        raise HTTPException(
            status_code=400,
            detail="Automatic plan adjustment requires Praxys mode",
        )
    if candidate.get("delivery_enabled"):
        if candidate.get("mode") != "praxys":
            raise HTTPException(
                status_code=400,
                detail="Managed-plan delivery requires Praxys mode",
            )
        if not candidate.get("execution_target"):
            raise HTTPException(
                status_code=400,
                detail="Managed-plan delivery requires an execution target",
            )

    target = candidate.get("execution_target")
    if target is not None and (
        "execution_target" in changes
        or changes.get("delivery_enabled") is True
    ):
        if is_stryd_provider(target) and not stryd_eligible:
            raise HTTPException(status_code=404, detail="Not found")
        if target not in config.connections:
            raise HTTPException(
                status_code=400,
                detail="Plan execution target must be a connected platform",
            )
        # Lock in the same user-then-connection order as reconnect, region,
        # and token-rotation paths. Re-read the row after the user lock so a
        # Garmin fence can never be computed from a stale credential
        # generation while credentials are changing concurrently.
        _assert_execution_target_switch_safe(
            db,
            user_id=user_id,
            target=target,
        )
        # Preserve any connection invalidation performed earlier in this
        # request (for example, a Garmin region change) before refreshing the
        # locked row from the database.
        db.flush()
        connection = db.execute(
            select(UserConnection)
            .where(
                UserConnection.user_id == user_id,
                UserConnection.platform == target,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if connection is None or connection.status != "connected":
            raise HTTPException(
                status_code=409,
                detail="Plan execution target must be actively connected",
            )
        if not plan_delivery_target_selectable(
            target,
            source_options=config.source_options,
            connection=connection,
            garmin_eligible=garmin_eligible,
            target_registered=is_plan_delivery_target_registered(target),
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Garmin workout delivery is not available for this "
                    "account"
                    if target == "garmin"
                    else f"{target} does not support plan delivery"
                ),
            )
        if target == "garmin":
            region = garmin_region(config.source_options)
            assert region is not None
            # The durable target/resume choice is the user's product intent.
            # This internal fence only binds writes to that live account
            # generation and region; it is not a separate consent setting.
            connection.plan_delivery_consent = (
                plan_delivery_account_fence_token(
                    connection,
                    region=region,
                )
            )

    config.plan_management = normalize_plan_management(candidate)


def _assert_execution_target_switch_safe(
    db: Session,
    *,
    user_id: str,
    target: str,
) -> None:
    """Reject a target switch while another connector owns future delivery."""
    from db.models import PlanDelivery
    from db.plan_ledger import lock_plan_writes

    lock_plan_writes(db, user_id)
    outstanding_targets = {
        str(existing_target)
        for existing_target in db.execute(
            select(PlanDelivery.target).where(
                PlanDelivery.user_id == user_id,
                PlanDelivery.workout_date >= date.today(),
                PlanDelivery.state != "removed",
                PlanDelivery.target != target,
            )
        ).scalars()
    }
    if outstanding_targets:
        names = ", ".join(sorted(outstanding_targets))
        raise HTTPException(
            status_code=409,
            detail=(
                "Remove future Praxys deliveries from "
                f"{names} before selecting {target}"
            ),
        )


def _detect_thresholds_from_db(user_id: str, db) -> dict:
    """Auto-detect thresholds from fitness_data in the database.

    For each threshold, returns:

        {
          "value":  latest value (float),           // display convenience
          "source": source of the latest value,
          "options": [                              // all known sources
            {"source": "stryd",  "value": 265.0, "date": "2026-04-20"},
            {"source": "garmin", "value": 350.0, "date": "2026-04-22"},
          ]
        }

    ``options`` powers the Settings UI's source selector when a threshold has
    multiple provider sources (typically CP — Stryd vs Garmin). With only one
    source, the selector can stay hidden and the single value is shown as
    read-only. With zero sources the threshold is simply absent from the
    result.
    """
    from db.models import FitnessData

    result: dict = {}
    # (metric_type, threshold_key, default_source_when_row.source_is_null)
    metric_map = [
        ("cp_estimate", "cp_watts", "stryd"),
        ("lthr_bpm", "lthr_bpm", "garmin"),
        ("lt_pace_sec_km", "threshold_pace_sec_km", "garmin"),
        ("max_hr_bpm", "max_hr_bpm", "garmin"),
        ("rest_hr_bpm", "rest_hr_bpm", "garmin"),
    ]

    for metric_type, threshold_key, default_source in metric_map:
        # Filter null-date rows at the DB level so the invariant "rows[0]
        # is the latest" holds regardless of SQLite's NULL-ordering quirks.
        # Python-side per-source grouping: <100 rows per user in practice,
        # so a subquery-less approach keeps this readable.
        rows = (
            db.query(FitnessData)
            .filter(
                FitnessData.user_id == user_id,
                FitnessData.metric_type == metric_type,
                FitnessData.value.isnot(None),
                FitnessData.date.isnot(None),
            )
            .order_by(FitnessData.date.desc())
            .all()
        )
        if not rows:
            continue
        seen_sources: dict[str, FitnessData] = {}
        for row in rows:
            src = row.source or default_source
            # First occurrence wins — rows are already date-desc, so this is
            # the most recent row per source.
            if src not in seen_sources:
                seen_sources[src] = row
        options: list[dict] = []
        for src, r in seen_sources.items():
            try:
                options.append({
                    "source": src,
                    "value": round(float(r.value), 1),
                    "date": r.date.isoformat() if r.date else None,
                })
            except (TypeError, ValueError) as exc:
                # One malformed row mustn't blank out the whole Settings page.
                logger.warning(
                    "detect_thresholds: skipping row %s for user %s (%s=%r): %s",
                    r.id, user_id, metric_type, r.value, exc,
                )
        if not options:
            continue
        options.sort(key=lambda o: o["date"] or "", reverse=True)
        # Use options[0] rather than rows[0] so the displayed value always
        # matches one of the options the UI will render.
        result[threshold_key] = {
            "value": options[0]["value"],
            "source": options[0]["source"],
            "options": options,
        }

    # Fallback: derive max HR from activities if fitness_data has no row.
    # Exposed as a synthetic "activities" source so the UI can still show a
    # value — users can't select a different source when there isn't one.
    if "max_hr_bpm" not in result:
        from db.models import Activity
        from sqlalchemy import func
        max_hr = db.query(func.max(Activity.max_hr)).filter(
            Activity.user_id == user_id,
            Activity.max_hr.isnot(None),
        ).scalar()
        if max_hr:
            result["max_hr_bpm"] = {
                "value": round(float(max_hr), 1),
                "source": "activities",
                "options": [
                    {"source": "activities", "value": round(float(max_hr), 1), "date": None},
                ],
            }

    return result


def _connection_statuses(
    db: Session,
    *,
    user_id: str,
    stryd_enabled: bool,
) -> dict[str, str]:
    """Return fresh mutation-relevant status for each configured platform."""
    connections = db.execute(
        select(UserConnection)
        .where(UserConnection.user_id == user_id)
        .execution_options(populate_existing=True)
    ).scalars().all()
    return {
        connection.platform: connection.status or "disconnected"
        for connection in connections
        if stryd_enabled or not is_stryd_provider(connection.platform)
    }


def _registered_plan_delivery_targets() -> set[str]:
    """Return targets whose delivery adapters are available to this worker."""
    return {
        platform
        for platform in PLATFORM_CAPABILITIES
        if is_plan_delivery_target_registered(platform)
    }


def resolve_thresholds(
    config_thresholds: dict,
    detected: dict,
    threshold_sources: dict | None = None,
    activity_source: str | None = None,
) -> dict:
    """Pick the effective value for each threshold from detected sources.

    ``config_thresholds`` is ignored (kept in the signature so callers don't
    break; remove on the next major API version). Manual numeric overrides
    are not supported — source selection lives in ``threshold_sources``.

    Selection order:
        1. Explicit: ``threshold_sources[metric_type]`` if that source has
           an entry in ``options``.
        2. Default: ``activity_source`` — keeps CP aligned with the
           activities the user is viewing.
        3. Fallback: ``options[0]``. _detect_thresholds_from_db sorts
           options by date desc, so this is the most recent row.
    """
    _ = config_thresholds  # intentionally unused
    # metric_type keys match fitness_data.metric_type for all but CP.
    threshold_to_metric = {
        "cp_watts": "cp_estimate",
        "lthr_bpm": "lthr_bpm",
        "threshold_pace_sec_km": "lt_pace_sec_km",
        "max_hr_bpm": "max_hr_bpm",
        "rest_hr_bpm": "rest_hr_bpm",
    }
    sources_pref = threshold_sources or {}
    effective: dict[str, Any] = {}

    for key, metric_type in threshold_to_metric.items():
        info = detected.get(key)
        if not info or not info.get("options"):
            effective[key] = {"value": None, "origin": "none"}
            continue
        options = info["options"]
        preferred = sources_pref.get(metric_type) or activity_source
        picked = None
        if preferred:
            picked = next((o for o in options if o["source"] == preferred), None)
            if picked is None:
                # User chose a source that has no data yet; log so the
                # apparent mismatch between selection and displayed value
                # is visible in server logs.
                logger.debug(
                    "resolve_thresholds: preferred source %r for %s has no data; "
                    "falling back to latest (%s=%s)",
                    preferred, metric_type, options[0]["source"], options[0]["value"],
                )
        if picked is None:
            # latest — invariant maintained by _detect_thresholds_from_db's
            # `options.sort(key=...date, reverse=True)`.
            picked = options[0]
        effective[key] = {
            "value": picked["value"],
            "origin": f"auto ({picked['source']})",
        }
    return effective


def _without_stryd_config(config: UserConfig) -> dict[str, Any]:
    """Return a client-safe config without private Stryd selections."""
    payload = asdict(config)
    payload["connections"] = [
        platform
        for platform in payload.get("connections", [])
        if not is_stryd_provider(platform)
    ]
    preferences = dict(payload.get("preferences") or {})
    for key, value in list(preferences.items()):
        if is_stryd_provider(value):
            preferences.pop(key)
    threshold_sources = preferences.get("threshold_sources")
    if isinstance(threshold_sources, dict):
        preferences["threshold_sources"] = {
            key: value
            for key, value in threshold_sources.items()
            if not is_stryd_provider(value)
        }
    payload["preferences"] = preferences
    plan_management = dict(payload.get("plan_management") or {})
    if is_stryd_provider(plan_management.get("execution_target")):
        plan_management["execution_target"] = None
        plan_management["delivery_enabled"] = False
    payload["plan_management"] = plan_management
    payload["activity_routing"] = {
        activity_type: platform
        for activity_type, platform in (
            payload.get("activity_routing") or {}
        ).items()
        if not is_stryd_provider(platform)
    }
    return payload


def _without_stryd_thresholds(detected: dict[str, Any]) -> dict[str, Any]:
    """Remove private Stryd threshold observations from a response."""
    visible: dict[str, Any] = {}
    for key, info in detected.items():
        options = [
            option
            for option in info.get("options", [])
            if not is_stryd_provider(option.get("source"))
        ]
        if not options:
            continue
        visible[key] = {
            **info,
            "value": options[0].get("value"),
            "source": options[0].get("source"),
            "options": options,
        }
    return visible


def _settings_update_requests_stryd(body: SettingsUpdate) -> bool:
    """Return whether one settings mutation selects the private provider."""
    if (
        body.connections is not None
        and any(is_stryd_provider(value) for value in body.connections)
    ):
        return True
    if (
        body.plan_management is not None
        and is_stryd_provider(body.plan_management.execution_target)
    ):
        return True

    def contains_stryd(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().casefold() == "stryd"
        if isinstance(value, dict):
            return any(contains_stryd(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(contains_stryd(item) for item in value)
        return False

    return contains_stryd(body.preferences)


@router.get("/settings")
def get_settings(
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Return current user config, platform capabilities, detected thresholds, and display config."""
    config = load_config_from_db(user_id, db)
    garmin_eligible = _garmin_delivery_eligibility(user_id, db, config)
    stryd_enabled = stryd_connection_enabled(
        db,
        user_id=viewer_user_id,
    )
    connections = {
        connection.platform: connection
        for connection in db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
        ).all()
    }
    registered_targets = _registered_plan_delivery_targets()
    avail = available_providers()
    detected = _detect_thresholds_from_db(user_id, db)
    if not stryd_enabled:
        detected = _without_stryd_thresholds(detected)
    effective = resolve_thresholds(
        config.thresholds,
        detected,
        threshold_sources=config.preferences.get("threshold_sources"),
        activity_source=config.preferences.get("activities"),
    )
    capabilities = effective_platform_capabilities(
        config,
        connections=connections,
        garmin_eligible=garmin_eligible,
        registered_targets=registered_targets,
    )
    delivery_options = plan_delivery_options(
        config,
        connections=connections,
        garmin_eligible=garmin_eligible,
        registered_targets=registered_targets,
    )
    if not stryd_enabled:
        capabilities.pop("stryd", None)
        delivery_options = [
            option
            for option in delivery_options
            if option.get("platform") != "stryd"
        ]
    return {
        "config": (
            asdict(config)
            if stryd_enabled
            else _without_stryd_config(config)
        ),
        "connection_statuses": _connection_statuses(
            db,
            user_id=user_id,
            stryd_enabled=stryd_enabled,
        ),
        "platform_capabilities": capabilities,
        "plan_delivery_options": delivery_options,
        "available_providers": {
            category: [
                provider
                for provider in avail.get(category, [])
                if stryd_enabled or not is_stryd_provider(provider)
            ]
            for category in ("activities", "recovery", "fitness", "plan")
        },
        "available_bases": ["power", "hr", "pace"],
        "display": get_display_config(config.training_base),
        "detected_thresholds": detected,
        "effective_thresholds": effective,
        "sync_interval_options_hours": list(ALLOWED_SYNC_INTERVAL_HOURS),
        "default_sync_interval_hours": DEFAULT_SYNC_INTERVAL_HOURS,
    }


@router.put("/settings")
def update_settings(
    body: SettingsUpdate,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Update user settings and persist to database."""
    token_lease = nullcontext()
    if (
        body.source_options is not None
        and "garmin_region" in body.source_options
    ):
        from api.routes.sync import _garmin_tokenstore_lease

        token_lease = _garmin_tokenstore_lease(user_id)
    with token_lease:
        return _update_settings(body, user_id, db)


def _update_settings(
    body: SettingsUpdate,
    user_id: str,
    db: Session,
) -> dict:
    """Apply a settings update after any required provider lease is held."""
    config = load_config_from_db(user_id, db)
    stryd_enabled = stryd_connection_enabled(db, user_id=user_id)
    if not stryd_enabled and _settings_update_requests_stryd(body):
        raise HTTPException(status_code=404, detail="Not found")
    prior_plan_management = dict(config.plan_management)
    prior_goal = dict(config.goal)
    requested_execution_target = prior_plan_management.get(
        "execution_target"
    )
    if (
        body.plan_management is not None
        and "execution_target" in body.plan_management.model_fields_set
    ):
        requested_execution_target = (
            body.plan_management.execution_target
        )
    elif (
        body.plan_management is None
        and prior_plan_management.get("mode") == "external"
        and body.preferences is not None
        and "plan" in body.preferences
    ):
        requested_execution_target = _legacy_execution_target(
            body.preferences["plan"]
        )
        candidate_connections = (
            body.connections
            if body.connections is not None
            else config.connections
        )
        if requested_execution_target not in candidate_connections:
            requested_execution_target = None
    if (
        requested_execution_target == "garmin"
        and prior_plan_management.get("execution_target") != "garmin"
    ):
        from api.routes.plan import _STRYD_PUSH_STATUS_DIR
        from db.plan_ledger import (
            has_unresolved_legacy_stryd_corruption,
            import_legacy_stryd_status,
        )

        db.rollback()
        legacy_import = import_legacy_stryd_status(
            db,
            user_id=user_id,
            status_dir=_STRYD_PUSH_STATUS_DIR,
        )
        if (
            legacy_import == "corrupt"
            or has_unresolved_legacy_stryd_corruption(
                db,
                user_id=user_id,
            )
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Legacy Stryd delivery state requires review before "
                    "changing execution targets"
                ),
            )
        config = load_config_from_db(user_id, db)
        prior_plan_management = dict(config.plan_management)
        prior_goal = dict(config.goal)
    prior_garmin_region = garmin_region(config.source_options)
    legacy_target_update_requested = False
    legacy_target: PlatformName | None = None

    if body.display_name is not None:
        config.display_name = body.display_name
    if body.unit_system is not None:
        config.unit_system = body.unit_system
    if body.training_base is not None:
        config.training_base = body.training_base
    if body.connections is not None:
        config.connections = body.connections
    if body.preferences is not None:
        config.preferences.update(body.preferences)
        if (
            body.plan_management is None
            and config.plan_management["mode"] == "external"
            and "plan" in body.preferences
        ):
            legacy_target_update_requested = True
            legacy_target = _legacy_execution_target(body.preferences["plan"])
            if legacy_target not in config.connections:
                legacy_target = None
    # `thresholds` updates are accepted-and-dropped: manual numeric overrides
    # are no longer supported; source selection lives in
    # ``preferences.threshold_sources``. Kept in the schema for API compat
    # with older clients. A non-empty payload means a client still thinks it
    # can write numeric thresholds — log so we can find it.
    if body.thresholds:
        logger.info(
            "settings.update: discarding legacy thresholds payload "
            "(user %s, keys=%s)",
            user_id, sorted(body.thresholds.keys()),
        )
    if body.zones is not None:
        config.zones.update(body.zones)
    if body.goal is not None:
        config.goal.update(body.goal)
    if body.source_options is not None:
        source_options_update = dict(body.source_options)
        if ATHLETE_TIMEZONE_OPTION in source_options_update:
            athlete_timezone = normalize_athlete_timezone(
                source_options_update[ATHLETE_TIMEZONE_OPTION]
            )
            if athlete_timezone is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "source_options.athlete_timezone must be a valid "
                        "IANA timezone"
                    ),
                )
            source_options_update[ATHLETE_TIMEZONE_OPTION] = athlete_timezone
        if "sync_interval_hours" in source_options_update:
            try:
                source_options_update["sync_interval_hours"] = normalize_sync_interval_hours(
                    source_options_update["sync_interval_hours"]
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        config.source_options.update(source_options_update)
    garmin_selection_requested = (
        body.plan_management is not None
        and requested_execution_target == "garmin"
        and (
            "execution_target" in body.plan_management.model_fields_set
            or body.plan_management.delivery_enabled is True
        )
    )
    garmin_region_backfilled = False
    if garmin_selection_requested:
        garmin_region_backfilled = _backfill_garmin_region_for_selection(
            user_id,
            db,
            config,
        )
    garmin_eligible = _garmin_delivery_eligibility(user_id, db, config)
    garmin_region_changed = (
        not garmin_region_backfilled
        and
        garmin_region(config.source_options) != prior_garmin_region
    )
    if garmin_region_changed:
        from db.plan_ledger import lock_plan_writes

        lock_plan_writes(db, user_id)
        connection = db.execute(
            select(UserConnection)
            .where(
                UserConnection.user_id == user_id,
                UserConnection.platform == "garmin",
            )
            .with_for_update()
        ).scalar_one_or_none()
        if connection is not None:
            from db.sync_scheduler import reset_connection_backoff

            connection.plan_delivery_consent = None
            connection.status = "disconnected"
            reset_connection_backoff(connection)
        if (
            config.plan_management["execution_target"] == "garmin"
            and config.plan_management["delivery_enabled"]
        ):
            config.plan_management = normalize_plan_management({
                **config.plan_management,
                "delivery_enabled": False,
            })
    if body.plan_management is not None:
        _apply_plan_management_update(
            config,
            body.plan_management,
            user_id=user_id,
            db=db,
            garmin_eligible=garmin_eligible,
            stryd_eligible=stryd_enabled,
        )
    elif legacy_target_update_requested:
        current_target = config.plan_management.get("execution_target")
        if legacy_target != current_target:
            if legacy_target is not None:
                _assert_execution_target_switch_safe(
                    db,
                    user_id=user_id,
                    target=legacy_target,
                )
            config.plan_management = normalize_plan_management({
                **config.plan_management,
                "execution_target": legacy_target,
            })
    if body.language is not None:
        if body.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {body.language}. Supported: {sorted(SUPPORTED_LANGUAGES)}",
            )
        config.language = body.language
    if (
        config.plan_management["adjustment_policy"] == "auto_conservative"
        and normalize_athlete_timezone(
            config.source_options.get(ATHLETE_TIMEZONE_OPTION)
        )
        is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Automatic plan adjustment requires a valid athlete timezone"
            ),
        )

    managed_delivery_transition = (
        config.plan_management["mode"] == "praxys"
        and config.plan_management["delivery_enabled"]
        and config.plan_management != prior_plan_management
    )
    plan_management_transition = _plan_management_transition(
        prior_plan_management,
        config.plan_management,
    )
    adjustment_policy_transition = (
        config.plan_management["mode"] == "praxys"
        and config.plan_management["adjustment_policy"] == "auto_conservative"
        and prior_plan_management.get("adjustment_policy")
        != "auto_conservative"
    )
    if (
        managed_delivery_transition
        and body.managed_plan_preview_start is not None
        and body.managed_plan_preview_start
        not in _valid_managed_preview_dates(
            config,
            now=datetime.now(timezone.utc),
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "The managed-plan preview expired. "
                "Refresh the preview before enabling delivery."
            ),
        )

    if body.goal is not None:
        from api.goal_baseline import retire_goal_baseline_for_goal_change

        retire_goal_baseline_for_goal_change(
            db,
            user_id=user_id,
            previous_goal=prior_goal,
            next_goal=config.goal,
            now=datetime.utcnow(),
        )

    # Bust ETag caches keyed on config (Today, Training, Goal, History,
    # Science). A settings edit can flip training_base, language, or goal —
    # any of which alters every endpoint's payload, so we bump unconditionally.
    # Bump BEFORE save_config_to_db so the commit inside save_config covers
    # both the config change and the revision bump atomically.
    from db.cache_revision import bump_revisions
    bump_revisions(db, user_id, ["config"])
    save_config_to_db(user_id, config, db)
    if garmin_region_changed:
        from api.routes.sync import clear_garmin_tokens

        clear_garmin_tokens(user_id, db, block_legacy=True)
        db.commit()
    if plan_management_transition is not None:
        telemetry.record_managed_plan_event(
            category="lifecycle",
            action=plan_management_transition,
            outcome="success",
            user_id=user_id,
            target=(
                prior_plan_management.get("execution_target")
                if plan_management_transition == "leave"
                else config.plan_management.get("execution_target")
            ),
            trigger="settings",
        )

    adjustment_run = None
    if adjustment_policy_transition:
        try:
            from api.plan_adjustments import run_plan_adjustment_for_user

            adjustment_run = run_plan_adjustment_for_user(
                user_id,
                trigger="adjustment_policy_enabled",
            )
        except Exception:
            logger.exception(
                "Consent-time plan adjustment failed user=%s",
                user_id,
            )

    adjustment_delivered = (
        isinstance(adjustment_run, dict)
        and adjustment_run.get("status") == "adjusted"
    )
    if managed_delivery_transition and not adjustment_delivered:
        try:
            from api.plan_delivery.rolling import trigger_managed_plan_delivery

            if body.managed_plan_preview_start is not None:
                trigger_managed_plan_delivery(
                    user_id,
                    trigger="plan_management_enabled",
                    window_start=body.managed_plan_preview_start,
                )
            else:
                trigger_managed_plan_delivery(
                    user_id,
                    trigger="plan_management_enabled",
                )
        except Exception:
            logger.exception(
                "Post-commit managed delivery hook failed user=%s "
                "trigger=plan_management_enabled",
                user_id,
            )

    connections = {
        connection.platform: connection
        for connection in db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
        ).all()
    }
    registered_targets = _registered_plan_delivery_targets()
    capabilities = effective_platform_capabilities(
        config,
        connections=connections,
        garmin_eligible=garmin_eligible,
        registered_targets=registered_targets,
    )
    delivery_options = plan_delivery_options(
        config,
        connections=connections,
        garmin_eligible=garmin_eligible,
        registered_targets=registered_targets,
    )
    if not stryd_enabled:
        capabilities.pop("stryd", None)
        delivery_options = [
            option
            for option in delivery_options
            if option.get("platform") != "stryd"
        ]
    return {
        "status": "ok",
        "config": (
            asdict(config)
            if stryd_enabled
            else _without_stryd_config(config)
        ),
        "display": get_display_config(config.training_base),
        "connection_statuses": _connection_statuses(
            db,
            user_id=user_id,
            stryd_enabled=stryd_enabled,
        ),
        "platform_capabilities": capabilities,
        "plan_delivery_options": delivery_options,
    }


# ---------------------------------------------------------------------------
# Platform connection management
# ---------------------------------------------------------------------------


class ConnectPlatformRequest(BaseModel):
    """Credentials for connecting a platform."""
    # Garmin / Stryd
    email: str | None = None
    password: str | None = None
    # Oura
    token: str | None = None
    # Garmin-specific
    is_cn: bool = False
    # COROS-specific region
    region: str | None = None
    # Strava manual token fallback
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: int | None = None
    scope: str | None = None
    athlete_id: int | None = None
    athlete_username: str | None = None


class StravaOAuthStartRequest(BaseModel):
    """Start parameters for the browser-based Strava OAuth flow."""

    web_origin: str | None = None
    return_to: str = "/settings"
    client_id: str | None = None
    client_secret: str | None = None


def _jwt_secret() -> str:
    """Return the signing secret used for short-lived Strava OAuth state."""

    from api.auth_secrets import get_jwt_secret

    return get_jwt_secret()


def _validate_web_origin(raw_origin: str | None) -> str:
    """Validate a frontend origin used for the Strava return redirect."""

    if not raw_origin:
        raise HTTPException(400, "Missing web origin for Strava OAuth flow")
    parsed = urlparse(raw_origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Invalid web origin for Strava OAuth flow")
    return f"{parsed.scheme}://{parsed.netloc}"


def _validate_return_to(return_to: str | None) -> str:
    """Restrict post-auth redirects to local app paths."""

    value = (return_to or "/settings").strip()
    if not value.startswith("/") or value.startswith("//"):
        return "/settings"
    return value


def _strava_client_config(user_id: str | None = None, db: Session | None = None) -> tuple[str, str]:
    """Load Strava OAuth client credentials from user's stored connection or env vars."""

    if user_id and db:
        creds = _get_strava_creds(user_id, db)
        if creds:
            cid = creds.get("client_id")
            csec = creds.get("client_secret")
            if cid and csec:
                return cid, csec

    client_id = getenv_compat("STRAVA_CLIENT_ID")
    client_secret = getenv_compat("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Strava OAuth is not configured. Provide your Strava Client ID and Client Secret when connecting.",
        )
    return client_id, client_secret


def _get_strava_creds(user_id: str, db: Session) -> dict | None:
    """Return decrypted Strava credentials for a user, or None."""
    import json as json_mod
    from db.crypto import get_vault
    from db.models import UserConnection

    conn = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == "strava",
    ).first()
    if not conn or not conn.encrypted_credentials or not conn.wrapped_dek:
        return None
    vault = get_vault()
    return json_mod.loads(vault.decrypt(conn.encrypted_credentials, conn.wrapped_dek))


def _store_strava_client_creds(user_id: str, client_id: str, client_secret: str, db: Session) -> None:
    """Store (or update) Strava client_id/client_secret in the user's connection.

    If a connection already exists, the client credentials are merged into the
    existing encrypted payload so OAuth tokens aren't lost. The connection
    status is NOT set to "connected" — that only happens after the OAuth
    callback successfully exchanges the authorization code for tokens.
    """
    import json as json_mod
    from db.crypto import get_vault
    from db.models import UserConnection

    existing = _get_strava_creds(user_id, db) or {}
    existing["client_id"] = client_id
    existing["client_secret"] = client_secret

    vault = get_vault()
    encrypted_data, wrapped_dek = vault.encrypt(json_mod.dumps(existing))

    conn = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == "strava",
    ).first()

    if conn:
        conn.encrypted_credentials = encrypted_data
        conn.wrapped_dek = wrapped_dek
        # Keep existing status — don't flip to "connected" yet
    else:
        conn = UserConnection(
            user_id=user_id,
            platform="strava",
            encrypted_credentials=encrypted_data,
            wrapped_dek=wrapped_dek,
            status="disconnected",
        )
        db.add(conn)
    db.commit()


def _strava_redirect_uri(request: Request) -> str:
    """Resolve the callback URI registered with the Strava app."""

    override = getenv_compat("STRAVA_REDIRECT_URI")
    if override:
        return override
    return str(request.url_for("strava_oauth_callback"))


def _encode_strava_state(user_id: str, web_origin: str, return_to: str) -> str:
    """Create a short-lived signed state token for the Strava OAuth callback."""

    payload = {
        "sub": user_id,
        "purpose": "strava_connect",
        "web_origin": web_origin,
        "return_to": return_to,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_STRAVA_STATE_TTL_MINUTES),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _decode_strava_state(state: str) -> dict[str, Any]:
    """Validate and decode a Strava OAuth state token."""

    try:
        payload = jwt.decode(state, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(400, "Invalid Strava OAuth state") from exc
    if payload.get("purpose") != "strava_connect":
        raise HTTPException(400, "Invalid Strava OAuth state")
    return payload


def _pause_garmin_delivery_for_connection_change(
    user_id: str,
    db: Session,
    *,
    region: str | None,
) -> None:
    """Align Garmin region and pause writes when its connection changes."""
    from db.models import UserConfig as UserConfigModel

    config_row = db.query(UserConfigModel).filter(
        UserConfigModel.user_id == user_id,
    ).first()
    if config_row is None:
        config_row = UserConfigModel(user_id=user_id)
        db.add(config_row)
    source_options = {
        **(
            config_row.source_options
            if isinstance(config_row.source_options, dict)
            else {}
        ),
    }
    if region is not None:
        source_options["garmin_region"] = region
    config_row.source_options = source_options
    plan_management = normalize_persisted_plan_management(
        config_row.plan_management,
        execution_target_fence=config_row.plan_execution_target,
    )
    if (
        plan_management["execution_target"] == "garmin"
        and plan_management["delivery_enabled"]
    ):
        config_row.plan_management = {
            **plan_management,
            "delivery_enabled": False,
        }


def _revoke_garmin_delivery_before_login(
    user_id: str,
    db: Session,
) -> None:
    """Commit the old Garmin write fence while the token lease is held."""
    from db.cache_revision import bump_revisions
    from db.plan_ledger import lock_plan_writes
    from db.sync_scheduler import reset_connection_backoff

    lock_plan_writes(db, user_id)
    connection = db.execute(
        select(UserConnection)
        .where(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        )
        .with_for_update()
    ).scalar_one_or_none()
    if connection is not None:
        connection.encrypted_garmin_tokens = None
        connection.wrapped_token_dek = None
        connection.garmin_token_generation = None
        connection.tokens_updated_at = None
        connection.plan_delivery_consent = None
        connection.status = "disconnected"
        reset_connection_backoff(connection)
    _pause_garmin_delivery_for_connection_change(
        user_id,
        db,
        region=None,
    )
    bump_revisions(db, user_id, ["config"])
    db.commit()


def _upsert_connection_credentials(
    user_id: str,
    platform: str,
    creds: dict[str, Any],
    db: Session,
) -> UserConnection:
    """Encrypt and upsert platform credentials in the existing connection row."""

    import json as json_mod

    from db.crypto import get_vault
    from db.models import UserConnection

    vault = get_vault()
    encrypted_data, wrapped_dek = vault.encrypt(json_mod.dumps(creds))

    conn = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == platform,
    ).first()

    caps = PLATFORM_CAPABILITIES.get(platform, {})
    prefs = {k: v for k, v in caps.items() if v}

    if conn:
        # Re-uploading credentials is the user's "I fixed it" signal —
        # reset scheduler-backoff state so an auth_required connection
        # rejoins the regular schedule once the user clears whatever
        # gate (CAPTCHA, password change, MFA) blocked it.
        from db.sync_scheduler import reset_connection_backoff

        conn.encrypted_credentials = encrypted_data
        conn.wrapped_dek = wrapped_dek
        conn.status = "connected"
        conn.preferences = prefs
        if platform == "garmin":
            conn.encrypted_garmin_tokens = None
            conn.wrapped_token_dek = None
            conn.garmin_token_generation = None
            conn.tokens_updated_at = None
            conn.plan_delivery_consent = None
        reset_connection_backoff(conn)
    else:
        conn = UserConnection(
            user_id=user_id,
            platform=platform,
            encrypted_credentials=encrypted_data,
            wrapped_dek=wrapped_dek,
            status="connected",
            preferences=prefs,
        )
        db.add(conn)

    if platform == "garmin":
        _pause_garmin_delivery_for_connection_change(
            user_id,
            db,
            region=("cn" if creds.get("is_cn") else "international"),
        )

    # Connection state feeds UserConfig.connections and /api/plan.sync_target.
    # Stage the revision in the same transaction as the connection mutation.
    from db.cache_revision import bump_revisions
    bump_revisions(db, user_id, ["config"])
    db.flush()
    return conn


def _strava_redirect_target(
    web_origin: str,
    return_to: str,
    *,
    status: str,
    message: str | None = None,
) -> str:
    """Build the final frontend redirect target after the Strava callback."""

    split = urlsplit(return_to)
    params = parse_qsl(split.query, keep_blank_values=True)
    params.append(("strava", status))
    if message:
        params.append(("strava_message", message))
    target = urlunsplit(("", "", split.path, urlencode(params), split.fragment))
    return f"{web_origin}{target}"


@router.get("/settings/connections")
def get_connections(
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Return connected platforms and their status (credentials are never returned)."""
    from db.models import UserConnection

    connections = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
    ).all()
    stryd_enabled = stryd_connection_enabled(
        db,
        user_id=viewer_user_id,
    )

    result = {}
    for conn in connections:
        if is_stryd_provider(conn.platform) and not stryd_enabled:
            continue
        result[conn.platform] = {
            "status": conn.status,
            "last_sync": utc_isoformat(conn.last_sync),
            "has_credentials": conn.encrypted_credentials is not None,
            # Surfaced so the UI can show "Reconnect required" instead of
            # "Sync" when status is auth_required, and so it can show
            # "Next retry in 4h" while a transient backoff is in effect.
            # Both are read-only — the user clears them by reconnecting.
            "next_retry_at": utc_isoformat(conn.next_retry_at),
            "consecutive_failures": conn.consecutive_failures or 0,
            "last_error": conn.last_error,
        }
    return {"connections": result}


@router.post("/settings/connections/strava/start")
def start_strava_oauth(
    body: StravaOAuthStartRequest,
    request: Request,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Return the Strava OAuth authorize URL for the current user."""

    from sync.strava_sync import DEFAULT_SCOPE, build_authorize_url

    # If the user supplied client credentials, persist them now so the
    # callback (and future token refreshes) can read them back.
    if body.client_id and body.client_secret:
        _store_strava_client_creds(user_id, body.client_id, body.client_secret, db)

    client_id, _client_secret = _strava_client_config(user_id, db)
    web_origin = _validate_web_origin(body.web_origin or request.headers.get("origin"))
    return_to = _validate_return_to(body.return_to)
    state = _encode_strava_state(user_id, web_origin, return_to)
    authorize_url = build_authorize_url(
        client_id,
        _strava_redirect_uri(request),
        state,
        scope=DEFAULT_SCOPE,
    )
    return {"authorize_url": authorize_url}


@router.get("/settings/connections/strava/callback", name="strava_oauth_callback")
def strava_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    scope: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle the Strava OAuth callback and persist the encrypted tokens."""

    payload = _decode_strava_state(state or "")
    web_origin = _validate_web_origin(payload.get("web_origin"))
    return_to = _validate_return_to(payload.get("return_to"))

    if error:
        return RedirectResponse(
            _strava_redirect_target(web_origin, return_to, status="error", message=error)
        )
    if not code:
        return RedirectResponse(
            _strava_redirect_target(
                web_origin, return_to, status="error", message="missing_code"
            )
        )

    from sync.strava_sync import DEFAULT_SCOPE, exchange_code_for_token, fetch_athlete_api

    user_id_from_state = str(payload["sub"])
    client_id, client_secret = _strava_client_config(user_id_from_state, db)
    try:
        token_payload = exchange_code_for_token(code, client_id, client_secret)
        athlete = token_payload.get("athlete") or {}
        access_token = token_payload.get("access_token")
        if access_token and not athlete:
            athlete = fetch_athlete_api(access_token)
    except Exception:
        logger.exception(
            "Strava OAuth callback failed during token exchange/profile fetch"
        )
        return RedirectResponse(
            _strava_redirect_target(
                web_origin,
                return_to,
                status="error",
                message="oauth_callback_failed",
            )
        )

    # Merge OAuth tokens into existing credentials so client_id/client_secret
    # (stored during /start) are preserved.
    existing = _get_strava_creds(user_id_from_state, db) or {}
    existing.update({
        "access_token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "expires_at": int(token_payload.get("expires_at") or 0),
        "expires_in": int(token_payload.get("expires_in") or 0),
        "scope": scope or DEFAULT_SCOPE,
        "athlete": athlete,
    })
    _upsert_connection_credentials(user_id_from_state, "strava", existing, db)
    db.commit()

    return RedirectResponse(
        _strava_redirect_target(web_origin, return_to, status="connected")
    )


class GarminMfaRequest(BaseModel):
    """MFA verification code for completing an interactive Garmin login."""
    code: str | None = None
    login_attempt_id: str | None = None


def _persist_connected_garmin_login(
    db: Session,
    *,
    user_id: str,
    creds: dict,
    login_attempt_id: str,
) -> None:
    """Atomically fence credentials and clean tokens if binding fails."""
    from api.routes.sync import (
        _garmin_tokenstore_lease,
        bind_garmin_login_tokens,
        discard_garmin_login_tokens,
    )
    from db.connection_credentials import connection_credentials_generation

    credential_generation: str | None = None
    try:
        with _garmin_tokenstore_lease(user_id):
            connection = _upsert_connection_credentials(
                user_id,
                "garmin",
                creds,
                db,
            )
            credential_generation = connection_credentials_generation(
                connection
            )
            bind_garmin_login_tokens(
                db,
                user_id,
                credential_generation,
                login_attempt_id,
            )
            db.commit()
    except Exception:
        db.rollback()
        discard_garmin_login_tokens(user_id, login_attempt_id)
        raise


@router.post("/settings/connections/garmin/login")
def connect_garmin(
    body: ConnectPlatformRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Connect Garmin interactively so MFA-protected accounts can authenticate.

    Unlike the generic lazy ``connect_platform`` (which stores credentials and
    defers login to the background sync, where an MFA code can't be prompted
    for), this validates the credentials up front. When Garmin requires MFA the
    response is ``{"status": "mfa_required"}`` and the caller follows up with
    :func:`verify_garmin_mfa`; otherwise the credentials are persisted and the
    OAuth tokens cached for future syncs.
    """
    from garminconnect import (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
    )

    from api.routes.sync import (
        _garmin_tokenstore_lease,
        begin_garmin_login,
    )

    if not body.email or not body.password:
        return {"status": "error", "message": "email and password required"}

    creds = {"email": body.email, "password": body.password, "is_cn": bool(body.is_cn)}
    region = "cn" if body.is_cn else "international"

    def _emit(*, flow: str, outcome: str, failure_class: str) -> None:
        try:
            from api import telemetry
            telemetry.record_connection(
                platform="garmin", flow=flow, stage="credentials", outcome=outcome,
                failure_class=failure_class, region=region, user_id=user_id,
            )
        except Exception:
            pass

    try:
        with _garmin_tokenstore_lease(user_id):
            _revoke_garmin_delivery_before_login(user_id, db)
            result, login_attempt_id = begin_garmin_login(user_id, creds)
    except GarminConnectTooManyRequestsError:
        logger.warning("Garmin login rate limited for user %s", user_id)
        _emit(flow="unknown", outcome="error", failure_class="rate_limited")
        return {
            "status": "error",
            "message": "Too many login attempts. Please wait a few minutes and try again.",
        }
    except GarminConnectAuthenticationError:
        logger.warning("Garmin login rejected credentials for user %s", user_id)
        _emit(flow="unknown", outcome="error", failure_class="bad_credentials")
        return {
            "status": "error",
            "message": "Garmin could not verify your credentials. "
            "Check your email, password, and region, then try again.",
        }
    except Exception:
        logger.exception("Garmin interactive login failed for user %s", user_id)
        _emit(flow="unknown", outcome="error", failure_class="unknown")
        return {"status": "error", "message": "Login failed. Please try again."}

    if result == "mfa_required":
        _emit(flow="mfa", outcome="mfa_required", failure_class="none")
        return {
            "status": "mfa_required",
            "platform": "garmin",
            "login_attempt_id": login_attempt_id,
        }

    try:
        _persist_connected_garmin_login(
            db,
            user_id=user_id,
            creds=creds,
            login_attempt_id=login_attempt_id,
        )
    except Exception:
        logger.exception(
            "Garmin login token binding failed for user %s",
            user_id,
        )
        _emit(
            flow="non_mfa",
            outcome="error",
            failure_class="token_binding",
        )
        return {"status": "error", "message": "Login failed. Please try again."}
    _emit(flow="non_mfa", outcome="connected", failure_class="none")
    return {"status": "connected", "platform": "garmin"}


@router.post("/settings/connections/garmin/mfa")
def verify_garmin_mfa(
    body: GarminMfaRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Complete a pending interactive Garmin login with the user's MFA code."""
    from garminconnect import (
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
    )

    from api.routes.sync import (
        complete_garmin_mfa,
    )

    code = (body.code or "").strip()
    if not code:
        return {"status": "error", "message": "code required"}

    def _emit(*, outcome: str, failure_class: str) -> None:
        try:
            from api import telemetry
            telemetry.record_connection(
                platform="garmin", flow="mfa", stage="mfa_verify", outcome=outcome,
                failure_class=failure_class, region="n/a", user_id=user_id,
            )
        except Exception:
            pass

    try:
        creds, login_attempt_id = complete_garmin_mfa(
            user_id,
            code,
            (body.login_attempt_id or "").strip() or None,
        )
    except RuntimeError as e:
        if str(e) == "GARMIN_MFA_EXPIRED":
            _emit(outcome="error", failure_class="mfa_session_expired")
            return {"status": "error", "message": "mfa_session_expired"}
        raise
    except GarminConnectTooManyRequestsError:
        logger.warning("Garmin MFA rate limited for user %s", user_id)
        _emit(outcome="error", failure_class="rate_limited")
        return {
            "status": "error",
            "message": "Too many attempts. Please wait a few minutes and try again.",
        }
    except GarminConnectAuthenticationError:
        logger.warning("Garmin MFA code rejected for user %s", user_id)
        _emit(outcome="error", failure_class="mfa_code_rejected")
        return {
            "status": "error",
            "message": "The verification code was not accepted. "
            "Check the code and try again.",
        }
    except Exception:
        logger.exception("Garmin MFA verification failed for user %s", user_id)
        _emit(outcome="error", failure_class="unknown")
        return {"status": "error", "message": "MFA verification failed. Please try again."}

    try:
        _persist_connected_garmin_login(
            db,
            user_id=user_id,
            creds=creds,
            login_attempt_id=login_attempt_id,
        )
    except Exception:
        logger.exception(
            "Garmin MFA token binding failed for user %s",
            user_id,
        )
        _emit(outcome="error", failure_class="token_binding")
        return {
            "status": "error",
            "message": "MFA verification failed. Please try again.",
        }
    _emit(outcome="connected", failure_class="none")
    return {"status": "connected", "platform": "garmin"}


@router.post("/settings/connections/{platform}")
def connect_platform(
    platform: str,
    body: ConnectPlatformRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Connect a platform by storing encrypted credentials."""

    if platform not in PLATFORM_CAPABILITIES:
        return {"status": "error", "message": f"Unknown platform: {platform}"}
    if platform == "stryd":
        require_stryd_connection_enabled(db, user_id=user_id)
        from sync.stryd_sync import stryd_client_available

        if not stryd_client_available():
            raise HTTPException(
                status_code=503,
                detail="Stryd integration is unavailable",
            )

    # Build credentials dict based on platform
    if platform in ("garmin", "stryd"):
        if not body.email or not body.password:
            return {"status": "error", "message": "email and password required"}
        creds = {"email": body.email, "password": body.password}
        if platform == "garmin":
            creds["is_cn"] = body.is_cn
    elif platform == "coros":
        if not body.email or not body.password:
            return {"status": "error", "message": "email and password required"}
        coros_region = body.region or "us"
        if coros_region not in ("eu", "us", "cn"):
            coros_region = "us"
        creds: dict[str, Any] = {
            "email": body.email,
            "password": body.password,
            "region": coros_region,
        }
    elif platform == "oura":
        if not body.token:
            return {"status": "error", "message": "token required"}
        creds = {"token": body.token}
    elif platform == "strava":
        if not body.access_token or not body.refresh_token:
            return {"status": "error", "message": "access_token and refresh_token required"}
        creds = {
            "access_token": body.access_token,
            "refresh_token": body.refresh_token,
            "expires_at": int(body.expires_at or 0),
            "scope": body.scope or "read,activity:read_all,profile:read_all",
            "athlete": {
                "id": body.athlete_id,
                "username": body.athlete_username,
            },
        }
    else:
        return {"status": "error", "message": f"Unsupported platform: {platform}"}

    if platform == "garmin":
        from api.routes.sync import (
            _garmin_tokenstore_lease,
            clear_garmin_tokens,
        )

        # Commit a disconnected write fence before touching cached tokens.
        # A failed token removal or credential commit then cannot let sync
        # reuse the previous account's authenticated session.
        with _garmin_tokenstore_lease(user_id):
            _revoke_garmin_delivery_before_login(user_id, db)
            clear_garmin_tokens(user_id, db, block_legacy=True)
            _upsert_connection_credentials(user_id, platform, creds, db)
            db.commit()
    else:
        _upsert_connection_credentials(user_id, platform, creds, db)
        db.commit()

    try:
        from api import telemetry
        telemetry.record_connection(
            platform=platform, flow="n/a", stage="credentials", outcome="connected",
            failure_class="none", region="n/a", user_id=user_id,
        )
    except Exception:
        pass
    return {"status": "connected", "platform": platform}


@router.delete("/settings/connections/{platform}")
def disconnect_platform(
    platform: str,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Disconnect a platform — deletes stored credentials."""
    from db.models import UserConnection
    from db.plan_ledger import lock_plan_writes

    token_lease = nullcontext()
    clear_tokens = None
    if platform == "garmin":
        from api.routes.sync import (
            _garmin_tokenstore_lease,
            clear_garmin_tokens,
        )

        token_lease = _garmin_tokenstore_lease(user_id)
        clear_tokens = clear_garmin_tokens

    with token_lease:
        lock_plan_writes(db, user_id)
        conn = db.execute(
            select(UserConnection)
            .where(
                UserConnection.user_id == user_id,
                UserConnection.platform == platform,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if conn:
            from db.cache_revision import bump_revisions

            if platform == "garmin":
                _pause_garmin_delivery_for_connection_change(
                    user_id,
                    db,
                    region=garmin_region(
                        load_config_from_db(user_id, db).source_options
                    ),
                )
            db.delete(conn)
            bump_revisions(db, user_id, ["config"])
            db.commit()

        if clear_tokens is not None:
            clear_tokens(user_id)

    return {"status": "disconnected", "platform": platform}
