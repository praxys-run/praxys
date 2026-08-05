"""Experimental delivery capability and consent-fence tests."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis.config import UserConfig
from api.plan_delivery.capabilities import (
    effective_platform_capabilities,
    garmin_plan_delivery_operator_enabled,
    garmin_plan_delivery_pilot_user_ids,
    has_plan_delivery_consent,
    plan_delivery_consent_token,
)
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


def test_operator_gate_defaults_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        raising=False,
    )
    config = UserConfig()
    connection = _connection()
    connection.plan_delivery_consent = plan_delivery_consent_token(
        connection,
        region="international",
    )

    capabilities = effective_platform_capabilities(
        config,
        user_id="capability-user",
        connections={"garmin": connection},
    )

    assert garmin_plan_delivery_operator_enabled() is False
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
    config = UserConfig()
    connection = _connection()
    connection.plan_delivery_consent = plan_delivery_consent_token(
        connection,
        region="international",
    )

    capabilities = effective_platform_capabilities(
        config,
        user_id="capability-user",
        connections={"garmin": connection},
    )

    assert capabilities["garmin"]["plan"] is True
    assert capabilities["stryd"]["plan"] is True


def test_pilot_allowlist_grants_only_the_named_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_PILOT_USER_IDS",
        " pilot-user,other-user, ",
    )

    assert garmin_plan_delivery_pilot_user_ids() == frozenset({
        "pilot-user",
        "other-user",
    })
    assert garmin_plan_delivery_operator_enabled("pilot-user")
    assert not garmin_plan_delivery_operator_enabled("regular-user")
    assert not garmin_plan_delivery_operator_enabled()


def test_pilot_removal_blocks_a_fresh_mutation_guard(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_PILOT_USER_IDS",
        "capability-user",
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'pilot-capability.db'}")
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

        monkeypatch.setenv(
            "PRAXYS_GARMIN_PLAN_DELIVERY_PILOT_USER_IDS",
            "",
        )
        with pytest.raises(
            DeliveryMutationBlockedError,
            match="experimental_delivery_disabled",
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


def test_deploy_workflow_propagates_documented_pilot_allowlist() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github" / "workflows" / "deploy-backend.yml"
    ).read_text(encoding="utf-8")
    docs = (
        root / "docs" / "ops" / "config-and-secrets.md"
    ).read_text(encoding="utf-8")
    example = (root / ".env.example").read_text(encoding="utf-8")
    variable = "PRAXYS_GARMIN_PLAN_DELIVERY_PILOT_USER_IDS"

    assert workflow.count(variable) >= 2
    assert f"${{{{ vars.{variable} }}}}" in workflow
    assert variable in docs
    assert f"{variable}=" in example


@pytest.mark.parametrize(
    ("revocation", "reason"),
    [
        ("consent", "experimental_consent_required"),
        ("operator", "experimental_delivery_disabled"),
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
        else:
            monkeypatch.setenv(
                "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
                "false",
            )

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
