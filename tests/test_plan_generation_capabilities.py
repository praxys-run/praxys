"""Plan-generation capability discovery contract tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.auth import AuthenticatedIdentity, _require_data_access
from tests.test_plan_proposals import _proposal_payload, proposal_client


def _save_goal(db_session, *, user_id: str, goal: dict) -> None:
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        row = (
            db.query(UserConfig)
            .filter(UserConfig.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            row = UserConfig(user_id=user_id)
            db.add(row)
        row.goal = goal
        db.commit()
    finally:
        db.close()


def _add_recent_5k_activity(
    db_session,
    *,
    user_id: str,
    activity_id: str,
) -> None:
    from db.models import Activity, ActivitySplit

    with db_session.SessionLocal() as db:
        db.add(Activity(
            user_id=user_id,
            activity_id=activity_id,
            date=datetime.now(timezone.utc).date(),
            distance_km=5.0,
            duration_sec=1_500,
            activity_type="running",
            source="garmin",
        ))
        for split_num in range(1, 6):
            db.add(ActivitySplit(
                user_id=user_id,
                activity_id=activity_id,
                split_num=split_num,
                duration_sec=300,
                distance_km=1.0,
            ))
        db.commit()


def _link_payload_to_goal(
    payload: dict,
    *,
    goal: dict,
    goal_id: str,
    revision: str,
) -> None:
    target: dict[str, Any] = {}
    if goal.get("distance") is not None:
        target["distance"] = goal["distance"]
    target_time_sec = goal.get("target_time_sec")
    if target_time_sec is None:
        target_time_sec = goal.get("race_target_time_sec")
    if target_time_sec is not None:
        target["target_time_sec"] = target_time_sec
    payload["goal"].update({
        "goal_kind": goal["goal_kind"],
        "target": target,
        "purpose_source": "current_goal",
        "source_goal_id": goal_id,
        "source_goal_revision": revision,
    })


def _plugin_identity() -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        user_id="plugin-owner",
        user=cast(Any, object()),
        claims={"scope": ["plugin:tools"]},
        is_demo=False,
        credential_kind="mcp_session",
    )


def _request(method: str, path: str) -> Request:
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
    })


def test_current_goal_revision_ignores_metadata_and_normalizes_aliases() -> None:
    """Only the normalized plan contract contributes to Goal provenance."""
    from api.plan_generation_capabilities import current_goal_reference

    first = current_goal_reference(
        user_id="goal-revision-owner",
        goal={
            "goal_kind": "PERFORMANCE_5K",
            "distance": "5K",
            "race_target_time_sec": "1500",
            "race_date": "",
            "display_label": "First label",
            "metadata": {"updated_by": "web"},
        },
    )
    second = current_goal_reference(
        user_id="goal-revision-owner",
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1500,
            "race_date": None,
            "display_label": "Renamed",
            "metadata": {"updated_by": "miniapp"},
        },
    )

    assert first is not None
    assert second is not None
    assert first.goal_id == second.goal_id
    assert first.revision == second.revision
    assert first.contract == {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
        "race_date": None,
    }


@pytest.mark.parametrize(
    ("first_aliases", "second_aliases", "changed_field"),
    [
        (
            {
                "race_target_time_sec": 1500,
                "target_event_date": "2027-04-18",
            },
            {
                "race_target_time_sec": 1440,
                "target_event_date": "2027-04-18",
            },
            "target_time_sec",
        ),
        (
            {
                "race_target_time_sec": 1500,
                "target_event_date": "2027-04-18",
            },
            {
                "race_target_time_sec": 1500,
                "target_event_date": "2027-05-02",
            },
            "race_date",
        ),
    ],
)
def test_current_goal_revision_falls_back_from_empty_canonical_fields(
    first_aliases: dict[str, object],
    second_aliases: dict[str, object],
    changed_field: str,
) -> None:
    """Legacy aliases remain material when canonical fields are sentinels."""
    from api.plan_generation_capabilities import current_goal_reference

    canonical_sentinels = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 0,
        "race_date": "",
    }
    first = current_goal_reference(
        user_id="goal-revision-owner",
        goal={**canonical_sentinels, **first_aliases},
    )
    second = current_goal_reference(
        user_id="goal-revision-owner",
        goal={**canonical_sentinels, **second_aliases},
    )

    assert first is not None
    assert second is not None
    assert first.contract[changed_field] != second.contract[changed_field]
    assert first.revision != second.revision


@pytest.mark.parametrize(
    "changed_goal",
    [
        {
            "goal_kind": "continuous",
            "distance": "5k",
            "target_time_sec": 1500,
        },
        {
            "goal_kind": "performance_5k",
            "distance": "10k",
            "target_time_sec": 1500,
        },
        {
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1440,
        },
        {
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1500,
            "race_date": "2027-04-18",
        },
    ],
)
def test_current_goal_revision_changes_with_plan_contract(
    changed_goal: dict[str, object],
) -> None:
    """Each plan-relevant Goal field advances immutable provenance."""
    from api.plan_generation_capabilities import current_goal_reference

    original = current_goal_reference(
        user_id="goal-revision-owner",
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1500,
        },
    )
    changed = current_goal_reference(
        user_id="goal-revision-owner",
        goal=changed_goal,
    )

    assert original is not None
    assert changed is not None
    assert changed.goal_id == original.goal_id
    assert changed.revision != original.revision


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/plan/generation/capabilities"),
        ("POST", "/api/plan/outdoor-5k/readiness"),
        ("POST", "/api/plan/outdoor-5k/alternatives"),
        ("POST", "/api/plan/outdoor-5k/generate"),
        (
            "POST",
            "/api/plan/outdoor-5k/proposals/"
            "123e4567-e89b-12d3-a456-426614174000/regenerate",
        ),
    ],
)
def test_plugin_session_can_follow_advertised_generation_actions(
    method: str,
    path: str,
) -> None:
    """Capability discovery must not advertise routes the plugin cannot call."""
    _require_data_access(_plugin_identity(), _request(method, path))


def test_plugin_session_still_cannot_expand_beyond_generation_actions() -> None:
    """The capability allowlist must not broaden unrelated MCP authority."""
    with pytest.raises(HTTPException) as exc_info:
        _require_data_access(
            _plugin_identity(),
            _request("GET", "/api/history"),
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/plan/outdoor-5k/proposals/not-a-uuid/regenerate",
        (
            "/api/plan/outdoor-5k/proposals/"
            "123e4567-e89b-12d3-a456-426614174000/regenerate/extra"
        ),
    ],
)
def test_plugin_session_rejects_noncanonical_regeneration_paths(
    path: str,
) -> None:
    """Only the exact UUID-fenced regeneration route is MCP-callable."""
    with pytest.raises(HTTPException) as exc_info:
        _require_data_access(_plugin_identity(), _request("POST", path))
    assert exc_info.value.status_code == 403


def test_capability_discovery_selects_the_accepted_outdoor_5k_policy(
    proposal_client,
) -> None:
    """The current supported goal resolves to exact accepted policy metadata."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1500,
        },
    )

    response = client.get("/api/plan/generation/capabilities")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == 1
    assert body["goal"] == {
        "goal_kind": "performance_5k",
        "distance": "5k",
    }
    assert body["current_goal"]["goal"] == body["goal"]
    assert len(body["current_goal"]["id"]) == 36
    assert len(body["current_goal"]["revision"]) == 64
    assert body["active_plan_goal"] is None
    assert body["unsupported_reason"] is None
    assert len(body["capabilities"]) == 1
    capability = body["selected_capability"]
    assert capability == body["capabilities"][0]
    assert capability["id"] == "outdoor_road_5k_v1"
    assert capability["policy_status"] == "accepted"
    assert capability["goal_match"] == {
        "goal_kinds": ["performance_5k"],
        "distances": ["5k"],
        "surfaces": ["outdoor_road"],
    }
    assert capability["constraint_schema_id"] == (
        "outdoor_road_5k_constraints_v1"
    )
    assert capability["purpose"] == {
        "schema_version": 1,
        "goal_kind": "performance_5k",
        "distance": "5k",
        "allows_capability_goal": True,
        "allows_unlinked": False,
    }
    assert capability["policy_version"] == (
        "outdoor-5k-plan-generation-policy-v1"
    )
    assert capability["actions"]["generate_href"] == (
        "/api/plan/outdoor-5k/generate"
    )
    assert capability["actions"]["regenerate_href_template"].endswith(
        "/{proposal_id}/regenerate"
    )


