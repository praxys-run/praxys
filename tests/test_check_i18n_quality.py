"""Tests for the deterministic Simplified Chinese catalog quality gate."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_i18n_quality import check_catalog, load_quality_config  # noqa: E402
from translate_missing import parse_po  # noqa: E402


def _entry(msgid: str, msgstr: str) -> dict:
    return {"prefix_lines": [], "msgid": msgid, "msgstr": msgstr}


CONFIG = {
    "style": {
        "forbidden_target": [{"term": "您", "prefer": "省略或用“你”"}],
        "exact_translations": [
            {"source": "Follow Plan", "target": "按计划训练"},
        ],
        "allowed_same_as_source": ["Praxys"],
    },
    "terms": [
        {"en": "HRV", "zh": "HRV"},
    ],
}


def test_native_catalog_passes():
    source = [
        _entry("Follow Plan", "Follow Plan"),
        _entry("Praxys", "Praxys"),
        _entry("HRV trend", "HRV trend"),
        _entry("Hello {name}", "Hello {name}"),
    ]
    target = [
        _entry("Follow Plan", "按计划训练"),
        _entry("Praxys", "Praxys"),
        _entry("HRV trend", "HRV 趋势"),
        _entry("Hello {name}", "{name}，你好"),
    ]
    assert check_catalog(source, target, CONFIG) == []


def test_reports_coverage_structure_tone_and_typography():
    source = [
        _entry("Follow Plan", "Follow Plan"),
        _entry("Hello {name}", "Hello {name}"),
        _entry("Compare", "Compare"),
        _entry("Missing", "Missing"),
    ]
    target = [
        _entry("Follow Plan", "按计划进行"),
        _entry("Hello {name}", "您好"),
        _entry("Compare", "实际 vs 计划 — 查看详情..."),
        _entry("Orphan", "多余"),
    ]
    codes = {
        finding.code for finding in check_catalog(source, target, CONFIG)
    }
    assert {
        "missing-entry",
        "orphan-entry",
        "canonical",
        "structure",
        "forbidden-term",
        "typography",
    } <= codes


def test_reports_untranslated_copy_but_allows_brand():
    source = [_entry("Continue", "Continue"), _entry("Praxys", "Praxys")]
    target = [_entry("Continue", "Continue"), _entry("Praxys", "Praxys")]
    findings = check_catalog(source, target, CONFIG)
    assert [(finding.code, finding.msgid) for finding in findings] == [
        ("untranslated", "Continue")
    ]


def test_reports_dropped_protected_token():
    source = [_entry("HRV trend", "HRV trend")]
    target = [_entry("HRV trend", "恢复趋势")]
    findings = check_catalog(source, target, CONFIG)
    assert any(finding.code == "protected-token" for finding in findings)


def test_repository_catalog_passes_quality_gate():
    source, _ = parse_po(ROOT / "web" / "src" / "locales" / "en" / "messages.po")
    target, _ = parse_po(ROOT / "web" / "src" / "locales" / "zh" / "messages.po")
    config = load_quality_config(ROOT / "scripts" / "i18n_glossary.yaml")
    findings = check_catalog(source, target, config)
    assert findings == []
