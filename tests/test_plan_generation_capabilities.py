"""Plan-generation capability discovery contract tests."""
from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.auth import AuthenticatedIdentity, _require_data_access
from tests.test_plan_proposals import proposal_client


def _save_goal(db_session, *, user_id: str, goal: dict) -> None:
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        db.add(UserConfig(user_id=user_id, goal=goal))
        db.commit()
    finally:
        db.close()


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
    assert capability["policy_version"] == (
        "outdoor-5k-plan-generation-policy-v1"
    )
    assert capability["actions"]["generate_href"] == (
        "/api/plan/outdoor-5k/generate"
    )
    assert capability["actions"]["regenerate_href_template"].endswith(
        "/{proposal_id}/regenerate"
    )


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
    assert other.json()["selected_capability"] is None
    assert other.json()["unsupported_reason"] == "no_accepted_policy"
    assert [item["id"] for item in other.json()["capabilities"]] == [
        "outdoor_road_5k_v1"
    ]
