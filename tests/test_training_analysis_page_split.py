"""UI contracts for the managed Training and Analysis page split."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")


def test_web_separates_plan_management_from_analysis() -> None:
    """Training owns plans while Analysis owns observed-training interpretation."""
    training = _source("web/src/pages/Training.tsx")
    analysis = _source("web/src/pages/Analysis.tsx")
    app = _source("web/src/App.tsx")
    sidebar = _source("web/src/components/AppSidebar.tsx")

    for component in (
        "Outdoor5KPlanStart",
        "UpcomingPlanCard",
        "PersonalContextPanel",
    ):
        assert component in training
        assert component not in analysis

    assert "useApi<TrainingResponse>('/api/training')" not in training
    assert "PeerMetricList" not in training
    assert "AiInsightsCard" not in training
    assert "useApi<TrainingResponse>('/api/training')" in analysis
    assert "PeerMetricList" in analysis
    assert "AiInsightsCard" in analysis
    assert "location.hash === '#heat-adaptation'" in training
    assert '<Navigate to="/analysis#heat-adaptation" replace />' in training

    assert 'path="training"' in app
    assert 'path="analysis"' in app
    assert "{ to: '/training'" in sidebar
    assert "{ to: '/analysis'" in sidebar


def test_miniapp_uses_analysis_and_me_as_primary_tabs() -> None:
    """The five-tab miniapp exposes observed training and secondary tools."""
    training = _source("miniapp/pages/training/index.wxml")
    training_script = _source("miniapp/pages/training/index.ts")
    analysis = _source("miniapp/pages/analysis/index.wxml")
    analysis_script = _source("miniapp/pages/analysis/index.ts")
    me = _source("miniapp/pages/me/index.wxml")
    settings = _source("miniapp/pages/settings/index.wxml")
    settings_script = _source("miniapp/pages/settings/index.ts")
    managed_plan = _source("miniapp/components/managed-plan/index.ts")
    custom_tabbar = _source("miniapp/custom-tab-bar/index.ts")
    localized_tabbar = _source("miniapp/utils/tabbar.ts")
    app = json.loads(_source("miniapp/app.json"))

    assert [item["pagePath"] for item in app["tabBar"]["list"]] == [
        "pages/today/index",
        "pages/training/index",
        "pages/analysis/index",
        "pages/goal/index",
        "pages/me/index",
    ]
    assert [item["text"] for item in app["tabBar"]["list"]] == [
        "Today",
        "Training",
        "Analysis",
        "Goal",
        "Me",
    ]
    for source in (custom_tabbar, localized_tabbar):
        assert "pages/analysis/index" in source
        assert "text: t('Analysis')" in source
        assert "kind: 'analysis'" in source
        assert "pages/me/index" in source
        assert "text: t('Me')" in source
        assert "kind: 'me'" in source
        assert "pages/history/index" not in source

    assert '<outdoor-5k-plan-start />' in training
    assert '<managed-plan id="training-managed-plan" scope="window" />' in training
    assert '<personal-context id="training-personal-context" />' in training
    assert "train-metric-row" not in training
    assert "onOpenAnalysis" not in training
    assert "options.metric === 'heat'" in training_script
    assert "HEAT_HISTORY_SCROLL_KEY" in training_script
    assert "wx.switchTab({" in training_script
    assert "url: '/pages/analysis/index'" in training_script

    assert "train-metric-row" in analysis
    assert "coach-receipt" in analysis
    assert "<managed-plan" not in analysis
    assert "<personal-context" not in analysis
    assert "<observed-training-switch" in analysis
    assert "<activity-history" in analysis
    assert "setTabBarSelected(this, 2)" in analysis_script
    assert "consumeHeatHistoryScrollRequest()" in analysis_script
    assert "activeMetric: 'heat'" in analysis_script

    assert 'bindtap="onOpenSettings"' in me
    assert 'bindtap="onOpenScience"' in me
    assert 'bindtap="onOpenLabs"' in me
    assert 'bindtap="onOpenLegal"' in me
    assert "show-back=\"{{true}}\"" in settings
    assert "onNavigateToScience" not in settings
    assert "onNavigateToLabs" not in settings
    assert "wx.reLaunch({ url: '/pages/me/index' })" in settings_script
    assert "wx.navigateTo({ url: '/pages/settings/index' })" in managed_plan


def test_legacy_activity_page_reuses_analysis_history() -> None:
    """Old Activities deep links retain the shared history implementation."""
    history = _source("miniapp/pages/history/index.wxml")
    history_script = _source("miniapp/pages/history/index.ts")

    assert '<activity-history' in history
    assert 'id="legacy-activity-history"' in history
    assert 'show-back="{{true}}"' in history
    assert "wx.switchTab({ url: '/pages/analysis/index' })" in history_script


def test_goal_keeps_secondary_plan_entry() -> None:
    """Goal remains independent while retaining its supported plan-start handoff."""
    goal = _source("web/src/pages/Goal.tsx")
    mini_goal = _source("miniapp/pages/goal/index.ts")

    assert "Outdoor5KGoalEntry" in goal
    assert "navigate('/training#outdoor-5k-plan')" in _source(
        "web/src/components/Outdoor5KPlanStart.tsx"
    )
    assert "wx.switchTab({ url: '/pages/training/index' })" in mini_goal
