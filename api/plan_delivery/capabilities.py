"""Per-connection capability gates for experimental plan delivery."""
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

EXPERIMENTAL_PLAN_DELIVERY_TARGETS = frozenset({"garmin"})
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


def plan_delivery_consent_token(
    connection: UserConnection,
    *,
    region: str,
) -> str:
    """Bind experimental consent to one credential generation and region."""
    generation = connection_credentials_generation(connection)
    return hashlib.sha256(
        f"{connection.platform}\0{generation}\0{region}".encode("utf-8")
    ).hexdigest()


def has_plan_delivery_consent(
    connection: UserConnection | None,
    *,
    source_options: Mapping[str, Any],
) -> bool:
    """Return whether the current Garmin connection retains explicit consent."""
    if (
        connection is None
        or connection.platform not in EXPERIMENTAL_PLAN_DELIVERY_TARGETS
        or connection.status != "connected"
        or not connection.plan_delivery_consent
    ):
        return False
    region = garmin_region(source_options)
    if region is None:
        return False
    expected = plan_delivery_consent_token(
        connection,
        region=region,
    )
    return hmac.compare_digest(
        str(connection.plan_delivery_consent),
        expected,
    )


def plan_delivery_capability_enabled(
    target: str,
    *,
    source_options: Mapping[str, Any],
    connection: UserConnection | None,
    garmin_eligible: bool,
) -> bool:
    """Return whether this user may select and mutate one execution target."""
    capabilities = PLATFORM_CAPABILITIES.get(target)
    if capabilities and capabilities.get("plan"):
        return True
    if target == "garmin":
        return (
            garmin_eligible
            and has_plan_delivery_consent(
                connection,
                source_options=source_options,
            )
        )
    return False


def effective_platform_capabilities(
    config: UserConfig,
    *,
    connections: Mapping[str, UserConnection],
    garmin_eligible: bool,
) -> dict[str, dict[str, bool]]:
    """Return public capability flags after applying per-user consent."""
    result = {
        platform: dict(capabilities)
        for platform, capabilities in PLATFORM_CAPABILITIES.items()
    }
    garmin = connections.get("garmin")
    result["garmin"]["plan"] = (
        garmin_eligible
        and has_plan_delivery_consent(
            garmin,
            source_options=config.source_options,
        )
    )
    return result


def experimental_plan_delivery_status(
    config: UserConfig,
    *,
    connections: Mapping[str, UserConnection],
    garmin_eligible: bool,
) -> dict[str, dict[str, Any]]:
    """Describe experimental target availability without granting consent."""
    connection = connections.get("garmin")
    return {
        "garmin": {
            "experimental": True,
            "available": garmin_eligible,
            "enabled": (
                garmin_eligible
                and has_plan_delivery_consent(
                    connection,
                    source_options=config.source_options,
                )
            ),
            "region": garmin_region(config.source_options),
            "connected": (
                connection is not None
                and connection.status == "connected"
            ),
            "fidelity": "duration_only",
        }
    }
