"""Regenerate gh-aw locks with the accepted compiler and info-artifact lifetime."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPILER_VERSION = "v0.89.21"
# Official github/gh-aw v0.89.21 linux-amd64 release asset and checksums.txt.
COMPILER_SHA256 = "1c74ff5fc28b1891d32b67f4348a9b7f750946b6d4a721e909187a848868016b"
WORKFLOWS = (
    "change-loop-outcomes",
    "change-loop-policy-tuner",
    "ci-failure-doctor",
    "praxys-invariant-review",
)
INFO_STEP = """      - name: Upload info artifact
        if: success() || failure()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: info
          path: /tmp/gh-aw/aw_info.json
          if-no-files-found: ignore
"""


def preserve_info_retention(source: str) -> str:
    """Limit the newly duplicated info artifact to the existing one-day lifetime."""
    document = yaml.load(source, Loader=yaml.BaseLoader)
    matches = [
        step for step in document["jobs"]["activation"]["steps"]
        if step.get("with", {}).get("name") == "info"
    ]
    if len(matches) != 1 or source.count(INFO_STEP) != 1:
        raise ValueError("Unexpected generated info upload; review the compiler contract")
    step = matches[0]
    expected = yaml.load(INFO_STEP, Loader=yaml.BaseLoader)[0]
    retention = step["with"].get("retention-days")
    if retention is not None:
        if retention != "1":
            raise ValueError("Unexpected info retention; review the compiler contract")
        expected["with"]["retention-days"] = "1"
    if step != expected:
        raise ValueError("Unexpected info upload structure; review the compiler contract")
    if retention == "1":
        return source
    return source.replace(INFO_STEP, INFO_STEP + "          retention-days: 1\n", 1)


def preserve_all_info_retention(paths: tuple[Path, ...]) -> None:
    """Validate every target before applying any retention adjustment."""
    replacements = [(path, preserve_info_retention(path.read_text())) for path in paths]
    for path, source in replacements:
        path.write_text(source)


def verify_compiler(compiler: Path) -> None:
    """Reject any binary other than the reviewed release before executing it."""
    if hashlib.sha256(compiler.read_bytes()).hexdigest() != COMPILER_SHA256:
        raise ValueError("Compiler digest differs from reviewed v0.89.21 linux-amd64")


def main() -> int:
    """Run strict upstream generation, then apply the single retention preservation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    verify_compiler(compiler)
    subprocess.run(
        [str(compiler), "compile", "--purge", "--no-check-update", "--strict",
         "--schedule-seed", "praxys-run/praxys"],
        cwd=ROOT, check=True, timeout=180,
    )
    paths = tuple(ROOT / ".github" / "workflows" / f"{name}.lock.yml" for name in WORKFLOWS)
    preserve_all_info_retention(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