def test_capability_routing_requires_explicit_intent_for_general_goal(
    proposal_client,
) -> None:
    """A distance alone must not silently choose completion or performance."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "race",
            "distance": "5k",
            "race_date": "2027-04-18",
        },
    )

    response = client.get("/api/plan/generation/capabilities")

    assert response.status_code == 200, response.text
    routing = response.json()["routing"]
    assert routing["state"] == "clarification_required"
    assert routing["intent"] is None
    assert routing["intent_source"] == "unconfirmed"
    assert routing["reason_code"] == "intent_confirmation_required"
    assert [option["intent"] for option in routing["options"]] == [
        "first_completion",
        "performance",
        "return_to_consistency",
    ]


def test_capability_routing_keeps_distinct_intents_off_performance_policy(
    proposal_client,
) -> None:
    """Completion and consistency cannot borrow the accepted 5K policy."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1_500,
        },
    )

    completion = client.get(
        "/api/plan/generation/capabilities?intent=first_completion",
    )
    consistency = client.get(
        "/api/plan/generation/capabilities?intent=return_to_consistency",
    )

    assert completion.status_code == 200, completion.text
    assert consistency.status_code == 200, consistency.text
    for response in (completion, consistency):
        routing = response.json()["routing"]
        assert routing["state"] == "policy_unavailable"
        assert routing["reason_code"] == "no_accepted_policy_for_intent"
        assert routing["capability_id"] is None
        assert routing["purpose_source"] is None


