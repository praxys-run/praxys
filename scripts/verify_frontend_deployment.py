"""Wait for the running frontend and served app bundle to match its package."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

BASE_URLS = (
    "https://praxys-frontend.azurewebsites.net",
    "https://praxys.run",
    "https://www.praxys.run",
)


class _AppEntry(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        source = values.get("src", "") or ""
        if tag == "script" and source.startswith("/assets/"):
            self.scripts.append(source)


def expected_resources(dist: Path) -> dict[str, str]:
    """Fingerprint the app document, its bootstrap, and update authority."""
    shell = dist / "app-shell.html"
    entry = _AppEntry()
    entry.feed(shell.read_text(encoding="utf-8"))
    if len(entry.scripts) != 1 or ".." in entry.scripts[0].split("/"):
        raise ValueError("package must have one local application bootstrap")
    paths = {"/settings": shell, "/sw.js": dist / "sw.js"}
    paths[entry.scripts[0]] = dist / entry.scripts[0].lstrip("/")
    return {url: hashlib.sha256(path.read_bytes()).hexdigest() for url, path in paths.items()}


def fetch(url: str, timeout: float) -> bytes:
    """Read public deployment resources without using cached responses."""
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def probe(base_url: str, source_sha: str, resources: dict[str, str], deadline: float) -> dict:
    """Return bounded, non-sensitive evidence for one frontend origin."""
    result: dict = {"url": base_url, "matched": False, "resources": {}}
    try:
        def read(path: str) -> bytes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("verification deadline exceeded")
            return fetch(base_url + path, min(15, remaining))

        health = json.loads(read("/healthz"))
        observed = health.get("deployed_sha") if isinstance(health, dict) else None
        result["observedSha"] = observed
        if not isinstance(health, dict) or health.get("ok") is not True or observed != source_sha:
            result["error"] = "running version does not match package"
            return result
        for path, expected in resources.items():
            actual = hashlib.sha256(read(path)).hexdigest()
            result["resources"][path] = {"expected": expected, "observed": actual}
            if actual != expected:
                result["error"] = "served resource does not match package"
                return result
        result["matched"] = True
    except (OSError, ValueError, TimeoutError) as exc:
        result["error"] = type(exc).__name__
    return result


def verify(dist: Path, source_sha: str, timeout: float = 600) -> dict:
    """Wait up to ten minutes for App Service startup and public readback."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or timeout <= 0:
        raise ValueError("a full source SHA and positive timeout are required")
    resources = expected_resources(dist)
    deadline = time.monotonic() + timeout
    evidence: dict = {"sourceSha": source_sha, "status": "failure", "checks": []}
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        # Repeat every origin together so success describes one observed release.
        evidence["checks"] = [probe(url, source_sha, resources, deadline) for url in BASE_URLS]
        if all(check["matched"] for check in evidence["checks"]):
            evidence["status"] = "success"
        print(json.dumps({"attempt": attempt, **evidence}), flush=True)
        if evidence["status"] == "success":
            break
        time.sleep(min(10, max(0, deadline - time.monotonic())))
    return evidence


def main() -> int:
    """Write verification evidence even when the rollout fails to settle."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    evidence = verify(args.dist, args.source_sha, args.timeout)
    args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
