"""Fail-closed owner opt-in primitive for the inactive Road 10K capability."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from analysis.road_10k_contract import (
    ROAD_10K_CAPABILITY,
    ROAD_10K_POLICY_VERSION,
)
from api.plan_generation_capabilities import road_10k_capability_available
from db.models import Road10KOwnerOptInReceipt

ROAD_10K_OWNER_OPT_IN_SCHEMA_VERSION = "road-10k-owner-opt-in-v1"
ROAD_10K_OWNER_OPT_IN_CONSENT_VERSION = "road-10k-owner-consent-v1"

logger = logging.getLogger(__name__)


def road_10k_owner_opted_in(db: Session, user_id: str) -> bool:
    """Return effective authorization, never bypassing the inactive capability.

    This read-only primitive is intentionally not called by any route or
    client. Missing rows, stale versions, withdrawn decisions, ambiguous
    receipts, and database errors all return ``False``.
    """
    if not road_10k_capability_available() or not user_id:
        return False
    try:
        receipts = (
            db.query(Road10KOwnerOptInReceipt)
            .filter(
                Road10KOwnerOptInReceipt.user_id == user_id,
                Road10KOwnerOptInReceipt.capability_id
                == str(ROAD_10K_CAPABILITY["capability_id"]),
            )
            .order_by(
                Road10KOwnerOptInReceipt.decided_at.desc(),
                Road10KOwnerOptInReceipt.id.desc(),
            )
            .limit(2)
            .all()
        )
        if not receipts:
            return False
        receipt = receipts[0]
        # A timestamp tie is ambiguous even though the secondary id ordering
        # makes the query deterministic. Never authorize from that state.
        if len(receipts) > 1 and receipts[1].decided_at == receipt.decided_at:
            return False
        return (
            receipt.schema_version == ROAD_10K_OWNER_OPT_IN_SCHEMA_VERSION
            and receipt.policy_version == ROAD_10K_POLICY_VERSION
            and receipt.consent_text_version
            == ROAD_10K_OWNER_OPT_IN_CONSENT_VERSION
            and receipt.decision == "granted"
            and receipt.client in {"web", "miniapp"}
        )
    except Exception:
        logger.warning("Road 10K owner opt-in lookup failed closed", exc_info=True)
        return False
