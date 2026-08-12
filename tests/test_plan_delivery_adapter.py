"""Provider-neutral plan-delivery adapter tests."""
import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.plan_delivery.base import (
    PlanDeliveryAdapter,
    ProviderAuthenticationError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.service import (
    DeliveryMutationBlockedError,
    PlanDeliveryService,
)
from api.plan_delivery.stryd import StrydPlanDeliveryAdapter


def test_stryd_adapter_implements_contract_and_reuses_login(monkeypatch):
    calls = {"login": 0, "calendar": 0, "delete": 0}

    def _login(email: str, password: str) -> tuple[str, str]:
        calls["login"] += 1
        assert (email, password) == ("runner@example.test", "secret")
        return "provider-user", "provider-token"

    def _calendar(
        user_id: str,
        token: str,
        *,
        cp_watts: float | None,
        days_ahead: int,
        days_back: int,
        tz_name: str | None,
    ) -> list[dict]:
        calls["calendar"] += 1
        assert (user_id, token) == ("provider-user", "provider-token")
        assert (cp_watts, days_ahead, days_back, tz_name) == (
            280.0,
            21,
            0,
            "Asia/Shanghai",
        )
        return [{"date": "2026-08-01", "external_id": "calendar-id"}]

    def _delete(user_id: str, token: str, external_id: str) -> bool:
        calls["delete"] += 1
        assert (user_id, token, external_id) == (
            "provider-user",
            "provider-token",
            "calendar-id",
        )
        return True

    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    monkeypatch.setattr("sync.stryd_sync.fetch_training_plan_api", _calendar)
    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", _delete)

    adapter = StrydPlanDeliveryAdapter({
        "email": "runner@example.test",
        "password": "secret",
    })

    assert isinstance(adapter, PlanDeliveryAdapter)
    assert adapter.fetch_calendar(
        threshold_value=280.0,
        days_ahead=21,
        timezone_name="Asia/Shanghai",
    ) == [{"date": "2026-08-01", "external_id": "calendar-id"}]
    assert adapter.account_id == "provider-user"
    assert adapter.delete_workout("calendar-id").already_absent is False
    assert calls == {"login": 1, "calendar": 1, "delete": 1}


def test_stryd_adapter_treats_missing_delete_as_already_absent(monkeypatch):
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("provider-user", "provider-token"),
    )

    def _missing(user_id: str, token: str, external_id: str) -> bool:
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("not found", response=response)

    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", _missing)
    adapter = StrydPlanDeliveryAdapter({
        "email": "runner@example.test",
        "password": "secret",
    })

    assert adapter.delete_workout("missing-id").already_absent is True


def test_stryd_adapter_sends_the_prepared_payload_unchanged(monkeypatch):
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("provider-user", "provider-token"),
    )
    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return {"id": "created-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    adapter = StrydPlanDeliveryAdapter({
        "email": "runner@example.test",
        "password": "secret",
    })
    prepared = adapter.prepare_workout(
        {
            "date": "2026-08-02",
            "workout_type": "threshold",
            "planned_duration_min": 60,
            "workout_description": "WU 10min, 3x3min @275-290W w/ 3min, CD 10min",
        },
        threshold_value=280.0,
    )

    result = adapter.create_workout(prepared)

    assert result.external_id == "created-id"
    assert result.provider_account_id == "provider-user"
    assert {
        key: value
        for key, value in captured.items()
        if key not in {"user_id", "token"}
    } == prepared.request


def test_stryd_adapter_marks_rate_limit_as_safely_retryable(monkeypatch):
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("provider-user", "provider-token"),
    )

    def _rate_limited(**kwargs):
        response = requests.Response()
        response.status_code = 429
        raise requests.HTTPError("rate limited", response=response)

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _rate_limited)
    adapter = StrydPlanDeliveryAdapter({
        "email": "runner@example.test",
        "password": "secret",
    })
    prepared = adapter.prepare_workout(
        {
            "date": "2026-08-02",
            "workout_type": "easy",
            "planned_duration_min": 45,
        },
        threshold_value=280.0,
    )

    with pytest.raises(ProviderTransientError):
        adapter.create_workout(prepared)


def test_stryd_prepared_payload_ignores_free_text_and_tracks_real_targets():
    adapter = StrydPlanDeliveryAdapter({
        "email": "runner@example.test",
        "password": "secret",
    })
    free_text_only = {
        "date": "2026-08-02",
        "workout_type": "threshold",
        "planned_duration_min": 60,
        "workout_description": "20min @250-270W",
    }
    power_target = {
        **free_text_only,
        "target_power_min": 250,
        "target_power_max": 270,
    }

    first = adapter.prepare_workout(free_text_only, threshold_value=280.0)
    repeated = adapter.prepare_workout(free_text_only, threshold_value=280.0)
    changed = adapter.prepare_workout(free_text_only, threshold_value=285.0)
    targeted = adapter.prepare_workout(power_target, threshold_value=280.0)
    targeted_changed = adapter.prepare_workout(power_target, threshold_value=285.0)

    assert first == repeated
    assert first.version == changed.version
    assert targeted.version != targeted_changed.version


def test_stryd_adapter_returns_typed_unsupported_error_for_step_wording():
    adapter = StrydPlanDeliveryAdapter({
        "email": "runner@example.test",
        "password": "secret",
    })

    with pytest.raises(
        ProviderRequestError,
        match="cannot safely encode user-defined wording",
    ):
        adapter.prepare_workout(
            {
                "date": "2026-08-02",
                "workout_type": "threshold",
                "workout_structure_version": "v1",
                "workout_structure": {
                    "steps": [{
                        "type": "step",
                        "phase": "work",
                        "label": "Threshold",
                        "instructions": "Stay smooth.",
                        "termination": {
                            "type": "time",
                            "seconds": 300,
                        },
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 95,
                            "max": 100,
                        },
                    }],
                },
            },
            threshold_value=280.0,
        )


