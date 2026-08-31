"""Tests for the deterministic Simplified Chinese catalog quality gate."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_i18n_quality import check_catalog, load_quality_config  # noqa: E402
from i18n_semantics import (  # noqa: E402
    check_semantic_rules,
    human_review_reasons,
    is_fuzzy,
    validate_semantic_rules,
)
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
    "semantic_rules": [],
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


def test_semantic_rule_supports_path_scope_and_multiple_source_refs():
    config = {
        "semantic_rules": [
            {
                "id": "training-base",
                "source_contains": "training base",
                "source_paths": ["src/pages/**"],
                "required_target_terms": ["训练基准"],
                "forbidden_target_terms": ["训练依据"],
            }
        ]
    }
    matching = {
        "prefix_lines": [
            "#: src/components/Setup.tsx:1 src/pages/Setup.tsx:2",
        ],
        "msgid": "Choose training base",
        "msgstr": "选择训练依据",
    }
    findings = check_semantic_rules(matching, config)
    assert {finding.message for finding in findings} == {
        "required target term '训练基准' is missing",
        "forbidden target term '训练依据' is present",
    }

    outside_scope = {**matching, "prefix_lines": ["#: src/components/Setup.tsx:1"]}
    assert check_semantic_rules(outside_scope, config) == []


def test_source_equals_is_case_insensitive_but_not_a_substring():
    config = {
        "semantic_rules": [
            {
                "id": "peer-metrics",
                "source_equals": "Peer metrics",
                "required_target_terms": ["训练指标"],
            }
        ]
    }
    exact = _entry("peer METRICS", "对比指标")
    assert check_semantic_rules(exact, config)
    assert check_semantic_rules(_entry("Open peer metrics", "查看训练指标"), config) == []


def test_sensitive_match_routes_human_review_without_becoming_approval():
    config = {
        "semantic_rules": [
            {
                "id": "symptom-stop",
                "source_contains": "symptom stop",
                "required_target_terms": ["症状停止"],
                "human_review_category": "safety",
            }
        ]
    }
    entry = _entry("Symptom stop", "症状停止")
    assert check_semantic_rules(entry, config) == []
    assert human_review_reasons(entry, config) == ["safety:symptom-stop"]
    assert human_review_reasons(_entry("Other", "其他"), config) == []


@pytest.mark.parametrize(
    "rules, message",
    [
        ({}, "exactly one"),
        ({"source_equals": "A", "source_contains": "A"}, "exactly one"),
        ({"source_equals": "A", "unknown": []}, "unknown fields"),
    ],
)
def test_invalid_semantic_rule_schema_fails_closed(rules, message):
    rule = {"id": "bad", "human_review_category": "safety", **rules}
    with pytest.raises(ValueError, match=message):
        validate_semantic_rules({"semantic_rules": [rule]})


def test_check_catalog_also_fails_closed_on_invalid_semantic_policy():
    invalid = {**CONFIG, "semantic_rules": [{"id": "bad"}]}
    with pytest.raises(ValueError, match="exactly one"):
        check_catalog([_entry("Hello", "Hello")], [_entry("Hello", "你好")], invalid)


def test_fuzzy_translation_is_blocking_even_with_nonempty_msgstr():
    entry = {
        "prefix_lines": ["#, fuzzy"],
        "msgid": "Changed source",
        "msgstr": "旧译文",
    }
    assert is_fuzzy(entry)
    findings = check_catalog([_entry("Changed source", "Changed source")], [entry], CONFIG)
    assert any(finding.code == "fuzzy" for finding in findings)


def test_source_path_scope_cannot_escape_source_root(tmp_path, monkeypatch):
    import check_i18n_quality as quality

    source = tmp_path / "en.po"
    target = tmp_path / "zh.po"
    glossary = tmp_path / "glossary.yaml"
    source.write_text('msgid "Hello"\nmsgstr "Hello"\n', encoding="utf-8")
    target.write_text(
        '#: ../secret.ts:1\nmsgid "Hello"\nmsgstr "你好"\n',
        encoding="utf-8",
    )
    glossary.write_text("semantic_rules: []\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_i18n_quality.py",
            "--source", str(source),
            "--target", str(target),
            "--glossary", str(glossary),
            "--source-root", str(tmp_path / "web"),
        ],
    )
    with pytest.raises(ValueError, match="escapes source root"):
        quality.main()
