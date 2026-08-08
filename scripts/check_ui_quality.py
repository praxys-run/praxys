"""Gate rendered UI changes on Impeccable findings and review evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parent.parent
DETECTOR = ROOT / ".github" / "skills" / "impeccable" / "scripts" / "detect.mjs"

_WEB_CODE_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".less",
    ".sass",
    ".scss",
    ".ts",
    ".tsx",
}
_MINIAPP_CODE_EXTENSIONS = {
    ".css",
    ".js",
    ".json",
    ".ts",
    ".wxml",
    ".wxss",
}
_ASSET_EXTENSIONS = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}
_DETECTOR_EXTENSIONS = {
    ".astro",
    ".css",
    ".html",
    ".htm",
    ".js",
    ".jsx",
    ".less",
    ".sass",
    ".scss",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
    ".wxml",
    ".wxss",
}
_DESIGN_GOVERNANCE_FILES = {
    "DESIGN.md",
    "PRODUCT.md",
    "docs/dev/design-system.md",
}
_EVIDENCE_FIELDS = (
    "impeccable",
    "visual review",
    "states checked",
    "accessibility",
    "design system impact",
    "miniapp parity",
    "exceptions",
)
_IMPECCABLE_COMMANDS = {
    "adapt",
    "animate",
    "audit",
    "bolder",
    "clarify",
    "colorize",
    "critique",
    "delight",
    "distill",
    "document",
    "extract",
    "harden",
    "init",
    "layout",
    "live",
    "new-work",
    "onboard",
    "optimize",
    "overdrive",
    "polish",
    "quieter",
    "shape",
    "typeset",
}
_PLACEHOLDER_RE = re.compile(
    r"(?:^|\b)(?:todo|tbd|pending|not checked|not run|n/?a)(?:\b|$)",
    re.IGNORECASE,
)


def normalize_repo_path(raw_path: str) -> str:
    """Return a stable repository-relative POSIX path."""
    normalized = raw_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return str(PurePosixPath(normalized))


def rendered_surface(path: str) -> str | None:
    """Return ``web`` or ``miniapp`` when a path can change rendered UI."""
    normalized = normalize_repo_path(path)
    pure = PurePosixPath(normalized)
    suffix = pure.suffix.lower()
    lower_name = pure.name.lower()

    if (
        "/tests/" in f"/{normalized.lower()}/"
        or "/__tests__/" in f"/{normalized.lower()}/"
        or ".test." in lower_name
        or ".spec." in lower_name
    ):
        return None

    if normalized == "web/index.html":
        return "web"
    if normalized.startswith("web/public/") and suffix in _ASSET_EXTENSIONS:
        return "web"
    if normalized.startswith("web/src/locales/") and suffix == ".po":
        return "web"
    if normalized.startswith("web/src/"):
        if "/types/" in f"/{normalized}" or normalized.endswith(".d.ts"):
            return None
        if suffix in _WEB_CODE_EXTENSIONS or suffix in _ASSET_EXTENSIONS:
            return "web"

    if normalized.startswith("miniapp/"):
        if normalized.startswith(("miniapp/scripts/", "miniapp/types/")):
            return None
        if pure.name in {"package.json", "package-lock.json", "tsconfig.json"}:
            return None
        if suffix in _MINIAPP_CODE_EXTENSIONS or suffix in _ASSET_EXTENSIONS:
            return "miniapp"

    return None


def is_design_governance_path(path: str) -> bool:
    """Return whether a path defines shared product or visual direction."""
    normalized = normalize_repo_path(path)
    return (
        normalized in _DESIGN_GOVERNANCE_FILES
        or normalized.startswith("docs/brand/")
    )


def detector_targets(paths: Iterable[str], root: Path = ROOT) -> list[str]:
    """Return existing changed source files supported by the detector."""
    targets: list[str] = []
    for path in paths:
        normalized = normalize_repo_path(path)
        if PurePosixPath(normalized).suffix.lower() not in _DETECTOR_EXTENSIONS:
            continue
        if not (root / Path(normalized)).is_file():
            continue
        targets.append(normalized)
    return sorted(set(targets))


def changed_files(base: str, head: str, root: Path = ROOT) -> list[str]:
    """Return added, copied, deleted, modified, or renamed files."""
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=ACDMR",
                f"{base}...{head}",
                "--",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise RuntimeError(f"could not run git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git diff failed for {base}...{head}: {detail}")
    return sorted(
        {
            normalize_repo_path(line)
            for line in result.stdout.splitlines()
            if line.strip()
        }
    )


def _ui_quality_section(body: str) -> str | None:
    match = re.search(
        r"(?ims)^##\s+UI quality\s*$\s*(.*?)(?=^##\s+|\Z)",
        body,
    )
    return match.group(1) if match else None


def _evidence_values(section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(
            r"^\s*-\s*(?:\*\*)?([^:*]+?)(?:\*\*)?\s*:\s*(.*?)\s*$",
            line,
        )
        if not match:
            continue
        key = re.sub(r"\s+", " ", match.group(1).strip().lower())
        values[key] = match.group(2).strip().strip("`")
    return values


def _is_placeholder(value: str) -> bool:
    return (
        not value.strip()
        or "<!--" in value
        or "-->" in value
        or _PLACEHOLDER_RE.search(value) is not None
    )


def _validate_design_system_impact(
    value: str,
    governance_paths: Sequence[str],
) -> list[str]:
    normalized = re.sub(r"\s+", " ", value.strip())
    lowered = normalized.lower()

    if lowered.startswith("none"):
        if re.fullmatch(r"none\s*-\s*\S.*", normalized, re.IGNORECASE):
            return []
        return [
            "UI quality field 'design system impact' must explain why the "
            "existing system already covers the change."
        ]

    updated = re.fullmatch(
        r"updated in this pr\s*-\s*(\S.*)",
        normalized,
        re.IGNORECASE,
    )
    if updated:
        if not governance_paths:
            return [
                "Design system impact says 'updated in this PR', but no "
                "design-governance file changed."
            ]
        detail = updated.group(1).lower()
        if not any(path.lower() in detail for path in governance_paths):
            return [
                "Design system impact must name a changed design-governance "
                "path."
            ]
        return []

    if lowered.startswith("follow-up"):
        if re.search(r"(?<!\w)#\d+\b", normalized):
            return []
        return [
            "Design system follow-ups must reference a filed GitHub issue "
            "such as 'follow-up #123 - missing chart token'."
        ]

    return [
        "UI quality field 'design system impact' must be one of: "
        "'none - <reason>', 'updated in this PR - <changed path>', or "
        "'follow-up #123 - <gap>'."
    ]


def validate_ui_evidence(
    body: str,
    *,
    has_web: bool,
    has_miniapp: bool,
    changed_paths: Iterable[str] = (),
    allow_unverified: bool = False,
) -> list[str]:
    """Return PR evidence errors for a rendered UI change."""
    section = _ui_quality_section(body)
    if section is None:
        return ["PR body is missing the required '## UI quality' section."]

    values = _evidence_values(section)
    if allow_unverified:
        return [
            f"UI quality field '{field}' is missing from the draft evidence block."
            for field in _EVIDENCE_FIELDS
            if field not in values
        ]

    errors: list[str] = []
    for field in _EVIDENCE_FIELDS:
        value = values.get(field, "")
        if _is_placeholder(value):
            errors.append(f"UI quality field '{field}' is missing or unverified.")
        elif field != "exceptions" and value.strip().lower() == "none":
            errors.append(f"UI quality field '{field}' cannot be 'none'.")

    impact_value = values.get("design system impact", "")
    if not _is_placeholder(impact_value):
        governance_paths = sorted(
            {
                normalize_repo_path(path)
                for path in changed_paths
                if is_design_governance_path(path)
            }
        )
        errors.extend(
            _validate_design_system_impact(
                impact_value,
                governance_paths,
            )
        )

    impeccable_value = values.get("impeccable", "").lower()
    if impeccable_value and not any(
        re.search(rf"\b{re.escape(command)}\b", impeccable_value)
        for command in _IMPECCABLE_COMMANDS
    ):
        errors.append(
            "UI quality field 'impeccable' must name the command used and target."
        )

    visual_value = values.get("visual review", "").lower()
    if has_web:
        if "desktop" not in visual_value or "mobile" not in visual_value:
            errors.append(
                "Web UI evidence must include both desktop and mobile review."
            )
    if has_miniapp:
        if not any(
            marker in visual_value
            for marker in ("miniapp", "wechat", "skyline", "devtools")
        ):
            errors.append(
                "Miniapp UI evidence must name the WeChat/Skyline review target."
            )

    parity_value = values.get("miniapp parity", "").lower()
    if parity_value in {"not applicable", "n/a", "na"}:
        errors.append(
            "Miniapp parity marked not applicable must include a concrete reason."
        )

    return errors


def _chunks(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _parse_detector_output(stdout: str) -> list[dict[str, Any]]:
    if not stdout.strip():
        return []
    parsed = json.loads(stdout)
    if not isinstance(parsed, list):
        raise ValueError("detector JSON output must be a list")
    return [item for item in parsed if isinstance(item, dict)]


def run_detector(
    targets: Sequence[str],
    *,
    root: Path = ROOT,
    detector: Path = DETECTOR,
) -> list[dict[str, Any]]:
    """Run the vendored detector over explicit files and return findings."""
    if not detector.is_file():
        raise RuntimeError(f"vendored Impeccable detector is missing: {detector}")

    findings: list[dict[str, Any]] = []
    for batch in _chunks(list(targets), 40):
        try:
            result = subprocess.run(
                ["node", str(detector), "--json", *batch],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise RuntimeError(f"could not run the Impeccable detector: {exc}") from exc
        try:
            findings.extend(_parse_detector_output(result.stdout))
        except (json.JSONDecodeError, ValueError) as exc:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Impeccable detector returned invalid JSON: {detail}") from exc
        if result.returncode not in {0, 2}:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Impeccable detector failed with exit {result.returncode}: {detail}"
            )

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for finding in findings:
        key = (
            finding.get("antipattern"),
            finding.get("file"),
            finding.get("line"),
            finding.get("snippet"),
        )
        unique[key] = finding
    return list(unique.values())


def _display_path(raw_path: Any, root: Path = ROOT) -> str:
    try:
        return Path(str(raw_path)).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(raw_path)


def _github_escape(message: str) -> str:
    return (
        message.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def report_findings(findings: Sequence[dict[str, Any]]) -> int:
    """Print detector findings and return the number that block CI."""
    blocking = [
        finding
        for finding in findings
        if str(finding.get("severity", "")).lower() != "advisory"
    ]
    advisory = [finding for finding in findings if finding not in blocking]

    for finding in blocking:
        path = _display_path(finding.get("file", ""))
        line = int(finding.get("line") or 1)
        name = str(finding.get("name") or finding.get("antipattern") or "finding")
        description = str(finding.get("description") or "")
        print(f"Impeccable: {path}:{line}: {name} - {description}")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(
                f"::error file={path},line={line}::"
                f"{_github_escape(f'{name}: {description}')}"
            )

    for finding in advisory:
        path = _display_path(finding.get("file", ""))
        line = int(finding.get("line") or 1)
        name = str(finding.get("name") or finding.get("antipattern") or "advisory")
        print(f"Impeccable advisory: {path}:{line}: {name}")

    return len(blocking)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Base git ref or SHA.")
    parser.add_argument("--head", default="HEAD", help="Head git ref or SHA.")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Explicit changed path; repeat to bypass git diff.",
    )
    parser.add_argument(
        "--pr-body-env",
        help="Environment variable containing the pull-request body.",
    )
    parser.add_argument(
        "--skip-evidence",
        action="store_true",
        help="Skip PR body evidence validation for local smoke checks.",
    )
    parser.add_argument(
        "--allow-unverified-draft",
        action="store_true",
        help=(
            "Allow explicitly incomplete evidence values while a Copilot PR "
            "remains draft; all evidence fields must still be present."
        ),
    )
    parser.add_argument(
        "--skip-detector",
        action="store_true",
        help="Skip the Impeccable detector.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the UI quality gate."""
    args = build_parser().parse_args(argv)
    if args.changed_file:
        paths = sorted({normalize_repo_path(path) for path in args.changed_file})
    else:
        if not args.base:
            raise SystemExit("--base is required unless --changed-file is used")
        try:
            paths = changed_files(args.base, args.head)
        except RuntimeError as exc:
            print(f"UI quality gate: {exc}", file=sys.stderr)
            return 1

    surfaces = {surface for path in paths if (surface := rendered_surface(path))}
    governance = [path for path in paths if is_design_governance_path(path)]
    rendered = [path for path in paths if rendered_surface(path)]

    if not rendered:
        detail = (
            f" Design-governance files changed: {', '.join(governance)}."
            if governance
            else ""
        )
        print(f"UI quality gate: no rendered UI files changed.{detail}")
        return 0

    print("UI quality gate: rendered UI changes detected:")
    for path in rendered:
        print(f"- {path}")

    errors: list[str] = []
    if not args.skip_evidence:
        body = os.environ.get(args.pr_body_env or "", "")
        errors.extend(
            validate_ui_evidence(
                body,
                has_web="web" in surfaces,
                has_miniapp="miniapp" in surfaces,
                changed_paths=paths,
                allow_unverified=args.allow_unverified_draft,
            )
        )

    if not args.skip_detector:
        targets = detector_targets(rendered)
        try:
            findings = run_detector(targets) if targets else []
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            if report_findings(findings):
                errors.append(
                    "Impeccable reported blocking findings in changed UI files."
                )

    if errors:
        for error in errors:
            print(f"UI quality gate: {error}", file=sys.stderr)
        return 1

    print("UI quality gate: passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
