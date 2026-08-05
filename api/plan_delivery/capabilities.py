"""Per-connection capability gates for experimental plan delivery."""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Mapping

from analysis.config import PLATFORM_CAPABILITIES, UserConfig
from db.connection_credentials import connection_credentials_generation
from db.models import UserConnection

EXPERIMENTAL_PLAN_DELIVERY_TARGETS = frozenset({"garmin"})
GARMIN_PLAN_DELIVERY_ENABLED_ENV = (
    "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED"
)
GARMIN_PLAN_DELIVERY_PILOT_USER_IDS_ENV = (
    "PRAXYS_GARMIN_PLAN_DELIVERY_PILOT_USER_IDS"
)


def garmin_plan_delivery_pilot_user_ids() -> frozenset[str]:
    """Return user IDs admitted to the production Garmin validation pilot."""
    return frozenset(
        user_id.strip()
        for user_id in os.environ.get(
            GARMIN_PLAN_DELIVERY_PILOT_USER_IDS_ENV,
            "",
        ).split(",")
        if user_id.strip()
    )


def garmin_plan_delivery_operator_enabled(
    user_id: str | None = None,
) -> bool:
    """Return whether this deployment permits Garmin writes for one user."""
    globally_enabled = os.environ.get(
        GARMIN_PLAN_DELIVERY_ENABLED_ENV,
        "",
    ).strip().casefold() in {"1", "true", "yes", "on"}
    return globally_enabled or (
        user_id is not None
        and user_id in garmin_plan_delivery_pilot_user_ids()
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
    user_id: str,
    source_options: Mapping[str, Any],
    connection: UserConnection | None,
) -> bool:
    """Return whether this user may select and mutate one execution target."""
    capabilities = PLATFORM_CAPABILITIES.get(target)
    if capabilities and capabilities.get("plan"):
        return True
    if target == "garmin":
        return (
            garmin_plan_delivery_operator_enabled(user_id)
            and has_plan_delivery_consent(
                connection,
                source_options=source_options,
            )
        )
    return False


def effective_platform_capabilities(
    config: UserConfig,
    *,
    user_id: str,
    connections: Mapping[str, UserConnection],
) -> dict[str, dict[str, bool]]:
    """Return public capability flags after applying per-user consent."""
    result = {
        platform: dict(capabilities)
        for platform, capabilities in PLATFORM_CAPABILITIES.items()
    }
    garmin = connections.get("garmin")
    result["garmin"]["plan"] = (
        garmin_plan_delivery_operator_enabled(user_id)
        and has_plan_delivery_consent(
            garmin,
            source_options=config.source_options,
        )
    )
    return result


def experimental_plan_delivery_status(
    config: UserConfig,
    *,
    user_id: str,
    connections: Mapping[str, UserConnection],
) -> dict[str, dict[str, Any]]:
    """Describe experimental target availability without granting consent."""
    connection = connections.get("garmin")
    available = garmin_plan_delivery_operator_enabled(user_id)
    return {
        "garmin": {
            "experimental": True,
            "available": available,
            "enabled": (
                available
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
