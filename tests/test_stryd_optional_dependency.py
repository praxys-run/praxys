"""Tests for clean startup without the private Stryd transport."""
import pytest


def test_missing_stryd_client_fails_explicitly(monkeypatch) -> None:
    """A gated worker without the package must not fail at module import."""
    from sync import stryd_sync

    monkeypatch.setattr(stryd_sync, "StrydClient", None)

    assert stryd_sync.stryd_client_available() is False
    with pytest.raises(
        stryd_sync.StrydClientUnavailableError,
        match="unavailable",
    ):
        stryd_sync._login_api("runner@example.test", "secret")