def test_capability_routing_returns_readiness_only_for_unqualified_5k_history(
    proposal_client,
) -> None:
    """An applicable policy stays readiness-only until baseline evidence exists."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "race",
            "distance": "5k",
            "race_date": "2027-04-18",
        },
    )

    response = client.get(
        "/api/plan/generation/capabilities?intent=performance",
    )

    assert response.status_code == 200, response.text
    routing = response.json()["routing"]
    assert routing["state"] == "readiness_only"
    assert routing["intent"] == "performance"
    assert routing["intent_source"] == "explicit"
    assert routing["reason_code"] == "accepted_policy_requires_readiness"
    assert routing["capability_id"] == "outdoor_road_5k_v1"
    assert routing["purpose_source"] == "capability"
    assert routing["baseline_readiness"] == "insufficient_evidence"


def test_capability_routing_supports_unlinked_only_purpose(
    proposal_client,
    monkeypatch,
) -> None:
    """A capability may route through its accepted unlinked purpose."""
    import api.plan_generation_capabilities as capabilities

    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "race",
            "distance": "5k",
            "race_date": "2027-04-18",
        },
    )
    unlinked_capability = replace(
        capabilities.OUTDOOR_ROAD_5K_CAPABILITY,
        allows_capability_goal=False,
        allows_unlinked=True,
    )
    monkeypatch.setattr(
        capabilities,
        "PLAN_GENERATION_CAPABILITIES",
        (unlinked_capability,),
    )

    response = client.get(
        "/api/plan/generation/capabilities?intent=performance",
    )

    assert response.status_code == 200, response.text
    routing = response.json()["routing"]
    assert routing["state"] == "readiness_only"
    assert routing["capability_id"] == "outdoor_road_5k_v1"
    assert routing["purpose_source"] == "unlinked"
    assert routing["baseline_readiness"] == "insufficient_evidence"


def test_capability_routing_returns_plan_candidate_for_qualified_5k_history(
    proposal_client,
) -> None:
    """Current qualified evidence promotes the route to a plan candidate."""
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _save_goal(
        db_session,
        user_id=user_id,
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1_500,
        },
    )
    _add_recent_5k_activity(
        db_session,
        user_id=user_id,
        activity_id="routing-qualified-5k",
    )
    confirmed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={"Idempotency-Key": "routing-qualified-5k"},
        json={
            "activity_id": "routing-qualified-5k",
            "response": "intentional_all_out",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    response = client.get("/api/plan/generation/capabilities")

    assert response.status_code == 200, response.text
    routing = response.json()["routing"]
    assert routing["state"] == "plan_candidate"
    assert routing["intent"] == "performance"
    assert routing["intent_source"] == "current_goal"
    assert routing["reason_code"] == (
        "accepted_policy_with_sufficient_baseline"
    )
    assert routing["capability_id"] == "outdoor_road_5k_v1"
    assert routing["purpose_source"] == "current_goal"
    assert routing["baseline_readiness"] == "sufficient_baseline"


def test_capability_routing_does_not_repurpose_performance_across_distance(
    proposal_client,
) -> None:
    """A selected performance intent still requires a same-distance policy."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "race",
            "distance": "10k",
            "race_date": "2027-04-18",
        },
    )

    response = client.get(
        "/api/plan/generation/capabilities?intent=performance",
    )

    assert response.status_code == 200, response.text
    routing = response.json()["routing"]
    assert routing["state"] == "policy_unavailable"
    assert routing["capability_id"] is None
    assert routing["reason_code"] == "no_accepted_policy_for_intent"


