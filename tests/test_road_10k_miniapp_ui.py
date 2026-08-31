"""Native hard-off UI contracts for the dormant Road 10K foundation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_road_10k_has_no_mounted_native_opt_in_surface() -> None:
    assert not (ROOT / "miniapp/components/road-10k-controlled-opt-in").exists()
    for page in ("goal", "training", "settings"):
        assert "road-10k-controlled-opt-in" not in _source(
            f"miniapp/pages/{page}/index.wxml"
        )
        assert "road-10k-controlled-opt-in" not in _source(
            f"miniapp/pages/{page}/index.json"
        )


def test_native_plan_start_rejects_dormant_road_discovery() -> None:
    source = _source("miniapp/utils/plan-start-routing.ts")
    declaration = source.split(
        "SUPPORTED_PLAN_START_CAPABILITY_CONTRACTS", 1
    )[1].split("};", 1)[0]
    assert "outdoor_road_5k_v1" in declaration
    assert "outdoor_road_5k_constraints_v1" in declaration
    assert "outdoor_road_10k_performance_v1" not in declaration
    assert "outdoor_road_10k_constraints_v1" not in declaration


def test_native_goal_does_not_promote_stale_road_discovery() -> None:
    source = _source("miniapp/pages/goal/index.ts")
    declaration = _source("miniapp/utils/plan-start-routing.ts")
    assert "outdoor_road_5k_v1" in declaration
    assert "outdoor_road_5k_constraints_v1" in declaration
    assert "outdoor_road_10k_performance_v1" not in declaration
    assert "outdoor_road_10k_constraints_v1" not in declaration
    assert "hasSupportedPlanStartContract" in source
    assert "performance10kEnabled: false" in source
    assert (
        "performance10kEnabled: supportedCapabilityIds.includes"
        not in source
    )
