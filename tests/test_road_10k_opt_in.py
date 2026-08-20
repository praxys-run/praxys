"""Repository-only tests for the inactive Road 10K opt-in primitive."""
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Road10KOwnerOptInReceipt, User


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _receipt(user_id: str, *, decision: str, when: datetime):
    from api.road_10k_opt_in import (
        ROAD_10K_OWNER_OPT_IN_CONSENT_VERSION,
        ROAD_10K_OWNER_OPT_IN_SCHEMA_VERSION,
    )

    return Road10KOwnerOptInReceipt(
        id=f"receipt-{decision}-{when.timestamp()}",
        user_id=user_id,
        capability_id="outdoor_road_10k_performance_v1",
        schema_version=ROAD_10K_OWNER_OPT_IN_SCHEMA_VERSION,
        policy_version="road-10k-plan-generation-policy-v2",
        decision=decision,
        consent_text_version=ROAD_10K_OWNER_OPT_IN_CONSENT_VERSION,
        client="web",
        decided_at=when,
    )


def test_owner_opt_in_is_hidden_and_fail_closed_while_capability_is_inactive(
    monkeypatch,
):
    from api import road_10k_opt_in

    db = _db()
    db.add(
        User(
            id="owner-1",
            email="owner-1@example.test",
            hashed_password="not-used",
        )
    )
    db.add(_receipt("owner-1", decision="granted", when=datetime.utcnow()))
    db.commit()

    monkeypatch.setattr(road_10k_opt_in, "road_10k_capability_available", lambda: False)
    assert road_10k_opt_in.road_10k_owner_opted_in(db, "owner-1") is False


def test_owner_opt_in_uses_latest_receipt_and_requires_exact_contract(monkeypatch):
    from api import road_10k_opt_in

    db = _db()
    db.add(
        User(
            id="owner-2",
            email="owner-2@example.test",
            hashed_password="not-used",
        )
    )
    now = datetime.utcnow()
    db.add(_receipt("owner-2", decision="granted", when=now))
    db.commit()
    monkeypatch.setattr(road_10k_opt_in, "road_10k_capability_available", lambda: True)

    assert road_10k_opt_in.road_10k_owner_opted_in(db, "owner-2") is True

    db.add(_receipt("owner-2", decision="withdrawn", when=now + timedelta(seconds=1)))
    db.commit()
    assert road_10k_opt_in.road_10k_owner_opted_in(db, "owner-2") is False


def test_owner_opt_in_lookup_errors_fail_closed(monkeypatch):
    from api import road_10k_opt_in

    class BrokenDB:
        def query(self, *_args, **_kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(road_10k_opt_in, "road_10k_capability_available", lambda: True)
    assert road_10k_opt_in.road_10k_owner_opted_in(BrokenDB(), "owner-3") is False
