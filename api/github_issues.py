"""Typed GitHub Issues client for consent-bound feedback publication.

The client creates issues only in the fixed public repository
``praxys-run/praxys`` and reconciles ambiguous sends by an exact opaque marker.
It uses ``httpx`` directly to avoid adding a GitHub SDK dependency.

Configuration is optional and fail-closed: when credentials, the exact
repository setting, or publication authority are absent, no request is sent.

Auth uses a **GitHub App** (no token to rotate): ``PRAXYS_GITHUB_APP_ID`` +
``PRAXYS_GITHUB_APP_INSTALLATION_ID`` + ``PRAXYS_GITHUB_APP_PRIVATE_KEY`` (PEM).
We sign a short-lived JWT, exchange it for a ~1h installation token, and cache
it. The app needs *Issues: write* and *Pull requests: read* on the target repo.
The latter is used only to reconcile closing-PR outcome metadata. Setup:
``docs/ops/setup-github-app.md``.

- ``PRAXYS_FEEDBACK_GITHUB_REPO`` — must equal ``praxys-run/praxys``.
- ``PRAXYS_FEEDBACK_GITHUB_LABELS`` — comma-separated labels added to every
  issue *in addition* to the per-kind label (e.g. a label your coding-agent
  automation watches). Optional.
- ``PRAXYS_FEEDBACK_GITHUB_ASSIGNEES`` — comma-separated logins to assign
  (e.g. the GitHub Copilot coding-agent bot login, once enabled on the repo).
  Optional.

Create and reconciliation calls return bounded typed outcomes. Ambiguous
provider results remain unknown for marker-only reconciliation and are never
blindly re-sent.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from typing import Literal, TypedDict
from urllib.parse import quote, urlsplit

import httpx

from api.optional_processing import (
    feedback_publication_disabled,
    feedback_publication_switch_status,
)

logger = logging.getLogger(__name__)

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_TIMEOUT_S = 15.0
FEEDBACK_REPOSITORY = "praxys-run/praxys"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class IssueCreateOutcome(TypedDict):
    """Bounded result of a single GitHub issue POST."""

    outcome: Literal["created", "not_sent", "rejected", "unknown"]
    number: int | None
    url: str | None
    http_status: int | None
    error_code: str | None


class IssueReconcileOutcome(TypedDict):
    """Bounded exact-marker reconciliation result."""

    outcome: Literal["reconciled", "unknown", "multiple", "provider_failure"]
    number: int | None
    url: str | None
    http_status: int | None
    error_code: str | None


def _repo() -> str | None:
    raw = (os.environ.get("PRAXYS_FEEDBACK_GITHUB_REPO") or "").strip()
    return FEEDBACK_REPOSITORY if raw == FEEDBACK_REPOSITORY else None


# --- GitHub App auth (preferred — no token to rotate) ----------------------

def _app_id() -> str | None:
    return os.environ.get("PRAXYS_GITHUB_APP_ID") or None


def _configured_app_id() -> int | None:
    """Return only a canonical positive decimal GitHub App identifier."""
    raw = _app_id()
    if not raw or not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if value > 0 and str(value) == raw else None


def _app_installation_id() -> str | None:
    return os.environ.get("PRAXYS_GITHUB_APP_INSTALLATION_ID") or None


def _app_private_key() -> str | None:
    raw = os.environ.get("PRAXYS_GITHUB_APP_PRIVATE_KEY") or None
    # App Service settings commonly hold the PEM single-line with literal "\n";
    # restore real newlines. A no-op on PEMs that already have newlines.
    return raw.replace("\\n", "\n") if raw else None


def _app_configured() -> bool:
    return bool(
        _configured_app_id()
        and _app_installation_id()
        and _app_private_key()
    )


def credential_config_status() -> dict[str, bool]:
    """Return non-secret GitHub App configuration presence."""
    return {
        "app_id_present": bool(_app_id()),
        "installation_id_present": bool(_app_installation_id()),
        "private_key_present": bool(_app_private_key()),
        "credentials_present": _app_configured(),
    }


def publication_readiness() -> dict[str, bool | str]:
    """Return a private, metadata-only publication readiness snapshot."""
    switches = feedback_publication_switch_status()
    credentials = credential_config_status()
    repo_valid = _repo() == FEEDBACK_REPOSITORY
    effective = bool(
        switches["effective"]
        and repo_valid
        and credentials["credentials_present"]
    )
    if not switches["config_valid"] or not switches["positive_enable"] or not repo_valid:
        reason = "policy_disabled"
    elif switches["kill_switch"]:
        reason = "emergency_stop"
    elif not credentials["credentials_present"]:
        reason = "credentials_missing"
    else:
        reason = "ready"
    return {
        **switches,
        **credentials,
        "repository_valid": repo_valid,
        "target_repository": FEEDBACK_REPOSITORY,
        "effective": effective,
        "reason": reason,
    }


# Cache the minted installation token until shortly before it expires (~1h
# lifetime) so we don't re-mint on every issue. Cleared by tests.
_install_token: dict = {"token": None, "exp": 0.0}


def _app_jwt() -> str | None:
    """Short-lived RS256 JWT authenticating AS the GitHub App."""
    try:
        import jwt  # PyJWT — already a dependency (see api/auth.py)
    except ImportError:  # pragma: no cover
        logger.warning("PyJWT missing — GitHub App auth unavailable")
        return None
    import time

    app_id, key = _app_id(), _app_private_key()
    if not app_id or not key:
        return None
    now = int(time.time())
    # iat backdated 60s for clock skew; exp must be <= 10 min per GitHub.
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": app_id}
    try:
        return jwt.encode(payload, key, algorithm="RS256")
    except Exception:
        logger.warning("GitHub App JWT signing failed")
        return None


def _mint_installation_token() -> str | None:
    """Exchange the app JWT for a ~1h installation access token, and cache it."""
    import time
    from datetime import datetime

    app_jwt = _app_jwt()
    installation_id = _app_installation_id()
    if not app_jwt or not installation_id:
        return None
    url = f"{_API_ROOT}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "praxys-feedback",
    }
    try:
        resp = httpx.post(url, headers=headers, timeout=_TIMEOUT_S)
    except httpx.HTTPError:
        logger.warning("GitHub App token mint failed during provider request")
        return None
    if resp.status_code != 201:
        logger.warning("GitHub App token mint rejected by provider")
        return None
    # Parse once; a malformed-but-201 body must degrade to None (the module
    # contract is "never raise to the caller" — the admin approve route calls
    # create_issue without its own guard around the mint).
    try:
        data = resp.json() or {}
    except Exception:
        logger.warning("GitHub App token mint returned a non-JSON 201 body")
        return None
    token = data.get("token")
    if not token:
        return None
    # Refresh 5 min before the stated expiry; fall back to ~50 min.
    exp_epoch = time.time() + 3000
    try:
        exp_str = data.get("expires_at")
        if exp_str:
            exp_epoch = datetime.fromisoformat(exp_str.replace("Z", "+00:00")).timestamp() - 300
    except Exception:
        pass
    _install_token["token"] = token
    _install_token["exp"] = exp_epoch
    return token


def _bearer_token() -> str | None:
    """Return a cached/auto-minted GitHub App installation token, or ``None``.

    No rotation: the token lives ~1h and is re-minted on demand just before it
    expires. ``None`` when the GitHub App isn't configured.
    """
    if not _app_configured():
        return None
    import time

    cached = _install_token["token"]
    if cached and _install_token["exp"] > time.time():
        return cached
    return _mint_installation_token()


def is_configured() -> bool:
    """Return whether external feedback publication is configured and allowed."""
    return bool(publication_readiness()["effective"])


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


def create_issue_outcome(
    *,
    title: str,
    body: str,
    labels: list[str] | None = None,
    assignees_override: list[str] | None = None,
    publication_authorized: bool = False,
) -> IssueCreateOutcome:
    """POST one issue and classify ambiguous outcomes without retrying them."""
    if feedback_publication_disabled() or not publication_authorized:
        logger.info(
            "GitHub issue creation skipped — publication disabled or unauthorized"
        )
        return {
            "outcome": "not_sent",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "publication_not_authorized",
        }

    token, repo = _bearer_token(), _repo()
    if not token or not repo:
        logger.info("GitHub issue creation skipped — GitHub App not configured "
                    "or PRAXYS_FEEDBACK_GITHUB_REPO unset")
        return {
            "outcome": "not_sent",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "auth_missing",
        }

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
    except httpx.HTTPError:
        # The request may have left this process. Never ordinary-retry it.
        logger.warning("GitHub issue creation outcome is unknown (network)")
        return {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "network_unknown",
        }

    if resp.status_code >= 500:
        logger.warning(
            "GitHub issue creation outcome is unknown after provider error"
        )
        return {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": resp.status_code,
            "error_code": "provider_5xx",
        }
    if resp.status_code not in (200, 201):
        # Don't log the response body verbatim at INFO — it can echo the
        # submitted title. Status + a short reason is enough for operators.
        logger.warning("GitHub issue creation rejected by provider")
        return {
            "outcome": "rejected",
            "number": None,
            "url": None,
            "http_status": resp.status_code,
            "error_code": "provider_rejected",
        }

    try:
        data = resp.json() or {}
        number = int(data.get("number"))
        issue_url = str(data.get("html_url") or "")
    except (TypeError, ValueError):
        number = 0
        issue_url = ""
    if number < 1 or not issue_url_allowed(number, issue_url):
        logger.warning("GitHub issue creation returned malformed success metadata")
        return {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": resp.status_code,
            "error_code": "malformed_success",
        }
    return {
        "outcome": "created",
        "number": number,
        "url": issue_url,
        "http_status": resp.status_code,
        "error_code": None,
    }


def create_issue(
    *,
    title: str,
    body: str,
    labels: list[str] | None = None,
    assignees_override: list[str] | None = None,
    publication_authorized: bool = False,
) -> dict | None:
    """Compatibility adapter returning a link only for confirmed creation."""
    outcome = create_issue_outcome(
        title=title,
        body=body,
        labels=labels,
        assignees_override=assignees_override,
        publication_authorized=publication_authorized,
    )
    if outcome["outcome"] != "created":
        return None
    return {"number": outcome["number"], "url": outcome["url"]}


def issue_url_allowed(number: int, issue_url: str | None) -> bool:
    """Allow only the exact public feedback repository issue URL."""
    if not issue_url:
        return False
    parsed = urlsplit(issue_url)
    return (
        parsed.scheme == "https"
        and parsed.netloc.casefold() == "github.com"
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path.rstrip("/").casefold()
        == f"/{FEEDBACK_REPOSITORY}/issues/{number}".casefold()
    )


def public_issue_content_sha256(*, title: str, body: str) -> str:
    """Digest the exact public title/body without retaining either value."""
    canonical = json.dumps(
        {"body": body, "title": title},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def reconcile_issue_marker(
    marker: str,
    *,
    public_content_sha256: str,
) -> IssueReconcileOutcome:
    """Find one exact, content-bound non-PR issue marker."""
    if _SHA256_RE.fullmatch(public_content_sha256) is None:
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "invalid_content_binding",
        }
    token, repo = _bearer_token(), _repo()
    expected_app_id = _configured_app_id()
    if not token or not repo or expected_app_id is None:
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "auth_missing",
        }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "praxys-feedback",
    }
    try:
        response = httpx.get(
            f"{_API_ROOT}/search/issues",
            params={"q": f'"{marker}" repo:{repo} type:issue', "per_page": 100},
            headers=headers,
            timeout=_TIMEOUT_S,
        )
    except httpx.HTTPError:
        logger.warning("GitHub publication reconciliation failed (network)")
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "network_failure",
        }
    if response.status_code != 200:
        logger.warning("GitHub publication reconciliation rejected by provider")
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": response.status_code,
            "error_code": "provider_failure",
        }
    try:
        search_payload = response.json() or {}
    except Exception:
        search_payload = None
    if not isinstance(search_payload, dict):
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": response.status_code,
            "error_code": "malformed_response",
        }
    items = search_payload.get("items") or []
    incomplete_results = search_payload.get("incomplete_results")
    total_count = search_payload.get("total_count")
    malformed_completeness = (
        incomplete_results is not None
        and type(incomplete_results) is not bool
    ) or (
        total_count is not None
        and (type(total_count) is not int or total_count < 0)
    )
    if not isinstance(items, list) or malformed_completeness:
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": response.status_code,
            "error_code": "malformed_response",
        }
    if incomplete_results is True or (
        type(total_count) is int and total_count > len(items)
    ):
        return {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": response.status_code,
            "error_code": "incomplete_search_results",
        }
    matches: list[tuple[int, str]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("pull_request") is not None:
            continue
        try:
            number = int(item.get("number"))
        except (TypeError, ValueError):
            continue
        url = str(item.get("html_url") or "")
        title = item.get("title")
        body = item.get("body")
        performed_via = item.get("performed_via_github_app")
        performed_via_id = (
            performed_via.get("id")
            if isinstance(performed_via, dict)
            else None
        )
        if (
            isinstance(title, str)
            and isinstance(body, str)
            and body.count(marker) == 1
            and body.endswith("\n\n" + marker)
            and hmac.compare_digest(
                public_issue_content_sha256(title=title, body=body),
                public_content_sha256,
            )
            and issue_url_allowed(number, url)
            and type(performed_via_id) is int
            and performed_via_id == expected_app_id
        ):
            matches.append((number, url))
    if len(matches) == 1:
        number, url = matches[0]
        return {
            "outcome": "reconciled",
            "number": number,
            "url": url,
            "http_status": response.status_code,
            "error_code": None,
        }
    if len(matches) > 1:
        return {
            "outcome": "multiple",
            "number": None,
            "url": None,
            "http_status": response.status_code,
            "error_code": "multiple_matches",
        }
    # Search is eventually consistent: zero matches never proves no POST.
    return {
        "outcome": "unknown",
        "number": None,
        "url": None,
        "http_status": response.status_code,
        "error_code": "not_indexed_or_absent",
    }


def set_issue_label(number: int, label: str, *, present: bool) -> bool:
    """Add or remove one issue label, returning whether GitHub is in sync."""
    token, repo = _bearer_token(), _repo()
    if not token or not repo:
        logger.warning("GitHub issue label update skipped — App not configured")
        return False
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "praxys-feedback",
    }
    try:
        if present:
            resp = httpx.post(
                f"{_API_ROOT}/repos/{repo}/issues/{number}/labels",
                json={"labels": [label]},
                headers=headers,
                timeout=_TIMEOUT_S,
            )
            ok = resp.status_code == 200
        else:
            encoded = quote(label, safe="")
            resp = httpx.delete(
                f"{_API_ROOT}/repos/{repo}/issues/{number}/labels/{encoded}",
                headers=headers,
                timeout=_TIMEOUT_S,
            )
            ok = resp.status_code in (200, 204, 404)
    except httpx.HTTPError:
        logger.warning("GitHub issue label update failed during provider request")
        return False
    if not ok:
        logger.warning("GitHub issue label update rejected by provider")
    return ok


def issue_matches_configured_repo(
    number: int,
    issue_url: str | None,
) -> bool:
    """Return whether a stored GitHub issue URL matches the configured repo."""
    return _repo() == FEEDBACK_REPOSITORY and issue_url_allowed(
        number, issue_url
    )


def get_issue_state(number: int) -> dict | None:
    """Return a linked issue's current state, or ``None``.

    Used as a state-only fallback when the installation has not yet approved
    Pull requests read permission. Read-only and privacy-preserving: it reads
    only issue lifecycle fields — no user-submitted ticket text is parsed.
    ``None`` when GitHub isn't configured or the fetch fails.
    """
    token, repo = _bearer_token(), _repo()
    if not token or not repo:
        return None
    url = f"{_API_ROOT}/repos/{repo}/issues/{number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "praxys-feedback",
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT_S)
    except httpx.HTTPError:
        logger.warning("GitHub issue state fetch failed during provider request")
        return None
    if resp.status_code != 200:
        logger.warning("GitHub issue state fetch rejected by provider")
        return None
    try:
        data = resp.json() or {}
    except Exception:
        logger.warning("GitHub issue state fetch returned a non-JSON 200 body")
        return None
    state = data.get("state")
    if state not in ("open", "closed"):
        return None
    return {
        "state": state,
        "state_reason": data.get("state_reason"),
        "closed_at": data.get("closed_at"),
        "updated_at": data.get("updated_at"),
    }


def _state_only_outcome(number: int) -> dict | None:
    """Adapt the REST issue state response to the richer outcome contract."""
    state = get_issue_state(number)
    if state is None:
        return None
    return {
        **state,
        "agent_ready": False,
        "closing_pull_requests": [],
    }


def get_issue_outcome(number: int) -> dict | None:
    """Return issue state, labels, and closing-PR metadata without fetching text.

    The GraphQL selection deliberately excludes issue/PR titles, bodies, comments,
    authors, commits, and reviews. This gives the learning substrate durable
    outcome facts without copying user feedback back out of the public tracker.
    """
    token, repo = _bearer_token(), _repo()
    if not token or not repo or "/" not in repo:
        return None
    owner, name = repo.split("/", 1)
    query = """
    query FeedbackOutcome($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) {
          state
          stateReason
          closedAt
          updatedAt
          labels(first: 100) { nodes { name } }
          closedByPullRequestsReferences(first: 10) {
            nodes {
              number
              state
              isDraft
              merged
              updatedAt
              mergedAt
              closedAt
              url
            }
          }
        }
      }
    }
    """
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "praxys-feedback",
    }
    try:
        resp = httpx.post(
            f"{_API_ROOT}/graphql",
            json={
                "query": query,
                "variables": {
                    "owner": owner,
                    "name": name,
                    "number": number,
                },
            },
            headers=headers,
            timeout=_TIMEOUT_S,
        )
    except httpx.HTTPError:
        logger.warning("GitHub issue outcome fetch failed during provider request")
        return _state_only_outcome(number)
    if resp.status_code != 200:
        logger.warning("GitHub issue outcome fetch rejected by provider")
        return _state_only_outcome(number)
    try:
        payload = resp.json() or {}
    except Exception:
        logger.warning("GitHub issue outcome fetch returned a non-JSON 200 body")
        return _state_only_outcome(number)
    if payload.get("errors"):
        logger.warning(
            "GitHub issue outcome query returned GraphQL errors; "
            "falling back to issue state only"
        )
        return _state_only_outcome(number)
    issue = ((payload.get("data") or {}).get("repository") or {}).get("issue")
    if not isinstance(issue, dict):
        return _state_only_outcome(number)
    state = str(issue.get("state", "")).lower()
    if state not in ("open", "closed"):
        return _state_only_outcome(number)
    labels = sorted(
        str(node.get("name"))
        for node in ((issue.get("labels") or {}).get("nodes") or [])
        if isinstance(node, dict) and node.get("name")
    )
    pulls = []
    for pull in (
        (issue.get("closedByPullRequestsReferences") or {}).get("nodes") or []
    ):
        if not isinstance(pull, dict) or not pull.get("number"):
            continue
        pulls.append(
            {
                "number": int(pull["number"]),
                "state": str(pull.get("state", "")).lower(),
                "is_draft": bool(pull.get("isDraft")),
                "merged": bool(pull.get("merged")),
                "updated_at": pull.get("updatedAt"),
                "merged_at": pull.get("mergedAt"),
                "closed_at": pull.get("closedAt"),
                "url": pull.get("url"),
            }
        )
    state_reason = issue.get("stateReason")
    return {
        "state": state,
        "state_reason": str(state_reason).lower() if state_reason else None,
        "closed_at": issue.get("closedAt"),
        "updated_at": issue.get("updatedAt"),
        "agent_ready": "agent-ready" in labels,
        "closing_pull_requests": pulls,
    }
