"""Regression contracts for miniapp managed-plan parity."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SETTINGS_TS = ROOT / "miniapp" / "pages" / "settings" / "index.ts"
SETTINGS_WXML = ROOT / "miniapp" / "pages" / "settings" / "index.wxml"
TRAINING_WXML = ROOT / "miniapp" / "pages" / "training" / "index.wxml"
TRAINING_JSON = ROOT / "miniapp" / "pages" / "training" / "index.json"
TODAY_WXML = ROOT / "miniapp" / "pages" / "today" / "index.wxml"
TODAY_JSON = ROOT / "miniapp" / "pages" / "today" / "index.json"
MANAGED_PLAN_TS = ROOT / "miniapp" / "components" / "managed-plan" / "index.ts"
MANAGED_PLAN_WXML = ROOT / "miniapp" / "components" / "managed-plan" / "index.wxml"
MANAGED_PLAN_UTIL = ROOT / "miniapp" / "utils" / "managed-plan.ts"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_settings_owns_explicit_managed_plan_lifecycle() -> None:
    """Settings must expose consent, pause/resume, and safe leave choices."""
    source = _source(SETTINGS_TS)
    markup = _source(SETTINGS_WXML)

    assert "managed_plan_preview_start" in source
    assert "mode: 'praxys'" in source
    assert "delivery_enabled: true" in source
    assert "delivery_enabled: false" in source
    assert "mode: 'external'" in source
    assert "'/api/plan/deliveries/cleanup'" in source
    assert "scope: 'future'" in source
    assert "onReviewManagedPlan" in source
    assert "onPauseManagedPlan" in source
    assert "onLeaveManagedPlan" in source
    assert "onRetryPlanCleanup" in source
    assert "beginManagedPlanRequest(this)" in source
    assert "await this.refetchPlan(requestGeneration)" in source

    assert "{{tr.planManagement}}" in markup
    assert 'bindtap="onPickPlanTarget"' in markup
    assert 'bindtap="onReviewManagedPlan"' in markup
    assert 'bindtap="onPauseManagedPlan"' in markup
    assert 'bindtap="onLeaveManagedPlan"' in markup
    assert 'bindtap="onRetryPlanCleanup"' in markup
    assert "planCleanupPartial && planManagementState === 'external'" in markup


def test_training_and_today_share_native_managed_plan_surface() -> None:
    """Both daily-use pages must surface the same ownership semantics."""
    training_markup = _source(TRAINING_WXML)
    today_markup = _source(TODAY_WXML)
    training_components = json.loads(_source(TRAINING_JSON))["usingComponents"]
    today_components = json.loads(_source(TODAY_JSON))["usingComponents"]

    assert training_components["managed-plan"] == "/components/managed-plan/index"
    assert today_components["managed-plan"] == "/components/managed-plan/index"
    assert '<managed-plan id="training-managed-plan" scope="window"' in training_markup
    assert '<managed-plan id="today-managed-plan" scope="today"' in today_markup


def test_managed_plan_actions_use_opaque_identity_and_ownership() -> None:
    """Miniapp actions must preserve the server's ownership-safe contracts."""
    source = _source(MANAGED_PLAN_TS)
    markup = _source(MANAGED_PLAN_WXML)
    helper = _source(MANAGED_PLAN_UTIL)

    assert "'/api/settings'" in source
    assert "'/api/plan/reconciliation/resolve'" in source
    assert "'/api/plan/push-stryd'" in source
    assert "if (!workout.canonical_id)" in source
    assert "canonical_ids: [workout.canonical_id]" in source
    assert "isLatestManagedPlanRequest(this, requestGeneration)" in source
    assert "reconciliation_id" in source
    assert "'restore_praxys'" in source
    assert "'accept_target'" in source
    assert "workout.reconciliation?.id" in source

    assert "workout.owner === 'praxys'" in helper
    assert "workout.owner === undefined && workout.source === 'ai'" in helper
    assert "MANAGED_PLAN_WINDOW_DAYS = 14" in helper

    assert 'bindtap="onWorkoutAction"' in markup
    assert "{{managementAction}}" in markup
    assert "{{tr.externalWorkoutsUntouched}}" in markup
