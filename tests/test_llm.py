"""Tests for Azure OpenAI client gating."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from api import llm
from scripts import translate_missing


@pytest.mark.parametrize("model", [
    "gpt-6.1-sol", "gpt-6.1-sol-canary", "gpt-6-luna", "gpt-6-luna-canary",
])
@pytest.mark.parametrize("budget,expected", [(80, 2048), (160, 2048), (4096, 4096)])
def test_reasoning_request_profile(model: str, budget: int, expected: int) -> None:
    assert llm.completion_options(
        model=model, max_completion_tokens=budget, temperature=0,
    ) == {"max_completion_tokens": expected, "reasoning_effort": "low"}


@pytest.mark.parametrize("model", [
    "gpt-5.4", "gpt-5.4-mini", "custom-deployment", "gpt-6-lunar",
])
def test_rollback_request_profile(model: str) -> None:
    assert llm.completion_options(
        model=model, max_completion_tokens=80, temperature=0.3,
    ) == {"max_completion_tokens": 80, "temperature": 0.3}
    assert llm.completion_options(
        model=model, max_completion_tokens=80,
    ) == {"max_completion_tokens": 80}


def test_sol_multimodal_request_keeps_images_and_json_contract(monkeypatch) -> None:
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(
                finish_reason="stop", message=SimpleNamespace(content='{"ok": true}'),
            )],
        )

    client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    assert llm.chat_json(
        client, system="system", user="describe", model="gpt-6.1-sol",
        images=["data:image/png;base64,synthetic"], max_completion_tokens=1200,
        temperature=0, retry=0,
    ) == {"ok": True}
    assert len(calls) == 1
    call = calls[0]
    assert "temperature" not in call
    assert call["reasoning_effort"] == "low"
    assert call["max_completion_tokens"] == 2048
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][1]["content"] == [
        {"type": "text", "text": "describe"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,synthetic"}},
    ]


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
def test_truncated_valid_json_fails_closed_and_records_all_attempts(
    monkeypatch, finish_reason: str,
) -> None:
    usage_calls = []
    provider_calls = []
    monkeypatch.setattr(llm, "record_token_usage", lambda *a, **kw: usage_calls.append(kw))

    def create(**kwargs):
        provider_calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content='{"safe_to_publish": true}'),
            )],
        )

    client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    assert llm.chat_json(
        client, system="system", user="user", model="gpt-6.1-sol",
        max_completion_tokens=80, retry=1,
    ) is None
    assert len(provider_calls) == len(usage_calls) == 2
    assert llm.runtime_ai_available() is False


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
def test_private_classifier_rejects_truncated_valid_json_without_payload_logs(
    monkeypatch, caplog, finish_reason,
) -> None:
    from api import personal_context_processing as personal
    narrative = "private synthetic narrative"
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(content='{"outcome":"no_change","reason_code":'
                                    '"current_plan_supported","proposal_scope":"none","uncertainty":"high"}'),
        )])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    request = personal.AiContextRequest(
        purpose="plan_adjustment", allowed_proposal_scope="week",
        system_prompt=personal.SYSTEM_PROMPT, user_prompt=narrative, disclosures=(),
    )
    assert personal._call_azure_context_model(client, request) is None
    assert len(calls) == 1
    assert narrative not in caplog.text
    assert calls[0]["timeout"] == 30.0
    assert "tools" not in calls[0]


def _confirm_provider_recovery() -> None:
    attempt = llm.begin_runtime_provider_attempt()
    assert attempt is not None
    assert llm.record_runtime_provider_success(attempt) is True


@pytest.fixture(autouse=True)
def reset_provider_health(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    _confirm_provider_recovery()
    yield
    _confirm_provider_recovery()


def test_runtime_client_respects_emergency_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = object()
    monkeypatch.setattr(llm, "_get_cached_client", lambda: client)

    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")
    assert llm.get_client() is None

    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    assert llm.get_client() is client


def test_automation_client_ignores_user_data_emergency_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = object()
    monkeypatch.setattr(llm, "_get_cached_client", lambda: client)
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")

    assert llm.get_automation_client() is client


def test_translation_uses_automation_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = object()
    monkeypatch.setattr(llm, "get_automation_client", lambda: client)
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: pytest.fail("translation must not use the runtime client"),
    )

    assert translate_missing._client() is client


def test_runtime_availability_requires_a_configured_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: None)

    assert llm.runtime_ai_available() is False


def test_recent_provider_failure_marks_runtime_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingCompletions:
        def create(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=FailingCompletions()),
    )
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: client)

    assert llm.runtime_ai_available() is True
    assert (
        llm.chat_json(
            client,
            system="system",
            user="user",
            model="model",
            retry=0,
        )
        is None
    )
    assert llm.runtime_ai_available() is False


def test_successful_provider_response_clears_failure_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SuccessfulCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"ok": true}'),
                    )
                ],
            )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SuccessfulCompletions()),
    )
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: client)
    llm.record_runtime_provider_failure()

    assert llm.runtime_ai_available() is False
    assert llm.chat_json(
        client,
        system="system",
        user="user",
        model="model",
        retry=0,
    ) == {"ok": True}
    assert llm.runtime_ai_available() is True


def test_runtime_provider_failure_stays_latched_without_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Elapsed time alone must never claim that Azure recovered."""
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: object())

    llm.record_runtime_provider_failure()

    assert llm.runtime_ai_available() is False
    assert llm.runtime_ai_available() is False


