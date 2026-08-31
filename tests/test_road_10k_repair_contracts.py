"""Source contracts for the bounded Road repair."""
from pathlib import Path

from scripts.check_ui_quality import detector_targets, rendered_surface


ROOT = Path(__file__).resolve().parent.parent


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_marker_docs_state_actual_unscheduled_lifecycle() -> None:
    runbook = _source("docs/ops/road-10k-controlled-opt-in.md")
    restore = _source("docs/ops/backup-and-restore.md")
    config = _source("docs/ops/config-and-secrets.md")
    combined = "\n".join((runbook, restore, config))

    assert "14-day marker cleanup horizon" not in combined
    assert "payload-free" in combined
    assert "enumeration-based cleanup is not scheduled" in combined
    assert "prepared markers are not age-retired" in combined
    assert "release-only" in combined
    assert "private-store cleanup proof" in combined


def test_native_road_targets_are_at_least_88_rpx_and_scss_is_detected() -> None:
    styles = _source("miniapp/components/outdoor-5k-plan-start/index.scss")
    assert "min-height: 88rpx" in styles
    assert "min-width: 88rpx" in styles or "width: 88rpx" in styles

    input_rule = styles.split(".plan-start-input {", 1)[1].split("}", 1)[0]
    assert "min-height: 88rpx" in input_rule

    path = "miniapp/components/outdoor-5k-plan-start/index.scss"
    assert rendered_surface(path) == "miniapp"
    assert detector_targets([path]) == [path]
