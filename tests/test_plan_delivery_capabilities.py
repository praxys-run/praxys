"""Experimental delivery capability and consent-fence tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis.config import UserConfig
from api.plan_delivery.capabilities import (
    effective_platform_capabilities,
    garmin_plan_delivery_deployment_enabled,
    garmin_plan_delivery_eligible,
    has_plan_delivery_consent,
    plan_delivery_consent_token,
)
from api.statsig_client import get_statsig_user
from api.plan_delivery.guards import (
    capture_delivery_connection_generation,
    guard_delivery_connection,
)
from api.plan_delivery.service import DeliveryMutationBlockedError
from db.models import (
    Base,
    User,
    UserConfig as UserConfigModel,
    UserConnection,
)


def _connection() -> UserConnection:
    return UserConnection(
        id=41,
        user_id="capability-user",
        platform="garmin",
        status="connected",
        encrypted_credentials=b"credentials-a",
        wrapped_dek=b"dek-a",
    )


def _statsig_user():
    return get_statsig_user(
        user_id="capability-user",
        email="capability@example.test",
        is_admin=False,
        is_demo=False,
        training_base="power",
        language="en",
    )


def test_consent_is_bound_to_credentials_and_region() -> None:
    connection = _connection()
    connection.plan_delivery_consent = plan_delivery_consent_token(
        connection,
        region="international",
    )

    assert has_plan_delivery_consent(
        connection,
        source_options={"garmin_region": "international"},
    )

    connection.encrypted_credentials = b"credentials-b"
    assert not has_plan_delivery_consent(
        connection,
        source_options={"garmin_region": "international"},
    )

    connection.encrypted_credentials = b"credentials-a"
    assert not has_plan_delivery_consent(
        connection,
        source_options={"garmin_region": "cn"},
    )
    assert not has_plan_delivery_consent(
        connection,
        source_options={},
    )


def test_deployment_gate_defaults_off_even_when_statsig_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        raising=False,
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name == "garmin_plan_delivery_eligible",
    )
    config = UserConfig()
    connection = _connection()
    connection.plan_delivery_consent = plan_delivery_consent_token(
        connection,
        region="international",
    )

    capabilities = effective_platform_capabilities(
        config,
        connections={"garmin": connection},
        garmin_eligible=garmin_plan_delivery_eligible(_statsig_user()),
    )

    assert garmin_plan_delivery_deployment_enabled() is False
    assert garmin_plan_delivery_eligible(_statsig_user()) is False
    assert has_plan_delivery_consent(
        connection,
        source_options=config.source_options,
    )
    assert capabilities["garmin"]["plan"] is False


def test_effective_capability_does_not_change_static_provider_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name == "garmin_plan_delivery_eligible",
    )
    config = UserConfig()
    connection = _connection()
    connection.plan_delivery_consent = plan_delivery_consent_token(
        connection,
        region="international",
    )

    capabilities = effective_platform_capabilities(
        config,
        connections={"garmin": connection},
        garmin_eligible=garmin_plan_delivery_eligible(_statsig_user()),
    )

    assert capabilities["garmin"]["plan"] is True
    assert capabilities["stryd"]["plan"] is True


def test_missing_statsig_key_is_ineligible_with_deployment_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr("api.statsig_client._initialized", False)

    assert garmin_plan_delivery_deployment_enabled() is True
    assert garmin_plan_delivery_eligible(_statsig_user()) is False


def test_statsig_eligibility_uses_the_named_gate_and_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    calls = []
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, user: calls.append((gate_name, user)) or True,
    )

    user = _statsig_user()
    assert garmin_plan_delivery_eligible(user) is True
    assert calls == [("garmin_plan_delivery_eligible", user)]


@pytest.mark.parametrize(
    ("revocation", "reason"),
    [
        ("consent", "experimental_consent_required"),
        ("deployment", "experimental_delivery_disabled"),
        ("eligibility", "experimental_delivery_disabled"),
    ],
)
def test_live_gate_blocks_a_previously_captured_mutation_guard(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
    reason: str,
) -> None:
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    eligible = {"value": True}
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: (
            gate_name == "garmin_plan_delivery_eligible"
            and eligible["value"]
        ),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'capability.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(User(
            id="capability-user",
            email="capability@example.test",
            hashed_password="test",
        ))
        db.add(UserConfigModel(
            user_id="capability-user",
            source_options={"garmin_region": "international"},
        ))
        connection = _connection()
        db.add(connection)
        db.flush()
        connection.plan_delivery_consent = plan_delivery_consent_token(
            connection,
            region="international",
        )
        db.commit()
        generation = capture_delivery_connection_generation(
            db,
            user_id="capability-user",
            target="garmin",
        )
        assert generation is not None

        if revocation == "consent":
            connection.plan_delivery_consent = None
            db.commit()
        elif revocation == "deployment":
            monkeypatch.setenv(
                "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
                "false",
            )
        else:
            eligible["value"] = False

        with pytest.raises(
            DeliveryMutationBlockedError,
            match=reason,
        ):
            guard_delivery_connection(
                db,
                user_id="capability-user",
                target="garmin",
                expected_generation=generation,
            )
    finally:
        db.close()
        engine.dispose()
