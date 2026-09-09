"""Cross-layer regression for the actual Trail service/client fixture."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from tests import trail_api_contract_fixture as fixture_generator
from tests.test_non_ultra_trail_plan_generation import _record_schedule_returns
from tests.test_trail_plan_service import _unknown, _valid_request
from tests.trail_api_contract_fixture import (
    FIXTURE_PATH,
    build_trail_readiness_contract_fixture,
)


NONCE_DIGEST_KEYS = {
    "source_revision", "course_revision", "planning_context_revision",
    "composite_revision", "current_revision", "confirmed_revision",
    "assumption_confirmed_revision", "deterministic_input_hash",
    "readiness_receipt_digest",
}
PRESERVED_DIGEST_KEYS = {
    "history_revision", "source_revision_fingerprint", "contract_digest",
    "source_decision_digest", "ontology_contract_digest",
    "ontology_source_decision_digest",
}


def _leaves(value: Any, path: tuple = ()) -> dict[tuple, Any]:
    if isinstance(value, dict):
        return {
            leaf: child
            for key, item in value.items()
            for leaf, child in _leaves(item, (*path, key)).items()
        }
    if isinstance(value, list):
        return {
            leaf: child
            for index, item in enumerate(value)
            for leaf, child in _leaves(item, (*path, index)).items()
        }
    return {path: value}


def _set_path(value: Any, path: tuple, replacement: Any) -> None:
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


@pytest.fixture(scope="module")
def raw_service_cases() -> dict[str, dict[str, Any]]:
    """Intercept only fixture normalization, never service/evaluator execution."""
    cases: dict[str, dict[str, Any]] = {}

    def capture(name: str, source_case: str) -> None:
        with _record_schedule_returns() as schedules:
            cases[name] = fixture_generator._build_case(source_case)
        cases[name]["schedule_returns"] = schedules

    with patch.object(
        fixture_generator,
        "_canonicalize_dynamic_digests",
        side_effect=lambda _name, raw: deepcopy(raw),
    ) as normalization:
        for name in (
            "ordinary_confirmed", "expired_unavailable_date",
            "old_loaded_activity", "empty_history_fallback",
            "contradictory_preferred_weekday",
        ):
            capture(name, name)
        capture("ordinary_confirmed_again", "ordinary_confirmed")
        unknown = _valid_request()
        unknown["constraints"]["available_weekdays"] = _unknown()
        with patch.object(fixture_generator, "_valid_request", return_value=unknown):
            capture("unknown_available_weekdays", "ordinary_confirmed")
        assert normalization.call_count == len(cases)
    return cases


def test_trail_readiness_fixture_matches_actual_service_serialization() -> None:
    tracked = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert tracked == build_trail_readiness_contract_fixture()


@pytest.mark.parametrize("bad_hash", [
    None, 7, True, [], {},
    "sha256:" + "a" * 64, "A" * 64, "g" * 64,
    "a" * 63, "a" * 65, " " + "a" * 64, "a" * 64 + " ",
    "\t" + "a" * 64, "a" * 64 + "\n", "a" * 64 + "\r\n",
    "a" * 32 + "\n" + "a" * 32,
])
def test_nonce_normalization_rejects_invalid_raw_input_hash(
    raw_service_cases: dict[str, dict[str, Any]], bad_hash: Any,
) -> None:
    raw = deepcopy(raw_service_cases["ordinary_confirmed"]["response"])
    raw["readiness"]["deterministic_input_hash"] = bad_hash
    with pytest.raises(ValueError):
        fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", raw)


@pytest.mark.parametrize("bad_digest", [
    None, 7, True, [], {}, "a" * 64,
    "sha256:" + "A" * 64, "sha256:" + "g" * 64,
    "sha256:" + "a" * 63, "sha256:" + "a" * 65,
    " sha256:" + "a" * 64, "sha256:" + "a" * 64 + " ",
    "sha256:" + "a" * 64 + "\n", "sha256:" + "a" * 64 + "\r\n",
    "sha256:" + "a" * 32 + "\n" + "a" * 32,
    "SHA256:" + "a" * 64, "sha256:sha256:" + "a" * 64,
    "sha256x" + "a" * 64, "sha256:",
])
def test_nonce_normalization_rejects_invalid_raw_prefixed_digests(
    raw_service_cases: dict[str, dict[str, Any]], bad_digest: Any,
) -> None:
    original = raw_service_cases["ordinary_confirmed"]["response"]
    for path in _leaves(original):
        if path[-1] not in (NONCE_DIGEST_KEYS | PRESERVED_DIGEST_KEYS) - {
            "deterministic_input_hash",
        }:
            continue
        raw = deepcopy(original)
        _set_path(raw, path, bad_digest)
        with pytest.raises(ValueError):
            fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", raw)


@pytest.mark.parametrize("path", [
    ("draft", "composite_revision"),
    *[
        (side, "revision_bindings", key)
        for side in ("draft", "readiness")
        for key in (
            "course_revision", "planning_context_revision",
            "history_revision", "composite_revision",
        )
    ],
    ("draft", "revision_bindings", "section_confirmations", 0, "current_revision"),
    ("readiness", "revision_bindings", "section_confirmations", 0, "confirmed_revision"),
])
def test_nonce_normalization_rejects_well_formed_mismatched_bindings(
    raw_service_cases: dict[str, dict[str, Any]], path: tuple,
) -> None:
    raw = deepcopy(raw_service_cases["ordinary_confirmed"]["response"])
    _set_path(raw, path, "sha256:" + "a" * 64)
    with pytest.raises(ValueError):
        fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", raw)


def test_nonce_normalization_rejects_mirrored_but_stale_or_missing_confirmations(
    raw_service_cases: dict[str, dict[str, Any]],
) -> None:
    for missing in (False, True):
        raw = deepcopy(raw_service_cases["ordinary_confirmed"]["response"])
        for side in ("draft", "readiness"):
            confirmations = raw[side]["revision_bindings"]["section_confirmations"]
            if missing:
                confirmations.pop()
            else:
                confirmations[0]["confirmed_revision"] = "sha256:" + "a" * 64
        with pytest.raises(ValueError):
            fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", raw)


@pytest.mark.parametrize("path", [
    ("revision_bindings", "history_revision"),
    ("revision_bindings", "section_confirmations", 0, "current_revision"),
    ("course_demand", "fields", "distance_meters", "source_revision"),
])
def test_fixture_rejects_fresh_read_disagreement_before_normalization(path: tuple) -> None:
    read = fixture_generator.read_trail_plan_draft

    def mismatched_read(*args: Any, **kwargs: Any) -> dict[str, Any]:
        fresh = read(*args, **kwargs)
        _set_path(fresh, path, "sha256:" + "a" * 64)
        return fresh

    with (
        patch.object(fixture_generator, "read_trail_plan_draft", mismatched_read),
        patch.object(
            fixture_generator, "_canonicalize_dynamic_digests",
            wraps=fixture_generator._canonicalize_dynamic_digests,
        ) as normalize,
        pytest.raises(ValueError),
    ):
        fixture_generator._build_case("ordinary_confirmed")
    normalize.assert_not_called()


def test_raw_validation_precedes_any_digest_substitution(
    raw_service_cases: dict[str, dict[str, Any]],
) -> None:
    raw = deepcopy(raw_service_cases["ordinary_confirmed"]["response"])
    raw["readiness"]["readiness_receipt_digest"] += "\n"
    with (
        patch.object(
            fixture_generator.hashlib, "sha256",
            side_effect=AssertionError("nonce substitution ran before raw validation"),
        ),
        pytest.raises(ValueError),
    ):
        fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", raw)


def test_nonce_normalization_retains_deterministic_history_revisions(
    raw_service_cases: dict[str, dict[str, Any]],
) -> None:
    for name, case in raw_service_cases.items():
        raw = case["response"]
        normalized = fixture_generator._canonicalize_dynamic_digests(name, raw)
        assert normalized["readiness"]["history_statistics"] == raw["readiness"]["history_statistics"]
        for side in ("draft", "readiness"):
            assert normalized[side]["revision_bindings"]["history_revision"] == (
                raw[side]["revision_bindings"]["history_revision"]
            )


def test_nonce_normalization_preserves_every_equal_and_distinct_raw_reference(
    raw_service_cases: dict[str, dict[str, Any]],
) -> None:
    originals = [
        raw_service_cases[name]["response"]
        for name in ("ordinary_confirmed", "ordinary_confirmed_again")
    ]
    first, second = map(_leaves, originals)
    assert first.keys() == second.keys()
    for path, value in first.items():
        if path[-1] in NONCE_DIGEST_KEYS:
            assert value != second[path], f"actual fresh-save nonce dependency: {path}"
        else:
            assert value == second[path], f"nonce-independent value: {path}"

    normalized = fixture_generator._canonicalize_dynamic_digests("nonce-proof", originals)
    references: dict[str, set[str]] = {}
    for raw, canonical in zip(originals, normalized, strict=True):
        raw_leaves = _leaves(raw)
        canonical_leaves = _leaves(canonical)
        assert raw_leaves.keys() == canonical_leaves.keys()
        for path, value in raw_leaves.items():
            replacement = canonical_leaves[path]
            if path[-1] not in NONCE_DIGEST_KEYS:
                assert replacement == value
            if path[-1] in NONCE_DIGEST_KEYS | PRESERVED_DIGEST_KEYS:
                references.setdefault(value, set()).add(replacement)
    assert all(len(values) == 1 for values in references.values())
    assert len({next(iter(values)) for values in references.values()}) == len(references)
    assert (
        fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", originals[0])
        == fixture_generator._canonicalize_dynamic_digests("ordinary_confirmed", originals[1])
    )


def test_fresh_raw_service_payloads_parse_directly_before_nonce_normalization(
    raw_service_cases: dict[str, dict[str, Any]],
) -> None:
    result = subprocess.run(
        [
            "node", "--experimental-strip-types", "--input-type=module", "--eval",
            """
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseTrailDraftResponse, parseTrailReadinessResponse }
  from './src/components/trail-course-review/validation.ts';
