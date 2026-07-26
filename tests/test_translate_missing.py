"""Unit tests for scripts/translate_missing.py placeholder validator + glossary."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from translate_missing import (  # noqa: E402
    _extract_context,
    _group_by_screen,
    _icu_variable_names,
    _json_decisions_by_id,
    _json_text_by_id,
    _json_revisions_by_id,
    _placeholders,
    _placeholders_match,
    _read_source_excerpt,
    _review_candidates,
    build_system_prompt,
    main as translate_cli_main,
    review_translations,
    translate_batch,
)


class TestICUVariableNames:
    def test_simple(self):
        assert _icu_variable_names("hello {name}") == ["name"]

    def test_multiple(self):
        assert _icu_variable_names("{a}, {b}, {c}") == ["a", "b", "c"]

    def test_plural_outer_only(self):
        # Nested braces in plural branches don't count as separate vars
        assert _icu_variable_names(
            "{count, plural, one {# item} other {# items}}"
        ) == ["count"]

    def test_collapsed_plural(self):
        # Chinese shape — still just one outer variable named `count`
        assert _icu_variable_names("{count, plural, other {# 项}}") == ["count"]

    def test_numeric_placeholder(self):
        assert _icu_variable_names("got {0} of {1}") == ["0", "1"]

    def test_no_braces(self):
        assert _icu_variable_names("no placeholders here") == []


class TestPlaceholdersMatch:
    def test_identical(self):
        assert _placeholders_match("hello {name}", "hello {name}")

    def test_translated_ok(self):
        # Content between placeholders can change; vars must match
        assert _placeholders_match("hello {name}", "ni hao {name}")

    def test_dropped_placeholder_rejects(self):
        assert not _placeholders_match("hello {name}", "ni hao")

    def test_renamed_placeholder_rejects(self):
        # {x} → {y} is a real bug; the caller's format() would KeyError
        assert not _placeholders_match("a {x}", "a {y}")

    def test_duplicate_placeholder_rejects(self):
        assert not _placeholders_match("{a}, {b}", "{a}, {b}, {b}")

    def test_reordered_placeholders_ok(self):
        # Order changes are fine — the sorted comparison treats them equal
        assert _placeholders_match("{a}, {b}, {c}", "{c} {b} {a}")

    def test_plural_branches_differ_ok(self):
        # The whole reason we compare variable names, not full tokens:
        # zh legitimately collapses one+other branches to other only.
        assert _placeholders_match(
            "{count, plural, one {# item} other {# items}}",
            "{count, plural, other {# 项}}",
        )

    def test_plural_variable_rename_rejects(self):
        assert not _placeholders_match(
            "{count, plural, other {# item}}",
            "{total, plural, other {# item}}",
        )

    def test_line_breaks_must_match(self):
        assert _placeholders_match("Subject\nBody", "主题\n正文")
        assert not _placeholders_match("Subject\nBody", "主题 正文")


class TestXMLTags:
    def test_open_close(self):
        assert _placeholders_match("<0>{name}</0>", "<0>{name}</0>")

    def test_reordered_rejects(self):
        # <0> and <1> point to distinct React children — swapping breaks
        assert not _placeholders_match("<0>x</0>", "<1>y</1>")

    def test_dropped_rejects(self):
        assert not _placeholders_match("<0>x</0>", "x")

    def test_self_closing(self):
        s = "click <0/> to retry"
        assert _placeholders(s)["xml"] == ["<0/>"]

    def test_crossed_tags_reject(self):
        assert not _placeholders_match(
            "<0>{x}</0><1>{y}</1>",
            "<0>{x}</1><1>{y}</0>",
        )

    def test_well_formed_components_can_reorder(self):
        assert _placeholders_match(
            "<0>{x}</0><1>{y}</1>",
            "<1>{y}</1><0>{x}</0>",
        )


class TestGlossaryInjection:
    def test_prompt_includes_canonical_terms(self):
        prompt = build_system_prompt()
        # Core domain terms must be pinned
        assert "HRV" in prompt
        assert "恢复" in prompt  # Recovery → 恢复 (zone + status)
        assert "阈值功率" in prompt  # Critical Power
        assert "乳酸阈" in prompt  # Threshold (zone) — matches both 乳酸阈 and 乳酸阈值心率
        assert "马拉松" in prompt  # Marathon

    def test_prompt_warns_about_placeholders(self):
        prompt = build_system_prompt()
        # The CI bot must be explicitly told to preserve placeholders
        assert "placeholder" in prompt.lower() or "VERBATIM" in prompt

    def test_prompt_requires_native_product_chinese(self):
        prompt = build_system_prompt()
        assert "native Mainland Simplified Chinese" in prompt
        assert "不用过度正式的“您”" in prompt


class TestPromptFallbacksGracefully:
    def test_missing_glossary_still_returns_base_prompt(self, tmp_path, monkeypatch):
        """If someone deletes scripts/i18n_glossary.yaml the translator
        still produces a usable prompt — the glossary is best-effort."""
        import translate_missing as tm

        # Monkeypatch the resolved glossary path to something that doesn't exist
        original_file = tm.__file__
        fake_file = str(tmp_path / "translate_missing.py")
        monkeypatch.setattr(tm, "__file__", fake_file)
        try:
            prompt = tm.build_system_prompt()
            # Base rules are still present
            assert "VERBATIM" in prompt
            assert "Praxys" in prompt
        finally:
            monkeypatch.setattr(tm, "__file__", original_file)


class TestPageContext:
    def test_source_refs_are_split_for_shared_strings(self):
        sources, comments = _extract_context([
            "#. button label",
            "#: src/pages/Goal.tsx:10 src/pages/Today.tsx:20",
        ])
        assert sources == ["src/pages/Goal.tsx:10", "src/pages/Today.tsx:20"]
        assert comments == ["button label"]

    def test_source_excerpt_includes_neighboring_copy(self, tmp_path):
        source = tmp_path / "src" / "pages" / "Goal.tsx"
        source.parent.mkdir(parents=True)
        source.write_text(
            "\n".join([
                "const heading = t`Race goal`;",
                "const helper = t`Choose your target race.`;",
                "const action = t`Save goal`;",
            ]),
            encoding="utf-8",
        )
        entry = {
            "prefix_lines": ["#: src/pages/Goal.tsx:2"],
            "msgid": "Choose your target race.",
            "msgstr": "选择目标比赛。",
        }
        excerpt = _read_source_excerpt(entry, tmp_path, radius=1)
        assert "Race goal" in excerpt
        assert "Choose your target race" in excerpt
        assert "Save goal" in excerpt

    def test_entries_are_grouped_by_primary_screen(self):
        entries = [
            {"prefix_lines": ["#: src/A.tsx:1"], "msgid": "A1", "msgstr": "甲"},
            {"prefix_lines": ["#: src/B.tsx:1"], "msgid": "B1", "msgstr": "乙"},
            {"prefix_lines": ["#: src/A.tsx:2"], "msgid": "A2", "msgstr": "丙"},
        ]
        groups = _group_by_screen(entries)
        assert [[entry["msgid"] for entry in group] for group in groups] == [
            ["A1", "A2"],
            ["B1"],
        ]


class TestReviewSelection:
    def test_selection_is_stable_and_capped(self):
        entries = [
            {
                "prefix_lines": [f"#: src/Page.tsx:{index}"],
                "msgid": f"String {index}",
                "msgstr": f"文案 {index}",
            }
            for index in range(20)
        ]
        first, capped = _review_candidates(
            entries,
            review_shards=1,
            review_shard=0,
            max_reviews=5,
        )
        second, _ = _review_candidates(
            list(reversed(entries)),
            review_shards=1,
            review_shard=0,
            max_reviews=5,
        )
        assert [entry["msgid"] for entry in first] == [
            entry["msgid"] for entry in second
        ]
        assert capped == 15

    def test_selection_can_be_limited_to_new_msgids(self):
        entries = [
            {
                "prefix_lines": ["#: src/Page.tsx:1"],
                "msgid": "Existing",
                "msgstr": "已有",
            },
            {
                "prefix_lines": ["#: src/Page.tsx:2"],
                "msgid": "New",
                "msgstr": "新增",
            },
        ]
        selected, capped = _review_candidates(
            entries,
            review_shards=1,
            review_shard=0,
            max_reviews=0,
            include_msgids={"New"},
        )
        assert [entry["msgid"] for entry in selected] == ["New"]
        assert capped == 0

    def test_capped_selection_rotates_through_shard_tail(self):
        entries = [
            {
                "prefix_lines": ["#: src/Page.tsx:1"],
                "msgid": f"String {index:02d}",
                "msgstr": f"文案 {index:02d}",
            }
            for index in range(7)
        ]
        first, _ = _review_candidates(
            entries,
            review_shards=1,
            review_shard=0,
            max_reviews=3,
            review_cycle=0,
        )
        second, _ = _review_candidates(
            entries,
            review_shards=1,
            review_shard=0,
            max_reviews=3,
            review_cycle=1,
        )
        assert [entry["msgid"] for entry in first] == [
            "String 00",
            "String 01",
            "String 02",
        ]
        assert [entry["msgid"] for entry in second] == [
            "String 03",
            "String 04",
            "String 05",
        ]

    def test_json_parser_ignores_invalid_and_out_of_range_items(self):
        parsed = _json_text_by_id(
            {
                "revisions": [
                    {"id": 1, "text": "自然文案", "reason": "更自然"},
                    {"id": 3, "text": "超出范围"},
                    {"id": "2", "text": "错误 ID"},
                    {"id": 2, "text": ""},
                ]
            },
            "revisions",
            expected=2,
        )
        assert parsed == {1: ("自然文案", "更自然")}

    def test_review_parser_requires_bounded_confidence(self):
        parsed = _json_revisions_by_id(
            {
                "revisions": [
                    {
                        "id": 1,
                        "text": "自然文案",
                        "reason": "更自然",
                        "confidence": 0.96,
                    },
                    {"id": 2, "text": "缺少置信度"},
                    {"id": 3, "text": "越界", "confidence": 1.2},
                ]
            },
            expected=3,
        )
        assert parsed == {1: ("自然文案", "更自然", 0.96)}

    def test_critic_parser_requires_boolean_decision(self):
        parsed = _json_decisions_by_id(
            {
                "decisions": [
                    {
                        "id": 1,
                        "accept": True,
                        "confidence": 0.94,
                        "reason": "语义准确",
                    },
                    {"id": 2, "accept": "yes", "confidence": 0.99},
                    {"id": 3, "accept": False, "confidence": 0.75},
                ]
            },
            expected=3,
        )
        assert parsed == {
            1: (True, 0.94, "语义准确"),
            3: (False, 0.75, ""),
        }

    def test_review_applies_only_editor_critic_agreement(self, monkeypatch):
        import translate_missing as tm

        entries = [
            {
                "prefix_lines": ["#: src/Page.tsx:1"],
                "msgid": "Follow Plan",
                "msgstr": "按计划进行",
            },
            {
                "prefix_lines": ["#: src/Page.tsx:2"],
                "msgid": "Open details",
                "msgstr": "打开详情",
            },
        ]
        responses = iter([
            {
                "revisions": [
                    {
                        "id": 1,
                        "text": "按计划训练",
                        "reason": "更自然",
                        "confidence": 0.98,
                    },
                    {
                        "id": 2,
                        "text": "查看详情",
                        "reason": "按钮更自然",
                        "confidence": 0.96,
                    },
                ]
            },
            {
                "decisions": [
                    {
                        "id": 1,
                        "accept": True,
                        "confidence": 0.97,
                        "reason": "明确改善",
                    },
                    {
                        "id": 2,
                        "accept": False,
                        "confidence": 0.95,
                        "reason": "原文可能是打开动作",
                    },
                ]
            },
        ])
        monkeypatch.setattr(tm, "_client", lambda: object())
        monkeypatch.setattr(
            tm,
            "_complete_json",
            lambda *_args, **_kwargs: next(responses),
        )

        summary = review_translations(
            entries,
            "Simplified Chinese",
            source_root=None,
            review_shards=1,
            review_shard=0,
            max_reviews=0,
        )

        assert entries[0]["msgstr"] == "按计划训练"
        assert entries[1]["msgstr"] == "打开详情"
        assert summary["revised"] == 1
        assert summary["critic_rejected"] == 1


def test_translation_limit_fails_before_opening_client(monkeypatch):
    import translate_missing as tm

    entries = [
        {"prefix_lines": [], "msgid": f"String {index}", "msgstr": ""}
        for index in range(3)
    ]
    monkeypatch.setattr(
        tm,
        "_client",
        lambda: (_ for _ in ()).throw(AssertionError("client should not open")),
    )
    with pytest.raises(ValueError, match="exceed the configured limit"):
        translate_batch(
            entries,
            "Simplified Chinese",
            max_translations=2,
        )


def test_review_cli_accepts_review_cycle_without_model_call(tmp_path, monkeypatch):
    import translate_missing as tm

    source = tmp_path / "en.po"
    target = tmp_path / "zh.po"
    baseline = tmp_path / "baseline.po"
    source.write_text('msgid "Hello"\nmsgstr "Hello"\n', encoding="utf-8")
    target.write_text('msgid "Hello"\nmsgstr "你好"\n', encoding="utf-8")
    baseline.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        tm,
        "_client",
        lambda: (_ for _ in ()).throw(AssertionError("client should not open")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "translate_missing.py",
            "review-po",
            "--source",
            str(source),
            "--target",
            str(target),
            "--language",
            "Simplified Chinese",
            "--review-shards",
            "1",
            "--review-shard",
            "0",
            "--review-cycle",
            "4",
            "--new-since-catalog",
            str(baseline),
        ],
    )

    assert translate_cli_main() == 0
