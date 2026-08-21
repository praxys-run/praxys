"""Native UI contracts for the Road 10K controlled opt-in journey."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")


def test_road_10k_sheet_uses_skyline_safe_bottom_positioning() -> None:
    """The enrollment sheet stays full-width and above the custom tab bar."""
    styles = _source(
        "miniapp/components/road-10k-controlled-opt-in/index.scss"
    )

    assert "flex-direction: column;" in styles
    assert "justify-content: flex-end;" in styles
    assert "z-index: 240;" in styles
    assert "margin-bottom: calc(110rpx + env(safe-area-inset-bottom));" in styles
    assert "inset: 0;" not in styles


def test_road_10k_copy_wraps_between_english_words_with_stable_selectors() -> None:
    """English notice copy and automation selectors remain native-safe."""
    component = _source(
        "miniapp/components/road-10k-controlled-opt-in/index.wxml"
    )
    script = _source(
        "miniapp/components/road-10k-controlled-opt-in/index.ts"
    )
    styles = _source(
        "miniapp/components/road-10k-controlled-opt-in/index.scss"
    )
    goal = _source("miniapp/pages/goal/index.wxml")
    settings = _source("miniapp/pages/settings/index.wxml")
    training = _source("miniapp/pages/training/index.wxml")

    assert "function wordList(value: string): string[]" in script
    assert '<template name="road-10k-body">' in component
    assert 'wx:for="{{words}}"' in component
    assert 'class="road-10k-word"' in component
    assert ".road-10k-word {" in styles
    assert "display: inline-block;" in styles
    assert 'id="goal-road-10k"' in goal
    assert 'id="settings-road-10k"' in settings
    assert 'id="training-road-10k"' in training
