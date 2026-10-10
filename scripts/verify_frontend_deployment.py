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
from urllib.error import HTTPError
from urllib.parse import urlsplit

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


class _DocumentFingerprint(HTMLParser):
    """Preserve application HTML while allowing the known edge beacon."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple] = []
        self.beacon = False
        self.raw_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        source = urlsplit(values.get("src") or "")
        allowed = {"src", "type", "integrity", "data-cf-beacon", "crossorigin", "async", "defer"}
        if (tag == "script" and source.scheme == "https"
                and source.netloc == "static.cloudflareinsights.com"
                and re.fullmatch(r"/beacon\.min\.js(?:/[A-Za-z0-9]+)?", source.path)
                and not source.query and not source.fragment
                and "data-cf-beacon" in values and set(values) <= allowed
                and len(values) == len(attrs)):
            self.beacon = True
            return
        self.events.append(("start", tag, sorted(attrs, key=lambda item: (item[0], item[1] or ""))))
        if tag in {"script", "style", "pre", "textarea"}:
            self.raw_text.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.append(("empty", tag, sorted(attrs, key=lambda item: (item[0], item[1] or ""))))

    def handle_endtag(self, tag: str) -> None:
        if self.beacon and tag == "script":
            self.beacon = False
            return
        self.events.append(("end", tag))
        if self.raw_text and self.raw_text[-1] == tag:
            self.raw_text.pop()

    def handle_data(self, data: str) -> None:
        if self.beacon:
            if data.strip():
                raise ValueError("edge beacon contains unexpected inline code")
            return
        # Only inter-element indentation is cosmetic. Preserve application
        # text, theme scripts and preformatted content byte for byte.
        if not self.raw_text and not data.strip() and "\n" in data:
            return
        self.events.append(("data", data))

    def handle_comment(self, data: str) -> None:
        self.events.append(("comment", data))

    def handle_decl(self, decl: str) -> None:
        self.events.append(("decl", decl))


def resource_fingerprint(path: str, body: bytes) -> str:
    """Fingerprint HTML structure or exact executable-resource bytes."""
    if path == "/settings":
        document = _DocumentFingerprint()
        document.feed(body.decode("utf-8"))
        document.close()
        if document.beacon:
            raise ValueError("unterminated edge beacon")
        body = json.dumps(document.events, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def expected_resources(dist: Path) -> dict[str, str]:
    """Fingerprint the app document, its bootstrap, and update authority."""
    shell = dist / "app-shell.html"
    entry = _AppEntry()
    entry.feed(shell.read_text(encoding="utf-8"))
    if len(entry.scripts) != 1 or ".." in entry.scripts[0].split("/"):
        raise ValueError("package must have one local application bootstrap")
    paths = {"/settings": shell, "/sw.js": dist / "sw.js"}
    paths[entry.scripts[0]] = dist / entry.scripts[0].lstrip("/")
    return {url: resource_fingerprint(url, path.read_bytes()) for url, path in paths.items()}


def fetch(url: str, timeout: float) -> bytes:
    """Read public deployment resources without using cached responses."""
    request = Request(url, headers={
        "Cache-Control": "no-cache",
        "User-Agent": "Praxys-Deployment-Monitor/1.0",
    })
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def probe(base_url: str, source_sha: str, resources: dict[str, str], deadline: float) -> dict:
    """Return bounded, non-sensitive evidence for one frontend origin."""
    result: dict = {"url": base_url, "matched": False, "resources": {}}
    try:
        def read(path: str) -> bytes:
            result["requestedPath"] = path
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
            actual = resource_fingerprint(path, read(path))
            result["resources"][path] = {"expected": expected, "observed": actual}
            if actual != expected:
                result["error"] = "served resource does not match package"
                return result
        result["matched"] = True
    except HTTPError as exc:
        result["error"] = "HTTPError"
        result["httpStatus"] = exc.code
    except (OSError, ValueError, TimeoutError) as exc:
        result["error"] = type(exc).__name__
    return result


def verify(dist: Path, source_sha: str, timeout: float = 600) -> dict:
    """Wait up to ten minutes for App Service startup and public readback."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or timeout <= 0:
        raise ValueError("a full source SHA and positive timeout are required")
    resources = expected_resources(dist)
    deadline = time.monotonic() + timeout
    evidence: dict = {"sourceSha": source_sha, "status": "failure", "checks": [], "attempts": []}
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        # Repeat every origin together so success describes one observed release.
        evidence["checks"] = [probe(url, source_sha, resources, deadline) for url in BASE_URLS]
        evidence["attempts"].append({"attempt": attempt, "checks": evidence["checks"]})
        if all(check["matched"] for check in evidence["checks"]):
            evidence["status"] = "success"
        print(json.dumps({"attempt": attempt, "sourceSha": source_sha,
                          "status": evidence["status"], "checks": evidence["checks"]}), flush=True)
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
