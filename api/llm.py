"""Shared Azure OpenAI client + JSON-mode chat helper.

Auth uses DefaultAzureCredential, picking up `az login` locally or workload
identity / OIDC in cloud. No API key path. When `AZURE_AI_ENDPOINT` is unset
or the `openai` / `azure-identity` SDKs are missing, `get_client()`
returns None — callers report AI unavailability; deterministic metrics remain separate.

Two model deployment names are exposed:
- ``INSIGHT_MODEL`` (env ``PRAXYS_INSIGHT_MODEL``): reasoning model used by the
  post-sync insight generator. Default ``gpt-5.4``.
- ``TRANSLATE_MODEL`` (env ``TRANSLATE_MODEL``): smaller model used by the
  i18n translation script. Default ``gpt-5.4-mini``.

This module is the canonical place for Azure OpenAI auth scaffolding;
repository automation delegates to ``get_automation_client()`` so the
production emergency stop remains scoped to user-data processing.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import portalocker

logger = logging.getLogger(__name__)

INSIGHT_MODEL = os.environ.get("PRAXYS_INSIGHT_MODEL", "gpt-5.4")
TRANSLATE_MODEL = os.environ.get("TRANSLATE_MODEL", "gpt-5.4-mini")
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
_provider_health_lock = threading.Lock()
_provider_failure_active = False
_PROVIDER_STATE_DIR = ".runtime_state"
_PROVIDER_HEALTH_STATE = "azure_ai_provider_health.json"
_PROVIDER_HEALTH_LOCK = "azure_ai_provider_health.lock"
_PROVIDER_FAIL_CLOSED_STATE = "azure_ai_provider_fail_closed.json"
_PROVIDER_FAIL_CLOSED_LOCK = "azure_ai_provider_fail_closed.lock"


@dataclass(frozen=True)
class RuntimeProviderAttempt:
    """Failure epoch observed immediately before one provider request."""

    failure_epoch: str | None


@lru_cache(maxsize=1)
def _get_cached_client() -> Any | None:
    """Return an AzureOpenAI client or None when unavailable.

    Returns None (rather than raising) when:
    - The ``openai`` or ``azure-identity`` SDKs are not installed.
    - The ``AZURE_AI_ENDPOINT`` env var is unset.

    Both unavailable paths log once at module-call time so operators see the
    AI-tier state in deploy logs (otherwise a missing SDK or unset endpoint
    silently disables AI insights for the lifetime of the process).

    The result is memoised at process scope.
    """
    try:
        from openai import AzureOpenAI  # type: ignore[import-not-found]
        from azure.identity import (  # type: ignore[import-not-found]
            DefaultAzureCredential,
            get_bearer_token_provider,
        )
    except ImportError as e:
        logger.warning(
            "Azure OpenAI SDK missing — AI insights unavailable (%s)", e
        )
        return None
    endpoint = os.environ.get("AZURE_AI_ENDPOINT")
    if not endpoint:
        logger.info(
            "AZURE_AI_ENDPOINT unset — AI insights unavailable"
        )
        return None
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    logger.info(
        "Azure OpenAI client initialised: endpoint=%s api_version=%s "
        "insight_model=%s translate_model=%s",
        endpoint, API_VERSION, INSIGHT_MODEL, TRANSLATE_MODEL,
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=API_VERSION,
        azure_ad_token_provider=token_provider,
    )


def get_client() -> Any | None:
    """Return the cached client unless the emergency switch is active."""
    from api.optional_processing import background_ai_disabled

    if background_ai_disabled():
        logger.info("Azure AI emergency stop active — AI unavailable")
        return None
    return _get_cached_client()


def get_automation_client() -> Any | None:
    """Return the client for repository automation that uses no user data.

    Translation and privacy-reviewed synthetic evaluations must remain
    independent from the production user-data emergency stop. They still
    require the same Azure endpoint, workload identity, and SDK dependencies.
    """
    return _get_cached_client()


def record_runtime_provider_failure() -> None:
    """Mark the shared runtime provider unavailable until confirmed recovery."""
    global _provider_failure_active
    with _provider_health_lock:
        try:
            (
                state_path,
                lock_path,
                fail_closed_path,
                fail_closed_lock_path,
            ) = _provider_health_paths()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(
                str(lock_path),
                mode="a",
                timeout=5.0,
            ), portalocker.Lock(
                str(fail_closed_lock_path),
                mode="a",
                timeout=5.0,
            ):
                _write_provider_health_state(
                    state_path,
                    failure_epoch=uuid.uuid4().hex,
                    failure_active=True,
                )
                fail_closed_path.unlink(missing_ok=True)
            _provider_failure_active = False
        except (OSError, ValueError, portalocker.exceptions.LockException):
            _latch_provider_state_io_failure()
            logger.exception(
                "Unable to persist Azure AI provider failure; failing closed"
            )


def begin_runtime_provider_attempt() -> RuntimeProviderAttempt | None:
    """Capture the shared failure epoch before a provider request starts."""
    global _provider_failure_active
    with _provider_health_lock:
        try:
            (
                state_path,
                lock_path,
                fail_closed_path,
                fail_closed_lock_path,
            ) = _provider_health_paths()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(
                str(lock_path),
                mode="a",
                timeout=5.0,
            ), portalocker.Lock(
                str(fail_closed_lock_path),
                mode="a",
                timeout=5.0,
            ):
                failure_epoch, _failure_active = (
                    _read_effective_provider_health_state(
                        state_path,
                        fail_closed_path,
                    )
                )
            return RuntimeProviderAttempt(failure_epoch=failure_epoch)
        except (OSError, ValueError, portalocker.exceptions.LockException):
            _latch_provider_state_io_failure()
            logger.exception(
                "Unable to read Azure AI provider health; failing closed"
            )
            return None


def record_runtime_provider_success(
    attempt: RuntimeProviderAttempt | None,
) -> bool:
    """Clear only the failure epoch observed by this successful request."""
    global _provider_failure_active
    if attempt is None:
        with _provider_health_lock:
            if _provider_failure_active:
                _latch_provider_state_io_failure()
        return False
    with _provider_health_lock:
        try:
            (
                state_path,
                lock_path,
                fail_closed_path,
                fail_closed_lock_path,
            ) = _provider_health_paths()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(
                str(lock_path),
                mode="a",
                timeout=5.0,
            ), portalocker.Lock(
                str(fail_closed_lock_path),
                mode="a",
                timeout=5.0,
            ):
                current_epoch, current_active = (
                    _read_effective_provider_health_state(
                        state_path,
                        fail_closed_path,
                    )
                )
                if current_epoch == attempt.failure_epoch:
                    _write_provider_health_state(
                        state_path,
                        failure_epoch=current_epoch,
                        failure_active=False,
                    )
                    fail_closed_path.unlink(missing_ok=True)
                    current_active = False
            _provider_failure_active = False
            return not current_active
        except (OSError, ValueError, portalocker.exceptions.LockException):
            _latch_provider_state_io_failure()
            logger.exception(
                "Unable to persist Azure AI provider recovery; failing closed"
            )
            return False


def _provider_health_paths() -> tuple[Path, Path, Path, Path]:
    """Return the provider state plus primary and fail-closed lock paths."""
    from db.session import get_data_dir

    state_dir = Path(get_data_dir()).resolve() / _PROVIDER_STATE_DIR
    return (
        state_dir / _PROVIDER_HEALTH_STATE,
        state_dir / _PROVIDER_HEALTH_LOCK,
        state_dir / _PROVIDER_FAIL_CLOSED_STATE,
        state_dir / _PROVIDER_FAIL_CLOSED_LOCK,
    )


def _read_provider_health_state(state_path: Path) -> tuple[str | None, bool]:
    """Read and validate the provider-health state while its lock is held."""
    if not state_path.exists():
        return None, False
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("provider health state must be an object")
    failure_epoch = payload.get("failure_epoch")
    failure_active = payload.get("failure_active")
    if failure_epoch is not None and not isinstance(failure_epoch, str):
        raise ValueError("provider failure epoch must be a string or null")
    if not isinstance(failure_active, bool):
        raise ValueError("provider failure state must be boolean")
    if failure_active and not failure_epoch:
        raise ValueError("active provider failure requires an epoch")
    return failure_epoch, failure_active


def _read_effective_provider_health_state(
    state_path: Path,
    fail_closed_path: Path,
) -> tuple[str | None, bool]:
    """Prefer the independent fail-closed epoch when it exists."""
    if fail_closed_path.exists():
        payload = json.loads(fail_closed_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("provider fail-closed state must be an object")
        failure_epoch = payload.get("failure_epoch")
        if not isinstance(failure_epoch, str) or not failure_epoch:
            raise ValueError("provider fail-closed epoch must be a string")
        return failure_epoch, True
    return _read_provider_health_state(state_path)


def _write_provider_health_state(
    state_path: Path,
    *,
    failure_epoch: str | None,
    failure_active: bool,
) -> None:
    """Atomically write provider health while its cross-process lock is held."""
    temporary = state_path.with_name(
        f"{state_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps(
                {
                    "failure_epoch": failure_epoch,
                    "failure_active": failure_active,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, state_path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_provider_fail_closed_state(fail_closed_path: Path) -> None:
    """Write a lock-independent shared failure epoch after state I/O errors."""
    temporary = fail_closed_path.with_name(
        f"{fail_closed_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps({"failure_epoch": uuid.uuid4().hex}),
            encoding="utf-8",
        )
        os.replace(temporary, fail_closed_path)
    finally:
        temporary.unlink(missing_ok=True)


def _latch_provider_state_io_failure() -> None:
    """Fail closed locally and through an independently written shared epoch."""
    global _provider_failure_active
    _provider_failure_active = True
    try:
        (
            _state_path,
            _lock_path,
            fail_closed_path,
            fail_closed_lock_path,
        ) = _provider_health_paths()
        fail_closed_path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(
            str(fail_closed_lock_path),
            mode="a",
            timeout=5.0,
        ):
            _write_provider_fail_closed_state(fail_closed_path)
        _provider_failure_active = False
    except (OSError, portalocker.exceptions.LockException):
        logger.exception(
            "Unable to persist shared Azure AI fail-closed state"
        )


def runtime_ai_available() -> bool:
    """Return best-effort provider availability without probing Azure.

    The result combines the emergency stop, local client configuration, and a
    latched failure state after authentication, rate-limit, transport, or
    provider failures. Only a successful model response clears that state.
    """
    if get_client() is None:
        return False
    with _provider_health_lock:
        if _provider_failure_active:
            _latch_provider_state_io_failure()
            if _provider_failure_active:
                return False
        try:
            (
                state_path,
                lock_path,
                fail_closed_path,
                fail_closed_lock_path,
            ) = _provider_health_paths()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(
                str(lock_path),
                mode="a",
                timeout=1.0,
            ), portalocker.Lock(
                str(fail_closed_lock_path),
                mode="a",
                timeout=1.0,
            ):
                _failure_epoch, failure_active = (
                    _read_effective_provider_health_state(
                        state_path,
                        fail_closed_path,
                    )
                )
            return not failure_active
        except (OSError, ValueError, portalocker.exceptions.LockException):
            _latch_provider_state_io_failure()
            logger.exception(
                "Unable to read Azure AI provider health; failing closed"
            )
            return False


# Preserve the established test/configuration cache-reset API.
get_client.cache_clear = _get_cached_client.cache_clear  # type: ignore[attr-defined]


def chat_json(
    client: Any,
    *,
    system: str,
    user: str,
    model: str,
    max_completion_tokens: int = 4096,
    temperature: float = 0.3,
    retry: int = 1,
    insight_type: str | None = None,
    images: list[str] | None = None,
) -> dict | None:
    """Strict JSON chat completion. Returns parsed dict or None on failure.

    Uses ``response_format={"type": "json_object"}`` so the model is
    constrained to emit a JSON object.

    ``images`` (optional) is a list of image data URLs
    (``data:image/png;base64,...``). When present the user turn is sent as a
    multimodal content array (text + image parts) for vision models — used by
    the feedback screenshot triage. The chosen ``model`` must be vision-capable.

    Failure handling distinguishes operator-actionable errors (auth misconfig,
    bad request — logged at ERROR, no retry) from transient errors (rate
    limit, transient API error, JSON decode — logged at WARNING and retried).
    Returns None in either case so callers expose AI unavailability; separately
    labelled deterministic functionality may continue, but is never AI output.
    Distinct log levels let alerting route operator-actionable failures
    differently from noisy transient ones.

    ``insight_type`` is forwarded to telemetry — when set, per-call token
    usage and operator-actionable errors are dimensioned by it so daily
    spend and Auth-error spikes are queryable per Coach surface in App
    Insights. Defaults to ``"unknown"`` so future non-Coach callers still
    emit metrics, just without per-surface breakdown.

    Token telemetry note: ``record_coach_tokens`` fires once per Azure API
    call that returns a usage payload, *before* the JSON parse. Retries
    triggered by ``JSONDecodeError`` therefore double-record — but that
    matches Azure's per-call billing (both attempts cost real tokens), so
    operators tracking spend see honest numbers rather than insight-success
    rate.
    """
    from api import telemetry

    itype = insight_type or "unknown"

    # SDK exception classes — imported here so this module stays importable
    # without the openai SDK (chat_json is unreachable in that case because
    # ``get_client`` returns None first). When the SDK is missing we still
    # need real BaseException subclasses in the ``except`` clauses below;
    # falling back to ``()`` made Python reject the tuple at runtime
    # ("catching classes that do not inherit from BaseException").
    try:
        from openai import (  # type: ignore[import-not-found]
            APIError,
            AuthenticationError,
            BadRequestError,
            RateLimitError,
        )
    except ImportError:  # pragma: no cover — get_client returns None first
        class _SdkUnavailable(BaseException):
            """Sentinel that never matches — keeps except clauses syntactically valid."""

        AuthenticationError = BadRequestError = RateLimitError = APIError = _SdkUnavailable  # type: ignore[assignment]

    # When images are supplied (feedback screenshot vision triage), the user
    # turn becomes a multimodal content array: the text payload plus one
    # image_url part per data URL. Text-only callers pass a plain string.
    user_content: Any = user
    if images:
        user_content = [{"type": "text", "text": user}]
        for data_url in images:
            user_content.append({"type": "image_url", "image_url": {"url": data_url}})

    last_err: Exception | None = None
    for attempt in range(retry + 1):
        provider_attempt = begin_runtime_provider_attempt()
        try:
            resp = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            )
            # ``resp.usage`` is None on streaming responses; we don't stream
            # but guarding keeps telemetry robust if a future caller flips it.
            usage = getattr(resp, "usage", None)
            if usage is not None:
                telemetry.record_coach_tokens(
                    insight_type=itype,
                    model=model,
                    prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                    completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                )
            content = resp.choices[0].message.content or ""
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise TypeError("chat_json response must be a JSON object")
            record_runtime_provider_success(provider_attempt)
            return parsed
        except AuthenticationError:
            record_runtime_provider_failure()
            logger.error(
                "chat_json: Azure auth failed — DefaultAzureCredential or "
                "endpoint misconfigured", exc_info=True,
            )
            telemetry.record_coach_error(error_class="Auth")
            return None  # operator-actionable, no retry
        except BadRequestError as e:
            logger.error("chat_json: bad request (no retry): %s", e)
            telemetry.record_coach_error(error_class="BadRequest")
            return None  # malformed prompt — bug in caller
        except json.JSONDecodeError as e:
            record_runtime_provider_failure()
            last_err = e
        except (RateLimitError, APIError) as e:
            record_runtime_provider_failure()
            last_err = e  # transient — fall through to retry
        except Exception as e:  # pragma: no cover — unexpected
            record_runtime_provider_failure()
            last_err = e
        if attempt < retry:
            continue
    logger.warning(
        "chat_json failed after %d attempt(s): %s",
        retry + 1, last_err,
    )
    return None
