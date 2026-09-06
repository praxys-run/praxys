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


def test_reports_untranslated_english_and_unlisted_latin_in_cjk_source():
    source = [
        _entry("Continue", "Continue"),
        _entry("Praxys", "Praxys"),
        _entry("Praxys 尚未连接 Garmin。", "Praxys 尚未连接 Garmin。"),
    ]
    target = [
        _entry("Continue", "Continue"),
        _entry("Praxys", "Praxys"),
        _entry("Praxys 尚未连接 Garmin。", "Praxys 尚未连接 Garmin。"),
    ]
    findings = check_catalog(source, target, CONFIG)
    assert [(finding.code, finding.msgid) for finding in findings] == [
        ("untranslated", "Continue"),
        ("untranslated", "Praxys 尚未连接 Garmin。"),
    ]


@pytest.mark.parametrize(
    "msgid",
    [
        "请继续",
        "Praxys 请继续",
        "未启用的越野 API 使用 v2。",
        "未启用的越野API使用v2。",
        "（Praxys）/ API-v2：共 2026 次，50%。",
        "请继续 {name} {0} {_count42}",
        "请 ''{name}''",
        "请 '{Praxys}'",
        "请 '{' {name} '}'",
        "请等待 {count, number} 分钟",
        "请核对 {date, date, short}",
        "共 {count, plural, one {一项} other {多项}}",
        "共 {count, plural, offset:1 =0 {无} other {{count, number} 项}}",
        "共 {count, plural, one {'{'} other {多项}}",
        "共 {count, plural, one {'}'} other {多项}}",
        "{mode, select, ready {请继续} other {请等待}}",
        "第 {count, selectordinal, one {# 项} other {# 项}}",
        "请<0>继续</0><1/>",
        '请 <strong class="label">继续</strong>',
        "请访问 https://example.test/help?version=v3。然后继续。",
        "请访问 https://example.test/帮助?locale=en。",
        "请访问 www.example.test/help",
        "请联系 runner+export@example.test。",
    ],
)
def test_cjk_identity_allows_only_closed_tokens_and_recognized_syntax(msgid):
    entry = _entry(msgid, msgid)
    assert check_catalog([entry], [entry], CONFIG) == []


@pytest.mark.parametrize(
    "msgid",
    [
        "请 click Continue",
        "请 a",
        "请 X",
        "请 Garmin",
        "请 HRV",
        "请 Trail",
        "请 praxys",
        "请 PRAXYS",
        "请 api",
        "请 Api",
        "请 V2",
        "请 xPraxys",
        "请 Praxyss",
        "请 APIv2",
        "请 API2",
        "请 v20",
        "请 2Praxys",
        "请 _API",
        "请 API_",
        "请 Praxys_API",
        "请 click https://example.test/help",
        "请 https://example.test/help click",
        "请 click runner@example.test",
        "请 x www.example.test/help",
        "请 x.test",
        "请 A@B",
        "请 {name} x",
        "请 '{Garmin}'",
        "请 '''{Garmin}'''",
        "请 '{count, number}'",
        "请 '{Garmin} {name}'",
        "请 <strong>click</strong>",
        "请 {not a placeholder}",
        "请 {unterminated",
        "请 Prax{name}ys",
        "请 Prax<0/>ys",
        "请 <strong class=\"label\" click",
        "请 https://example.test/帮助 click",
        "共 {count, plural, one {item} other {多项}}",
        "共 {count, plural, one {'{Garmin}'} other {多项}}",
        "共 {count, plural, other {{mode, select, ready {'{Garmin}'} other {请等待}}}}",
        "{mode, select, ready {x} other {请等待}}",
        "共 {count, plural, other {{mode, select, ready {click} other {请等待}}}}",
        "共 {count, plural, one {一项}}",
        "请 {count, not_a_format}",
    ],
)
def test_cjk_identity_rejects_any_remaining_ascii_letter(msgid):
    entry = _entry(msgid, msgid)
    findings = check_catalog([entry], [entry], CONFIG)
    assert [(finding.code, finding.msgid) for finding in findings] == [
        ("untranslated", msgid)
    ]


def test_cjk_identity_cannot_bypass_closed_tokens_with_general_allowlist():
    msgid = "请 Garmin"
    config = {
        **CONFIG,
        "style": {**CONFIG["style"], "allowed_same_as_source": [msgid]},
    }
    entry = _entry(msgid, msgid)
    assert [finding.code for finding in check_catalog([entry], [entry], config)] == [
        "untranslated"
    ]


def test_cjk_source_identity_still_fails_other_quality_rules():
    msgid = "Praxys 请您重试"
    findings = check_catalog(
        [_entry(msgid, msgid)],
        [_entry(msgid, msgid)],
        CONFIG,
    )
    assert [(finding.code, finding.msgid) for finding in findings] == [
        ("forbidden-term", msgid)
    ]


def test_cjk_identity_preserves_canonical_typography_semantic_fuzzy_and_review_rules():
    msgid = "Praxys 请您重试..."
    config = {
        **CONFIG,
        "style": {
            **CONFIG["style"],
            "exact_translations": [{"source": msgid, "target": "Praxys 请重试…"}],
        },
        "semantic_rules": [{
            "id": "retry",
            "source_equals": msgid,
            "required_target_terms": ["请重试"],
            "human_review_category": "privacy",
        }],
    }
    entry = {**_entry(msgid, msgid), "prefix_lines": ["#, fuzzy"]}
    assert {finding.code for finding in check_catalog([entry], [entry], config)} == {
        "forbidden-term", "canonical", "typography", "semantic-term", "fuzzy",
    }
    assert human_review_reasons(entry, config) == ["privacy:retry"]


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
