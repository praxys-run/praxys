"""Unit tests for scripts/translate_missing.py placeholder validator + glossary."""
import json
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import translate_missing as tm  # noqa: E402
from translate_missing import (  # noqa: E402
    _extract_context,
    _group_by_screen,
    _group_by_semantic_cluster,
    _icu_variable_names,
    _json_decisions_by_id,
    _json_text_by_id,
    _json_revisions_by_id,
    _placeholders,
    _placeholders_match,
    _read_source_excerpt,
    _review_candidates,
    _screen_translation_references,
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

    def test_prompt_includes_every_enforced_glossary_rule_family(self):
        prompt = build_system_prompt()
        # These are enforced later by check_i18n_quality.py, so the generator
        # should receive the same contract before it spends a model call.
        assert "avoid 账户 → prefer 账号" in prompt
        assert "Follow Plan → 按计划训练" in prompt
        assert "Keep these approved brands" in prompt
        assert "Azure Monitor" in prompt


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

    def test_semantic_clusters_are_screen_and_source_proximity_scoped(self):
        entries = [
            {"prefix_lines": ["#: src/A.tsx:1"], "msgid": "A1", "msgstr": "甲"},
            {"prefix_lines": ["#: src/A.tsx:79"], "msgid": "A2", "msgstr": "乙"},
            {"prefix_lines": ["#: src/A.tsx:81"], "msgid": "A3", "msgstr": "丙"},
            {"prefix_lines": ["#: src/B.tsx:1"], "msgid": "B1", "msgstr": "丁"},
        ]
        assert [
            [entry["msgid"] for entry in group]
            for group in _group_by_semantic_cluster(entries)
        ] == [["A1", "A2"], ["A3"], ["B1"]]

    def test_complete_semantic_cluster_is_one_model_request(
        self, monkeypatch
    ):
        import translate_missing as tm

        prompts: list[str] = []
        responses = iter([
            {
                "translations": [
                    {"id": index, "text": f"标签 {index}"}
                    for index in range(1, 21)
                ]
            },
            {
                "decisions": [
                    {
                        "id": index,
                        "accept": True,
                        "confidence": 0.99,
                        "reason": "语义忠实",
                    }
                    for index in range(1, 21)
                ]
            },
        ])
        monkeypatch.setattr(tm, "_client", lambda: object())

        def complete(_client, _system, user, **_kwargs):
            prompts.append(user)
            return next(responses)

        monkeypatch.setattr(tm, "_complete_json", complete)

        entries = [
            {
                "prefix_lines": [f"#: src/Page.tsx:{index}"],
                "msgid": f"Label {index}",
                "msgstr": "",
            }
            for index in range(1, 21)
        ]
        summary = translate_batch(entries, "Simplified Chinese")

        assert summary["filled"] == 20
        assert len(prompts) == 2
        assert all("Label 1" in prompt and "Label 20" in prompt for prompt in prompts)

    def test_screen_references_are_nearby_bounded_and_screen_scoped(self):
        entries = [
            {
                "prefix_lines": ["#: src/A.tsx:1"],
                "msgid": "Far label",
                "msgstr": "较远标签",
            },
            {
                "prefix_lines": ["#: src/A.tsx:98"],
                "msgid": "Nearby action",
                "msgstr": "附近操作",
            },
            {
                "prefix_lines": ["#: src/B.tsx:100"],
                "msgid": "Wrong screen",
                "msgstr": "其他页面",
            },
            {
                "prefix_lines": ["#: src/A.tsx:100"],
                "msgid": "New action",
                "msgstr": "",
            },
            {
                "prefix_lines": ["#: src/A.tsx:102"],
                "msgid": "Closest action",
                "msgstr": "最近操作",
            },
        ]

        references = _screen_translation_references(
            entries,
            [entries[3]],
            limit=2,
        )

        assert references == [
            {"english": "Nearby action", "approved_zh": "附近操作"},
            {"english": "Closest action", "approved_zh": "最近操作"},
        ]

    def test_screen_references_obey_character_budget(self):
        current = {
            "prefix_lines": ["#: src/A.tsx:10"],
            "msgid": "New",
            "msgstr": "",
        }
        existing = {
            "prefix_lines": ["#: src/A.tsx:11"],
            "msgid": "Long English",
            "msgstr": "很长的中文",
        }
        assert _screen_translation_references(
            [current, existing],
            [current],
            max_chars=5,
        ) == []


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
        # A source-proximity cluster is indivisible. One large cluster may
        # exceed the soft cap instead of being split across review runs.
        assert len(first) == 20
        assert capped == 0

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
                "prefix_lines": [f"#: src/Page{index}.tsx:1"],
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

    def test_soft_cap_never_splits_a_semantic_cluster_between_windows(self):
        entries = [
            {
                "prefix_lines": [f"#: src/A.tsx:{index}"],
                "msgid": f"A{index}",
                "msgstr": f"甲{index}",
            }
            for index in range(4)
        ] + [
            {
                "prefix_lines": [f"#: src/B.tsx:{index}"],
                "msgid": f"B{index}",
                "msgstr": f"乙{index}",
            }
            for index in range(4)
        ]

        first, first_capped = _review_candidates(
            entries,
            review_shards=1,
            review_shard=0,
            max_reviews=5,
            review_cycle=0,
        )
        second, second_capped = _review_candidates(
            entries,
            review_shards=1,
            review_shard=0,
            max_reviews=5,
            review_cycle=1,
        )

        assert [entry["msgid"] for entry in first] == ["A0", "A1", "A2", "A3"]
        assert [entry["msgid"] for entry in second] == ["B0", "B1", "B2", "B3"]
        assert first_capped == second_capped == 4

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

    def test_critic_parser_fails_closed_on_duplicate_or_boolean_ids(self):
        parsed = _json_decisions_by_id(
            {
                "decisions": [
                    {"id": 1, "accept": True, "confidence": 0.99},
                    {"id": 1, "accept": False, "confidence": 0.99},
                    {"id": True, "accept": True, "confidence": 0.99},
                    {"id": 2, "accept": True, "confidence": 0.98},
                ]
            },
            expected=2,
        )

        assert parsed == {2: (True, 0.98, "")}

    def test_new_translations_require_high_confidence_semantic_approval(
        self,
        monkeypatch,
    ):
        import translate_missing as tm

        entries = [
            {
                "prefix_lines": [f"#: src/Page.tsx:{index}"],
                "msgid": english,
                "msgstr": "",
            }
            for index, english in enumerate(
                [
                    "Follow Plan",
                    "Do not disconnect Garmin",
                    "Open details",
                    "Delete account",
                ],
                start=1,
            )
        ]
        calls: list[tuple[str, str]] = []
        responses = iter([
            {
                "translations": [
                    {"id": 1, "text": "按计划训练"},
                    {"id": 2, "text": "断开 Garmin 连接"},
                    {"id": 3, "text": "查看详情"},
                    {"id": 4, "text": "删除账号"},
                ]
            },
            {
                "decisions": [
                    {
                        "id": 1,
                        "accept": True,
                        "confidence": 0.98,
                        "reason": "含义完整",
                    },
                    {
                        "id": 2,
                        "accept": False,
                        "confidence": 0.99,
                        "reason": "丢失否定含义",
                    },
                    {
                        "id": 3,
                        "accept": True,
                        "confidence": 0.89,
                        "reason": "上下文仍有歧义",
                    },
                    # id 4 is deliberately absent: missing decisions fail closed.
                ]
            },
        ])

        def complete_json(_client, _system, user, *, model, **_kwargs):
            calls.append((model, user))
            return next(responses)

        monkeypatch.setattr(tm, "_client", lambda: object())
        monkeypatch.setattr(tm, "_complete_json", complete_json)

        summary = translate_batch(
            entries,
            "Simplified Chinese",
            max_translations=10,
        )

        assert [entry["msgstr"] for entry in entries] == [
            "按计划训练",
            "",
            "",
            "",
        ]
        assert summary == {
            "filled": 1,
            "rejected_placeholder_mismatch": 0,
            "rejected_semantic": 1,
            "semantic_low_confidence": 1,
            "semantic_unverified": 1,
            "glossary_warnings": 0,
            "capped": 0,
        }
        assert calls[0][0] == tm.MODEL
        assert calls[1][0] == tm.REVIEW_MODEL
        assert "semantic-faithfulness gate" in calls[1][1]
        assert "separate semantic-faithfulness gate" in calls[1][1]
        assert "Do not disconnect Garmin" in calls[1][1]
        assert "断开 Garmin 连接" in calls[1][1]

    def test_structurally_invalid_draft_never_reaches_semantic_gate(
        self,
        monkeypatch,
    ):
        import translate_missing as tm

        entries = [
            {
                "prefix_lines": ["#: src/Page.tsx:1"],
                "msgid": "Hello {name}",
                "msgstr": "",
            },
            {
                "prefix_lines": ["#: src/Page.tsx:2"],
                "msgid": "Open details",
                "msgstr": "",
            },
        ]
        prompts: list[str] = []
        responses = iter([
            {
                "translations": [
                    {"id": 1, "text": "你好"},
                    {"id": 2, "text": "查看详情"},
                ]
            },
            {
                "decisions": [
                    {
                        "id": 2,
                        "accept": True,
                        "confidence": 0.99,
                        "reason": "含义完整",
                    }
                ]
            },
        ])

        def complete_json(_client, _system, user, **_kwargs):
            prompts.append(user)
            return next(responses)

        monkeypatch.setattr(tm, "_client", lambda: object())
        monkeypatch.setattr(tm, "_complete_json", complete_json)

        summary = translate_batch(entries, "Simplified Chinese")

        assert entries[0]["msgstr"] == ""
        assert entries[1]["msgstr"] == "查看详情"
        assert summary["rejected_placeholder_mismatch"] == 1
        assert "Hello {name}" not in prompts[1]
        assert "Open details" in prompts[1]

    def test_new_translation_and_semantic_gate_receive_established_screen_copy(
        self,
        monkeypatch,
    ):
        import translate_missing as tm

        entries = [
            {
                "prefix_lines": ["#: src/Page.tsx:10"],
                "msgid": "Open feedback",
                "msgstr": "查看反馈",
            },
            {
                "prefix_lines": ["#: src/Page.tsx:12"],
                "msgid": "Open plan preview",
                "msgstr": "",
            },
        ]
        prompts: list[str] = []
        responses = iter([
            {"translations": [{"id": 1, "text": "查看计划预览"}]},
            {
                "decisions": [{
                    "id": 1,
                    "accept": True,
                    "confidence": 0.99,
                    "reason": "语义与同屏操作一致",
                }]
            },
        ])

        def complete_json(_client, _system, user, **_kwargs):
            prompts.append(user)
            return next(responses)

        monkeypatch.setattr(tm, "_client", lambda: object())
        monkeypatch.setattr(tm, "_complete_json", complete_json)

        summary = translate_batch(entries, "Simplified Chinese")

        assert summary["filled"] == 1
        assert entries[1]["msgstr"] == "查看计划预览"
        for prompt in prompts:
            payload = json.loads(prompt.split("INPUT:\n", 1)[1])
            assert payload["established_screen_copy_reference_only"] == [{
                "english": "Open feedback",
                "approved_zh": "查看反馈",
            }]

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

    def test_review_keeps_revision_that_breaks_deterministic_term_rule(
        self, monkeypatch
    ):
        import translate_missing as tm

        entry = {
            "prefix_lines": ["#: src/Page.tsx:1"],
            "msgid": "Choose training base",
            "msgstr": "选择训练基准",
        }
        responses = iter([
            {
                "revisions": [{
                    "id": 1,
                    "text": "选择训练依据",
                    "reason": "更自然",
                    "confidence": 0.99,
                }]
            },
        ])
        monkeypatch.setattr(tm, "_client", lambda: object())
        monkeypatch.setattr(
            tm, "_complete_json", lambda *_args, **_kwargs: next(responses)
        )

        summary = review_translations(
            [entry],
            "Simplified Chinese",
            source_root=None,
            review_shards=1,
            review_shard=0,
            max_reviews=0,
        )

        assert entry["msgstr"] == "选择训练基准"
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


def test_fuzzy_translation_is_retranslated_and_cleared_after_all_gates(monkeypatch):
    import translate_missing as tm

    entry = {
        "prefix_lines": ["#: src/Page.tsx:1", "#, fuzzy, python-format"],
        "msgid": "Choose training base",
        "msgstr": "选择训练依据",
    }
    responses = iter([
        {"translations": [{"id": 1, "text": "选择训练基准"}]},
        {
            "decisions": [{
                "id": 1,
                "accept": True,
                "confidence": 0.99,
                "reason": "语义忠实",
            }]
        },
    ])
    monkeypatch.setattr(tm, "_client", lambda: object())
    monkeypatch.setattr(tm, "_complete_json", lambda *_args, **_kwargs: next(responses))

    summary = translate_batch([entry], "Simplified Chinese")

    assert summary["filled"] == 1
    assert entry["msgstr"] == "选择训练基准"
    assert entry["prefix_lines"] == ["#: src/Page.tsx:1", "#, python-format"]


def test_fuzzy_translation_remains_fuzzy_when_semantic_gate_rejects(monkeypatch):
    import translate_missing as tm

    entry = {
        "prefix_lines": ["#, fuzzy"],
        "msgid": "Choose training base",
        "msgstr": "选择训练依据",
    }
    responses = iter([
        {"translations": [{"id": 1, "text": "选择训练基准"}]},
        {
            "decisions": [{
                "id": 1,
                "accept": False,
                "confidence": 0.99,
                "reason": "仍需人工判断",
            }]
        },
    ])
    monkeypatch.setattr(tm, "_client", lambda: object())
    monkeypatch.setattr(tm, "_complete_json", lambda *_args, **_kwargs: next(responses))

    summary = translate_batch([entry], "Simplified Chinese")

    assert summary["rejected_semantic"] == 1
    assert entry["msgstr"] == "选择训练依据"
    assert entry["prefix_lines"] == ["#, fuzzy"]


def test_nonempty_nonfuzzy_translation_does_not_open_client(monkeypatch):
    import translate_missing as tm

    entry = {"prefix_lines": [], "msgid": "Hello", "msgstr": "你好"}
    monkeypatch.setattr(
        tm,
        "_client",
        lambda: (_ for _ in ()).throw(AssertionError("client should not open")),
    )

    assert translate_batch([entry], "Simplified Chinese")["filled"] == 0


def test_deterministic_semantic_rule_rejects_model_approved_new_translation(
    monkeypatch,
):
    import translate_missing as tm

    entry = {
        "prefix_lines": ["#: src/Page.tsx:1"],
        "msgid": "Choose training base",
        "msgstr": "",
    }
    monkeypatch.setattr(tm, "_client", lambda: object())
    monkeypatch.setattr(
        tm,
        "_complete_json",
        lambda *_args, **_kwargs: {
            "translations": [{"id": 1, "text": "选择训练依据"}]
        },
    )

    summary = translate_batch([entry], "Simplified Chinese")

    assert summary["rejected_semantic"] == 1
    assert entry["msgstr"] == ""


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


def test_theory_translation_keeps_science_metadata_canonical(
    tmp_path,
    monkeypatch,
):
    source_dir = tmp_path / "science"
    source_path = source_dir / "load" / "example.yaml"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        yaml.safe_dump({
            "id": "example",
            "pillar": "load",
            "name": "Example",
            "description": "English description",
            "science_decision_id": "sdr-example-v1",
            "model_version": "example-v1",
            "params": {"constant": 42},
            "citations": [{"id": "source"}],
        }, sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(tm, "_client", lambda: object())
    monkeypatch.setattr(
        tm,
        "_complete",
        lambda *_args: "[name]\nTranslated\n\n[description]\nLocalized",
    )

    target_dir = tmp_path / "zh"
    tm.translate_yaml_tree(source_dir, target_dir, "Chinese")
    translated = yaml.safe_load(
        (target_dir / "load" / "example.yaml").read_text(encoding="utf-8")
    )

    assert translated == {
        "id": "example",
        "pillar": "load",
        "name": "Translated",
        "description": "Localized",
    }
