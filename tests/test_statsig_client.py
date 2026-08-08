"""Fail-closed contract tests for the Statsig server wrapper."""
from __future__ import annotations

import asyncio


def test_missing_sdk_key_keeps_gates_off_and_config_on_fallback(
    monkeypatch,
) -> None:
    from api import statsig_client

    monkeypatch.delenv("STATSIG_SDK_KEY", raising=False)
    monkeypatch.setattr(statsig_client, "_initialized", False)
    monkeypatch.setattr(
        statsig_client.statsig,
        "initialize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Statsig must not initialize without a key")
        ),
    )

    asyncio.run(statsig_client.init_statsig())
    user = statsig_client.get_statsig_user(
        user_id="user-1",
        email="runner@example.test",
        is_admin=False,
        is_demo=False,
        training_base="power",
        language="en",
    )

    assert (
        statsig_client.check_gate(
            "garmin_plan_delivery_eligible",
            user,
        )
        is False
    )
    assert statsig_client.get_config("insight_daily_cap", user, 30) == 30


def test_statsig_user_contains_targeting_attributes() -> None:
    from api.statsig_client import get_statsig_user

    user = get_statsig_user(
        user_id="user-2",
        email="admin@example.test",
        is_admin=True,
        is_demo=True,
        training_base="pace",
        language="zh",
    )

    assert user.user_id == "user-2"
    assert user.email == "admin@example.test"
    assert user.custom == {
        "is_admin": True,
        "is_demo": True,
        "training_base": "pace",
        "language": "zh",
    }


def test_gate_and_config_errors_fail_closed(monkeypatch) -> None:
    from api import statsig_client

    user = statsig_client.get_statsig_user(
        user_id="user-3",
        email="runner@example.test",
        is_admin=False,
        is_demo=False,
        training_base="hr",
        language=None,
    )
    monkeypatch.setattr(statsig_client, "_initialized", True)
    monkeypatch.setattr(
        statsig_client.statsig,
        "check_gate",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(
        statsig_client.statsig,
        "get_config",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert (
        statsig_client.check_gate(
            "garmin_plan_delivery_eligible",
            user,
        )
        is False
    )
    assert statsig_client.get_config("insight_daily_cap", user, 17) == 17


def test_shutdown_flushes_and_stops_initialized_sdk(monkeypatch) -> None:
    from api import statsig_client

    calls: list[str] = []
    monkeypatch.setattr(statsig_client, "_initialized", True)
    monkeypatch.setattr(
        statsig_client.statsig,
        "flush",
        lambda: calls.append("flush"),
    )
    monkeypatch.setattr(
        statsig_client.statsig,
        "shutdown",
        lambda: calls.append("shutdown"),
    )

    asyncio.run(statsig_client.shutdown_statsig())

    assert calls == ["flush", "shutdown"]
    assert statsig_client._initialized is False
