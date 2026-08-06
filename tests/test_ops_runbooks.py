"""Tests for the AI-native operations runbook contract."""

from copy import deepcopy

from scripts.validate_ops_runbooks import (
    build_eval_fixture,
    discover_runbooks,
    load_registry,
    validate_all,
    validate_runbook,
)


def test_structured_ops_runbooks_and_fixtures_are_valid() -> None:
    assert validate_all() == []


def test_routes_generate_action_and_verification_oracles() -> None:
    runbooks = dict((path.stem, data) for path, data in discover_runbooks())
    fixture = build_eval_fixture(runbooks["incident-response"])
    assert fixture["runbook"] == "incident-response"
    assert fixture["cases"][0]["expected"] == {
        "action": "restart-backend",
        "verify": ["api-health", "api-ready"],
        "on_failure": "escalate",
    }


def test_validator_rejects_unregistered_tool_and_signal_references() -> None:
    _, runbook = discover_runbooks()[0]
    invalid = deepcopy(runbook)
    invalid["actions"][0]["tool"] = "azure.subscription.delete"
    invalid["routes"][0]["verify"].append("missing-signal")

    errors = validate_runbook(invalid, load_registry(), "test-runbook")

    assert any("unknown action tool" in error for error in errors)
    assert any("unknown verify signal" in error for error in errors)
