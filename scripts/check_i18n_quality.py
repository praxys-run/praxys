"""Deterministic quality gate for the Praxys Simplified Chinese catalog.

The AI editor handles semantic quality. This script enforces the objective
invariants that should never depend on a reviewer: catalog coverage, placeholder
integrity, protected technical tokens, canonical product terms, voice choices,
and Chinese typography.

Run from the repository root:

    python scripts/check_i18n_quality.py \
        --source web/src/locales/en/messages.po \
        --target web/src/locales/zh/messages.po \
        --glossary scripts/i18n_glossary.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from translate_missing import _placeholders_match, parse_po


_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_URL_OR_EMAIL_RE = re.compile(r"(?:https?://|www\.|@|\.[a-z]{2,}(?:/|$))", re.I)


@dataclass(frozen=True)
class Finding:
    """One actionable catalog quality violation."""

    code: str
    msgid: str
    message: str


def load_quality_config(path: Path) -> dict[str, Any]:
    """Load the style section and glossary terms from YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _entry_map(entries: list[dict]) -> dict[str, dict]:
    return {entry["msgid"]: entry for entry in entries if entry["msgid"]}


def _contains_token(text: str, token: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _same_as_source_allowed(source: str, allowed: set[str]) -> bool:
    if source in allowed:
        return True
    if not _ASCII_WORD_RE.search(source):
        return True
    if _URL_OR_EMAIL_RE.search(source):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9.+/-]{1,7}", source):
        return True
    return False


def check_catalog(
    source_entries: list[dict],
    target_entries: list[dict],
    config: dict[str, Any],
) -> list[Finding]:
    """Return deterministic quality violations for active catalog entries."""
    findings: list[Finding] = []
    source = _entry_map(source_entries)
    target = _entry_map(target_entries)

    for missing in sorted(source.keys() - target.keys()):
        findings.append(Finding("missing-entry", missing, "missing from zh catalog"))
    for extra in sorted(target.keys() - source.keys()):
        findings.append(Finding("orphan-entry", extra, "not present in source catalog"))

    style = config.get("style") or {}
    forbidden = style.get("forbidden_target") or []
    exact_rules = style.get("exact_translations") or []
    allowed_same = {
        item for item in style.get("allowed_same_as_source") or []
        if isinstance(item, str)
    }
    exact = {
        item["source"]: item["target"]
        for item in exact_rules
        if (
            isinstance(item, dict)
            and isinstance(item.get("source"), str)
            and isinstance(item.get("target"), str)
        )
    }
    protected = {
        item["en"]
        for item in config.get("terms") or []
        if (
            isinstance(item, dict)
            and isinstance(item.get("en"), str)
            and item.get("zh") == item.get("en")
        )
    }

    for msgid in sorted(source.keys() & target.keys()):
        translation = target[msgid]["msgstr"]
        if not translation:
            findings.append(Finding("empty", msgid, "zh translation is empty"))
            continue
        if not _placeholders_match(msgid, translation):
            findings.append(
                Finding(
                    "structure",
                    msgid,
                    "ICU placeholders, Lingui tags, or line breaks do not match",
                )
            )

        expected = exact.get(msgid)
        if expected is not None and translation != expected:
            findings.append(
                Finding(
                    "canonical",
                    msgid,
                    f"expected exact translation {expected!r}, got {translation!r}",
                )
            )

        for rule in forbidden:
            if not isinstance(rule, dict):
                continue
            term = rule.get("term")
            prefer = rule.get("prefer")
            if isinstance(term, str) and term and term in translation:
                findings.append(
                    Finding(
                        "forbidden-term",
                        msgid,
                        f"replace {term!r} with {prefer or 'native product wording'}",
                    )
                )

        if _CJK_RE.search(translation):
            if "..." in translation:
                findings.append(
                    Finding("typography", msgid, "use the single Chinese ellipsis character …")
                )
            if re.search(r"\s[—–]\s", translation):
                findings.append(
                    Finding(
                        "typography",
                        msgid,
                        "replace an English-style spaced dash with Chinese punctuation",
                    )
                )
            if re.search(r"(?<![A-Za-z])vs\.?(?![A-Za-z])", translation, re.I):
                findings.append(
                    Finding("typography", msgid, "translate literal 'vs' as 与 or 对比")
                )

        if translation == msgid and not _same_as_source_allowed(msgid, allowed_same):
            findings.append(
                Finding(
                    "untranslated",
                    msgid,
                    "translation is identical to English source",
                )
            )

        for token in protected:
            if _contains_token(msgid, token) and not _contains_token(translation, token):
                findings.append(
                    Finding(
                        "protected-token",
                        msgid,
                        f"technical token {token!r} must remain unchanged",
                    )
                )

    return findings


def main() -> int:
    """Run the catalog quality gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--glossary", required=True, type=Path)
    args = parser.parse_args()

    source_entries, _ = parse_po(args.source)
    target_entries, _ = parse_po(args.target)
    config = load_quality_config(args.glossary)
    findings = check_catalog(source_entries, target_entries, config)

    if not findings:
        print(
            f"Chinese catalog quality check passed "
            f"({len(_entry_map(target_entries))} active entries)."
        )
        return 0

    for finding in findings:
        print(
            f"[{finding.code}] {finding.msgid!r}: {finding.message}",
            file=sys.stderr,
        )
    print(
        f"Chinese catalog quality check failed with {len(findings)} finding(s).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
