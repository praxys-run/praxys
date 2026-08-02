"""Regression contracts for miniapp managed-plan parity."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_SETTINGS_TS = (
    ROOT / "web" / "src" / "components" / "ManagedPlanSettingsCard.tsx"
)
WEB_PLAN_UTIL = ROOT / "web" / "src" / "lib" / "plan.ts"
WEB_UPCOMING_TS = (
    ROOT / "web" / "src" / "components" / "UpcomingPlanCard.tsx"
)
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
    web_source = _source(WEB_SETTINGS_TS)
    web_plan_helper = _source(WEB_PLAN_UTIL)
    web_upcoming = _source(WEB_UPCOMING_TS)
    mini_plan_helper = _source(MANAGED_PLAN_UTIL)

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
    assert "adjustment_policy: policy" in source
    assert "onReviewAutomaticAdjustment" in source
    assert "onUndoPlanAdjustment" in source
    assert "/api/plan/adjustments/" in source
    assert "mode === 'adopt'" in source
    assert "response.adjustments !== undefined" in source
    assert "if (!this.data.adjustmentSupported" in source
    assert 'wx:if="{{adjustmentSupported}}"' in markup

    # Initial adoption selects the safe default, while resume omits the field
    # so an existing opt-in survives on both clients.
    assert "...(mode === 'adopt'" in source
    assert "...(confirmMode === 'adopt'" in web_source
    assert "source_options: { athlete_timezone: athleteTimezone }" in source
    assert "source_options: { athlete_timezone: athleteTimezone }" in web_source

    # Logical plan dates follow the athlete's device day rather than UTC.
    assert "value.getFullYear()" in web_plan_helper
    assert "value.getFullYear()" in mini_plan_helper
    assert "athletePlanWindow(days, now)" in web_plan_helper
    assert "athletePlanWindow(days, now)" in mini_plan_helper
    assert "athletePlanWindow(1).start" in web_upcoming
    assert "nextMidnight.setHours(24, 0, 0, 0)" in web_upcoming
    assert "managedPlanPreviewUrl" in source
    assert "managedPlanPreviewUrl" in web_source

    # Older backends omit the additive capability field. Neither client may
    # call the history endpoint or expose controls until it is present.
    assert "if (response.adjustments !== undefined)" in source
    assert "{ enabled: plan?.adjustments !== undefined }" in web_source
    assert "{adjustmentSupported && (" in web_source
    assert "if (apiError.status === 409) await this.refetch()" in source
    assert "if (response.status === 409)" in web_source

    assert "{{tr.planManagement}}" in markup
    assert 'bindtap="onPickPlanTarget"' in markup
    assert 'bindtap="onReviewManagedPlan"' in markup
    assert 'bindtap="onPauseManagedPlan"' in markup
    assert 'bindtap="onLeaveManagedPlan"' in markup
    assert 'bindtap="onRetryPlanCleanup"' in markup
    assert "planCleanupPartial && planManagementState === 'external'" in markup
    assert 'bindtap="onReviewAutomaticAdjustment"' in markup
    assert 'bindtap="onUndoPlanAdjustment"' in markup


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
    assert "onUndoAdjustment" in source
    assert "/api/plan/adjustments/" in source
    assert "scheduleMidnightRefresh" in source
    assert "nextMidnight.setHours(24, 0, 0, 0)" in source
    assert "clearMidnightRefresh" in source
    assert "if (apiError.status === 409) await this.refresh()" in source
    assert "if (response.status === 409) await refetch()" in _source(
        WEB_UPCOMING_TS
    )

    assert "workout.owner === 'praxys'" in helper
    assert "workout.owner === undefined && workout.source === 'ai'" in helper
    assert "MANAGED_PLAN_WINDOW_DAYS = 14" in helper

    assert 'bindtap="onWorkoutAction"' in markup
    assert "{{managementAction}}" in markup
    assert "{{tr.externalWorkoutsUntouched}}" in markup
    assert 'bindtap="onUndoAdjustment"' in markup
