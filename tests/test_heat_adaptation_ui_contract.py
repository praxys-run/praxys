"""Regression contracts for heat-adaptation placement and disclosure."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_TODAY = ROOT / "web" / "src" / "pages" / "Today.tsx"
WEB_TRAINING = ROOT / "web" / "src" / "pages" / "Training.tsx"
WEB_HEAT = ROOT / "web" / "src" / "components" / "HeatAdaptationPanel.tsx"
MINI_TODAY = ROOT / "miniapp" / "pages" / "today" / "index.wxml"
MINI_TODAY_TS = ROOT / "miniapp" / "pages" / "today" / "index.ts"
MINI_TRAINING = ROOT / "miniapp" / "pages" / "training" / "index.wxml"
MINI_TRAINING_TS = ROOT / "miniapp" / "pages" / "training" / "index.ts"
MINI_HEAT = ROOT / "miniapp" / "utils" / "heat-adaptation.ts"
WEB_SCIENCE = ROOT / "web" / "src" / "pages" / "Science.tsx"
MINI_SCIENCE = ROOT / "miniapp" / "pages" / "science" / "index.wxml"
MINI_SCIENCE_TS = ROOT / "miniapp" / "pages" / "science" / "index.ts"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_today_does_not_imply_current_weather_is_available() -> None:
    """Heat stays off Today until a real current-weather input exists."""
    web_today = _source(WEB_TODAY)
    web_heat = _source(WEB_HEAT)
    mini_today = _source(MINI_TODAY)
    mini_today_ts = _source(MINI_TODAY_TS)

    assert "data.heat_adaptation.today_restricted" not in web_today
    assert "TodayHeatConstraint" not in web_today
    assert "<HeatAdaptationPanel" not in web_today
    assert "TodayHeatConstraint" not in web_heat

    assert "today-heat" not in mini_today
    assert "HEAT_HISTORY_SCROLL_KEY" not in mini_today_ts
    assert "buildHeatAdaptationView" not in mini_today_ts


def test_training_owns_the_longitudinal_heat_story() -> None:
    """Training should present heat history before charts with evidence on demand."""
    web_training = _source(WEB_TRAINING)
    web_heat = _source(WEB_HEAT)
    mini_training = _source(MINI_TRAINING)
    mini_training_ts = _source(MINI_TRAINING_TS)
    mini_today_ts = _source(MINI_TODAY_TS)
    mini_heat = _source(MINI_HEAT)

    heat_panel = "<HeatAdaptationPanel"
    assert heat_panel in web_training
    assert web_training.index(heat_panel) < web_training.index("<DiagnosisChartSwitcher")
    assert "id: 'heat'" not in web_training
    assert "location.hash !== '#heat-adaptation'" in web_training
    assert "scrollIntoView({ block: 'start' })" in web_training
    assert "Recent qualifying training range" in web_heat
    assert "How this estimate was built" in web_heat
    assert 'to="/science#heat"' in web_heat
    assert "<EvidenceProgress" not in web_heat
    assert "<ScienceNote embedded>" in web_heat
    assert "<HeatCadence status={status} />" in web_heat
    assert "(status.cadence ?? []).flatMap" in web_heat
    assert "sessionMap" not in web_heat
    assert "<HeatEvidenceLedger status={status} />" in web_heat

    heat_section = 'id="heat-adaptation" class="train-heat-section"'
    assert heat_section in mini_training
    assert mini_training.index(heat_section) < mini_training.index('class="train-pills"')
    assert '<block wx:if="{{hasAnyData}}">' not in mini_training[:mini_training.index(heat_section)]
    assert 'data-pill="heat"' not in mini_training
    assert 'bindtap="onToggleHeatEvidence"' in mini_training
    assert 'bindtap="onToggleHeatMethodology"' not in mini_training
    assert "{{heat.conditionRange}}" in mini_training
    assert "{{heat.evidenceDisclosureLabel}}" in mini_training
    assert 'wx:if="{{heat.showCadence}}"' in mini_training
    assert "(status.cadence ?? []).flatMap" in mini_heat
    assert "const byDate" not in mini_heat
    assert "scrollToHeatIfPending" in mini_training_ts


def test_science_shows_heat_as_active_fixed_model() -> None:
    """Heat methodology is visible without presenting a fake switch."""
    web_science = _source(WEB_SCIENCE)
    mini_science = _source(MINI_SCIENCE)
    mini_science_ts = _source(MINI_SCIENCE_TS)

    assert "key: 'heat'" in web_science
    assert "fixed_pillars.includes(focused)" in web_science
    assert "Active fixed model" in web_science
    assert "key: 'heat'" in mini_science_ts or "'heat'" in mini_science_ts
    assert "isFixed" in mini_science_ts
    assert "{{tr.fixedModelTag}}" in mini_science


def test_evidence_details_are_localizable_and_explain_mixed_providers() -> None:
    """Evidence detail values should not leak raw API tokens or wrong reasons."""
    web_heat = _source(WEB_HEAT)
    mini_heat = _source(MINI_HEAT)
    mixed_reason = (
        "Observed, but not included because workload evidence mixed power providers."
    )

    assert mixed_reason in web_heat
    assert mixed_reason in mini_heat
    assert "powerAlignmentLabel(session.power_source_alignment)" in web_heat
    assert "{session.power_source_alignment}" not in web_heat
    assert "effectiveMinutesLabel(" in web_heat
    assert "formatRange(conditions.relative_humidity_pct.min" in web_heat