def test_stale_success_cannot_clear_a_newer_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response started before the latest failure cannot claim recovery."""
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: object())
    stale_attempt = llm.begin_runtime_provider_attempt()
    assert stale_attempt is not None

    llm.record_runtime_provider_failure()

    assert llm.record_runtime_provider_success(stale_attempt) is False
    assert llm.runtime_ai_available() is False
    _confirm_provider_recovery()
    assert llm.runtime_ai_available() is True


def test_runtime_provider_failure_is_visible_across_process_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shared state must outlive one worker's in-memory state."""
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: object())
    llm.record_runtime_provider_failure()

    monkeypatch.setattr(llm, "_provider_failure_active", False)

    assert llm.runtime_ai_available() is False


def test_primary_state_lock_failure_sets_shared_fail_closed_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A primary lock failure must still become visible to other workers."""
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: object())
    original_lock = llm.portalocker.Lock

    class BrokenPrimaryLock:
        def __enter__(self):
            raise OSError("primary state lock unavailable")

        def __exit__(self, *_args):
            return False

    def _selective_lock(filename, *args, **kwargs):
        if str(filename).endswith(llm._PROVIDER_HEALTH_LOCK):
            return BrokenPrimaryLock()
        return original_lock(filename, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(llm.portalocker, "Lock", _selective_lock)
        llm.record_runtime_provider_failure()

    _state, _lock, fail_closed, _fail_closed_lock = (
        llm._provider_health_paths()
    )
    assert fail_closed.exists()
    monkeypatch.setattr(llm, "_provider_failure_active", False)
    assert llm.runtime_ai_available() is False


def test_local_fail_closed_state_reconciles_through_shared_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recovered state store must not strand one worker permanently."""
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: object())
    monkeypatch.setattr(llm, "_provider_failure_active", True)

    assert llm.runtime_ai_available() is False
    assert llm._provider_failure_active is False

    recovery_attempt = llm.begin_runtime_provider_attempt()
    assert recovery_attempt is not None
    assert llm.record_runtime_provider_success(recovery_attempt) is True
    assert llm.runtime_ai_available() is True


def test_invalid_json_does_not_clear_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a fully parsed model response may confirm provider recovery."""
    class InvalidJsonCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="not-json"),
                    )
                ],
            )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=InvalidJsonCompletions()),
    )
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setattr(llm, "_get_cached_client", lambda: client)
    llm.record_runtime_provider_failure()

    assert llm.chat_json(
        client,
        system="system",
        user="user",
        model="model",
        retry=0,
    ) is None
    assert llm.runtime_ai_available() is False