def test_delivery_authenticates_before_starting_ledger_attempt(tmp_path):
    from db.models import Base, PlanDelivery, PlanDeliveryAttempt, User

    engine = create_engine(f"sqlite:///{tmp_path / 'delivery.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(
        id="auth-failure-user",
        email="auth-failure@example.test",
        hashed_password="test",
    ))
    db.commit()

    class AuthFailureAdapter:
        target = "stryd"
        display_name = "Stryd"

        @property
        def account_id(self) -> str:
            raise AssertionError("account_id must not be read after failed auth")

        def authenticate(self) -> None:
            raise ProviderAuthenticationError("login failed")

        def prepare_workout(self, workout, *, threshold_value):
            from api.plan_delivery.base import PreparedWorkoutDelivery

            return PreparedWorkoutDelivery(
                version="a" * 64,
                request={},
            )

        def create_workout(self, prepared, *, hooks):
            raise AssertionError("create must not run")

        def delete_workout(self, external_id, *, hooks):
            raise AssertionError("delete must not run")

        def fetch_calendar(
            self,
            *,
            threshold_value=None,
            days_ahead=14,
            days_back=0,
            timezone_name=None,
        ):
            raise AssertionError("calendar must not run")

    service = PlanDeliveryService(
        db=db,
        user_id="auth-failure-user",
        target="stryd",
        adapter_loader=AuthFailureAdapter,
    )

    try:
        with pytest.raises(ProviderAuthenticationError):
            service.deliver(
                {
                    "date": "2026-08-03",
                    "source": "ai",
                    "workout_type": "easy",
                },
                threshold_value=280.0,
                observed_external_ids=None,
            )
        assert db.query(PlanDelivery).count() == 0
        assert db.query(PlanDeliveryAttempt).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_delivery_reports_preflight_mutation_guard_change(tmp_path):
    from api.plan_delivery.base import PreparedWorkoutDelivery
    from db.models import Base, PlanDelivery, User

    engine = create_engine(f"sqlite:///{tmp_path / 'delivery-guard.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(
        id="guard-change-user",
        email="guard-change@example.test",
        hashed_password="test",
    ))
    db.commit()

    class GuardedAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "provider-account"

        def authenticate(self) -> None:
            return None

        def prepare_workout(
            self,
            workout,
            *,
            threshold_value,
        ) -> PreparedWorkoutDelivery:
            return PreparedWorkoutDelivery(
                version="a" * 64,
                request={},
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            raise AssertionError("create must not run")

        def delete_workout(self, external_id, *, hooks):
            raise AssertionError("delete must not run")

        def fetch_calendar(self, **kwargs):
            raise AssertionError("calendar must not run")

    def block_mutation() -> None:
        raise DeliveryMutationBlockedError("connection_changed")

    service = PlanDeliveryService(
        db=db,
        user_id="guard-change-user",
        target="stryd",
        adapter_loader=GuardedAdapter,
    )

    try:
        result = service.deliver(
            {
                "date": "2026-08-03",
                "source": "ai",
                "workout_type": "easy",
            },
            threshold_value=280.0,
            observed_external_ids=None,
            mutation_guard=block_mutation,
        )

        assert result.status == "error"
        assert result.error == "connection_changed"
        assert result.error_category == "delivery_gate_changed"
        assert result.retryable is True
        assert db.query(PlanDelivery).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_delivery_flushes_auth_only_after_ledger_transactions_close(tmp_path):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )
    from db.models import Base, User

    engine = create_engine(f"sqlite:///{tmp_path / 'auth-flush.db'}")
    db = sessionmaker(bind=engine)()
    Base.metadata.create_all(engine)
    db.add(User(
        id="auth-flush-user",
        email="auth-flush@example.test",
        hashed_password="test",
    ))
    db.commit()
    flush_transactions: list[bool] = []

    class FlushAdapter:
        target = "garmin"
        display_name = "Garmin"
        account_id = "provider-account"

        def authenticate(self) -> None:
            return None

        def flush_auth_state(self) -> None:
            flush_transactions.append(db.in_transaction())

        def prepare_workout(self, workout, *, threshold_value):
            del workout, threshold_value
            return PreparedWorkoutDelivery(
                version="a" * 64,
                content_version="b" * 64,
                request={},
            )

        def create_workout(self, prepared, *, hooks):
            del prepared, hooks
            return ProviderCreateResult(
                external_id="garmin-schedule-1",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            del hooks
            assert external_id == "garmin-schedule-1"
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            del kwargs
            return []

    adapter = FlushAdapter()
    service = PlanDeliveryService(
        db=db,
        user_id="auth-flush-user",
        target="garmin",
        adapter_loader=lambda: adapter,
    )
    snapshot = {
        "canonical_id": "8fcba122-c7d7-41b3-8138-c3ef4b291ed9",
        "date": "2026-08-06",
        "source": "ai",
        "workout_type": "easy",
        "planned_duration_min": 30,
    }

    try:
        delivered = service.deliver(snapshot, threshold_value=280.0)
        removed = service.remove("garmin-schedule-1")

        assert delivered.status == "success"
        assert removed.external_id == "garmin-schedule-1"
        assert flush_transactions == [False, False]
    finally:
        db.close()
        engine.dispose()