const cases = JSON.parse(readFileSync(0, 'utf8'));
for (const [name, fixture] of Object.entries(cases)) {
  const raw = fixture.response;
  const before = JSON.stringify(raw);
  assert.equal(parseTrailDraftResponse(raw.draft), raw.draft, name);
  assert.equal(
    parseTrailReadinessResponse(raw, fixture.expected_composite_revision), raw, name,
  );
  assert.equal(JSON.stringify(raw), before, `${name}: parser must not rewrite raw data`);
}
console.log(`Parsed ${Object.keys(cases).length} fresh raw service payloads before nonce normalization.`);
""",
        ],
        input=json.dumps(raw_service_cases),
        cwd=Path(__file__).resolve().parents[1] / "web",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())


@pytest.mark.parametrize("name", [
    "ordinary_confirmed", "expired_unavailable_date",
    "unknown_available_weekdays", "contradictory_preferred_weekday",
])
def test_actual_service_schedule_reasons_distinguish_infeasible_from_skipped(
    raw_service_cases: dict[str, dict[str, Any]], name: str,
) -> None:
    case = raw_service_cases[name]
    response = case["response"]
    readiness = response["readiness"]
    expected = [
        "policy_unavailable.policy_inactive",
        "readiness_blocked.insufficient_recent_running_history",
        "readiness_blocked.insufficient_comparable_trail_history",
        "readiness_blocked.insufficient_descent_history",
    ]
    if name in {"ordinary_confirmed", "contradictory_preferred_weekday"}:
        assert case["schedule_returns"] == [None, None]
        expected.append("readiness_blocked.no_schedule_within_envelope")
    else:
        assert case["schedule_returns"] == []
    if name == "expired_unavailable_date":
        expected.insert(0, "validation_failed.invalid_field_value")
        assert case["evaluation_date"] == "2026-09-05"
        assert response["draft"]["constraints"]["unavailable_dates"]["value"] == ["2026-09-04"]
    elif name == "unknown_available_weekdays":
        expected.append("clarification_required.training_constraints_missing")
    elif name == "contradictory_preferred_weekday":
        expected.append("clarification_required.contradictory_input")
        assert response["draft"]["constraints"]["available_weekdays"]["value"] == [2, 4]
        assert response["draft"]["constraints"]["preferred_longest_weekday"] == 6
    assert [
        f"{reason['status']}.{reason['detail_reason']}"
        for reason in readiness["matching_reasons"]
    ] == expected
    assert readiness["plan"] is None
    assert readiness["inactive_dry_run"] is False
    assert readiness["contract_runtime_state"] == "inactive"
    assert case["evaluation_statement_count"] == 4
    confirmations = readiness["revision_bindings"]["section_confirmations"]
    assert len(confirmations) == 4
    assert all(item["current_revision"] == item["confirmed_revision"] for item in confirmations)