def test_capability_discovery_canonicalizes_legacy_goal_values(
    proposal_client,
) -> None:
    """Legacy case and omitted 5K distance still resolve canonically."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "PERFORMANCE_5K",
            "target_time_sec": "not-a-number",
        },
    )

    response = client.get("/api/plan/generation/capabilities")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["goal"] == {
        "goal_kind": "performance_5k",
        "distance": "5k",
    }
    assert body["selected_capability"]["id"] == (
        "outdoor_road_5k_v1"
    )
    from api.plan_generation_capabilities import (
        resolve_plan_generation_purpose,
    )

    with db_session.SessionLocal() as db:
        purpose = resolve_plan_generation_purpose(
            db,
            user_id=current_user["value"],
            selection={
                "capability_id": body["selected_capability"]["id"],
                "source": "current_goal",
                "expected_goal_id": body["current_goal"]["id"],
                "expected_goal_revision": body["current_goal"]["revision"],
            },
        )
    assert purpose.public_payload()["goal"] == {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": None,
        "race_date": None,
    }


def test_capability_discovery_is_owner_scoped_and_fails_closed(
    proposal_client,
) -> None:
    """Each caller sees only their goal match; unsupported goals gain no policy."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id="proposal-owner",
        goal={"goal_kind": "performance_5k", "distance": "5k"},
    )
    _save_goal(
        db_session,
        user_id="proposal-other",
        goal={
            "goal_kind": "race",
            "distance": "marathon",
            "race_date": "2027-04-18",
        },
    )

    owner = client.get("/api/plan/generation/capabilities")
    current_user["value"] = "proposal-other"
    other = client.get("/api/plan/generation/capabilities")

    assert owner.status_code == 200, owner.text
    assert owner.json()["selected_capability"]["id"] == "outdoor_road_5k_v1"
    assert other.status_code == 200, other.text
    assert other.json()["goal"] == {
        "goal_kind": "race",
        "distance": "marathon",
    }
    assert other.json()["current_goal"]["goal"] == other.json()["goal"]
    assert other.json()["selected_capability"] is None
    assert other.json()["unsupported_reason"] == "no_accepted_policy"
    assert [item["id"] for item in other.json()["capabilities"]] == [
        "outdoor_road_5k_v1"
    ]
    assert other.json()["capabilities"][0]["purpose"][
        "allows_capability_goal"
    ] is True


def test_inactive_road_10k_capability_stays_out_of_active_discovery(
    proposal_client,
) -> None:
    """The reviewed 10K capability metadata must not appear until activation."""
    client, db_session, current_user = proposal_client
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "performance_10k",
            "distance": "10k",
            "target_time_sec": 2_520,
            "race_date": "2026-09-20",
        },
    )

    response = client.get("/api/plan/generation/capabilities")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["goal"] == {
        "goal_kind": "performance_10k",
        "distance": "10k",
    }
    assert body["selected_capability"] is None
    assert all(
        capability["id"] != "outdoor_road_10k_performance_v1"
        for capability in body["capabilities"]
    )
    assert body["routing"]["intent"] == "performance"
    assert body["routing"]["intent_source"] == "current_goal"
    assert body["routing"]["state"] == "policy_unavailable"
    assert body["routing"]["reason_code"] == "no_accepted_policy_for_intent"
    assert body["current_goal"]["goal"] == body["goal"]
    assert body["unsupported_reason"] == "no_accepted_policy"


def test_capability_discovery_uses_fresh_active_proposal_goal(
    proposal_client,
) -> None:
    """A reassessed draft must not inherit stale linkage from the adopted plan."""
    from api.plan_generation_capabilities import current_goal_reference

    client, db_session, current_user = proposal_client
    first_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
    }
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal=first_goal,
    )
    first_reference = current_goal_reference(
        user_id=current_user["value"],
        goal=first_goal,
    )
    assert first_reference is not None
    initial_payload = _proposal_payload(key="capability-link-initial")
    _link_payload_to_goal(
        initial_payload,
        goal=first_goal,
        goal_id=first_reference.goal_id,
        revision=first_reference.revision,
    )
    initial = client.post(
        "/api/plan/proposals",
        json=initial_payload,
    )
    assert initial.status_code == 201, initial.text
    initial_body = initial.json()
    adopted = client.post(
        f"/api/plan/proposals/{initial_body['id']}/adopt",
        json={
            "expected_proposal_version": initial_body["version"],
            "expected_plan_version": initial_body["adaptive_plan"]["version"],
            "idempotency_key": "capability-link-adopt",
        },
    )
    assert adopted.status_code == 200, adopted.text

    next_goal = {
        **first_goal,
        "target_time_sec": 1440,
    }
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal=next_goal,
    )
    next_reference = current_goal_reference(
        user_id=current_user["value"],
        goal=next_goal,
    )
    assert next_reference is not None
    next_payload = _proposal_payload(key="capability-link-reassessed")
    _link_payload_to_goal(
        next_payload,
        goal=next_goal,
        goal_id=next_reference.goal_id,
        revision=next_reference.revision,
    )
    reassessed = client.post("/api/plan/proposals", json=next_payload)
    assert reassessed.status_code == 201, reassessed.text
    reassessed_body = reassessed.json()

    discovery = client.get("/api/plan/generation/capabilities")
    assert discovery.status_code == 200, discovery.text
    active_goal = discovery.json()["active_plan_goal"]
    assert active_goal["goal_snapshot_id"] == (
        reassessed_body["goal_snapshot_id"]
    )
    assert active_goal["source_goal_revision"] == next_reference.revision
    assert active_goal["link_status"] == "current"


