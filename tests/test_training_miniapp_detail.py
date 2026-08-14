"""Regression coverage for Analysis metric-sheet selection races."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_PAGE = ROOT / "miniapp" / "pages" / "analysis" / "index.ts"


def test_metric_sheet_selection_survives_concurrent_refetch() -> None:
    """Open and close intents must override stale rendered page data."""
    source = ANALYSIS_PAGE.read_text(encoding="utf-8")

    assert "pageState._activeMetric = metric;" in source
    assert "pageState._activeMetric = '';" in source
    assert "if (pending === '') return '';" in source
    assert "const activeMetric = readActiveMetric(pageState, this.data.activeMetric);" in source
    assert "buildState(" in source
    assert "activeMetric," in source
