"""Minimal GitHub Issues REST client for the feedback triage pipeline.

Why a hand-rolled client instead of PyGithub: we make exactly one call
(create an issue) against one repo, already depend on ``httpx``, and want to
avoid pulling a new dependency into ``requirements.txt`` for a single POST.

Configuration (all optional — when unset, issue creation is skipped and the
feedback row stays at ``triaged`` for manual admin promotion):

- ``PRAXYS_GITHUB_TOKEN`` — a fine-grained PAT (or GitHub App installation
  token) with ``issues:write`` on the target repo. Treated as a secret.
- ``PRAXYS_FEEDBACK_GITHUB_REPO`` — ``owner/repo`` of the triage repo. Because
  the main repo is public, operators are encouraged to point this at a
  PRIVATE triage repo so even scrubbed reports aren't world-readable.
- ``PRAXYS_FEEDBACK_GITHUB_LABELS`` — comma-separated labels added to every
  issue *in addition* to the per-kind label (e.g. a label your coding-agent
  automation watches). Optional.
- ``PRAXYS_FEEDBACK_GITHUB_ASSIGNEES`` — comma-separated logins to assign
  (e.g. the GitHub Copilot coding-agent bot login, once enabled on the repo).
  Optional.

Nothing here raises to the caller: a GitHub outage must not turn into a
500 on the user's submit or an unhandled exception in a background task.
Failures return ``None`` (or are logged) so the triage step can mark the row
``failed`` and an admin can retry.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_TIMEOUT_S = 15.0


def _token() -> str | None:
    return os.environ.get("PRAXYS_GITHUB_TOKEN") or None


def _repo() -> str | None:
    return os.environ.get("PRAXYS_FEEDBACK_GITHUB_REPO") or None


def is_configured() -> bool:
    """True iff both a token and a target repo are set."""
    return bool(_token() and _repo())


def _csv_env(name: str) -> list[str]:
    """Parse a comma-separated env var into a trimmed, non-empty list."""
    raw = os.environ.get(name, "") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def extra_labels() -> list[str]:
    """Operator-configured labels added to every feedback issue."""
    return _csv_env("PRAXYS_FEEDBACK_GITHUB_LABELS")


def assignees() -> list[str]:
    """Operator-configured assignees (e.g. the coding-agent bot login)."""
    return _csv_env("PRAXYS_FEEDBACK_GITHUB_ASSIGNEES")


def create_issue(
    *,
    title: str,
    body: str,
    labels: list[str] | None = None,
    assignees_override: list[str] | None = None,
) -> dict | None:
    """Create a GitHub issue and return ``{"number", "url"}`` or ``None``.

    ``None`` is returned (and the cause logged) when GitHub isn't configured or
    the API call fails for any reason. Callers must treat ``None`` as
    "not published" and persist a retryable state.
    """
    token, repo = _token(), _repo()
    if not token or not repo:
        logger.info("GitHub issue creation skipped — PRAXYS_GITHUB_TOKEN / "
                    "PRAXYS_FEEDBACK_GITHUB_REPO not configured")
        return None

    payload: dict = {"title": title[:256], "body": body}
    all_labels = list(labels or []) + extra_labels()
    if all_labels:
        # De-dupe while preserving order.
        payload["labels"] = list(dict.fromkeys(all_labels))
    who = assignees_override if assignees_override is not None else assignees()
    if who:
        payload["assignees"] = who

    url = f"{_API_ROOT}/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "praxys-feedback",
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=_TIMEOUT_S)
    except httpx.HTTPError as exc:
        logger.warning("GitHub issue creation failed (network): %s", exc)
        return None

    if resp.status_code not in (200, 201):
        # Don't log the response body verbatim at INFO — it can echo the
        # submitted title. Status + a short reason is enough for operators.
        logger.warning(
            "GitHub issue creation failed: HTTP %s (%s)",
            resp.status_code, resp.reason_phrase,
        )
        return None

    data = resp.json()
    return {"number": data.get("number"), "url": data.get("html_url")}
