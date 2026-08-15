"""Unit coverage for the private Stryd authorization boundary."""
import json
from types import SimpleNamespace

import pandas as pd

from api.stryd_access import (
    stryd_connection_enabled,
    without_stryd_delivery_metadata,
    without_stryd_plan_rows,
)


def test_demo_account_cannot_enable_stryd(monkeypatch) -> None:
    """Demo viewers fail closed before any Statsig evaluation."""

    class DemoDb:
        def execute(self, _statement):
            return SimpleNamespace(
                one_or_none=lambda: SimpleNamespace(
                    id="demo-viewer",
                    email="demo@example.com",
                    is_active=True,
                    is_superuser=False,
                    is_demo=True,
                )
            )

    def unexpected_gate_check(_gate_name, _user):
        raise AssertionError("demo accounts must not reach Statsig")

    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        unexpected_gate_check,
    )

    assert not stryd_connection_enabled(
        DemoDb(),
        user_id="demo-viewer",
    )


def test_stryd_delivery_metadata_is_removed() -> None:
    """Private target names and external IDs stay out of hidden responses."""
    assert without_stryd_delivery_metadata({
        "requested": True,
        "target": "stryd",
        "status": "success",
        "window_start": "2026-06-01",
        "window_end": "2026-06-14",
        "items": [{"external_id": "private-id"}],
    }) == {
        "requested": True,
        "status": "success",
        "window_start": "2026-06-01",
        "window_end": "2026-06-14",
    }


def test_non_stryd_delivery_metadata_is_preserved() -> None:
    """Public provider delivery details are unchanged."""
    delivery = {
        "target": "garmin",
        "status": "success",
        "items": [{"external_id": "garmin-id"}],
    }
    assert without_stryd_delivery_metadata(delivery) == delivery


def test_stryd_plan_rows_are_removed_case_insensitively() -> None:
    """Legacy mixed-case plan provenance cannot evade the private boundary."""
    plan = pd.DataFrame([
        {"source": " STRYD ", "workout_type": "private"},
        {"source": "ai", "workout_type": "public"},
        {"source": None, "workout_type": "legacy"},
    ])

    visible = without_stryd_plan_rows(plan)

    assert visible["workout_type"].tolist() == ["public", "legacy"]


def test_public_openapi_omits_private_stryd_surface() -> None:
    """Anonymous API discovery contains no private paths or provider schemas."""
    from api.main import app

    schema = app.openapi()

    assert all("/api/labs/" not in path for path in schema["paths"])
    assert "stryd" not in json.dumps(schema).casefold()
