"""Deterministic semantic invariants and human-review routing for i18n.

The model-based translator can improve fluency, but it is not authoritative for
product terms or sensitive copy.  This module interprets the narrow, checked-in
``semantic_rules`` section of ``i18n_glossary.yaml``.  Blocking term invariants
and non-blocking human-review routing deliberately share the same matcher so a
rule cannot protect one path while silently reviewing another.
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import re
from typing import Any


_SOURCE_REF_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?$")
_ALLOWED_RULE_FIELDS = {
    "id",
    "source_contains",
    "source_equals",
    "required_target_terms",
    "forbidden_target_terms",
    "source_paths",
    "human_review_category",
}


@dataclass(frozen=True)
class SemanticFinding:
    """One deterministic translation invariant violated by an entry."""

    rule_id: str
    msgid: str
    message: str


def _string_list(value: Any, *, field: str, rule_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(
            f"semantic rule {rule_id!r} field {field!r} must be a list "
            "of non-empty strings"
        )
    return tuple(value)


def validate_semantic_rules(config: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Validate and normalize checked-in semantic rules, failing closed."""

    raw_rules = config.get("semantic_rules", [])
    if not isinstance(raw_rules, list):
        raise ValueError("semantic_rules must be a list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise ValueError(f"semantic rule at index {index} must be a mapping")
        unknown = sorted(set(raw) - _ALLOWED_RULE_FIELDS)
        if unknown:
            raise ValueError(
                f"semantic rule at index {index} has unknown fields: "
                + ", ".join(unknown)
            )
        rule_id = raw.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"semantic rule at index {index} needs a non-empty id")
        if rule_id in seen_ids:
            raise ValueError(f"duplicate semantic rule id: {rule_id}")
        seen_ids.add(rule_id)

        source_equals = raw.get("source_equals")
        source_contains = raw.get("source_contains")
        if (source_equals is None) == (source_contains is None):
            raise ValueError(
                f"semantic rule {rule_id!r} must define exactly one of "
                "source_equals or source_contains"
            )
        matcher = source_equals if source_equals is not None else source_contains
        if not isinstance(matcher, str) or not matcher:
            raise ValueError(f"semantic rule {rule_id!r} source matcher must be a non-empty string")

        required = _string_list(
            raw.get("required_target_terms"),
            field="required_target_terms",
            rule_id=rule_id,
        )
        forbidden = _string_list(
            raw.get("forbidden_target_terms"),
            field="forbidden_target_terms",
            rule_id=rule_id,
        )
        source_paths = _string_list(
            raw.get("source_paths"),
            field="source_paths",
            rule_id=rule_id,
        )
        category = raw.get("human_review_category")
        if category is not None and (not isinstance(category, str) or not category):
            raise ValueError(
                f"semantic rule {rule_id!r} human_review_category must be a non-empty string"
            )
        if not required and not forbidden and category is None:
            raise ValueError(f"semantic rule {rule_id!r} has no invariant or review route")

        normalized.append(
            {
                "id": rule_id,
                "source_equals": source_equals,
                "source_contains": source_contains,
                "required_target_terms": required,
                "forbidden_target_terms": forbidden,
                "source_paths": source_paths,
                "human_review_category": category,
            }
        )
    return tuple(normalized)


def source_paths(entry: dict[str, Any]) -> tuple[str, ...]:
    """Return source file paths from Lingui ``#: path:line`` comments."""

    paths: list[str] = []
    for line in entry.get("prefix_lines", []):
        stripped = str(line).strip()
        if not stripped.startswith("#:"):
            continue
        for ref in stripped[2:].strip().split():
            match = _SOURCE_REF_RE.match(ref)
            path = match.group("path") if match else ref
            if path not in paths:
                paths.append(path)
    return tuple(paths)


def is_fuzzy(entry: dict[str, Any]) -> bool:
    """Whether Lingui marked an entry's retained translation as fuzzy."""

    for line in entry.get("prefix_lines", []):
        stripped = str(line).strip()
        if not stripped.startswith("#,"):
            continue
        flags = {flag.strip() for flag in stripped[2:].split(",")}
        if "fuzzy" in flags:
            return True
    return False


def _matches(entry: dict[str, Any], rule: dict[str, Any]) -> bool:
    msgid = str(entry.get("msgid", ""))
    equals = rule["source_equals"]
    contains = rule["source_contains"]
    if equals is not None and msgid.casefold() != equals.casefold():
        return False
    if contains is not None and contains.casefold() not in msgid.casefold():
        return False
    patterns = rule["source_paths"]
    if patterns:
        paths = source_paths(entry)
        if not any(fnmatchcase(path, pattern) for path in paths for pattern in patterns):
            return False
    return True


def check_semantic_rules(
    entry: dict[str, Any],
    config: dict[str, Any],
) -> list[SemanticFinding]:
    """Return blocking invariant failures for one translated entry."""

    findings: list[SemanticFinding] = []
    msgid = str(entry.get("msgid", ""))
    translation = str(entry.get("msgstr", ""))
    for rule in validate_semantic_rules(config):
        if not _matches(entry, rule):
            continue
        for term in rule["required_target_terms"]:
            if term not in translation:
                findings.append(
                    SemanticFinding(
                        rule["id"],
                        msgid,
                        f"required target term {term!r} is missing",
                    )
                )
        for term in rule["forbidden_target_terms"]:
            if term in translation:
                findings.append(
                    SemanticFinding(
                        rule["id"],
                        msgid,
                        f"forbidden target term {term!r} is present",
                    )
                )
    return findings


def human_review_reasons(
    entry: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    """Return review categories; an empty list is never an approval."""

    reasons: list[str] = []
    for rule in validate_semantic_rules(config):
        category = rule["human_review_category"]
        if category is not None and _matches(entry, rule):
            reason = f"{category}:{rule['id']}"
            if reason not in reasons:
                reasons.append(reason)
    return reasons