def test_capability_discovery_ignores_expired_active_draft_goal(
    proposal_client,
) -> None:
    """An expired draft cannot mask the adopted plan's purpose provenance."""
    from datetime import datetime, timedelta

    from api.plan_generation_capabilities import current_goal_reference
    from db.models import PlanProposal

    client, db_session, current_user = proposal_client
    first_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
    }
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal=first_goal,
    )
    first_reference = current_goal_reference(
        user_id=current_user["value"],
        goal=first_goal,
    )
    assert first_reference is not None
    initial_payload = _proposal_payload(key="expired-link-initial")
    _link_payload_to_goal(
        initial_payload,
        goal=first_goal,
        goal_id=first_reference.goal_id,
        revision=first_reference.revision,
    )
    initial = client.post("/api/plan/proposals", json=initial_payload)
    assert initial.status_code == 201, initial.text
    initial_body = initial.json()
    adopted = client.post(
        f"/api/plan/proposals/{initial_body['id']}/adopt",
        json={
            "expected_proposal_version": initial_body["version"],
            "expected_plan_version": initial_body["adaptive_plan"]["version"],
            "idempotency_key": "expired-link-adopt",
        },
    )
    assert adopted.status_code == 200, adopted.text
    adopted_goal_snapshot_id = adopted.json()["proposal"]["goal_snapshot_id"]

    next_goal = {**first_goal, "target_time_sec": 1440}
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal=next_goal,
    )
    next_reference = current_goal_reference(
        user_id=current_user["value"],
        goal=next_goal,
    )
    assert next_reference is not None
    next_payload = _proposal_payload(key="expired-link-draft")
    _link_payload_to_goal(
        next_payload,
        goal=next_goal,
        goal_id=next_reference.goal_id,
        revision=next_reference.revision,
    )
    draft = client.post("/api/plan/proposals", json=next_payload)
    assert draft.status_code == 201, draft.text
    with db_session.SessionLocal() as db:
        row = db.get(PlanProposal, draft.json()["id"])
        assert row is not None
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()

    discovery = client.get("/api/plan/generation/capabilities")

    assert discovery.status_code == 200, discovery.text
    active_goal = discovery.json()["active_plan_goal"]
    assert active_goal["goal_snapshot_id"] == adopted_goal_snapshot_id
    assert active_goal["source_goal_revision"] == first_reference.revision
    assert active_goal["link_status"] == "reassessment_required"


def test_unsupported_goal_still_reports_linked_draft_for_recovery(
    proposal_client,
) -> None:
    """Clients retain lifecycle access when a linked draft loses goal support."""
    from api.plan_generation_capabilities import current_goal_reference

    client, db_session, current_user = proposal_client
    goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
    }
    _save_goal(db_session, user_id=current_user["value"], goal=goal)
    reference = current_goal_reference(
        user_id=current_user["value"],
        goal=goal,
    )
    assert reference is not None
    payload = _proposal_payload(key="unsupported-goal-draft")
    _link_payload_to_goal(
        payload,
        goal=goal,
        goal_id=reference.goal_id,
        revision=reference.revision,
    )
    draft = client.post("/api/plan/proposals", json=payload)
    assert draft.status_code == 201, draft.text
    _save_goal(
        db_session,
        user_id=current_user["value"],
        goal={
            "goal_kind": "race",
            "distance": "marathon",
            "race_date": "2027-04-18",
        },
    )

    discovery = client.get("/api/plan/generation/capabilities")

    assert discovery.status_code == 200, discovery.text
    assert discovery.json()["selected_capability"] is None
    active_goal = discovery.json()["active_plan_goal"]
    assert active_goal["goal_snapshot_id"] == draft.json()["goal_snapshot_id"]
    assert active_goal["purpose_source"] == "current_goal"
    assert active_goal["source_goal_id"] == reference.goal_id
    assert active_goal["source_goal_revision"] == reference.revision
    assert active_goal["link_status"] == "reassessment_required"
