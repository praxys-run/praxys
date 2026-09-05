"""Tests for self-service account deletion."""
from __future__ import annotations

import importlib
import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


def test_account_deletion_failure_logs_omit_user_and_filesystem_path(
    monkeypatch,
    caplog,
):
    import errno
    from contextlib import contextmanager

    from api import account_deletion
    from api.routes import plan as plan_route
    from api.routes import sync as sync_route

    user_id = "private-account-id-sentinel"
    base_path = "/tmp/private-account-id-sentinel/status.json"
    archive_path = f"{base_path}.corrupt-private-sentinel"
    token_path = "/tmp/private-account-id-sentinel/garmin-token.json"
    caplog.set_level("ERROR", logger="api.account_deletion")
    monkeypatch.setattr(
        sync_route,
        "clear_garmin_tokens",
        lambda _user_id: (_ for _ in ()).throw(
            OSError(errno.EACCES, "cleanup unavailable", token_path)
        ),
    )
    account_deletion._clear_tokenstore(user_id)

    class FakeSession:
        rolled_back = False

        def rollback(self):
            self.rolled_back = True

    @contextmanager
    def status_lock(*_args, **_kwargs):
        yield

    session = FakeSession()
    monkeypatch.setattr(account_deletion, "lock_plan_writes", lambda *_args: None)
    monkeypatch.setattr(account_deletion, "legacy_stryd_status_lock", status_lock)
    monkeypatch.setattr(plan_route, "_stryd_push_status_path", lambda _user_id: base_path)
    monkeypatch.setattr(account_deletion.glob, "glob", lambda _pattern: [archive_path])
    monkeypatch.setattr(
        account_deletion.os,
        "unlink",
        lambda _candidate: (_ for _ in ()).throw(
            OSError(errno.EACCES, "unlink unavailable", _candidate)
        ),
    )

    account_deletion._clear_legacy_plan_status(session, user_id)

    assert session.rolled_back is True
    assert user_id not in caplog.text
    assert base_path not in caplog.text
    assert archive_path not in caplog.text
    assert token_path not in caplog.text


def test_account_deletion_logging_does_not_interpolate_runtime_identifiers():
    import ast
    import inspect

    from api import account_deletion

    tree = ast.parse(inspect.getsource(account_deletion))
    logger_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
    ]
    assert logger_calls
    assert all(len(call.args) == 1 for call in logger_calls)
    assert all(call.func.attr != "exception" for call in logger_calls)
    assert all(
        all(keyword.arg != "exc_info" for keyword in call.keywords)
        for call in logger_calls
    )


