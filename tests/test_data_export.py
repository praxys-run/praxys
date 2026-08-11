"""Integration coverage for the authenticated self-service data export."""
from datetime import date
import json

from tests.test_settings_api import api_client


def test_data_export_requires_authentication(api_client):
    """The self-service export remains unavailable without a bearer token."""
    client, _ = api_client

    response = client.get("/api/me/export")

    assert response.status_code == 401


def test_data_export_is_downloadable_and_isolated_to_the_authenticated_user(api_client):
    """Exports all requested caller-owned records without credentials or other users' data."""
    client, owner_id = api_client

    from api.auth import get_current_user_id
    from api.main import app
    from db.models import (
        Activity,
        ActivitySplit,
        FitnessData,
        GoalBaselineAssessment,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        GoalBaselineTestRecord,
        RecoveryData,
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
                workout_type="tempo",
            ),
            TrainingPlan(
                user_id=other_id,
                canonical_id="other-plan",
                date=date(2026, 8, 4),
                workout_type="rest",
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
    assert payload["schema_version"] == 3
    assert payload["user_config"]["goal"]["target_label"] == "owner-goal"
    assert [row["activity_id"] for row in payload["activities"]] == ["owner-activity"]
    assert [row["activity_id"] for row in payload["activity_splits"]] == ["owner-activity"]
    assert [row["readiness_score"] for row in payload["recovery"]] == [88.0]
    assert [row["value"] for row in payload["fitness"]] == [290.0]
    assert [row["canonical_id"] for row in payload["training_plans"]] == ["owner-plan"]
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
        "owner-raw-credential",
        "owner-wrapped-key",
        "owner-encrypted-token",
        "other-raw-credential",
        "config-raw-token",
        "other-confirmation",
    ):
        assert excluded not in serialized
