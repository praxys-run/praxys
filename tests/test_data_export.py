"""Integration coverage for the authenticated self-service data export."""
from datetime import date
import json

from tests.test_settings_api import api_client


def test_data_export_requires_authentication(api_client):
    """The self-service export remains unavailable without a bearer token."""
    client, _ = api_client
    from api.auth import get_current_user_id
    from api.main import app

    app.dependency_overrides.pop(get_current_user_id, None)

    response = client.get("/api/me/export")

    assert response.status_code == 401


def test_data_export_is_downloadable_and_isolated_to_the_authenticated_user(api_client):
    """Exports all requested caller-owned records without credentials or other users' data."""
    client, owner_id = api_client

    from api.auth import get_current_user_id
    from api.main import app
    from db.models import (
        AdaptivePlan,
        AdaptivePlanGoalSnapshot,
        Activity,
        ActivitySplit,
        FitnessData,
        GoalBaselineAssessment,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        GoalBaselineTestRecord,
        Outdoor5KPlanGeneration,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
        Road10KPlanGeneration,
        RecoveryData,
        PlanProposal,
        TrainingPlan,
        User,
        UserConfig,
        UserConnection,
    )
    from db.session import SessionLocal

    app.dependency_overrides[get_current_user_id] = lambda: owner_id
    db = SessionLocal()
    try:
        other_id = "other-user-data-export"
        db.add_all([
            User(
                id=other_id,
                email="other-export@test.local",
                hashed_password="x",
                is_active=True,
            ),
            UserConfig(
                user_id=owner_id,
                display_name="Owner",
                preferences={"activities": "garmin"},
                goal={"distance": "marathon", "target_label": "owner-goal"},
                source_options={
                    "athlete_timezone": "UTC",
                    "oauth_token": "config-raw-token",
                },
            ),
            UserConfig(
                user_id=other_id,
                display_name="Other",
                goal={"target_label": "other-goal"},
            ),
            AdaptivePlanGoalSnapshot(
                id="owner-goal-snapshot",
                user_id=owner_id,
                version=1,
                state="active",
                goal_kind="race",
                target={"distance": "10k", "target_label": "owner-proposal-goal"},
                horizon_start=date(2026, 8, 1),
                horizon_end=date(2026, 8, 31),
                snapshot={"goal_kind": "race"},
            ),
            AdaptivePlanGoalSnapshot(
                id="other-goal-snapshot",
                user_id=other_id,
                version=1,
                state="active",
                goal_kind="race",
                target={"target_label": "other-proposal-goal"},
                horizon_start=date(2026, 8, 1),
                horizon_end=date(2026, 8, 31),
                snapshot={"goal_kind": "race"},
            ),
            AdaptivePlan(
                id="owner-adaptive-plan",
                user_id=owner_id,
                goal_snapshot_id="owner-goal-snapshot",
                discipline="running",
                lifecycle="active",
                version=1,
                active_proposal_id="owner-proposal",
            ),
            AdaptivePlan(
                id="other-adaptive-plan",
                user_id=other_id,
                goal_snapshot_id="other-goal-snapshot",
                discipline="running",
                lifecycle="active",
                version=1,
                active_proposal_id="other-proposal",
            ),
            PlanProposal(
                id="owner-proposal",
                user_id=owner_id,
                adaptive_plan_id="owner-adaptive-plan",
                goal_snapshot_id="owner-goal-snapshot",
                discipline="running",
                version=1,
                state="adopted",
                origin="test",
                actor_type="user",
                actor_id=owner_id,
                base_plan_version=0,
                assumptions=[],
                unknowns=[],
                warnings=[],
                alternatives=[],
                workout_snapshot=[{
                    "canonical_id": "owner-plan",
                    "date": "2026-08-05",
                    "workout_structure_version": "v1",
                    "workout_structure": {
                        "steps": [{
                            "type": "step",
                            "phase": "work",
                            "label": "Owner tempo",
                            "instructions": "Hold form through the finish.",
                            "termination": {
                                "type": "time",
                                "seconds": 2700,
                            },
                            "target": {
                                "metric": "power",
                                "unit": "watts",
                                "reference": "absolute",
                                "min": 240,
                                "max": 260,
                            },
                        }],
                    },
                }],
            ),
            PlanProposal(
                id="other-proposal",
                user_id=other_id,
                adaptive_plan_id="other-adaptive-plan",
                goal_snapshot_id="other-goal-snapshot",
                discipline="running",
                version=1,
                state="adopted",
                origin="test",
                actor_type="user",
                actor_id=other_id,
                base_plan_version=0,
                assumptions=[],
                unknowns=[],
                warnings=[],
                alternatives=[],
                workout_snapshot=[{"canonical_id": "other-plan", "date": "2026-08-05"}],
            ),
            Outdoor5KPlanGeneration(
                id="owner-generation",
                user_id=owner_id,
                proposal_id="owner-proposal",
                policy_version="outdoor-5k-plan-generation-policy-v1",
                generator_version="outdoor-5k-deterministic-generator-v1",
                science_decision_id="sdr-outdoor-5k-plan-generation-policy-v1",
                evidence_review_ids=["evidence-outdoor-5k-plan-generation-policy-v1"],
                evidence_claim_ids=["outdoor-5k-plan.fixed-progression-not-safety-threshold"],
                ai_explanation_present=False,
                baseline_snapshot_id="owner-snapshot",
                source_revision="a" * 64,
                deterministic_input_hash="a" * 64,
                request_kind="generate",
                request_fingerprint="c" * 64,
                observed_input_snapshot={"completed_running_history": []},
                constraint_snapshot={"available_weekdays": [0, 2, 5]},
                derived_history_statistics={"usable_completed_weeks": 3},
                validation_results={"code": "ready"},
            ),
            Outdoor5KPlanGeneration(
                id="other-generation",
                user_id=other_id,
                proposal_id="other-proposal",
                policy_version="outdoor-5k-plan-generation-policy-v1",
                generator_version="outdoor-5k-deterministic-generator-v1",
                science_decision_id="sdr-outdoor-5k-plan-generation-policy-v1",
                evidence_review_ids=["evidence-outdoor-5k-plan-generation-policy-v1"],
                evidence_claim_ids=["outdoor-5k-plan.fixed-progression-not-safety-threshold"],
                ai_explanation_present=False,
                baseline_snapshot_id=None,
                source_revision="b" * 64,
                deterministic_input_hash="b" * 64,
                request_kind="generate",
                request_fingerprint="d" * 64,
                observed_input_snapshot={"completed_running_history": []},
                constraint_snapshot={"available_weekdays": [0, 2, 5]},
                derived_history_statistics={"usable_completed_weeks": 3},
                validation_results={"code": "ready"},
            ),
            Road10KBaselineConfirmation(
                id="owner-road-10k-confirmation",
                lineage_id="owner-road-10k-confirmation-lineage",
                user_id=owner_id,
                goal_signature="owner-road-10k-goal-signature",
                goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
                version=1,
                activity_id="owner-activity",
                response="race",
                measured_10k=True,
                elapsed_timing_confirmed=True,
                request_fingerprint="e" * 64,
            ),
            Road10KBaselineSnapshot(
                id="owner-road-10k-snapshot",
                lineage_id="owner-road-10k-snapshot-lineage",
                user_id=owner_id,
                goal_signature="owner-road-10k-goal-signature",
                goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
                version=1,
                source_kind="history_confirmation",
                source_id="owner-activity",
                provenance="race",
                observed_date=date(2026, 8, 1),
                distance_km=10.0,
                elapsed_time_sec=2_520,
                measured_10k=True,
                elapsed_timing_confirmed=True,
                qualification_status="direct_current",
                change_comparability="not_assessed",
                invalidators=[],
            ),
            Road10KPlanGeneration(
                id="owner-road-10k-generation",
                user_id=owner_id,
                proposal_id="owner-proposal",
                capability_id="outdoor_road_10k_performance_v1",
                policy_version="road-10k-plan-generation-policy-v2",
                generator_version="road-10k-deterministic-generator-v1",
                science_decision_id="sdr-road-10k-plan-generation-policy-v2",
                source_decision_digest="s" * 71,
                contract_digest="t" * 71,
                baseline_snapshot_id="owner-road-10k-snapshot",
                baseline_source="race",
                source_goal_id=None,
                source_goal_revision=None,
                history_cutoff_completed_days=56,
                history_observation_ids=["owner-activity"],
                training_pattern_snapshot_version="road-10k-training-pattern-v1",
                event_context_snapshot_version="road-10k-event-context-v1",
                active_zone_model_id=None,
                active_zone_model_version=None,
                normalized_constraints={"available_weekdays": [0, 2, 5]},
                selected_template_ids=["road-10k-controlled-threshold-quality-v1"],
                source_revision="e" * 64,
                deterministic_input_hash="f" * 64,
                request_kind="generate",
                request_fingerprint="g" * 64,
                predecessor_proposal_id=None,
                predecessor_version=None,
                observed_input_snapshot={"completed_running_history": []},
                derived_history_statistics={"usable_completed_weeks": 8},
                validation_results={"code": "eligible_rolling_proposal"},
            ),
            Activity(
                user_id=owner_id,
                activity_id="owner-activity",
                date=date(2026, 8, 1),
                distance_km=12.3,
            ),
            Activity(
                user_id=other_id,
                activity_id="other-activity",
                date=date(2026, 8, 2),
                distance_km=99.9,
            ),
            ActivitySplit(
                user_id=owner_id,
                activity_id="owner-activity",
                split_num=1,
                duration_sec=600,
                avg_power=250,
            ),
            ActivitySplit(
                user_id=other_id,
                activity_id="other-activity",
                split_num=1,
                duration_sec=700,
                avg_power=300,
            ),
            RecoveryData(
                user_id=owner_id,
                date=date(2026, 8, 1),
                readiness_score=88,
            ),
            RecoveryData(
                user_id=other_id,
                date=date(2026, 8, 2),
                readiness_score=12,
            ),
            FitnessData(
                user_id=owner_id,
                date=date(2026, 8, 1),
                metric_type="cp_estimate",
                value=290,
            ),
            FitnessData(
                user_id=other_id,
                date=date(2026, 8, 2),
                metric_type="cp_estimate",
                value=123,
            ),
            TrainingPlan(
                user_id=owner_id,
                canonical_id="owner-plan",
                date=date(2026, 8, 3),
                activity_type="running",
                workout_type="tempo",
                workout_structure_version="v1",
                workout_structure={
                    "steps": [
                        {
                            "type": "step",
                            "phase": "other",
                            "label": "Owner tempo",
                            "instructions": "Hold form through the finish.",
                            "termination": {"type": "time", "seconds": 2700},
                            "target": {
                                "metric": "power",
                                "unit": "watts",
                                "reference": "absolute",
                                "min": 240,
                                "max": 260,
                            },
                        }
                    ]
                },
            ),
            TrainingPlan(
                user_id=other_id,
                canonical_id="other-plan",
                date=date(2026, 8, 4),
                activity_type="rest",
                workout_type="rest",
                workout_structure_version="v1",
                workout_structure={"steps": []},
            ),
            GoalBaselineConfirmation(
                id="owner-confirmation",
                lineage_id="owner-confirmation-lineage",
                user_id=owner_id,
                goal_signature="owner-goal-signature",
                goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
                version=1,
                activity_id="owner-activity",
                response="race",
                measured_5k=True,
                elapsed_timing_confirmed=True,
                request_fingerprint="a" * 64,
            ),
            GoalBaselineTestRecord(
                id="owner-test",
                lineage_id="owner-test-lineage",
                user_id=owner_id,
                goal_signature="owner-goal-signature",
                goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
                version=1,
                state="scheduled",
                protocol_id="outdoor-5k-tt-pilot-v1",
                request_fingerprint="b" * 64,
                scheduled_date=date(2026, 8, 5),
            ),
            GoalBaselineSnapshot(
                id="owner-snapshot",
                lineage_id="owner-snapshot-lineage",
                user_id=owner_id,
                goal_signature="owner-goal-signature",
                goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
                version=1,
                source_kind="history_confirmation",
                source_id="owner-activity",
                provenance="race",
                observed_date=date(2026, 8, 1),
                distance_km=5.0,
                elapsed_time_sec=1234,
                measured_5k=True,
                elapsed_timing_confirmed=True,
                qualification_status="direct_current",
                change_comparability="not_assessed",
                invalidators=[],
            ),
            GoalBaselineAssessment(
                id="owner-assessment",
                lineage_id="owner-assessment-lineage",
                user_id=owner_id,
                goal_signature="owner-goal-signature",
                goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
                version=1,
                policy_version="preplan-baseline-policy-v1",
                science_decision_id="sdr-preplan-baseline-policy-v1",
                status="current",
                readiness="sufficient_baseline",
                evidence_snapshot_id="owner-snapshot",
                test_record_id="owner-test",
                candidate_count=1,
            ),
            GoalBaselineConfirmation(
                id="other-confirmation",
                lineage_id="other-confirmation-lineage",
                user_id=other_id,
                goal_signature="other-goal-signature",
                goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
                version=1,
                activity_id="other-activity",
                response="race",
                measured_5k=True,
                elapsed_timing_confirmed=True,
                request_fingerprint="c" * 64,
            ),
            UserConnection(
                user_id=owner_id,
                platform="garmin",
                encrypted_credentials=b"owner-raw-credential",
                wrapped_dek=b"owner-wrapped-key",
                encrypted_garmin_tokens=b"owner-encrypted-token",
            ),
            UserConnection(
                user_id=other_id,
                platform="oura",
                encrypted_credentials=b"other-raw-credential",
            ),
        ])
        db.commit()
    finally:
        db.close()

    response = client.get("/api/me/export")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="praxys-data-export-'
    )
    payload = response.json()
    assert payload["schema_version"] == 4
    assert payload["user_config"]["goal"]["target_label"] == "owner-goal"
    assert [row["activity_id"] for row in payload["activities"]] == ["owner-activity"]
    assert [row["activity_id"] for row in payload["activity_splits"]] == ["owner-activity"]
    assert [row["readiness_score"] for row in payload["recovery"]] == [88.0]
    assert [row["value"] for row in payload["fitness"]] == [290.0]
    assert [row["canonical_id"] for row in payload["training_plans"]] == ["owner-plan"]
    assert payload["training_plans"][0]["activity_type"] == "running"
    assert payload["training_plans"][0]["workout_structure_version"] == "v1"
    assert payload["training_plans"][0]["workout_structure"]["steps"][0][
        "label"
    ] == "Owner tempo"
    assert payload["training_plans"][0]["workout_structure"]["steps"][0][
        "instructions"
    ] == "Hold form through the finish."
    assert payload["adaptive_plan_proposals"]["schema_version"] == 1
    assert [
        row["id"] for row in payload["adaptive_plan_proposals"]["goal_snapshots"]
    ] == ["owner-goal-snapshot"]
    assert [
        row["id"] for row in payload["adaptive_plan_proposals"]["plans"]
    ] == ["owner-adaptive-plan"]
    assert payload["adaptive_plan_proposals"]["plans"][0]["discipline"] == "running"
    assert [
        row["id"] for row in payload["adaptive_plan_proposals"]["proposals"]
    ] == ["owner-proposal"]
    assert (
        payload["adaptive_plan_proposals"]["proposals"][0]["discipline"]
        == "running"
    )
    exported_proposal_step = payload["adaptive_plan_proposals"]["proposals"][0][
        "workout_snapshot"
    ][0]["workout_structure"]["steps"][0]
    assert exported_proposal_step["label"] == "Owner tempo"
    assert exported_proposal_step["instructions"] == (
        "Hold form through the finish."
    )
    assert payload["goal_baseline"] == {
        "schema_version": 1,
        "exported_at": payload["goal_baseline"]["exported_at"],
        "confirmations": [payload["goal_baseline"]["confirmations"][0]],
        "tests": [payload["goal_baseline"]["tests"][0]],
        "snapshots": [payload["goal_baseline"]["snapshots"][0]],
        "assessments": [payload["goal_baseline"]["assessments"][0]],
    }
    assert payload["goal_baseline"]["confirmations"][0]["id"] == "owner-confirmation"
    assert payload["goal_baseline"]["tests"][0]["id"] == "owner-test"
    assert payload["goal_baseline"]["snapshots"][0]["id"] == "owner-snapshot"
    assert payload["goal_baseline"]["assessments"][0]["id"] == "owner-assessment"
    assert payload["outdoor_5k_plan_generation"] == {
        "schema_version": 1,
        "exported_at": payload["outdoor_5k_plan_generation"]["exported_at"],
        "records": [payload["outdoor_5k_plan_generation"]["records"][0]],
    }
    assert payload["outdoor_5k_plan_generation"]["records"][0]["id"] == (
        "owner-generation"
    )
    assert payload["road_10k_baseline"] == {
        "schema_version": 1,
        "exported_at": payload["road_10k_baseline"]["exported_at"],
        "confirmations": [payload["road_10k_baseline"]["confirmations"][0]],
        "snapshots": [payload["road_10k_baseline"]["snapshots"][0]],
    }
    assert payload["road_10k_baseline"]["confirmations"][0]["id"] == (
        "owner-road-10k-confirmation"
    )
    assert payload["road_10k_baseline"]["snapshots"][0]["id"] == (
        "owner-road-10k-snapshot"
    )
    assert payload["road_10k_plan_generation"] == {
        "schema_version": 1,
        "exported_at": payload["road_10k_plan_generation"]["exported_at"],
        "records": [payload["road_10k_plan_generation"]["records"][0]],
    }
    assert payload["road_10k_plan_generation"]["records"][0]["id"] == (
        "owner-road-10k-generation"
    )
    assert payload["personal_context"] == {
        "schema_version": 1,
        "exported_at": payload["personal_context"]["exported_at"],
        "items": [],
        "consent_receipts": [],
        "use_receipts": [],
        "linked_revisions": [],
    }
    assert "user_id" not in json.dumps(payload)

    serialized = response.text
    for excluded in (
        "other-export@test.local",
        "other-goal",
        "other-activity",
        "other-plan",
        "other-proposal",
        "other-proposal-goal",
        "owner-raw-credential",
        "owner-wrapped-key",
        "owner-encrypted-token",
        "other-raw-credential",
        "config-raw-token",
        "other-confirmation",
    ):
        assert excluded not in serialized
