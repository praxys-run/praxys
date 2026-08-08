"""Per-connection rollout, selection, and runtime delivery fences."""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import TYPE_CHECKING, Any, Mapping

from analysis.config import PLATFORM_CAPABILITIES, UserConfig
from api import statsig_client
from db.connection_credentials import connection_credentials_generation
from db.models import UserConnection

if TYPE_CHECKING:
    from statsig import StatsigUser

ACCOUNT_FENCED_PLAN_DELIVERY_TARGETS = frozenset({"garmin"})
GARMIN_PLAN_DELIVERY_ENABLED_ENV = (
    "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED"
)
GARMIN_PLAN_DELIVERY_ELIGIBILITY_GATE = (
    "garmin_plan_delivery_eligible"
)


def garmin_plan_delivery_deployment_enabled() -> bool:
    """Return whether this deployment permits any Garmin workout writes."""
    return os.environ.get(
        GARMIN_PLAN_DELIVERY_ENABLED_ENV,
        "",
    ).strip().casefold() in {"1", "true", "yes", "on"}


def garmin_plan_delivery_eligible(
    statsig_user: StatsigUser | None,
) -> bool:
    """Return rollout eligibility layered under the hard deployment gate."""
    return (
        garmin_plan_delivery_deployment_enabled()
        and statsig_client.check_gate(
            GARMIN_PLAN_DELIVERY_ELIGIBILITY_GATE,
            statsig_user,
        )
    )


def garmin_region(source_options: Mapping[str, Any]) -> str | None:
    """Return the explicit Garmin account region, if configured."""
    region = source_options.get("garmin_region")
    return region if region in {"cn", "international"} else None


def plan_delivery_account_fence_token(
    connection: UserConnection,
    *,
    region: str,
) -> str:
    """Bind delivery authorization to one credential generation and region."""
    generation = connection_credentials_generation(connection)
    return hashlib.sha256(
        f"{connection.platform}\0{generation}\0{region}".encode("utf-8")
    ).hexdigest()


def has_plan_delivery_account_fence(
    connection: UserConnection | None,
    *,
    source_options: Mapping[str, Any],
) -> bool:
    """Return whether Garmin delivery matches the live account generation."""
    if (
        connection is None
        or connection.platform not in ACCOUNT_FENCED_PLAN_DELIVERY_TARGETS
        or connection.status != "connected"
        or not connection.plan_delivery_consent
    ):
        return False
    region = garmin_region(source_options)
    if region is None:
        return False
    expected = plan_delivery_account_fence_token(
        connection,
        region=region,
    )
    return hmac.compare_digest(
        str(connection.plan_delivery_consent),
        expected,
    )


def plan_delivery_target_selectable(
    target: str,
    *,
    source_options: Mapping[str, Any],
    connection: UserConnection | None,
    garmin_eligible: bool,
    target_registered: bool,
) -> bool:
    """Return whether the live connection can be chosen for delivery."""
    if (
        connection is None
        or connection.status != "connected"
        or not target_registered
    ):
        return False
    capabilities = PLATFORM_CAPABILITIES.get(target)
    if capabilities and capabilities.get("plan"):
        return True
    if target == "garmin":
        return (
            garmin_eligible
            and garmin_region(source_options) is not None
        )
    return False


def plan_delivery_capability_enabled(
    target: str,
    *,
    source_options: Mapping[str, Any],
    connection: UserConnection | None,
    garmin_eligible: bool,
    target_registered: bool = True,
) -> bool:
    """Return whether one target is authorized for a provider mutation."""
    if not plan_delivery_target_selectable(
        target,
        source_options=source_options,
        connection=connection,
        garmin_eligible=garmin_eligible,
        target_registered=target_registered,
    ):
        return False
    return (
        has_plan_delivery_account_fence(
            connection,
            source_options=source_options,
        )
        if target == "garmin"
        else True
    )


def effective_platform_capabilities(
    config: UserConfig,
    *,
    connections: Mapping[str, UserConnection],
    garmin_eligible: bool,
    registered_targets: set[str],
) -> dict[str, dict[str, bool]]:
    """Return public capabilities after applying connection eligibility."""
    result = {
        platform: dict(capabilities)
        for platform, capabilities in PLATFORM_CAPABILITIES.items()
    }
    garmin = connections.get("garmin")
    result["garmin"]["plan"] = plan_delivery_target_selectable(
        "garmin",
        source_options=config.source_options,
        connection=garmin,
        garmin_eligible=garmin_eligible,
        target_registered="garmin" in registered_targets,
    )
    return result


def plan_delivery_options(
    config: UserConfig,
    *,
    connections: Mapping[str, UserConnection],
    garmin_eligible: bool,
    registered_targets: set[str],
) -> list[dict[str, Any]]:
    """Describe every connected activity platform as a delivery choice."""
    options: list[dict[str, Any]] = []
    for platform, capabilities in PLATFORM_CAPABILITIES.items():
        connection = connections.get(platform)
        if (
            not capabilities.get("activities")
            or connection is None
            or connection.status != "connected"
        ):
            continue
        selectable = plan_delivery_target_selectable(
            platform,
            source_options=config.source_options,
            connection=connection,
            garmin_eligible=garmin_eligible,
            target_registered=platform in registered_targets,
        )
        reason = None
        if not selectable:
            reason = (
                "account_not_eligible"
                if platform == "garmin"
                else "delivery_not_supported"
            )
        options.append({
            "platform": platform,
            "selectable": selectable,
            "reason": reason,
        })
    return options