@pytest.fixture
def account_client(monkeypatch):
    """Yield a TestClient backed by a fresh SQLite DB and overridable user id."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", os.path.join(tmpdir.name, "data"))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", raising=False)
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL", raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    import api.main

    importlib.reload(api.main)
    app = api.main.app

    current_user_id = {"value": "delete-me"}

    def _override_user() -> str:
        return current_user_id["value"]

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    from fastapi import HTTPException
    from api.auth import get_current_user_id, require_account_deletion_access
    from db.models import User
    from db.session import get_db

    def _override_delete_access() -> str:
        db = db_session.SessionLocal()
        try:
            user = db.query(User).filter(User.id == current_user_id["value"]).first()
            if user and user.is_demo:
                raise HTTPException(403, "Demo accounts cannot modify data")
            return current_user_id["value"]
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[require_account_deletion_access] = _override_delete_access
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    client.current_user_id = current_user_id  # type: ignore[attr-defined]
    try:
        yield client, db_session
    finally:
        app.dependency_overrides.clear()
        if db_session.engine is not None:
            db_session.engine.dispose()
        if db_session.async_engine is not None:
            import asyncio

            try:
                asyncio.run(db_session.async_engine.dispose())
            except RuntimeError:
                pass
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _seed_account_rows(db_session, user_id: str = "delete-me") -> None:
    """Insert one row in every user-owned table account deletion must purge."""
    from db.agent_loop import record_decision, record_outcome
    from db.models import (
        AdaptivePlan,
        AdaptivePlanGoalSnapshot,
        Activity,
        ActivitySample,
        ActivitySplit,
        AiInsight,
        AiInsightFeedback,
        AppConfig,
        CacheRevision,
        DashboardCache,
        Feedback,
        FitnessData,
        GoalBaselineAssessment,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        GoalBaselineTestRecord,
        GoalBaselineAssessment,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        GoalBaselineTestRecord,
        Invitation,
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        LabsDeletionTombstone,
        LabsExperimentEnrollment,
        LabsExperimentResult,
        McpAccessHandoff,
        McpAccessToken,
        Outdoor5KPlanGeneration,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
        Road10KPlanGeneration,
        Road10KTrainingPatternSnapshot,
        PlanDelivery,
        PlanDeliveryAttempt,
        PlanProposal,
        PlanRevision,
        PlanTargetCalendarSync,
        PlanTargetWorkout,
        PersonalContextConsentReceipt,
        PersonalContextDeletionJob,
        PersonalContextItem,
        PersonalContextUseReceipt,
        RecoveryData,
        TermsAcceptanceReceipt,
        TrainingPlan,
        User,
        UserConfig,
        UserConnection,
        WaitlistSignup,
    )

    db = db_session.SessionLocal()
    try:
        admin = User(id="admin", email="admin@example.test", hashed_password="x", is_superuser=True)
        user = User(
            id=user_id,
            email="athlete@example.test",
            hashed_password="x",
            wechat_openid="openid-delete-me",
        )
        demo = User(id="demo-user", email="demo@example.test", hashed_password="x", is_demo=True, demo_of=user_id)
        db.add_all([admin, user, demo])
        db.add(
            TermsAcceptanceReceipt(
                user_id=user_id,
                terms_version="2026.08.3",
                terms_digest="sha256:" + ("1" * 64),
                locale="en",
                channel="web",
            )
        )
        db.add(UserConfig(user_id=user_id, display_name="Delete Me"))
        db.add(UserConnection(user_id=user_id, platform="garmin", encrypted_credentials=b"secret"))
        db.add(Activity(user_id=user_id, activity_id="a1", date=date(2026, 6, 1)))
        db.add(ActivitySplit(user_id=user_id, activity_id="a1", split_num=1))
        db.add(ActivitySample(user_id=user_id, activity_id="a1", source="garmin", t_sec=1))
        db.add(RecoveryData(user_id=user_id, date=date(2026, 6, 1), source="oura"))
        db.add(FitnessData(user_id=user_id, date=date(2026, 6, 1), metric_type="cp_estimate", value=300))
        db.add(AdaptivePlanGoalSnapshot(
            id="delete-goal-snapshot",
            user_id=user_id,
            version=1,
            state="active",
            goal_kind="race",
            target={"distance": "10k"},
            horizon_start=date(2026, 6, 1),
            horizon_end=date(2026, 6, 30),
            snapshot={"goal_kind": "race"},
        ))
        db.add(AdaptivePlan(
            id="delete-adaptive-plan",
            user_id=user_id,
            goal_snapshot_id="delete-goal-snapshot",
            discipline="running",
            lifecycle="active",
            version=1,
            active_proposal_id="delete-proposal",
        ))
        db.add(PlanProposal(
            id="delete-proposal",
            user_id=user_id,
            adaptive_plan_id="delete-adaptive-plan",
            goal_snapshot_id="delete-goal-snapshot",
            discipline="running",
            version=1,
            state="adopted",
            origin="test",
            actor_type="user",
            actor_id=user_id,
            base_plan_version=0,
            assumptions=[],
            unknowns=[],
            warnings=[],
            alternatives=[],
            workout_snapshot=[{
                "canonical_id": "delete-plan",
                "date": "2026-06-02",
                "workout_structure_version": "v1",
                "workout_structure": {
                    "steps": [{
                        "type": "step",
                        "phase": "work",
                        "label": "Delete this label",
                        "instructions": "Delete this private coaching cue.",
                        "termination": {
                            "type": "time",
                            "seconds": 1800,
                        },
                        "target": {
                            "metric": "none",
                            "unit": "none",
                            "reference": "none",
                        },
                    }],
                },
            }],
        ))
        db.add(Outdoor5KPlanGeneration(
            id="delete-generation",
            user_id=user_id,
            proposal_id="delete-proposal",
            policy_version="outdoor-5k-plan-generation-policy-v1",
            generator_version="outdoor-5k-deterministic-generator-v1",
            science_decision_id="sdr-outdoor-5k-plan-generation-policy-v1",
            evidence_review_ids=["evidence-outdoor-5k-plan-generation-policy-v1"],
            evidence_claim_ids=["outdoor-5k-plan.fixed-progression-not-safety-threshold"],
            ai_explanation_present=False,
            baseline_snapshot_id=None,
            source_revision="3" * 64,
            deterministic_input_hash="3" * 64,
            request_kind="generate",
            request_fingerprint="4" * 64,
            observed_input_snapshot={"completed_running_history": []},
            constraint_snapshot={"available_weekdays": [0, 2, 5]},
            derived_history_statistics={"usable_completed_weeks": 3},
            validation_results={"code": "ready"},
        ))
        db.add(Road10KBaselineConfirmation(
            id="road-10k-baseline-confirmation",
            lineage_id="road-10k-baseline-confirmation-lineage",
            user_id=user_id,
            goal_signature="road-10k-goal-signature",
            goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
            version=1,
            activity_id="a1",
            response="race",
            measured_10k=True,
            elapsed_timing_confirmed=True,
            completed_at=datetime(2026, 6, 1, 8, 42),
            elapsed_time_sec=2_520,
            surface_or_protocol="organized_outdoor_road_10k_race",
            route_or_venue_identifier="delete-road-10k-race",
            assistance_status="unassisted",
            source_provider="garmin",
            request_fingerprint="5" * 64,
        ))
        db.add(Road10KBaselineSnapshot(
            id="road-10k-baseline-snapshot",
            lineage_id="road-10k-baseline-snapshot-lineage",
            user_id=user_id,
            goal_signature="road-10k-goal-signature",
            goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
            version=1,
            source_kind="history_confirmation",
            source_id="a1",
            provenance="race",
            observed_date=date(2026, 6, 1),
            completed_at=datetime(2026, 6, 1, 8, 42),
            distance_km=10.0,
            elapsed_time_sec=2_520,
            measured_10k=True,
            elapsed_timing_confirmed=True,
            surface_or_protocol="organized_outdoor_road_10k_race",
            route_or_venue_identifier="delete-road-10k-race",
            assistance_status="unassisted",
            source_provider="garmin",
            qualification_status="direct_current",
            change_comparability="not_assessed",
            invalidators=[],
        ))
        db.add(Road10KTrainingPatternSnapshot(
            user_id=user_id,
            version=f"v1:{'a' * 64}",
            schema_version="road-10k-training-pattern-v1",
            policy_version="road-10k-plan-generation-policy-v2",
            usable_completed_weeks=8,
            recent_modal_running_frequency=3,
            recent_median_usable_weekly_minutes=180,
            recent_maximum_usable_weekly_minutes=190,
            recent_maximum_session_minutes=70,
            recent_maximum_session_distance_km=12.0,
            latest_run_date=date(2026, 6, 1),
            history_observation_count=24,
            history_provenance_fingerprint="b" * 64,
            intensity_observation_count=24,
            intensity_provenance_fingerprint="c" * 64,
            reserved_date_count=0,
            reservation_fingerprint="d" * 64,
            canonical_fingerprint="a" * 64,
        ))
        db.add(Road10KPlanGeneration(
            id="road-10k-delete-generation",
            user_id=user_id,
            proposal_id="delete-proposal",
            capability_id="outdoor_road_10k_performance_v1",
            policy_version="road-10k-plan-generation-policy-v2",
            generator_version="road-10k-deterministic-generator-v1",
            science_decision_id="sdr-road-10k-plan-generation-policy-v2",
            source_decision_digest="5" * 71,
            contract_digest="6" * 71,
            baseline_snapshot_id="road-10k-baseline-snapshot",
            baseline_source="race",
            source_goal_id=None,
            source_goal_revision=None,
            history_cutoff_completed_days=56,
            training_pattern_snapshot_version=f"v1:{'a' * 64}",
            event_context_snapshot_version="road-10k-event-context-v1",
            active_zone_model_id=None,
            active_zone_model_version=None,
            normalized_constraints={"available_weekdays": [0, 2, 5]},
            selected_template_ids=["road-10k-controlled-threshold-quality-v1"],
            source_revision="7" * 64,
            deterministic_input_hash="8" * 64,
            request_kind="generate",
            request_fingerprint="9" * 64,
            result_code="eligible_rolling_proposal",
            validation_reason_code=None,
        ))
        db.add(GoalBaselineConfirmation(
            id="baseline-confirmation",
            lineage_id="baseline-confirmation-lineage",
            user_id=user_id,
            goal_signature="goal-signature",
            goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
            version=1,
            activity_id="a1",
            response="race",
            measured_5k=True,
            elapsed_timing_confirmed=True,
            request_fingerprint="1" * 64,
        ))
        db.add(GoalBaselineTestRecord(
            id="baseline-test",
            lineage_id="baseline-test-lineage",
            user_id=user_id,
            goal_signature="goal-signature",
            goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
            version=1,
            state="scheduled",
            protocol_id="outdoor-5k-tt-pilot-v1",
            request_fingerprint="2" * 64,
            scheduled_date=date(2026, 6, 3),
        ))
        db.add(GoalBaselineSnapshot(
            id="baseline-snapshot",
            lineage_id="baseline-snapshot-lineage",
            user_id=user_id,
            goal_signature="goal-signature",
            goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
            version=1,
            source_kind="history_confirmation",
            source_id="a1",
            provenance="race",
            observed_date=date(2026, 6, 1),
            distance_km=5.0,
            elapsed_time_sec=1500,
            measured_5k=True,
            elapsed_timing_confirmed=True,
            qualification_status="direct_current",
            change_comparability="not_assessed",
            invalidators=[],
        ))
        db.add(GoalBaselineAssessment(
            id="baseline-assessment",
            lineage_id="baseline-assessment-lineage",
            user_id=user_id,
            goal_signature="goal-signature",
            goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
            version=1,
            policy_version="preplan-baseline-policy-v1",
            science_decision_id="sdr-preplan-baseline-policy-v1",
            status="current",
            readiness="sufficient_baseline",
            evidence_snapshot_id="baseline-snapshot",
            test_record_id="baseline-test",
            candidate_count=1,
        ))
        db.add(TrainingPlan(
            user_id=user_id,
            adaptive_plan_id="delete-adaptive-plan",
            date=date(2026, 6, 2),
            activity_type="running",
            source="ai",
            workout_type="easy",
            workout_structure_version="v1",
            workout_structure={
                "steps": [
                    {
                        "type": "step",
                        "phase": "other",
                        "label": "Delete this label",
                        "instructions": "Delete this private coaching cue.",
                        "termination": {"type": "time", "seconds": 1800},
                        "target": {
                            "metric": "none",
                            "unit": "none",
                            "reference": "none",
                        },
                    }
                ]
            },
        ))
        revision = PlanRevision(
            user_id=user_id,
            operation="upsert",
            actor_type="user",
            actor_id=user_id,
            origin="test",
            before_snapshot=[],
            after_snapshot=[],
            details={},
        )
        delivery = PlanDelivery(
            user_id=user_id,
            canonical_key="ai:2026-06-02",
            workout_date=date(2026, 6, 2),
            workout_version="a" * 64,
            target="stryd",
            state="synced",
            external_id="stryd-delete-me",
        )
        db.add_all([revision, delivery])
        db.flush()
        db.add(PlanDeliveryAttempt(
            delivery_id=delivery.id,
            attempt_number=1,
            operation="deliver",
            state="synced",
            external_id="stryd-delete-me",
        ))
        db.add(PlanTargetCalendarSync(
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            window_start=date(2026, 6, 1),
            window_end=date(2026, 6, 30),
        ))
        db.add(PlanTargetWorkout(
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            external_id="stryd-delete-me",
            workout_date=date(2026, 6, 2),
            normalized_workout={"date": "2026-06-02"},
        ))
        db.add(AiInsight(user_id=user_id, insight_type="daily_brief"))
        db.add(AiInsightFeedback(
            user_id=user_id,
            insight_type="daily_brief",
            dataset_hash="a" * 64,
            vote="up",
        ))
        db.add(CacheRevision(user_id=user_id, scope="activities", revision=1))
        db.add(DashboardCache(user_id=user_id, section="today", source_version="v1", payload_json=b"{}"))
        db.add(LabsExperimentEnrollment(
            user_id=user_id,
            experiment_id="environment-response-v1",
            consent_version="environment-response-consent-v1",
            adult_attested_at=datetime.utcnow(),
            status="available",
            model_version="labs-v1",
            source_revision="rev1:test",
            correlation_id="labs-correlation",
        ))
        db.add(LabsExperimentResult(
            user_id=user_id,
            experiment_id="environment-response-v1",
            model_version="labs-v1",
            source_revision="rev1:test",
            result_state="historical_association_only",
            eligibility_counts={},
            aggregate_curve_points=[],
            aggregate_uncertainty={},
            gate_statuses={},
            prediction_status="failed_research_diagnostics",
            power_regime="stryd_continuous_samples",
        ))
        db.add(LabsDeletionTombstone(
            user_id=user_id,
            experiment_id="older-experiment",
        ))
        labs_job = LabsAnalysisJob(
            id="labs-delete-job",
            user_id=user_id,
            experiment_id="environment-response-v1",
            trigger="enrollment",
            status="succeeded",
            model_version="labs-v1",
            source_revision="rev1:test",
            correlation_id="labs-correlation",
            attempt_count=1,
            retryable_failure=False,
        )
        db.add(labs_job)
        db.flush()
        db.add(LabsAnalysisOutbox(
            id="labs-delete-outbox",
            job_id=labs_job.id,
            status="dispatched",
            attempt_count=1,
        ))
        from db.crypto import get_vault

        context_now = datetime(2026, 6, 1)
        for context_owner, index in ((user_id, 1), ("demo-user", 2)):
            encrypted, wrapped = get_vault().encrypt(json.dumps({
                "category": "other",
                "fields": {"synthetic": True},
                "narrative": "Synthetic deletion fixture",
            }))
            item_id = f"{index}1111111-1111-1111-1111-111111111111"
            lineage_id = f"{index}2222222-2222-2222-2222-222222222222"
            consent_id = f"{index}3333333-3333-3333-3333-333333333333"
            db.add(PersonalContextItem(
                id=item_id,
                lineage_id=lineage_id,
                user_id=context_owner,
                version=1,
                kind="temporary_constraint",
                purpose="plan_adjustment",
                state="active",
                encrypted_payload=encrypted,
                wrapped_dek=wrapped,
                payload_schema_version=1,
                has_narrative=True,
                source_actor_type="first_party_web",
                processing_mode="ai_allowed",
                consent_receipt_id=consent_id,
                starts_at=context_now,
                expires_at=context_now + timedelta(days=14),
                narrative_purge_at=context_now + timedelta(days=30),
                purge_after=context_now + timedelta(days=44),
            ))
            db.add(PersonalContextConsentReceipt(
                id=consent_id,
                user_id=context_owner,
                context_item_id=item_id,
                context_version=1,
                purpose="plan_adjustment",
                provider="azure_openai",
                disclosed_fields=["category"],
                consent_text_version="context-ai-v1",
                decision="granted",
                client="web",
            ))
            db.add(PersonalContextUseReceipt(
                id=f"{index}4444444-4444-4444-4444-444444444444",
                user_id=context_owner,
                context_item_id=item_id,
                context_version=1,
                purpose="plan_adjustment",
                consumer_type="planning_ai",
                consumer_name="adaptive-plan-v1",
                disclosed_fields=["category"],
                consent_receipt_id=consent_id,
            ))
            db.add(PersonalContextDeletionJob(
                id=f"{index}5555555-5555-5555-5555-555555555555",
                user_id=context_owner,
                operation="purge_narrative",
                lineage_id=lineage_id,
                target_item_id=item_id,
                reason="retention",
                status="failed",
                attempts=1,
            ))
            db.add(McpAccessHandoff(
                id=f"{index}6666666-6666-6666-6666-666666666666",
                user_id=context_owner,
                state_digest=str(index) * 64,
                exchange_digest=str(index + 2) * 64,
                request_type="context",
                audience="praxys-coach-plugin",
                actor_id=f"mcp:delete-{index}",
                requested_scopes=["plan:context:read"],
                requested_purposes=["plan_adjustment"],
                requested_kinds=["temporary_constraint"],
                status="approved",
                expires_at=context_now + timedelta(minutes=10),
            ))
            db.add(McpAccessToken(
                id=f"{index}7777777-7777-7777-7777-777777777777",
                user_id=context_owner,
                token_digest=str(index + 4) * 64,
                token_type="context",
                audience="praxys-coach-plugin",
                actor_type="mcp",
                actor_id=f"mcp:delete-{index}",
                scopes=["plan:context:read"],
                purposes=["plan_adjustment"],
                kinds=["temporary_constraint"],
                expires_at=context_now + timedelta(minutes=15),
            ))
        feedback = Feedback(
            user_id=user_id,
            kind="bug",
            message="delete me",
            status="new",
        )
        db.add(feedback)
        db.add(UserConfig(user_id="demo-user", display_name="Demo"))
        used = Invitation(code="TS-USED-0001", created_by="admin", used_by=user_id, is_active=False)
        made = Invitation(code="TS-MADE-0001", created_by=user_id, is_active=True)
        db.add_all([used, made])
        db.flush()
        decision = record_decision(
            db,
            loop="change",
            subject_type="feedback",
            subject_ref=str(feedback.id),
            policy_name="change.agent_ready",
            policy_version="agent-ready-v2",
            prompt_version=None,
            model="rule-based",
            mode="active",
            input_data={"message_sha256": "a" * 64},
            output_data={"agent_ready_candidate": False},
        )
        record_outcome(
            db,
            decision_id=decision.id,
            outcome_type="held_for_review",
            source="triage",
            payload={"status": "needs_review"},
        )
        # A waitlist lead linked to the invitation the user *created*: it must
        # survive the user's deletion with invitation_id detached (issue #366).
        db.add(WaitlistSignup(email="lead@example.test", invitation_id=made.id))
        # The user last toggled an operator flag; the row must survive with
        # updated_by nulled rather than left dangling (issue #366).
        db.add(AppConfig(key="registration_open", value="true", updated_by=user_id))
        db.commit()
    finally:
        db.close()


def test_delete_me_removes_user_and_owned_rows(account_client):
    """DELETE /api/me hard-deletes account data, credentials, demo, and invitation links."""
    client, db_session = account_client
    _seed_account_rows(db_session)

    res = client.delete("/api/me")
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "deleted", "email": "athlete@example.test"}

    from db.models import (
        AdaptivePlan,
        AdaptivePlanGoalSnapshot,
        Activity,
        ActivitySample,
        ActivitySplit,
        AgentDecision,
        AgentOutcome,
        AiInsight,
        AiInsightFeedback,
        AppConfig,
        CacheRevision,
        DashboardCache,
        Feedback,
        FitnessData,
        GoalBaselineAssessment,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        GoalBaselineTestRecord,
        Invitation,
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        LabsDeletionTombstone,
        LabsExperimentEnrollment,
        LabsExperimentResult,
        McpAccessHandoff,
        McpAccessToken,
        Outdoor5KPlanGeneration,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
        Road10KPlanGeneration,
        Road10KTrainingPatternSnapshot,
        PlanDelivery,
        PlanDeliveryAttempt,
        PlanProposal,
        PlanRevision,
        PlanTargetCalendarSync,
        PlanTargetWorkout,
        PersonalContextConsentReceipt,
        PersonalContextDeletionJob,
        PersonalContextItem,
        PersonalContextUseReceipt,
        RecoveryData,
        TermsAcceptanceReceipt,
        TrainingPlan,
        User,
        UserConfig,
        UserConnection,
        WaitlistSignup,
    )

    db = db_session.SessionLocal()
    try:
        assert db.query(User).filter(User.id.in_(["delete-me", "demo-user"])).count() == 0
        for model in (
            Activity,
            ActivitySample,
            ActivitySplit,
            AiInsight,
            AiInsightFeedback,
            CacheRevision,
            DashboardCache,
            Feedback,
            FitnessData,
            Outdoor5KPlanGeneration,
            Road10KBaselineConfirmation,
            Road10KBaselineSnapshot,
            Road10KPlanGeneration,
            Road10KTrainingPatternSnapshot,
            PlanProposal,
            AdaptivePlan,
            AdaptivePlanGoalSnapshot,
            LabsAnalysisJob,
            LabsDeletionTombstone,
            LabsExperimentEnrollment,
            LabsExperimentResult,
            McpAccessHandoff,
            McpAccessToken,
            PlanTargetCalendarSync,
            PlanTargetWorkout,
            PlanDelivery,
            PlanRevision,
            PersonalContextConsentReceipt,
            PersonalContextDeletionJob,
            PersonalContextItem,
            PersonalContextUseReceipt,
            RecoveryData,
            TermsAcceptanceReceipt,
            TrainingPlan,
            UserConfig,
            UserConnection,
        ):
            assert db.query(model).filter(model.user_id.in_(["delete-me", "demo-user"])).count() == 0
        assert db.query(LabsAnalysisOutbox).count() == 0
        assert db.query(PlanDeliveryAttempt).count() == 0
        assert db.query(AgentDecision).count() == 0
        assert db.query(AgentOutcome).count() == 0
        assert db.query(Invitation).filter(
            (Invitation.used_by == "delete-me") | (Invitation.created_by == "delete-me")
        ).count() == 0

        # The admin-issued invitation the deleted user *used* is preserved as an
        # audit record, but detached (used_by NULL) and deactivated so the freed
        # code cannot be re-claimed (issue #366).
        used_inv = db.query(Invitation).filter(Invitation.code == "TS-USED-0001").one()
        assert used_inv.used_by is None
        assert used_inv.is_active is False

        # The operator-config row the user last touched survives with its
        # reference nulled, not deleted.
        cfg_row = db.query(AppConfig).filter(AppConfig.key == "registration_open").one()
        assert cfg_row.updated_by is None

        # The waitlist lead survives even though the invitation it was linked to
        # (created by the deleted user) is gone — the link is nulled (issue #366).
        lead = db.query(WaitlistSignup).filter(WaitlistSignup.email == "lead@example.test").one()
        assert lead.invitation_id is None

        # Belt-and-braces: nothing anywhere still references a deleted id.
        live_user_ids = {uid for (uid,) in db.query(User.id).all()}
        dangling_user_refs = (
            [r for (r,) in db.query(Invitation.used_by).filter(Invitation.used_by.isnot(None)).all()]
            + [r for (r,) in db.query(Invitation.created_by).all()]
            + [r for (r,) in db.query(AppConfig.updated_by).filter(AppConfig.updated_by.isnot(None)).all()]
        )
        assert all(ref in live_user_ids for ref in dangling_user_refs)
        live_inv_ids = {iid for (iid,) in db.query(Invitation.id).all()}
        waitlist_refs = [
            iid
            for (iid,) in db.query(WaitlistSignup.invitation_id)
            .filter(WaitlistSignup.invitation_id.isnot(None))
            .all()
        ]
        assert all(ref in live_inv_ids for ref in waitlist_refs)
    finally:
        db.close()

    from api import personal_context_deletion_storage

    manifests = list(personal_context_deletion_storage.iter_active())
    assert {
        (manifest["user_id"], manifest["operation"], manifest["status"])
        for manifest in manifests
    } == {
        ("delete-me", "delete_owner_context", "completed"),
        ("demo-user", "delete_owner_context", "completed"),
    }


def test_account_deletion_deletes_only_scoped_feedback_images(
    account_client, monkeypatch
):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from api import feedback_storage
    from db.models import Feedback, User

    with db_session.SessionLocal() as db:
        owner_feedback = db.query(Feedback).filter(
            Feedback.user_id == "delete-me"
        ).one()
        demo_feedback = Feedback(
            user_id="demo-user",
            kind="bug",
            message="demo screenshot",
            status="new",
        )
        outsider = User(
            id="other-user",
            email="other@example.test",
            hashed_password="x",
        )
        outsider_feedback = Feedback(
            user_id=outsider.id,
            kind="bug",
            message="unrelated screenshot",
            status="new",
        )
        db.add_all([demo_feedback, outsider, outsider_feedback])
        db.flush()
        owner_feedback.image_keys = [
            f"feedback/{owner_feedback.id}/0.png"
        ]
        demo_feedback.image_keys = [f"feedback/{demo_feedback.id}/0.png"]
        outsider_feedback.image_keys = [
            f"feedback/{outsider_feedback.id}/0.png"
        ]
        provenance = feedback_storage.current_storage_provenance()
        assert provenance is not None
        owner_feedback.image_storage_provenance = provenance
        demo_feedback.image_storage_provenance = provenance
        outsider_feedback.image_storage_provenance = provenance
        scoped = {
            (owner_feedback.image_keys[0], owner_feedback.id),
            (demo_feedback.image_keys[0], demo_feedback.id),
        }
        outsider_feedback_id = outsider_feedback.id
        db.commit()

    deleted: list[tuple[str, int]] = []

    def _delete_image(key: str, *, feedback_id: int, provenance: object) -> None:
        assert provenance is not None
        deleted.append((key, feedback_id))

    monkeypatch.setattr(feedback_storage, "delete_image", _delete_image)

    response = client.delete("/api/me")

    assert response.status_code == 200, response.text
    assert set(deleted) == scoped
    with db_session.SessionLocal() as db:
        remaining = db.get(Feedback, outsider_feedback_id)
        assert remaining is not None
        assert remaining.user_id == "other-user"
        assert remaining.image_keys == [
            f"feedback/{outsider_feedback_id}/0.png"
        ]


def test_account_deletion_storage_failure_is_visible_and_preserves_locators(
    account_client, monkeypatch
):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from api import feedback_storage
    from db.models import Feedback, User

    with db_session.SessionLocal() as db:
        row = db.query(Feedback).filter(Feedback.user_id == "delete-me").one()
        row.image_keys = [f"feedback/{row.id}/0.png"]
        feedback_id = row.id
        image_keys = list(row.image_keys)
        db.commit()

    monkeypatch.setattr(
        feedback_storage,
        "delete_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            feedback_storage.FeedbackStorageDeletionError("unavailable")
        ),
    )

    response = client.delete("/api/me")

    assert response.status_code == 503
    assert response.json()["detail"] == "ACCOUNT_DELETE_STORAGE_UNAVAILABLE"
    with db_session.SessionLocal() as db:
        users = db.query(User).filter(
            User.id.in_(["delete-me", "demo-user"])
        ).all()
        assert {user.id for user in users} == {"delete-me", "demo-user"}
        assert all(user.is_active is False for user in users)
        row = db.get(Feedback, feedback_id)
        assert row is not None
        assert row.image_keys == image_keys


def test_account_deletion_missing_storage_provenance_preserves_locator(
    account_client,
):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from db.models import Feedback, User

    with db_session.SessionLocal() as db:
        row = db.query(Feedback).filter(Feedback.user_id == "delete-me").one()
        row.image_keys = [f"feedback/{row.id}/0.png"]
        row.image_storage_provenance = None
        feedback_id = row.id
        db.commit()

    response = client.delete("/api/me")

    assert response.status_code == 503
    assert response.json()["detail"] == "ACCOUNT_DELETE_STORAGE_UNAVAILABLE"
    with db_session.SessionLocal() as db:
        assert db.get(User, "delete-me") is not None
        retained = db.get(Feedback, feedback_id)
        assert retained is not None
        assert retained.image_keys == [f"feedback/{feedback_id}/0.png"]
        assert retained.image_storage_provenance is None


def test_account_deletion_detaches_without_cancelling_ambiguous_evidence(
    account_client,
):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from db.models import (
        Feedback,
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
    )

    now = datetime.utcnow()
    with db_session.SessionLocal() as db:
        feedback = db.query(Feedback).filter(
            Feedback.user_id == "delete-me"
        ).one()
        feedback.status = "needs_review"
        feedback.publication_status = "manual_required"
        outbox = FeedbackPublicationOutbox(
            id="account-delete-ambiguous-outbox",
            feedback_id=feedback.id,
            public_id="a" * 32,
            marker_version="v2",
            target_repo="praxys-run/praxys",
            consent_version="feedback-publication-v2-public-github",
            consented_at=now,
            payload_sha256="sha256:" + "a" * 64,
            public_content_sha256="sha256:" + "b" * 64,
            state="manual_review",
            delivery_evidence="ambiguous",
            attempt_count=1,
            available_at=now,
            last_error_code="multiple_marker_matches",
        )
        db.add(outbox)
        db.flush()
        db.add(
            FeedbackPublicationAttempt(
                id="account-delete-ambiguous-attempt",
                outbox_id=outbox.id,
                attempt_no=1,
                lease_token="account-delete-ambiguous-lease",
                target_repo=outbox.target_repo,
                payload_sha256=outbox.payload_sha256,
                started_at=now,
                finished_at=now,
                outcome="not_sent",
                error_code="multiple_marker_matches",
            )
        )
        db.commit()

    response = client.delete("/api/me")

    assert response.status_code == 200, response.text
    with db_session.SessionLocal() as db:
        retained = db.get(
            FeedbackPublicationOutbox,
            "account-delete-ambiguous-outbox",
        )
        assert retained is not None
        assert retained.feedback_id is None
        assert retained.state == "manual_review"
        assert retained.delivery_evidence == "ambiguous"
        assert retained.last_error_code == "multiple_marker_matches"
        attempt = db.get(
            FeedbackPublicationAttempt,
            "account-delete-ambiguous-attempt",
        )
        assert attempt is not None
        assert attempt.outcome == "not_sent"
        assert attempt.error_code == "multiple_marker_matches"


def test_account_deletion_preserves_legacy_public_issue_locator(
    account_client,
):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from db.models import Feedback, FeedbackPublicationOutbox

    now = datetime.utcnow()
    issue_url = "https://github.com/legacy-owner/legacy-repo/issues/42"
    with db_session.SessionLocal() as db:
        feedback = db.query(Feedback).filter(
            Feedback.user_id == "delete-me"
        ).one()
        feedback.status = "resolved"
        feedback.publication_status = "published"
        feedback.github_issue_number = 42
        feedback.github_issue_url = issue_url
        db.add(
            FeedbackPublicationOutbox(
                id="account-delete-legacy-outbox",
                feedback_id=feedback.id,
                public_id="c" * 32,
                marker_version="legacy",
                target_repo="legacy-owner/legacy-repo",
                consent_version=None,
                consented_at=None,
                payload_sha256=None,
                public_content_sha256=None,
                state="published",
                delivery_evidence="published",
                attempt_count=0,
                reconcile_count=0,
                available_at=now,
                github_issue_number=42,
                github_issue_url=issue_url,
                published_at=now,
            )
        )
        db.commit()

    response = client.delete("/api/me")

    assert response.status_code == 200, response.text
    with db_session.SessionLocal() as db:
        retained = db.get(
            FeedbackPublicationOutbox,
            "account-delete-legacy-outbox",
        )
        assert retained is not None
        assert retained.feedback_id is None
        assert retained.marker_version == "legacy"
        assert retained.state == "published"
        assert retained.delivery_evidence == "published"
        assert retained.github_issue_number == 42
        assert retained.github_issue_url == issue_url
        assert retained.consent_version is None
        assert retained.payload_sha256 is None


def test_feedback_submission_serializes_with_account_deletion(
    account_client, monkeypatch
):
    _client, db_session = account_client
    _seed_account_rows(db_session)

    import threading

    from fastapi import BackgroundTasks

    from api import account_deletion, feedback_storage
    from api.routes.feedback import FeedbackRequest, submit_feedback
    from db.models import Feedback, User

    store_started = threading.Event()
    release_store = threading.Event()
    deletion_started = threading.Event()
    deletion_finished = threading.Event()
    deleted: list[tuple[str, int]] = []
    results: dict[str, object] = {}
    errors: list[Exception] = []

    def _store_image(
        _data: bytes,
        *,
        feedback_id: int,
        index: int,
        provenance: object,
    ) -> str:
        with db_session.SessionLocal() as observer:
            persisted = observer.get(Feedback, feedback_id)
            assert persisted is not None
            assert persisted.image_keys == [
                f"feedback/{feedback_id}/{index}.png"
            ]
            assert persisted.image_storage_provenance == provenance
        store_started.set()
        assert release_store.wait(3)
        return f"feedback/{feedback_id}/{index}.png"

    def _delete_image(key: str, *, feedback_id: int, provenance: object) -> None:
        assert provenance is not None
        deleted.append((key, feedback_id))

    original_guard = account_deletion.begin_active_admin_guard

    def _observed_guard(db) -> None:
        deletion_started.set()
        original_guard(db)

    monkeypatch.setattr(feedback_storage, "store_image", _store_image)
    monkeypatch.setattr(feedback_storage, "delete_image", _delete_image)
    monkeypatch.setattr(
        account_deletion,
        "begin_active_admin_guard",
        _observed_guard,
    )
    monkeypatch.setattr(
        account_deletion,
        "_clear_tokenstore",
        lambda _user_id: None,
    )
    monkeypatch.setattr(
        account_deletion,
        "_clear_legacy_plan_status",
        lambda _db, _user_id: None,
    )

    def _submit() -> None:
        try:
            with db_session.SessionLocal() as db:
                results["submit"] = submit_feedback(
                    FeedbackRequest(
                        kind="bug",
                        message="concurrent screenshot",
                        images=[
                            "data:image/png;base64,"
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
                            "CAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
                            "AtsB9Wl2nGQAAAAASUVORK5CYII="
                        ],
                    ),
                    background_tasks=BackgroundTasks(),
                    user_id="delete-me",
                    db=db,
                )
        except Exception as exc:
            errors.append(exc)

    def _delete() -> None:
        try:
            with db_session.SessionLocal() as db:
                results["delete"] = account_deletion.delete_user_account(
                    db,
                    "delete-me",
                )
        except Exception as exc:
            errors.append(exc)
        finally:
            deletion_finished.set()

    submit_thread = threading.Thread(target=_submit)
    delete_thread = threading.Thread(target=_delete)
    submit_thread.start()
    assert store_started.wait(3)
    delete_thread.start()
    assert deletion_started.wait(3)
    assert not deletion_finished.wait(0.2)

    release_store.set()
    submit_thread.join(5)
    delete_thread.join(5)

    assert not submit_thread.is_alive()
    assert not delete_thread.is_alive()
    assert errors == []
    submitted = results["submit"]
    feedback_id = submitted["id"]
    assert deleted == [(f"feedback/{feedback_id}/0.png", feedback_id)]
    with db_session.SessionLocal() as db:
        assert db.get(User, "delete-me") is None
        assert db.get(Feedback, feedback_id) is None


def test_inactive_account_can_retry_cleanup(account_client, monkeypatch):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from api import account_deletion
    from db.models import User

    db = db_session.SessionLocal()
    try:
        user = db.query(User).filter(User.id == "delete-me").one()
        user.is_active = False
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(account_deletion, "_clear_tokenstore", lambda user_id: None)
    response = client.delete("/api/me")

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "deleted", "email": "athlete@example.test"}
    db = db_session.SessionLocal()
    try:
        assert db.query(User).filter(User.id.in_(["delete-me", "demo-user"])).count() == 0
    finally:
        db.close()


def test_deletion_first_phase_cancels_labs_work_before_cleanup(
    account_client,
    monkeypatch,
) -> None:
    _, db_session = account_client
    _seed_account_rows(db_session)

    from api import account_deletion
    from db.models import (
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        User,
    )

    with db_session.SessionLocal() as db:
        owner_job = db.get(LabsAnalysisJob, "labs-delete-job")
        owner_job.status = "processing"
        owner_outbox = db.get(LabsAnalysisOutbox, "labs-delete-outbox")
        owner_outbox.status = "dispatched"
        demo_job = LabsAnalysisJob(
            id="labs-delete-demo-job",
            user_id="demo-user",
            experiment_id="environment-response-v1",
            trigger="enrollment",
            status="queued",
            model_version="labs-v1",
            source_revision="rev1:demo",
            correlation_id="labs-demo-correlation",
            attempt_count=0,
            retryable_failure=False,
        )
        db.add(demo_job)
        db.flush()
        db.add(LabsAnalysisOutbox(
            id="labs-delete-demo-outbox",
            job_id=demo_job.id,
            status="pending",
            attempt_count=0,
        ))
        db.commit()

    monkeypatch.setattr(
        account_deletion,
        "_delete_user_owned_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("cleanup interrupted")
        ),
    )

    with db_session.SessionLocal() as db:
        with pytest.raises(RuntimeError, match="cleanup interrupted"):
            account_deletion.delete_user_account(db, "delete-me")

    with db_session.SessionLocal() as db:
        users = {
            user.id: user.is_active
            for user in db.query(User).filter(
                User.id.in_(["delete-me", "demo-user"])
            )
        }
        jobs = {
            job.id: job.status
            for job in db.query(LabsAnalysisJob).filter(
                LabsAnalysisJob.id.in_(
                    ["labs-delete-job", "labs-delete-demo-job"]
                )
            )
        }
        outboxes = {
            outbox.id: outbox.status
            for outbox in db.query(LabsAnalysisOutbox).filter(
                LabsAnalysisOutbox.id.in_(
                    ["labs-delete-outbox", "labs-delete-demo-outbox"]
                )
            )
        }

    assert users == {"delete-me": False, "demo-user": False}
    assert jobs == {
        "labs-delete-job": "cancelled",
        "labs-delete-demo-job": "cancelled",
    }
    assert outboxes == {
        "labs-delete-outbox": "cancelled",
        "labs-delete-demo-outbox": "cancelled",
    }


def test_account_deletion_fails_closed_when_context_manifest_is_unavailable(
    account_client,
    monkeypatch,
):
    client, db_session = account_client
    _seed_account_rows(db_session)

    from api import personal_context_deletion_storage
    from db.models import PersonalContextItem, User

    monkeypatch.setattr(
        personal_context_deletion_storage,
        "store_requested",
        lambda **_kwargs: (_ for _ in ()).throw(
            personal_context_deletion_storage.DeletionManifestStorageError(
                "unavailable"
            )
        ),
    )

    response = client.delete("/api/me")

    assert response.status_code == 503
    assert response.json()["detail"] == "ACCOUNT_DELETE_STORAGE_UNAVAILABLE"
    with db_session.SessionLocal() as db:
        assert db.query(User).filter(
            User.id.in_(["delete-me", "demo-user"])
        ).count() == 2
        assert db.query(PersonalContextItem).filter(
            PersonalContextItem.user_id.in_(["delete-me", "demo-user"])
        ).count() == 2


def test_delete_me_removes_legacy_plan_status_files(
    account_client,
    monkeypatch,
    tmp_path,
):
    import glob
    import os

    client, db_session = account_client
    _seed_account_rows(db_session)

    from api.routes import plan as plan_route

    monkeypatch.setattr(plan_route, "_STRYD_PUSH_STATUS_DIR", str(tmp_path))
    path = plan_route._stryd_push_status_path("delete-me")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for candidate in (path, f"{path}.imported-old", f"{path}.corrupt-old"):
        with open(candidate, "w", encoding="utf-8") as handle:
            handle.write("{}")

    response = client.delete("/api/me")
    assert response.status_code == 200, response.text
    assert not os.path.exists(path)
    assert glob.glob(f"{path}.*") == []


def test_delete_access_accepts_valid_token_for_inactive_user(account_client):
    _, db_session = account_client

    import jwt

    from api.auth import require_account_deletion_access
    from api.auth_secrets import get_jwt_secret
    from db.models import User

    db = db_session.SessionLocal()
    try:
        db.add(User(
            id="pending-delete",
            email="pending@example.test",
            hashed_password="x",
            is_active=False,
        ))
        db.commit()

        token = jwt.encode(
            {
                "sub": "pending-delete",
                "aud": "fastapi-users:auth",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            get_jwt_secret(),
            algorithm="HS256",
        )

        class _StubRequest:
            headers = {"Authorization": f"Bearer {token}"}

        assert require_account_deletion_access(_StubRequest(), db) == "pending-delete"
    finally:
        db.close()


def test_delete_me_rejects_last_admin(account_client):
    """The only admin cannot delete their own account and strand the app adminless."""
    client, db_session = account_client
    client.current_user_id["value"] = "solo-admin"  # type: ignore[attr-defined]

    from db.models import User

    db = db_session.SessionLocal()
    try:
        db.add(User(id="solo-admin", email="admin@example.test", hashed_password="x", is_superuser=True))
        db.add(User(
            id="inactive-admin",
            email="former-admin@example.test",
            hashed_password="x",
            is_superuser=True,
            is_active=False,
        ))
        db.commit()
    finally:
        db.close()

    res = client.delete("/api/me")
    assert res.status_code == 400, res.text
    assert res.json()["detail"] == "LAST_ADMIN_CANNOT_DELETE_ACCOUNT"

    db = db_session.SessionLocal()
    try:
        solo = db.query(User).filter(User.id == "solo-admin").one()
        assert solo.is_active is True
    finally:
        db.close()


def test_deletion_takes_revision_lock_before_user_row(account_client, monkeypatch):
    _, db_session = account_client
    _seed_account_rows(db_session)

    from sqlalchemy import event

    from api import account_deletion
    from db.models import User

    setup_db = db_session.SessionLocal()
    try:
        user = setup_db.query(User).filter(User.id == "delete-me").one()
        user.is_active = False
        setup_db.commit()
    finally:
        setup_db.close()

    events: list[str] = []
    monkeypatch.setattr(
        account_deletion,
        "lock_revision_writes",
        lambda _db, _user_id: events.append("revision-lock"),
    )
    monkeypatch.setattr(account_deletion, "_clear_tokenstore", lambda _user_id: None)

    db = db_session.SessionLocal()

    def _track_user_select(
        _conn,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        normalized = statement.lstrip().upper()
        if normalized.startswith("SELECT") and "FROM USERS" in normalized:
            events.append("user-select")

    event.listen(db.get_bind(), "before_cursor_execute", _track_user_select)
    try:
        account_deletion.delete_user_account(db, "delete-me")
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", _track_user_select)
        db.close()

    assert events.index("revision-lock") < events.index("user-select")


def test_delete_refreshes_preloaded_user_before_last_admin_guard(account_client):
    _, db_session = account_client
    _seed_account_rows(db_session)

    from fastapi import HTTPException

    from api.account_deletion import delete_user_account
    from db.models import User

    stale_db = db_session.SessionLocal()
    fresh_db = db_session.SessionLocal()
    try:
        cached = stale_db.query(User).filter(User.id == "delete-me").one()
        assert cached.is_superuser is False

        promoted = fresh_db.query(User).filter(User.id == "delete-me").one()
        promoted.is_superuser = True
        prior_admin = fresh_db.query(User).filter(User.id == "admin").one()
        prior_admin.is_superuser = False
        fresh_db.commit()

        with pytest.raises(HTTPException) as exc:
            delete_user_account(stale_db, "delete-me")
        assert exc.value.status_code == 400
        assert exc.value.detail == "LAST_ADMIN_CANNOT_DELETE_ACCOUNT"
    finally:
        stale_db.close()
        fresh_db.close()

    db = db_session.SessionLocal()
    try:
        user = db.query(User).filter(User.id == "delete-me").one()
        assert user.is_active is True
        assert user.is_superuser is True
    finally:
        db.close()


def test_concurrent_admin_demotions_leave_one_active_admin(account_client):
    _, db_session = account_client

    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi import HTTPException
    from api.routes.admin import RoleChangeRequest, update_user_role
    from db.models import User

    db = db_session.SessionLocal()
    try:
        db.add_all([
            User(id="admin-a", email="a@example.test", hashed_password="x", is_superuser=True),
            User(id="admin-b", email="b@example.test", hashed_password="x", is_superuser=True),
        ])
        db.commit()
    finally:
        db.close()

    barrier = Barrier(2)

    def _demote(actor: str, target: str) -> int:
        thread_db = db_session.SessionLocal()
        try:
            # Mirror request auth: the actor is already in the identity map
            # before the serialized role-change transaction starts.
            thread_db.query(User).filter(User.id == actor).one()
            barrier.wait()
            update_user_role(
                target_user_id=target,
                body=RoleChangeRequest(is_superuser=False),
                user_id=actor,
                db=thread_db,
            )
            return 200
        except HTTPException as exc:
            return exc.status_code
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(
            lambda pair: _demote(*pair),
            [("admin-a", "admin-b"), ("admin-b", "admin-a")],
        ))

    assert sorted(statuses) == [200, 403]
    db = db_session.SessionLocal()
    try:
        assert db.query(User).filter(
            User.is_superuser == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
        ).count() == 1
    finally:
        db.close()



def test_delete_me_rejects_demo_account(account_client):
    """Demo users stay read-only and cannot self-delete the shared demo account."""
    client, db_session = account_client
    client.current_user_id["value"] = "demo-only"  # type: ignore[attr-defined]

    from db.models import User

    db = db_session.SessionLocal()
    try:
        db.add(User(id="admin", email="admin@example.test", hashed_password="x", is_superuser=True))
        db.add(User(id="demo-only", email="demo@example.test", hashed_password="x", is_demo=True, demo_of="admin"))
        db.commit()
    finally:
        db.close()

    res = client.delete("/api/me")
    assert res.status_code == 403, res.text
    assert res.json()["detail"] == "Demo accounts cannot modify data"

    db = db_session.SessionLocal()
    try:
        assert db.query(User).filter(User.id == "demo-only").count() == 1
    finally:
        db.close()

def test_run_sync_rolls_back_if_user_deactivated_before_commit(account_client, monkeypatch):
    """An in-flight sync must not commit orphaned rows after deletion starts."""
    _, db_session = account_client

    from datetime import date

    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from api.routes import sync as sync_routes
    from db.models import Activity, User, UserConnection

    db = db_session.SessionLocal()
    try:
        db.add(User(
            id="sync-user",
            email="sync@example.test",
            hashed_password="x",
            is_active=True,
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
        ))
        db.add(UserConnection(user_id="sync-user", platform="garmin", status="connected", consecutive_failures=0))
        db.commit()
    finally:
        db.close()

    def _fake_sync(user_id: str, creds: dict, from_date: str | None, db) -> dict:
        db.add(Activity(user_id=user_id, activity_id="orphan-candidate", date=date(2026, 6, 30)))
        other = db_session.SessionLocal()
        try:
            user = other.query(User).filter(User.id == user_id).one()
            user.is_active = False
            other.commit()
        finally:
            other.close()
        return {"activities": 1}

    monkeypatch.setattr(sync_routes, "_sync_garmin", _fake_sync)
    sync_routes._run_sync("sync-user", "garmin", {}, None)

    db = db_session.SessionLocal()
    try:
        assert db.query(Activity).filter(Activity.activity_id == "orphan-candidate").count() == 0
        assert db.query(User).filter(User.id == "sync-user", User.is_active == False).count() == 1  # noqa: E712
        conn = db.query(UserConnection).filter(UserConnection.user_id == "sync-user").one()
        assert conn.status == "connected"
        assert conn.consecutive_failures == 0
    finally:
        db.close()
def test_delete_user_account_no_dangling_fk_under_enforcement(monkeypatch):
    """Deletion commits under enforced FKs (Postgres-like) with zero orphans.

    Regression for #366: SQLite shipped FK enforcement off, so account deletion
    silently left dangling ``invitations.used_by`` / ``app_config.updated_by`` /
    ``waitlist_signups.invitation_id`` references. With ``PRAGMA foreign_keys=ON``
    those orphans become a hard error at commit, so this proves the deletion path
    clears every reference before dropping the user — exactly the invariant
    PostgreSQL now enforces in production.
    """
    from datetime import date

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import api.account_deletion as account_deletion
    from db.models import (
        Activity,
        AppConfig,
        Base,
        Feedback,
        Invitation,
        PlanDelivery,
        PlanDeliveryAttempt,
        PlanRevision,
        User,
        UserConfig,
        WaitlistSignup,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enforce_fks(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    # Mirror production's session config (db/session.py uses autoflush=False) so
    # this stays a faithful proxy for the enforced-FK deletion path.
    Session = sessionmaker(bind=engine, autoflush=False)

    # delete_user_account commits before touching disk tokenstores; stub that
    # step so the test stays DB-only (no DATA_DIR / filesystem dependency).
    monkeypatch.setattr(account_deletion, "_clear_tokenstore", lambda uid: None)

    db = Session()
    try:
        # Seed parents before children so inserts satisfy the enforced FKs: these
        # models use bare ForeignKey columns with no ORM relationship, so the
        # unit of work can't infer insert order (it mirrors the real app, which
        # commits a user at registration before syncing that user's data).
        db.add(User(id="admin", email="admin@x.test", hashed_password="x", is_superuser=True))
        db.add(User(id="target", email="t@x.test", hashed_password="x"))
        db.commit()
        db.add(User(id="target-demo", email="d@x.test", hashed_password="x", is_demo=True, demo_of="target"))
        db.commit()
        db.add(UserConfig(user_id="target", display_name="T"))
        db.add(Activity(user_id="target", activity_id="a1", date=date(2026, 6, 1)))
        db.add(Feedback(user_id="target", kind="bug", message="hi", status="new"))
        revision = PlanRevision(
            user_id="target",
            operation="upsert",
            actor_type="user",
            actor_id="target",
            origin="test",
            before_snapshot=[],
            after_snapshot=[],
            details={},
        )
        delivery = PlanDelivery(
            user_id="target",
            canonical_key="ai:2026-06-02",
            workout_date=date(2026, 6, 2),
            workout_version="b" * 64,
            target="stryd",
            state="synced",
            external_id="stryd-target",
        )
        db.add_all([revision, delivery])
        db.flush()
        db.add(PlanDeliveryAttempt(
            delivery_id=delivery.id,
            attempt_number=1,
            operation="deliver",
            state="synced",
            external_id="stryd-target",
        ))
        made = Invitation(code="TS-MADE-9999", created_by="target", is_active=True)
        used = Invitation(code="TS-USED-9999", created_by="admin", used_by="target", is_active=True)
        db.add_all([made, used])
        db.commit()
        db.add(WaitlistSignup(email="w1@x.test", invitation_id=made.id))
        db.add(AppConfig(key="registration_open", value="true", updated_by="target"))
        db.commit()
    finally:
        db.close()

    db = Session()
    try:
        result = account_deletion.delete_user_account(db, "target", enforce_last_admin_guard=False)
    finally:
        db.close()

    assert set(result.deleted_user_ids) == {"target", "target-demo"}

    db = Session()
    try:
        assert db.query(User).filter(User.id.in_(["target", "target-demo"])).count() == 0
        # Invitation the user *used* is preserved, detached, and deactivated.
        used_row = db.query(Invitation).filter(Invitation.code == "TS-USED-9999").one()
        assert used_row.used_by is None
        assert used_row.is_active is False
        # Invitation the user *created* is deleted (created_by is NOT NULL).
        assert db.query(Invitation).filter(Invitation.code == "TS-MADE-9999").count() == 0
        assert db.query(PlanRevision).filter(PlanRevision.user_id == "target").count() == 0
        assert db.query(PlanDelivery).filter(PlanDelivery.user_id == "target").count() == 0
        assert db.query(PlanDeliveryAttempt).count() == 0
        # Waitlist lead kept with its (now-deleted) invitation link nulled.
        wl = db.query(WaitlistSignup).filter(WaitlistSignup.email == "w1@x.test").one()
        assert wl.invitation_id is None
        # Operator-config row kept, updated_by nulled.
        cfg = db.query(AppConfig).filter(AppConfig.key == "registration_open").one()
        assert cfg.updated_by is None
    finally:
        db.close()
    engine.dispose()


def test_account_deletion_prelocks_publication_outboxes_before_feedback(
    monkeypatch, tmp_path
) -> None:
    """Owner and demo deletion use one O->F lock order without re-locking O."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Query, sessionmaker
    from sqlalchemy.pool import StaticPool

    import api.account_deletion as account_deletion
    import api.personal_context as personal_context
    from db.models import (
        Base,
        Feedback,
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
        User,
    )

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(account_deletion, "_clear_tokenstore", lambda _uid: None)
    monkeypatch.setattr(
        account_deletion, "_clear_legacy_plan_status", lambda _db, _uid: None
    )
    monkeypatch.setattr(
        personal_context,
        "stage_account_deletion_manifests",
        lambda _db, _user_ids: [],
    )
    monkeypatch.setattr(
        personal_context, "complete_account_deletion_manifests", lambda _items: None
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    now = datetime.utcnow()
    with Session() as db:
        db.add_all(
            (
                User(
                    id="lock-order-owner",
                    email="lock-owner@example.test",
                    hashed_password="x",
                ),
                User(
                    id="lock-order-demo",
                    email="lock-demo@example.test",
                    hashed_password="x",
                    is_demo=True,
                    demo_of="lock-order-owner",
                ),
            )
        )
        db.commit()
        for index, user_id in enumerate(
            ("lock-order-owner", "lock-order-demo"), start=1
        ):
            feedback = Feedback(
                user_id=user_id,
                kind="bug",
                message=f"private lock-order sentinel {index}",
                status="triaged",
                publication_status="queued",
            )
            db.add(feedback)
            db.flush()
            db.add(
                FeedbackPublicationOutbox(
                    id=f"lock-order-outbox-{index}",
                    feedback_id=feedback.id,
                    public_id=f"{index:032x}",
                    marker_version="v2",
                    target_repo="praxys-run/praxys",
                    consent_version="feedback-publication-v2",
                    consented_at=now,
                    payload_sha256="sha256:" + f"{index:064x}",
                    public_content_sha256=(
                        "sha256:" + f"{index + 10:064x}"
                    ),
                    state="sending" if index == 1 else "pending",
                    delivery_evidence=(
                        "ambiguous" if index == 1 else "not_sent"
                    ),
                    available_at=now,
                    lease_token="lock-order-lease" if index == 1 else None,
                    lease_expires_at=(
                        now + timedelta(minutes=2) if index == 1 else None
                    ),
                )
            )
            if index == 1:
                db.flush()
                db.add(
                    FeedbackPublicationAttempt(
                        id="lock-order-attempt-1",
                        outbox_id="lock-order-outbox-1",
                        attempt_no=1,
                        lease_token="lock-order-lease",
                        target_repo="praxys-run/praxys",
                        payload_sha256="sha256:" + f"{index:064x}",
                        started_at=now,
                        outcome="in_flight",
                    )
                )
        db.commit()

    lock_events: list[str] = []
    detach_batches: list[tuple[str, ...]] = []
    original_with_for_update = Query.with_for_update
    original_detach = account_deletion._detach_feedback_publication_evidence

    def _record_lock(query, *args, **kwargs):
        entities = {
            description.get("entity") for description in query.column_descriptions
        }
        if FeedbackPublicationOutbox in entities:
            lock_events.append("outbox")
        elif FeedbackPublicationAttempt in entities:
            lock_events.append("attempt")
        elif Feedback in entities:
            lock_events.append("feedback")
        return original_with_for_update(query, *args, **kwargs)

    def _record_detach(db, outboxes, *args, **kwargs):
        detach_batches.append(tuple(outbox.id for outbox in outboxes))
        return original_detach(db, outboxes, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", _record_lock)
    monkeypatch.setattr(
        account_deletion, "_detach_feedback_publication_evidence", _record_detach
    )

    with Session() as db:
        result = account_deletion.delete_user_account(
            db,
            "lock-order-owner",
            enforce_last_admin_guard=False,
        )

    assert set(result.deleted_user_ids) == {
        "lock-order-owner",
        "lock-order-demo",
    }
    assert lock_events[0] == "outbox"
    assert lock_events.count("outbox") == 1
    assert lock_events.count("attempt") == 1
    assert (
        lock_events.index("outbox")
        < lock_events.index("attempt")
        < lock_events.index("feedback")
    )
    assert {outbox_id for batch in detach_batches for outbox_id in batch} == {
        "lock-order-outbox-1",
        "lock-order-outbox-2",
    }

    with Session() as db:
        outboxes = db.query(FeedbackPublicationOutbox).order_by(
            FeedbackPublicationOutbox.id
        ).all()
        assert len(outboxes) == 2
        assert all(outbox.feedback_id is None for outbox in outboxes)
    engine.dispose()


def test_postgres_account_deletion_prelock_sql_is_exact_and_stable() -> None:
    """The joined scope query locks only Outbox rows in a total order."""
    from sqlalchemy import create_mock_engine
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Session

    import api.account_deletion as account_deletion

    engine = create_mock_engine("postgresql+psycopg://", lambda *_args, **_kw: None)
    with Session(bind=engine) as db:
        query = account_deletion._feedback_publication_outbox_lock_query(
            db,
            ("lock-order-demo", "lock-order-owner"),
        )
        outbox_sql = " ".join(
            str(
                query.statement.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).split()
        )
        attempt_query = account_deletion._feedback_publication_attempt_lock_query(
            db,
            ("lock-order-outbox-2", "lock-order-outbox-1"),
        )
        attempt_sql = " ".join(
            str(
                attempt_query.statement.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).split()
        )

    assert "ORDER BY feedback_publication_outbox.id ASC" in outbox_sql
    assert "FOR UPDATE OF feedback_publication_outbox" in outbox_sql
    assert "SKIP LOCKED" not in outbox_sql
    assert "ORDER BY feedback_publication_attempts.id ASC" in attempt_sql
    assert "FOR UPDATE OF feedback_publication_attempts" in attempt_sql
    assert "SKIP LOCKED" not in attempt_sql


@pytest.mark.parametrize("foreign_keys", (False, True))
def test_account_deletion_detaches_feedback_publication_evidence(
    monkeypatch, tmp_path, foreign_keys: bool
) -> None:
    """Private feedback is erased while delivery evidence remains deidentified."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import api.account_deletion as account_deletion
    import api.personal_context as personal_context
    from api import github_issues
    from api.feedback_publication import (
        claim_next_reconciliation,
        claim_next_send,
        publication_marker,
        reconcile_claim,
    )
    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from api.routes.feedback import feedback_publication_queue
    from db.models import (
        Base,
        Feedback,
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
        User,
    )
    from fastapi import Response

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(account_deletion, "_clear_tokenstore", lambda _uid: None)
    monkeypatch.setattr(
        account_deletion, "_clear_legacy_plan_status", lambda _db, _uid: None
    )
    monkeypatch.setattr(
        personal_context,
        "stage_account_deletion_manifests",
        lambda _db, _user_ids: [],
    )
    monkeypatch.setattr(
        personal_context, "complete_account_deletion_manifests", lambda _items: None
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if foreign_keys:
        @event.listens_for(engine, "connect")
        def _enforce_fks(dbapi_conn, _rec):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    now = datetime.utcnow()
    states = (
        "pending",
        "retry_wait",
        "held",
        "manual_review",
        "sending",
        "reconciling",
        "published",
    )
    original_evidence: dict[str, tuple[str, str, str, int | None, str | None]] = {}

    with Session() as db:
        db.add_all(
            (
                User(
                    id="publication-admin",
                    email="publication-admin@example.test",
                    hashed_password="x",
                    is_superuser=True,
                ),
                User(
                    id="publication-delete-target",
                    email="erase-this-account@example.test",
                    hashed_password="private-password-hash",
                ),
            )
        )
        db.commit()
        for index, state in enumerate(states, start=1):
            feedback = Feedback(
                user_id="publication-delete-target",
                kind="bug",
                message=f"private feedback sentinel {state}",
                status="issue_created" if state == "published" else "triaged",
                publication_status=(
                    "published"
                    if state == "published"
                    else "unknown"
                    if state in ("sending", "reconciling")
                    else "manual_required"
                    if state == "manual_review"
                    else "queued"
                ),
                publication_consent_version=FEEDBACK_PUBLICATION_CONSENT_VERSION,
                publication_consented_at=now,
                ai_title=f"private title sentinel {state}",
                ai_body=f"private body sentinel {state}",
                ai_labels=["bug", "feedback"],
            )
            db.add(feedback)
            db.flush()
            public_id = f"{index:032x}"
            digest = "sha256:" + f"{index:064x}"
            issue_number = 700 + index if state == "published" else None
            issue_url = (
                f"https://github.com/praxys-run/praxys/issues/{issue_number}"
                if issue_number is not None
                else None
            )
            lease = f"lease-{state}" if state in ("sending", "reconciling") else None
            outbox = FeedbackPublicationOutbox(
                id=f"publication-outbox-{index}",
                feedback_id=feedback.id,
                public_id=public_id,
                marker_version="v2",
                target_repo="praxys-run/praxys",
                consent_version=FEEDBACK_PUBLICATION_CONSENT_VERSION,
                consented_at=now,
                payload_sha256=digest,
                public_content_sha256=(
                    "sha256:" + f"{index + 10:064x}"
                ),
                state=state,
                delivery_evidence=(
                    "published"
                    if state == "published"
                    else "ambiguous"
                    if state in ("sending", "reconciling")
                    else "not_sent"
                ),
                attempt_count=1 if state in ("sending", "reconciling") else 0,
                reconcile_count=1 if state == "reconciling" else 0,
                available_at=now - timedelta(seconds=1),
                lease_token=lease,
                lease_expires_at=(
                    now + timedelta(minutes=2) if lease is not None else None
                ),
                github_issue_number=issue_number,
                github_issue_url=issue_url,
                published_at=now if state == "published" else None,
            )
            db.add(outbox)
            db.flush()
            if state in ("sending", "reconciling"):
                db.add(
                    FeedbackPublicationAttempt(
                        id=f"publication-attempt-{index}",
                        outbox_id=outbox.id,
                        attempt_no=1,
                        lease_token=(
                            lease if state == "sending" else "prior-send-lease"
                        ),
                        target_repo=outbox.target_repo,
                        payload_sha256=digest,
                        started_at=now - timedelta(seconds=10),
                        finished_at=(now if state == "reconciling" else None),
                        outcome=("in_flight" if state == "sending" else "unknown"),
                    )
                )
            original_evidence[outbox.id] = (
                public_id,
                digest,
                outbox.target_repo,
                issue_number,
                issue_url,
            )
        db.commit()

    with Session() as db:
        result = account_deletion.delete_user_account(
            db,
            "publication-delete-target",
            enforce_last_admin_guard=False,
        )
    assert result.deleted_user_ids == ["publication-delete-target"]

    with Session() as db:
        assert db.get(User, "publication-delete-target") is None
        assert (
            db.query(Feedback)
            .filter(Feedback.user_id == "publication-delete-target")
            .count()
            == 0
        )
        outboxes = {
            row.id: row
            for row in db.query(FeedbackPublicationOutbox)
            .order_by(FeedbackPublicationOutbox.id)
            .all()
        }
        assert len(outboxes) == len(states)
        assert all(row.feedback_id is None for row in outboxes.values())
        assert {
            outboxes[f"publication-outbox-{index}"].state
            for index in range(1, 5)
        } == {"cancelled"}
        assert outboxes["publication-outbox-5"].state == "reconciling"
        assert outboxes["publication-outbox-6"].state == "reconciling"
        assert outboxes["publication-outbox-7"].state == "published"
        for outbox_id, expected in original_evidence.items():
            row = outboxes[outbox_id]
            assert (
                row.public_id,
                row.payload_sha256,
                row.target_repo,
                row.github_issue_number,
                row.github_issue_url,
            ) == expected
            assert row.lease_token is None
            assert row.lease_expires_at is None

        sending_attempt = db.get(
            FeedbackPublicationAttempt, "publication-attempt-5"
        )
        assert sending_attempt is not None
        assert sending_attempt.outcome == "unknown"
        assert sending_attempt.finished_at is not None

        monkeypatch.setattr(
            github_issues,
            "create_issue_outcome",
            lambda **_kwargs: pytest.fail("detached publication must never POST"),
        )
        reconciled_markers: list[str] = []

        def _reconcile(marker: str, **_kwargs):
            reconciled_markers.append(marker)
            return {
                "outcome": "unknown",
                "number": None,
                "url": None,
                "http_status": 200,
                "error_code": "not_indexed_or_absent",
            }

        monkeypatch.setattr(github_issues, "reconcile_issue_marker", _reconcile)
        assert claim_next_send(db) is None
        for _ in range(2):
            claim = claim_next_reconciliation(db)
            assert claim is not None
            assert reconcile_claim(db, *claim) == "unknown"
        assert claim_next_reconciliation(db) is None
        assert set(reconciled_markers) == {
            publication_marker(
                original_evidence[f"publication-outbox-{index}"][0],
                original_evidence[f"publication-outbox-{index}"][1],
            )
            for index in (5, 6)
        }

        response = Response()
        queue = feedback_publication_queue(
            response,
            user_id="publication-admin",
            db=db,
        )
        serialized = json.dumps(queue)
        assert response.headers["Cache-Control"] == "private, no-store"
        assert len(queue["items"]) == len(states)
        assert all(item["detached"] is True for item in queue["items"])
        for forbidden in (
            "private feedback sentinel",
            "private title sentinel",
            "private body sentinel",
            "erase-this-account@example.test",
            "private-password-hash",
        ):
            assert forbidden not in serialized

    engine.dispose()
