"""Rollout checks must reject healthy servers that still serve an old bundle."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_frontend_deployment as deployment

SHA = "a" * 40


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    assets = tmp_path / "assets" / "client"
    assets.mkdir(parents=True)
    (assets / "index-new.js").write_text("new application", encoding="utf-8")
    (tmp_path / "app-shell.html").write_text(
        '<script type="module" src="/assets/client/index-new.js"></script>',
        encoding="utf-8",
    )
    (tmp_path / "sw.js").write_text("new worker", encoding="utf-8")
    return tmp_path


def serve(dist: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict | None = None) -> list[str]:
    seen: list[str] = []

    def fetch(url: str, timeout: float) -> bytes:
        assert 0 < timeout <= 15
        seen.append(url)
        path = "/" + url.split("/", 3)[3]
        if overrides and path in overrides:
            return overrides[path]
        if path == "/healthz":
            return json.dumps({"ok": True, "deployed_sha": SHA}).encode()
        local = "app-shell.html" if path == "/settings" else path.lstrip("/")
        return (dist / local).read_bytes()

    monkeypatch.setattr(deployment, "fetch", fetch)
    return seen


def test_checks_running_code_and_bundle_at_origin_apex_and_www(dist, monkeypatch):
    seen = serve(dist, monkeypatch)
    evidence = deployment.verify(dist, SHA)
    assert evidence["status"] == "success"
    assert [check["url"] for check in evidence["checks"]] == list(deployment.BASE_URLS)
    for url in deployment.BASE_URLS:
        assert url + "/healthz" in seen
        assert url + "/settings" in seen
        assert url + "/sw.js" in seen
        assert url + "/assets/client/index-new.js" in seen


@pytest.mark.parametrize("path", ["/settings", "/sw.js", "/assets/client/index-new.js"])
def test_current_health_does_not_hide_stale_documents_or_resources(dist, monkeypatch, path):
    serve(dist, monkeypatch, {path: b"old bundle"})
    result = deployment.probe(deployment.BASE_URLS[0], SHA, deployment.expected_resources(dist), float("inf"))
    assert result["matched"] is False
    assert result["observedSha"] == SHA
    assert result["error"] == "served resource does not match package"
    assert result["resources"][path]["observed"] != result["resources"][path]["expected"]


@pytest.mark.parametrize("health", [b"not json", b"[]", b'{"ok":true}', b'{"ok":true,"deployed_sha":"old"}'])
def test_malformed_missing_or_old_health_is_not_accepted(dist, monkeypatch, health):
    serve(dist, monkeypatch, {"/healthz": health})
    result = deployment.probe(deployment.BASE_URLS[0], SHA, deployment.expected_resources(dist), float("inf"))
    assert result["matched"] is False


def test_startup_can_settle_after_old_two_minute_window(dist, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(deployment.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(deployment.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    def probe(url, source_sha, resources, deadline):
        return {"url": url, "matched": clock[0] >= 240, "observedSha": source_sha if clock[0] >= 240 else "old"}

    monkeypatch.setattr(deployment, "probe", probe)
    evidence = deployment.verify(dist, SHA, timeout=600)
    assert evidence["status"] == "success"
    assert clock[0] == 240
    assert evidence["attempts"][0]["checks"][0]["matched"] is False
    assert evidence["attempts"][-1]["checks"][0]["matched"] is True


def test_deadline_retains_failure_evidence(dist, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(deployment.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(deployment.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(deployment, "probe", lambda url, *args: {"url": url, "matched": False, "observedSha": "old"})
    evidence = deployment.verify(dist, SHA, timeout=25)
    assert evidence["status"] == "failure"
    assert clock[0] == 25
    assert all(check["observedSha"] == "old" for check in evidence["checks"])


def test_network_failures_produce_evidence(dist, monkeypatch):
    def fail(*args):
        raise TimeoutError("network")
    monkeypatch.setattr(deployment, "fetch", fail)
    result = deployment.probe(deployment.BASE_URLS[0], SHA, deployment.expected_resources(dist), float("inf"))
    assert result["matched"] is False
    assert result["error"] == "TimeoutError"
