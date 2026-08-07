"""Run the deterministic final validation required for coding-agent PRs."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_ui_quality import rendered_surface


WEB_CANONICAL_MINIAPP_PATHS = (
    "web/src/lib/legal.ts",
    "web/src/locales/",
    "web/src/types/api.ts",
)


def changed_files(base: str, head: str = "HEAD") -> list[str]:
    """Return repository-relative paths changed between base and head."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACDMR", f"{base}...{head}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"could not determine changed files: {detail}")
    return sorted(
        {
            line.strip().replace("\\", "/")
            for line in result.stdout.splitlines()
            if line.strip()
        }
    )


def needs_web_validation(paths: Sequence[str]) -> bool:
    """Return whether the web dependency graph or source tree changed."""
    return any(path.startswith("web/") for path in paths)


def needs_miniapp_validation(paths: Sequence[str]) -> bool:
    """Return whether miniapp code or a web-canonical miniapp input changed."""
    return any(
        path.startswith("miniapp/")
        or any(
            path == canonical
            or (canonical.endswith("/") and path.startswith(canonical))
            for canonical in WEB_CANONICAL_MINIAPP_PATHS
        )
        for path in paths
    )


def has_rendered_ui(paths: Sequence[str]) -> bool:
    """Return whether any changed path can alter rendered web or miniapp UI."""
    return any(rendered_surface(path) is not None for path in paths)


def _npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _run(command: Sequence[str], *, cwd: Path = ROOT) -> None:
    printable = " ".join(command)
    print(f"\n==> {printable}", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {printable}")


def _worktree_changes(paths: Sequence[str] | None = None) -> list[str]:
    command = ["git", "status", "--short"]
    if paths:
        command.extend(["--", *paths])
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError("could not inspect the worktree")
    return [line for line in result.stdout.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="Base ref for the PR diff.")
    parser.add_argument("--head", default="HEAD", help="Head ref for the PR diff.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run all validations required before a coding-agent review handoff."""
    args = build_parser().parse_args(argv)
    try:
        paths = changed_files(args.base, args.head)
        if not paths:
            raise RuntimeError("no changed files found for the requested diff")

        _run([sys.executable, "-m", "pytest", "tests/"])

        if needs_web_validation(paths):
            _run([_npm(), "run", "i18n:extract"], cwd=ROOT / "web")
            catalog_changes = _worktree_changes(
                ["web/src/locales/en/messages.po", "web/src/locales/zh/messages.po"]
            )
            if catalog_changes:
                raise RuntimeError(
                    "Lingui catalogs changed during preflight. Review and commit "
                    "them, then rerun this command."
                )
            _run([_npm(), "run", "build"], cwd=ROOT / "web")

        if needs_miniapp_validation(paths):
            _run([_npm(), "run", "typecheck"], cwd=ROOT / "miniapp")

        if has_rendered_ui(paths):
            _run(
                [
                    sys.executable,
                    "scripts/check_ui_quality.py",
                    "--base",
                    args.base,
                    "--head",
                    args.head,
                    "--skip-evidence",
                ]
            )

        _run(["git", "diff", "--check", f"{args.base}...{args.head}"])
        dirty = _worktree_changes()
        if dirty:
            raise RuntimeError(
                "preflight left a dirty worktree:\n" + "\n".join(dirty)
            )
    except RuntimeError as exc:
        print(f"\nAgent preflight failed: {exc}", file=sys.stderr)
        return 1

    print("\nAgent preflight passed with a clean worktree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
