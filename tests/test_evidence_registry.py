"""Tests for the versioned science evidence and decision registry."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

import analysis.metrics as metrics
from analysis.evidence_registry import (
    CitationSource,
    EffectEstimate,
    EvidenceReview,
    ParameterProvenance,
    RecordStatus,
    _validate_supersession,
    load_science_registry,
    render_registry_index,
)
from analysis.metrics import compute_heat_adaptation
from analysis.science import load_theory


def test_shipped_registry_is_valid_and_heat_migration_is_complete() -> None:
    registry = load_science_registry()

    assert set(registry.evidence_reviews) == {
        "evidence-environmental-performance-v1",
        "evidence-heat-adaptation-v1",
        "evidence-heat-decay-v1",
        "evidence-personal-environment-response-v1",
    }
    assert set(registry.decisions) == {
        "sdr-environmental-performance-v1",
        "sdr-environmental-performance-v2",
        "sdr-heat-adaptation-v1",
    }
    assert registry.evidence_reviews[
        "evidence-personal-environment-response-v1"
    ].status == "accepted"
    assert registry.decisions["sdr-environmental-performance-v2"].status == (
        "accepted"
    )

    decision = registry.decisions["sdr-heat-adaptation-v1"]
    assert decision.status == "accepted"
    assert decision.model_version == "heat-adaptation-v8"
    assert decision.model_version == metrics._HEAT_MODEL_VERSION
    assert set(decision.evidence_review_ids) == {
        "evidence-environmental-performance-v1",
        "evidence-heat-adaptation-v1",
        "evidence-heat-decay-v1",
    }
    assert decision.human_reviewers == ["github:dddtc2005"]


def test_environmental_performance_decision_preserves_product_boundaries() -> None:
    registry = load_science_registry()
    decision = registry.decisions["sdr-environmental-performance-v1"]
    review = registry.evidence_reviews["evidence-environmental-performance-v1"]

    assert decision.status == "superseded"
    assert decision.model_version == "environmental-performance-context-v1"
    assert decision.superseded_by == "sdr-environmental-performance-v2"
    assert decision.evidence_review_ids == [review.id]
    assert decision.model_parameters == []
    assert {
        "environment.marathon-wbgt-performance-level",
        "environment.humidity-fixed-temperature-capacity",
        "environment.solar-radiation-first-order",
        "environment.wet-bulb-not-safety-boundary",
        "environment.morphology-not-sex-coefficient",
    } <= set(decision.evidence_claim_ids)

    limits = " ".join(decision.user_facing_claim_limits)
    privacy = " ".join(decision.privacy_implications)
    assert "Never call psychrometric wet bulb WBGT" in limits
    assert "counterfactual finish time" in limits
    assert "Do not infer core temperature" in limits
    assert "never send or store a route trace" in privacy
    assert "Do not infer home or training locations" in privacy


def test_environment_response_decision_preserves_lifecycle_and_limits() -> None:
    registry = load_science_registry()
    predecessor = registry.decisions["sdr-environmental-performance-v1"]
    accepted = registry.decisions["sdr-environmental-performance-v2"]
    review = registry.evidence_reviews[
        "evidence-personal-environment-response-v1"
    ]

    assert predecessor.status == "superseded"
    assert predecessor.superseded_by == accepted.id
    assert accepted.status == "accepted"
    assert accepted.supersedes == [predecessor.id]
    assert accepted.human_reviewers == ["github:dddtc2005"]
    assert review.status == "accepted"
    assert review.human_reviewers == ["github:dddtc2005"]
    assert review.supersedes == []

    interpretation = accepted.accepted_interpretation
    limits = " ".join(accepted.user_facing_claim_limits)
    privacy = " ".join(accepted.privacy_implications)
    assert "historical association; not predictively validated" in (
        interpretation
    )
    assert "not a causal effect" in interpretation
    assert "every user an explicit opt-in" in interpretation
    assert "Never call psychrometric wet bulb WBGT" in limits
    assert "Do not call the cross-activity curve heart-rate drift" in limits
    assert "unavailable or unevaluable" in limits
    assert "Cross-user contribution is excluded" in privacy
    assert "Do not persist activity IDs" in privacy
    assert "external weather or route enrichment is prohibited" in privacy
    assert "encrypted temporary storage" in privacy
    assert "14-day PostgreSQL retention window" in privacy
    assert "Queue payloads contain only owner ID" in privacy
    assert "Caches must not retain raw exports" in privacy
    assert "running work must re-check active consent" in privacy

    parameters = {
        parameter.name: parameter for parameter in accepted.model_parameters
    }
    assert parameters["primary_model"].value == {
        "method": "ridge",
        "alpha": 4.0,
        "outcome": "steady_segment_mean_hr_bpm",
        "required_predictors": [
            "wet_bulb_c",
            "mean_pct_cp",
            "start_offset_min",
            "duration_min",
        ],
        "optional_complete_case_predictors": [
            "terrain_gain_m_per_km",
            "pre_activity_tsb",
            "recovery_readiness_score",
        ],
        "weighting": "equal_activity_weight_within_partition",
        "predictor_standardization": "training_rows_only",
        "intercept_penalized": False,
    }
    assert parameters["predictive_unavailable_behavior"].value == (
        "withhold_curve"
    )
    assert parameters["enrollment_scope"].value == (
        "all_users_explicit_opt_in"
    )
    assert parameters["power_source"].value == [
        "stryd_continuous_samples",
    ]
    assert parameters["candidate_power_regimes"].value == [
        "garmin_native_wrist_only_continuous_samples",
    ]
    assert parameters["garmin_power_provenance"].value == (
        "required_before_provider_qualification"
    )
    assert parameters["power_regime_isolation"].value == (
        "provider_device_and_algorithm_era"
    )
    assert parameters["pace_workload_fallback"].value == "prohibited_in_v1"
    assert parameters["multiple_power_regime_behavior"].value == (
        "separate_results_no_outcome_based_selection"
    )
    assert parameters["adult_eligibility"].value == (
        "explicit_18_plus_attestation_required"
    )
    assert parameters["availability_reason_shape"].value == [
        "code",
        "category",
        "public_message_key",
        "observed_aggregate",
        "required_guardrail",
        "user_actionable",
        "suggested_action_key",
        "analysis_stage",
        "power_regime",
        "model_version",
        "correlation_id",
    ]
    assert "unverified_garmin_wrist_power" in parameters[
        "availability_reason_codes"
    ].value
    assert "prediction_unavailable" in parameters[
        "availability_reason_codes"
    ].value
    assert {
        "missing_continuous_sample_power",
        "missing_continuous_heart_rate",
        "missing_temperature",
        "missing_relative_humidity",
        "missing_provider_aligned_critical_power",
        "adult_eligibility_not_confirmed",
    } <= set(parameters["availability_reason_codes"].value)
    assert parameters["processing_failure_behavior"].value == (
        "explicit_error_with_correlation_id"
    )
    assert parameters["labs_backup_maximum_retention_days"].value == 14
    assert parameters["curve_environment_domain_percentiles"].value == [
        10,
        90,
    ]
    assert parameters["curve_support_bin_count"].value == 5
    assert parameters["minimum_activities_per_curve_bin"].value == 5
    assert parameters["minimum_segments_per_curve_bin"].value == 10
    assert parameters["curve_reference_power_pct_cp"].value == [75.0, 85.0]
    assert parameters[
        "minimum_reference_power_activities_per_curve_bin"
    ].value == 5
    assert parameters["bootstrap_interval_must_exclude_zero"].value is True
    assert parameters[
        "maximum_bootstrap_interval_width_to_absolute_estimate_ratio"
    ].value == 1.0
    assert parameters[
        "leave_one_activity_out_minimum_sign_agreement"
    ].value == 0.8
    assert parameters[
        "leave_one_activity_out_maximum_relative_coefficient_change"
    ].value == 0.5
    assert parameters["planned_sensitivity_variants"].value == [
        "wider_power_band_60_to_100_pct_cp",
        "narrower_power_band_70_to_90_pct_cp",
        "warmup_exclusion_300_sec",
        "warmup_exclusion_900_sec",
        "minimum_segment_duration_120_sec",
        "minimum_segment_duration_300_sec",
        "temperature_only",
        "critical_power_minus_5_pct",
        "critical_power_plus_5_pct",
    ]
    assert parameters["minimum_available_sensitivity_variants"].value == 8
    assert all(
        parameter.classification.value == "guardrail"
        for parameter in accepted.model_parameters
        if isinstance(parameter.value, (int, float))
        and not isinstance(parameter.value, bool)
    )


def test_environmental_sources_record_verified_identifiers_and_review_depth() -> None:
    review = load_science_registry().evidence_reviews[
        "evidence-environmental-performance-v1"
    ]
    sources = {source.id: source for source in review.citations}

    expected = {
        "ely-2007": ("10.1249/mss.0b013e31802d3aba", "17473775"),
        "maughan-otani-watson-2012": (
            "10.1007/s00421-011-2206-7",
            "22012542",
        ),
        "otani-2016": ("10.1007/s00421-016-3335-9", "26842928"),
        "vecellio-2022": (
            "10.1152/japplphysiol.00738.2021",
            "34913738",
        ),
        "notley-2017": ("10.1113/EP086112", "28231604"),
    }
    assert {
        source_id: (sources[source_id].doi, sources[source_id].pmid)
        for source_id in expected
    } == expected

    notes = " ".join(review.review_notes)
    limitations = " ".join(review.method.method_limitations)
    assert "PubMed abstracts" in notes
    assert "PubMed Central full text" in notes
    assert "only the Vecellio 2022 claim received a full-text check" in limitations


def test_heat_retention_copy_rejects_a_fixed_plateau() -> None:
    root = Path(__file__).resolve().parents[1]
    source_paths = [
        root / "web" / "src" / "components" / "HeatAdaptationPanel.tsx",
        root / "miniapp" / "utils" / "heat-adaptation.ts",
        root / "data" / "science" / "heat" / "praxys_heat_evidence.yaml",
        root / "data" / "science" / "zh" / "heat" / "praxys_heat_evidence.yaml",
    ]
    copy = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

    assert "likely still retained" not in copy
    assert "operational retention window" not in copy
    assert "initial retention window" not in copy
    assert "response-specific" in copy
    assert "may already be declining" in copy


def test_heat_theory_links_to_accepted_decision_and_shared_citations() -> None:
    registry = load_science_registry()
    decision = registry.decisions["sdr-heat-adaptation-v1"]
    en = load_theory("heat", "praxys_heat_evidence")
    zh = load_theory("heat", "praxys_heat_evidence", locale="zh")

    assert en.science_decision_id == decision.id
    assert en.model_version == decision.model_version
    assert en.evidence_review_ids == decision.evidence_review_ids
    assert zh.science_decision_id == decision.id
    assert zh.model_version == decision.model_version
    assert zh.evidence_review_ids == decision.evidence_review_ids
    assert [citation.key for citation in en.citations] == [
        citation.key for citation in zh.citations
    ]
    assert [citation.url for citation in en.citations] == [
        citation.url for citation in zh.citations
    ]
    assert en.citations


def test_every_heat_theory_parameter_has_decision_provenance() -> None:
    registry = load_science_registry()
    decision = registry.decisions["sdr-heat-adaptation-v1"]
    theory = load_theory("heat", "praxys_heat_evidence")
    provenance = {
        parameter.name: parameter for parameter in decision.model_parameters
    }

    assert set(theory.params) <= set(provenance)
    for name, value in theory.params.items():
        parameter = provenance[name]
        assert parameter.value == value
        if parameter.classification == "published":
            assert parameter.evidence_claim_ids
        else:
            assert parameter.rationale

    assert any(
        parameter.classification == "published"
        for parameter in decision.model_parameters
    )
    assert any(
        parameter.classification == "estimate"
        for parameter in decision.model_parameters
    )
    assert any(
        parameter.classification == "guardrail"
        for parameter in decision.model_parameters
    )


def test_heat_code_guardrails_have_decision_provenance() -> None:
    decision = load_science_registry().decisions["sdr-heat-adaptation-v1"]
    provenance = {
        parameter.name: parameter.value
        for parameter in decision.model_parameters
    }

    scalars = {
        "wet_bulb_method": metrics._HEAT_WET_BULB_METHOD,
        "wet_bulb_cold_corner_temperature_below_c": (
            metrics._HEAT_WET_BULB_COLD_CORNER_TEMPERATURE_BELOW_C
        ),
        "wet_bulb_cold_corner_humidity_below_pct": (
            metrics._HEAT_WET_BULB_COLD_CORNER_HUMIDITY_BELOW_PCT
        ),
        "value_precision_decimals": metrics._HEAT_VALUE_PRECISION_DECIMALS,
        "active_window_days": metrics._HEAT_ACTIVE_WINDOW_DAYS,
        "minimum_power_fraction_cp": metrics._HEAT_MIN_POWER_FRACTION_CP,
        "sample_coverage_ratio": metrics._HEAT_SAMPLE_COVERAGE_RATIO,
        "qualifying_effective_minutes": metrics._HEAT_QUALIFYING_EFFECTIVE_MIN,
        "building_days": metrics._HEAT_BUILDING_MIN_DAYS,
        "building_effective_minutes": metrics._HEAT_BUILDING_EFFECTIVE_MIN,
        "likely_adapted_days": metrics._HEAT_ADAPTED_MIN_DAYS,
        "likely_adapted_effective_minutes": metrics._HEAT_ADAPTED_EFFECTIVE_MIN,
        "wet_bulb_reference_c": metrics._HEAT_REFERENCE_WET_BULB_C,
        "wet_bulb_full_weight_c": metrics._HEAT_FULL_WEIGHT_WET_BULB_C,
        "dry_bulb_reference_c": metrics._HEAT_REFERENCE_DRY_BULB_C,
        "dry_bulb_full_weight_c": metrics._HEAT_FULL_WEIGHT_DRY_BULB_C,
        "decay_start_days": metrics._HEAT_DECAY_START_DAYS,
        "decay_end_days": metrics._HEAT_DECAY_END_DAYS,
        "environment_weight_combination": (
            metrics._HEAT_ENVIRONMENT_WEIGHT_COMBINATION
        ),
        "lookback_days": metrics.HEAT_LOOKBACK_DAYS,
        "sample_max_interval_sec": metrics.HEAT_SAMPLE_MAX_INTERVAL_SEC,
        "confidence_moderate_activity_count": (
            metrics._HEAT_CONFIDENCE_MODERATE_ACTIVITY_COUNT
        ),
        "confidence_high_activity_count": (
            metrics._HEAT_CONFIDENCE_HIGH_ACTIVITY_COUNT
        ),
        "public_session_limit": metrics._HEAT_PUBLIC_SESSION_LIMIT,
        "provider_alignment_required": metrics._HEAT_PROVIDER_ALIGNMENT_REQUIRED,
        "reacclimation_min_post_gap_sessions": (
            metrics._HEAT_REACCLIMATION_MIN_POST_GAP_SESSIONS
        ),
    }
    ordered_ranges = {
        "wet_bulb_valid_temperature_c": (
            metrics._HEAT_WET_BULB_VALID_TEMPERATURE_C
        ),
        "wet_bulb_valid_relative_humidity_pct": (
            metrics._HEAT_WET_BULB_VALID_RELATIVE_HUMIDITY_PCT
        ),
        "activity_environment_temperature_c": (
            metrics._HEAT_ACTIVITY_ENVIRONMENT_TEMPERATURE_C
        ),
        "activity_environment_relative_humidity_pct": (
            metrics._HEAT_ACTIVITY_ENVIRONMENT_RELATIVE_HUMIDITY_PCT
        ),
    }
    sets = {
        "supported_environment_sources": (
            metrics._HEAT_SUPPORTED_ENVIRONMENT_SOURCES
        ),
        "eligible_activity_types": metrics.HEAT_ELIGIBLE_ACTIVITY_TYPES,
        "restrictive_today_recommendations": (
            metrics._HEAT_RESTRICTIVE_TODAY_RECOMMENDATIONS
        ),
        "heat_exposure_actions": metrics._HEAT_EXPOSURE_ACTIONS,
    }

    assert set(provenance) == set(scalars) | set(ordered_ranges) | set(sets)
    for name, value in scalars.items():
        assert provenance[name] == value
    for name, value in ordered_ranges.items():
        assert tuple(provenance[name]) == value
    for name, value in sets.items():
        assert set(provenance[name]) == set(value)


def test_linked_heat_theory_does_not_duplicate_registry_data() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "science"
    en = yaml.safe_load(
        (root / "heat" / "praxys_heat_evidence.yaml").read_text(
            encoding="utf-8",
        )
    )
    zh = yaml.safe_load(
        (root / "zh" / "heat" / "praxys_heat_evidence.yaml").read_text(
            encoding="utf-8",
        )
    )

    assert en["science_decision_id"] == metrics._HEAT_SCIENCE_DECISION_ID
    assert "citations" not in en
    assert "citations" not in zh
    assert "params" not in zh
    assert "science_decision_id" not in zh


def test_theory_link_rejects_parameter_drift() -> None:
    registry = load_science_registry()
    theory = load_theory("heat", "praxys_heat_evidence")
    changed = {**theory.params, "active_window_days": 13}

    with pytest.raises(ValueError, match="parameter values differ"):
        registry.validate_theory_link(
            decision_id=theory.science_decision_id or "",
            model_key="heat/praxys_heat_evidence",
            model_version=theory.model_version or "",
            params=changed,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("doi", "not-a-doi"),
        ("pmid", "PMID-123"),
        ("url", "ftp://example.com/paper"),
    ],
)
def test_citation_identifier_syntax_is_validated(
    field: str,
    value: str,
) -> None:
    raw = {
        "id": "source-2026",
        "title": "Example source",
        "authors": ["Example, A."],
        "year": 2026,
        "journal": "Example Journal",
        "doi": "10.1000/example",
    }
    raw[field] = value

    with pytest.raises(ValidationError):
        CitationSource.model_validate(raw)


def test_citation_requires_a_stable_identifier() -> None:
    with pytest.raises(ValidationError):
        CitationSource.model_validate({
            "id": "source-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
        })


@pytest.mark.parametrize(
    "url",
    [
        "https://doi.org/10.1000/example",
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://www.ncbi.nlm.nih.gov/pubmed/12345678/",
    ],
)
def test_citation_resolver_urls_require_structured_identifiers(
    url: str,
) -> None:
    with pytest.raises(ValidationError, match="structured"):
        CitationSource.model_validate({
            "id": "example-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
            "url": url,
        })


def test_pubmed_url_must_match_structured_identifier() -> None:
    with pytest.raises(ValidationError, match="must match"):
        CitationSource.model_validate({
            "id": "example-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
            "pmid": "87654321",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        })


@pytest.mark.parametrize(
    "raw",
    [
        {
            "name": "published_value",
            "value": 1,
            "classification": "published",
            "rationale": "A rationale cannot replace a source claim.",
        },
        {
            "name": "estimated_value",
            "value": 1,
            "classification": "estimate",
            "evidence_claim_ids": ["claim.support"],
        },
        {
            "name": "guardrail_value",
            "value": 1,
            "classification": "guardrail",
        },
    ],
)
def test_parameter_provenance_requires_claims_or_rationale(raw: dict) -> None:
    with pytest.raises(ValidationError):
        ParameterProvenance.model_validate(raw)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_registry_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValidationError):
        EffectEstimate.model_validate({
            "metric": "Example",
            "estimate": value,
            "unit": "units",
            "context": "Synthetic fixture",
        })

    with pytest.raises(ValidationError):
        ParameterProvenance.model_validate({
            "name": "example",
            "value": value,
            "classification": "guardrail",
            "rationale": "Synthetic fixture.",
        })


def test_accepted_review_requires_human_review_metadata() -> None:
    with pytest.raises(ValidationError):
        EvidenceReview.model_validate({
            "schema_version": 1,
            "id": "evidence-example-v1",
            "version": 1,
            "title": "Example",
            "research_question": "What does the evidence support?",
            "topic": "example",
            "status": "accepted",
            "authors": ["agent:copilot"],
            "created_on": "2026-07-25",
            "intended_product_purpose": "Test validation.",
            "scope": {
                "population": ["Adults"],
                "intervention_or_exposure": ["Example exposure"],
                "comparator": ["Control"],
                "outcomes": ["Example outcome"],
            },
            "method": {
                "review_type": "rapid",
                "search_date": "2026-07-25",
                "sources": [{
                    "name": "PubMed",
                    "search_string": "example query",
                }],
                "inclusion_criteria": ["Peer-reviewed human research"],
                "exclusion_criteria": ["Non-human research"],
            },
            "claims": [{
                "id": "example.support",
                "statement": "The example supports the test fixture.",
                "source_ids": ["example-2026"],
                "evidence_strength": "low",
                "applicable_population": ["Adults"],
                "domain": ["Example"],
                "limitations": ["Synthetic fixture"],
            }],
            "citations": [{
                "id": "example-2026",
                "title": "Example source",
                "authors": ["Example, A."],
                "year": 2026,
                "journal": "Example Journal",
                "doi": "10.1000/example",
            }],
            "known_gaps": [],
            "conflicting_findings": [],
            "follow_up_questions": [],
        })


def test_registry_rejects_unknown_claim_reference(tmp_path: Path) -> None:
    science_dir = tmp_path / "science"
    evidence_dir = science_dir / "evidence" / "example"
    decisions_dir = science_dir / "decisions"
    evidence_dir.mkdir(parents=True)
    decisions_dir.mkdir(parents=True)

    review = {
        "schema_version": 1,
        "id": "evidence-example-v1",
        "version": 1,
        "title": "Example evidence",
        "research_question": "What does the evidence support?",
        "topic": "example",
        "status": "accepted",
        "authors": ["agent:copilot"],
        "human_reviewers": ["github:reviewer"],
        "created_on": "2026-07-25",
        "reviewed_on": "2026-07-25",
        "intended_product_purpose": "Exercise cross-record validation.",
        "scope": {
            "population": ["Adults"],
            "intervention_or_exposure": ["Example exposure"],
            "comparator": ["Control"],
            "outcomes": ["Example outcome"],
        },
        "method": {
            "review_type": "rapid",
            "search_date": "2026-07-25",
            "sources": [{
                "name": "PubMed",
                "search_string": "example query",
            }],
            "inclusion_criteria": ["Peer-reviewed human research"],
            "exclusion_criteria": ["Non-human research"],
        },
        "claims": [{
            "id": "example.support",
            "statement": "The example supports the test fixture.",
            "source_ids": ["example-2026"],
            "evidence_strength": "low",
            "applicable_population": ["Adults"],
            "domain": ["Example"],
            "limitations": ["Synthetic fixture"],
        }],
        "citations": [{
            "id": "example-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
            "doi": "10.1000/example",
        }],
        "known_gaps": [],
        "conflicting_findings": [],
        "follow_up_questions": [],
    }
    decision = {
        "schema_version": 1,
        "id": "sdr-example-v1",
        "version": 1,
        "title": "Example decision",
        "status": "accepted",
        "decision_date": "2026-07-25",
        "owners": ["team:praxys"],
        "human_reviewers": ["github:reviewer"],
        "model_version": "example-v1",
        "evidence_review_ids": ["evidence-example-v1"],
        "evidence_claim_ids": ["missing.claim"],
        "accepted_interpretation": "Use the example.",
        "rejected_alternatives": [{
            "alternative": "Do not use the example.",
            "rationale": "It would not exercise the registry.",
        }],
        "model_parameters": [],
        "applicability": ["Example domain"],
        "user_facing_claim_limits": ["Do not overclaim."],
        "safety_implications": ["None identified."],
        "privacy_implications": ["No personal data."],
        "validation_plan": ["Validate the example."],
        "falsification_conditions": ["Contradictory evidence."],
        "affected_surfaces": {
            "models": ["example/model"],
            "apis": [],
            "clients": [],
            "science_notes": [],
        },
    }
    (evidence_dir / "evidence-example-v1.yaml").write_text(
        yaml.safe_dump(review, sort_keys=False),
        encoding="utf-8",
    )
    (decisions_dir / "sdr-example-v1.yaml").write_text(
        yaml.safe_dump(decision, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing.claim"):
        load_science_registry(science_dir)


def test_registry_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "science" / "evidence" / "example"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "evidence-example-v2.yaml").write_text(
        "schema_version: 2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only understands version 1"):
        load_science_registry(tmp_path / "science")


def test_supersession_links_must_be_reciprocal_and_acyclic() -> None:
    registry = load_science_registry()
    current = registry.evidence_reviews["evidence-heat-decay-v1"]
    old = current.model_copy(update={
        "status": RecordStatus.SUPERSEDED,
        "superseded_by": "evidence-heat-decay-v2",
    })
    new = current.model_copy(update={
        "id": "evidence-heat-decay-v2",
        "version": 2,
        "supersedes": [old.id],
    })

    _validate_supersession({old.id: old, new.id: new})

    broken = new.model_copy(update={"supersedes": []})
    with pytest.raises(ValueError, match="must supersede"):
        _validate_supersession({old.id: old, broken.id: broken})


def test_superseding_review_can_reuse_identical_citations(
    tmp_path: Path,
) -> None:
    current = load_science_registry().evidence_reviews[
        "evidence-heat-decay-v1"
    ]
    old = current.model_dump(mode="json")
    old["status"] = "superseded"
    old["superseded_by"] = "evidence-heat-decay-v2"

    new = current.model_dump(mode="json")
    new["id"] = "evidence-heat-decay-v2"
    new["version"] = 2
    new["supersedes"] = ["evidence-heat-decay-v1"]
    for claim in new["claims"]:
        claim["id"] = claim["id"].replace("heat-decay.", "heat-decay-v2.")

    evidence_dir = tmp_path / "science" / "evidence" / "heat-decay"
    evidence_dir.mkdir(parents=True)
    for record in (old, new):
        (evidence_dir / f"{record['id']}.yaml").write_text(
            yaml.safe_dump(record, sort_keys=False),
            encoding="utf-8",
        )

    registry = load_science_registry(tmp_path / "science")

    assert set(registry.evidence_reviews) == {
        "evidence-heat-decay-v1",
        "evidence-heat-decay-v2",
    }
    assert len(registry.citations) == len(current.citations)


def test_registry_index_is_generated_from_current_records() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_science_registry()

    assert (root / "data" / "science" / "REGISTRY.md").read_text(
        encoding="utf-8",
    ) == render_registry_index(registry)


def test_metric_science_links_match_the_registry() -> None:
    registry = load_science_registry()
    expected = registry.source_links_for_decision(
        metrics._HEAT_SCIENCE_DECISION_ID
    )
    status = compute_heat_adaptation(
        pd.DataFrame(),
        pd.DataFrame(),
        cp_watts=None,
        current_date=date(2026, 7, 25),
    )

    assert status["science_sources"] == expected
    environment = metrics.build_activity_environment_context(
        None,
        None,
        None,
    )
    assert environment["science_sources"] == (
        registry.source_links_for_decision(
            "sdr-environmental-performance-v1"
        )
    )
    accepted_environment_sources = {
        source["id"]
        for source in registry.source_links_for_decision(
            metrics.ENVIRONMENT_CONTEXT_SCIENCE_DECISION_ID
        )
    }
    assert {
        source["id"] for source in environment["science_sources"]
    } < accepted_environment_sources
