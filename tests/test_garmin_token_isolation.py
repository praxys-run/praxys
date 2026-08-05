"""Regression tests for encrypted Garmin OAuth token persistence."""
import contextlib
import json
import math
import os
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.routes.sync import (
    _garmin_token_dir,
    _garmin_token_root,
    _garmin_tokenstore_lease,
    clear_garmin_tokens,
    migrate_legacy_garmin_tokenstores,
)


def test_token_dir_is_unique_per_user() -> None:
    a = _garmin_token_dir("user-a")
    b = _garmin_token_dir("user-b")
    assert a != b
    assert a.startswith(_garmin_token_root())
    assert b.startswith(_garmin_token_root())


def test_token_dir_is_nested_directly_under_root_as_user_id() -> None:
    """Strong invariant: the path under the root is exactly the user_id.

    Rejects sharded variants like `root/first-char/full-id` that could collapse
    for IDs sharing a prefix.
    """
    uid = "abc-123"
    path = _garmin_token_dir(uid)
    assert os.path.relpath(path, _garmin_token_root()) == uid


def test_tokenstore_lease_is_reentrant(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    with _garmin_tokenstore_lease("nested-user"):
        with _garmin_tokenstore_lease("nested-user"):
            pass


def test_tokenstore_lease_waits_without_default_timeout(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes import sync as sync_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    observed_timeout: list[float] = []

    class RecordingLock:
        def __init__(
            self,
            path: str,
            *,
            mode: str,
            timeout: float,
        ) -> None:
            del path, mode
            observed_timeout.append(timeout)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            del exc_type, exc, traceback

    monkeypatch.setattr(sync_mod.portalocker, "Lock", RecordingLock)

    with _garmin_tokenstore_lease("blocking-user"):
        pass

    assert len(observed_timeout) == 1
    assert math.isinf(observed_timeout[0])


def test_tokenstore_lease_serializes_threads(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def hold_first() -> None:
        with _garmin_tokenstore_lease("shared-user"):
            first_entered.set()
            assert release_first.wait(timeout=5)

    def enter_second() -> None:
        assert first_entered.wait(timeout=5)
        with _garmin_tokenstore_lease("shared-user"):
            second_entered.set()

    first = threading.Thread(target=hold_first)
    second = threading.Thread(target=enter_second)
    first.start()
    second.start()
    try:
        assert first_entered.wait(timeout=5)
        assert not second_entered.wait(timeout=0.1)
    finally:
        release_first.set()
        first.join(timeout=5)
        second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert second_entered.is_set()


def test_sync_garmin_holds_tokenstore_lease(tmp_path, monkeypatch) -> None:
    from api.routes import sync as sync_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    events: list[tuple[str, str]] = []

    @contextlib.contextmanager
    def recording_lease(user_id: str):
        events.append(("enter", user_id))
        try:
            yield
        finally:
            events.append(("exit", user_id))

    monkeypatch.setattr(
        sync_mod,
        "_garmin_tokenstore_lease",
        recording_lease,
    )
    monkeypatch.setattr(
        sync_mod,
        "_sync_garmin_locked",
        lambda user_id, creds, from_date, db, credential_generation=None,
        _token_state=None: {
            "activities": 1,
        },
    )

    result = sync_mod._sync_garmin(
        "sync-user",
        {"email": "runner@example.test", "password": "secret"},
        None,
        object(),
        credential_generation="generation",
    )

    assert result == {"activities": 1}
    assert events == [
        ("enter", "sync-user"),
        ("exit", "sync-user"),
    ]


def test_clear_garmin_tokens_removes_directory(tmp_path, monkeypatch) -> None:
    """Invalidation must delete the tokenstore so the next login re-auths."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    user_id = "user-x"
    path = _garmin_token_dir(user_id)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "oauth1_token.json"), "w") as f:
        f.write("{}")
    assert os.path.isdir(path)

    clear_garmin_tokens(user_id)
    assert not os.path.isdir(path)


def test_clear_garmin_tokens_is_noop_when_dir_missing(tmp_path, monkeypatch) -> None:
    """Clearing a non-existent directory must not raise — the connect-flow
    calls this unconditionally on first-ever Garmin connect."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    clear_garmin_tokens("never-synced-user")


def test_clear_garmin_tokens_propagates_filesystem_errors(tmp_path, monkeypatch) -> None:
    """Silencing rmtree failures would leave reusable bearer tokens behind."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    user_id = "user-err"
    os.makedirs(_garmin_token_dir(user_id), exist_ok=True)

    def _boom(*args, **kwargs):
        raise OSError("simulated permission denied")

    monkeypatch.setattr("shutil.rmtree", _boom)

    with pytest.raises(OSError):
        clear_garmin_tokens(user_id)


def _serialized_tokens(marker: str = "token") -> str:
    return json.dumps({
        "di_token": f"access-{marker}-" + ("a" * 600),
        "di_refresh_token": f"refresh-{marker}-" + ("b" * 600),
        "di_client_id": f"client-{marker}",
    })


def _assert_legacy_tokenstore_blocked(user_id: str) -> None:
    _garmin_token_dir(user_id)
    path = Path(_garmin_token_root())
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == (
        "praxys-encrypted-garmin-tokenstore-v1\n"
    )


def _token_db(monkeypatch):
    from db import crypto
    from db.models import Base, User, UserConnection

    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setattr(crypto, "_vault", None)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(
        id="token-user",
        email="token-user@example.test",
        hashed_password="x",
        is_active=True,
    ))
    db.add(UserConnection(
        user_id="token-user",
        platform="garmin",
        encrypted_credentials=b"credentials",
        wrapped_dek=b"credential-dek",
        status="connected",
    ))
    db.commit()
    return engine, Session, db


def test_tokens_round_trip_through_envelope_encryption(monkeypatch) -> None:
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens
    from db.models import UserConnection

    engine, _Session, db = _token_db(monkeypatch)
    try:
        connection = db.query(UserConnection).one()
        generation = connection_credentials_generation(connection)
        serialized = _serialized_tokens("round-trip")

        stage_garmin_tokens(
            db,
            user_id="token-user",
            serialized_tokens=serialized,
            expected_generation=generation,
            allowed_statuses=("connected",),
        )
        db.commit()
        db.refresh(connection)

        assert connection.encrypted_garmin_tokens is not None
        assert b"round-trip" not in connection.encrypted_garmin_tokens
        assert connection.wrapped_token_dek is not None
        assert connection.garmin_token_generation == generation
        assert connection.tokens_updated_at is not None
        assert load_garmin_tokens(
            db,
            user_id="token-user",
            expected_generation=generation,
            allowed_statuses=("connected",),
        ) == serialized
    finally:
        db.close()
        engine.dispose()


def test_serialization_matches_garminconnect_client_contract() -> None:
    from garminconnect.client import Client
    from db.garmin_tokens import validate_garmin_tokens

    client = Client()
    client.di_token = "access-" + ("a" * 600)
    client.di_refresh_token = "refresh-" + ("b" * 600)
    client.di_client_id = "client-id"

    serialized = client.dumps()
    restored = Client()
    restored.loads(validate_garmin_tokens(serialized))

    assert restored.di_token == client.di_token
    assert restored.di_refresh_token == client.di_refresh_token
    assert restored.di_client_id == client.di_client_id


def test_unreadable_tokens_require_reconnect() -> None:
    from db.garmin_tokens import GarminTokenAccessError
    from db.sync_scheduler import classify_sync_failure

    assert classify_sync_failure(
        GarminTokenAccessError("Stored Garmin OAuth tokens are malformed")
    ) == ("auth_required", True)


def test_tokens_cannot_cross_credential_generations(monkeypatch) -> None:
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import (
        GarminTokenAccessError,
        load_garmin_tokens,
        stage_garmin_tokens,
    )
    from db.models import UserConnection

    engine, _Session, db = _token_db(monkeypatch)
    try:
        connection = db.query(UserConnection).one()
        generation = connection_credentials_generation(connection)
        stage_garmin_tokens(
            db,
            user_id="token-user",
            serialized_tokens=_serialized_tokens("account-a"),
            expected_generation=generation,
        )
        db.commit()

        connection.encrypted_credentials = b"replacement-credentials"
        connection.wrapped_dek = b"replacement-dek"
        db.commit()

        with pytest.raises(
            GarminTokenAccessError,
            match="do not match current credentials",
        ):
            load_garmin_tokens(db, user_id="token-user")
    finally:
        db.close()
        engine.dispose()


def test_clear_removes_encrypted_and_legacy_tokens(
    tmp_path,
    monkeypatch,
) -> None:
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import stage_garmin_tokens
    from db.models import UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, _Session, db = _token_db(monkeypatch)
    try:
        connection = db.query(UserConnection).one()
        stage_garmin_tokens(
            db,
            user_id="token-user",
            serialized_tokens=_serialized_tokens("clear"),
            expected_generation=connection_credentials_generation(connection),
        )
        legacy = _garmin_token_dir("token-user")
        os.makedirs(legacy, exist_ok=True)
        Path(legacy, "oauth1_token.json").write_text(
            "plaintext",
            encoding="utf-8",
        )

        clear_garmin_tokens("token-user", db)
        db.commit()
        db.refresh(connection)

        assert connection.encrypted_garmin_tokens is None
        assert connection.wrapped_token_dek is None
        assert connection.garmin_token_generation is None
        assert connection.tokens_updated_at is None
        _assert_legacy_tokenstore_blocked("token-user")
    finally:
        db.close()
        engine.dispose()


def test_clear_without_explicit_session_removes_encrypted_tokens(
    tmp_path,
    monkeypatch,
) -> None:
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import stage_garmin_tokens
    from db.models import UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    connection = db.query(UserConnection).one()
    stage_garmin_tokens(
        db,
        user_id="token-user",
        serialized_tokens=_serialized_tokens("implicit-db"),
        expected_generation=connection_credentials_generation(connection),
    )
    db.commit()

    try:
        clear_garmin_tokens("token-user")
        db.expire_all()
        connection = db.query(UserConnection).one()

        assert connection.encrypted_garmin_tokens is None
        assert connection.wrapped_token_dek is None
        assert connection.garmin_token_generation is None
        _assert_legacy_tokenstore_blocked("token-user")
    finally:
        db.close()
        engine.dispose()


def test_second_sync_reuses_encrypted_tokens_without_disk(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes import sync as sync_mod
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import load_garmin_tokens
    from db.models import UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, _Session, db = _token_db(monkeypatch)
    login_arguments: list[str] = []
    serialized = _serialized_tokens("sync")
    rotated = _serialized_tokens("rotated")

    class _Inner:
        skip_strategies: set[str] = set()

        def __init__(self) -> None:
            self.serialized = serialized

        def dumps(self) -> str:
            return self.serialized

    class _FakeGarmin:
        def __init__(self, email, password, is_cn=False):
            del email, password, is_cn
            self.client = _Inner()

        def login(self, token_data):
            login_arguments.append(token_data)

        def get_activities_by_date(self, *args, **kwargs):
            return []

        def get_lactate_threshold(self, **kwargs):
            return []

        def get_user_profile(self):
            return {}

        def get_training_status(self, _day):
            self.client.serialized = rotated
            return {}

        def get_training_readiness(self, _day):
            return None

        def get_race_predictions(self):
            return None

        def get_hrv_data(self, _day):
            return None

        def get_sleep_data(self, _day):
            return None

        def get_heart_rates(self, _day):
            return None

    monkeypatch.setattr("garminconnect.Garmin", _FakeGarmin)
    monkeypatch.setattr("sync.garmin_sync.RATE_LIMIT_DELAY", 0)
    for name in (
        "write_activities",
        "write_splits",
        "write_samples",
        "write_lactate_threshold",
        "write_daily_metrics",
        "write_recovery",
        "write_profile_thresholds",
    ):
        monkeypatch.setattr(f"db.sync_writer.{name}", lambda *args, **kwargs: 0)

    class _Config:
        source_options = {"garmin_activity_categories": []}

    monkeypatch.setattr(
        "analysis.config.load_config_from_db",
        lambda user_id, session: _Config(),
    )

    try:
        connection = db.query(UserConnection).one()
        generation = connection_credentials_generation(connection)
        creds = {"email": "runner@example.test", "password": "secret"}

        sync_mod._sync_garmin(
            "token-user",
            creds,
            None,
            db,
            credential_generation=generation,
        )
        sync_mod._sync_garmin(
            "token-user",
            creds,
            None,
            db,
            credential_generation=generation,
        )

        assert len(login_arguments) == 2
        assert login_arguments[0].strip() == "{}"
        assert login_arguments[1].strip() == rotated
        assert all(len(argument) > 512 for argument in login_arguments)
        assert load_garmin_tokens(db, user_id="token-user") == rotated
        _assert_legacy_tokenstore_blocked("token-user")
    finally:
        db.close()
        engine.dispose()


def test_failed_sync_persists_request_time_token_rotation(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes.sync import _sync_garmin
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens
    from db.models import UserConnection
    from garminconnect import GarminConnectAuthenticationError

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, _Session, db = _token_db(monkeypatch)
    initial = _serialized_tokens("before-failure")
    rotated = _serialized_tokens("after-refresh")

    class _Inner:
        skip_strategies: set[str] = set()

        def __init__(self) -> None:
            self.serialized = initial

        def dumps(self) -> str:
            return self.serialized

    class _FakeGarmin:
        def __init__(self, email, password, is_cn=False):
            del email, password, is_cn
            self.client = _Inner()

        def login(self, serialized_tokens):
            assert serialized_tokens.strip() == initial

        def get_scheduled_workouts(self, *args, **kwargs):
            raise AssertionError("profile lookup must fail first")

        def connectapi(self, path):
            assert path == "/userprofile-service/socialProfile"
            self.client.serialized = rotated
            raise GarminConnectAuthenticationError("refreshed request rejected")

    class _Config:
        source_options = {"garmin_activity_categories": []}

    monkeypatch.setattr("garminconnect.Garmin", _FakeGarmin)
    monkeypatch.setattr(
        "analysis.config.load_config_from_db",
        lambda user_id, session: _Config(),
    )

    try:
        connection = db.query(UserConnection).one()
        generation = connection_credentials_generation(connection)
        stage_garmin_tokens(
            db,
            user_id="token-user",
            serialized_tokens=initial,
            expected_generation=generation,
        )
        db.commit()

        with pytest.raises(
            GarminConnectAuthenticationError,
            match="refreshed request rejected",
        ):
            _sync_garmin(
                "token-user",
                {"email": "runner@example.test", "password": "secret"},
                None,
                db,
                credential_generation=generation,
            )

        assert load_garmin_tokens(db, user_id="token-user") == rotated
    finally:
        db.close()
        engine.dispose()


def test_failed_login_persists_login_time_token_rotation(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes.sync import _sync_garmin
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens
    from db.models import UserConnection
    from garminconnect import GarminConnectAuthenticationError

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, _Session, db = _token_db(monkeypatch)
    initial = _serialized_tokens("before-login")
    rotated = _serialized_tokens("during-login")

    class _Inner:
        skip_strategies: set[str] = set()

        def __init__(self) -> None:
            self.serialized = initial

        def dumps(self) -> str:
            return self.serialized

    class _FakeGarmin:
        def __init__(self, email, password, is_cn=False):
            del email, password, is_cn
            self.client = _Inner()

        def login(self, serialized_tokens):
            assert serialized_tokens.strip() == initial
            self.client.serialized = rotated
            raise GarminConnectAuthenticationError("profile load failed")

    class _Config:
        source_options = {"garmin_activity_categories": []}

    monkeypatch.setattr("garminconnect.Garmin", _FakeGarmin)
    monkeypatch.setattr(
        "analysis.config.load_config_from_db",
        lambda user_id, session: _Config(),
    )

    try:
        connection = db.query(UserConnection).one()
        generation = connection_credentials_generation(connection)
        stage_garmin_tokens(
            db,
            user_id="token-user",
            serialized_tokens=initial,
            expected_generation=generation,
        )
        db.commit()

        with pytest.raises(
            GarminConnectAuthenticationError,
            match="profile load failed",
        ):
            _sync_garmin(
                "token-user",
                {"email": "runner@example.test", "password": "secret"},
                None,
                db,
                credential_generation=generation,
            )

        assert load_garmin_tokens(db, user_id="token-user") == rotated
    finally:
        db.close()
        engine.dispose()


def test_outer_commit_recovery_persists_pending_token_rotation(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes.sync import _persist_garmin_token_state_after_rollback
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens
    from db.models import UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, _Session, db = _token_db(monkeypatch)
    initial = _serialized_tokens("committed")
    pending = _serialized_tokens("pending")
    try:
        connection = db.query(UserConnection).one()
        generation = connection_credentials_generation(connection)
        stage_garmin_tokens(
            db,
            user_id="token-user",
            serialized_tokens=initial,
            expected_generation=generation,
        )
        db.commit()
        token_state: dict[str, object] = {
            "client": object(),
            "committed_tokens": initial,
            "pending_tokens": pending,
        }

        assert _persist_garmin_token_state_after_rollback(
            db,
            user_id="token-user",
            credential_generation=generation,
            token_state=token_state,
            allowed_statuses=("connected",),
        )
        assert load_garmin_tokens(db, user_id="token-user") == pending
    finally:
        db.close()
        engine.dispose()


def test_startup_migrates_legacy_tokens_and_deletes_plaintext(
    tmp_path,
    monkeypatch,
) -> None:
    from db import session as db_session
    from db.garmin_tokens import load_garmin_tokens
    from db.models import UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    user_id = "token-user"
    legacy = _garmin_token_dir(user_id)
    os.makedirs(legacy, exist_ok=True)
    serialized = _serialized_tokens("legacy")
    Path(legacy, "garmin_tokens.json").write_text(
        serialized,
        encoding="utf-8",
    )

    try:
        result = migrate_legacy_garmin_tokenstores()
        db.expire_all()
        connection = db.query(UserConnection).one()

        assert result == {"migrated": 1, "removed": 1}
        _assert_legacy_tokenstore_blocked(user_id)
        assert list(Path(_garmin_token_root()).rglob("*token*.json")) == []
        assert load_garmin_tokens(
            db,
            user_id=user_id,
        ) == serialized
        assert connection.encrypted_garmin_tokens is not None
        with pytest.raises(OSError):
            os.makedirs(
                _garmin_token_dir(user_id, "old-worker-generation"),
                exist_ok=True,
            )
        with pytest.raises(OSError):
            os.makedirs(_garmin_token_dir("brand-new-user"), exist_ok=True)
        assert migrate_legacy_garmin_tokenstores() == {
            "migrated": 0,
            "removed": 0,
        }
    finally:
        db.close()
        engine.dispose()


def test_concurrent_startups_elect_one_token_migrator(
    tmp_path,
    monkeypatch,
) -> None:
    from db import crypto
    from db import session as db_session
    from db.models import Base, User, UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setattr(crypto, "_vault", None)
    engine = create_engine(
        f"sqlite:///{tmp_path / 'migration.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    with Session() as db:
        db.add(User(
            id="concurrent-user",
            email="concurrent@example.test",
            hashed_password="x",
            is_active=True,
        ))
        db.add(UserConnection(
            user_id="concurrent-user",
            platform="garmin",
            encrypted_credentials=b"credentials",
            wrapped_dek=b"credential-dek",
            status="connected",
        ))
        db.commit()
    legacy = _garmin_token_dir("concurrent-user")
    os.makedirs(legacy, exist_ok=True)
    Path(legacy, "garmin_tokens.json").write_text(
        _serialized_tokens("concurrent"),
        encoding="utf-8",
    )
    barrier = threading.Barrier(2)
    results: list[dict[str, int]] = []
    errors: list[BaseException] = []

    def migrate() -> None:
        try:
            barrier.wait(timeout=5)
            results.append(migrate_legacy_garmin_tokenstores())
        except BaseException as exc:
            errors.append(exc)

    workers = [threading.Thread(target=migrate) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    try:
        assert not errors
        assert all(not worker.is_alive() for worker in workers)
        assert sorted(
            (result["migrated"], result["removed"])
            for result in results
        ) == [(0, 0), (1, 1)]
        _assert_legacy_tokenstore_blocked("concurrent-user")
    finally:
        engine.dispose()


def test_startup_recovers_root_recreated_after_cutover_crash(
    tmp_path,
    monkeypatch,
) -> None:
    from db import session as db_session
    from db.garmin_tokens import load_garmin_tokens

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    root = _garmin_token_root()
    first = _garmin_token_dir("token-user")
    os.makedirs(first, exist_ok=True)
    Path(first, "garmin_tokens.json").write_text(
        _serialized_tokens("before-crash"),
        encoding="utf-8",
    )
    os.replace(root, root + ".migration")
    recreated = _garmin_token_dir("token-user")
    os.makedirs(recreated, exist_ok=True)
    Path(recreated, "garmin_tokens.json").write_text(
        _serialized_tokens("after-crash"),
        encoding="utf-8",
    )

    try:
        migrate_legacy_garmin_tokenstores()

        assert load_garmin_tokens(
            db,
            user_id="token-user",
        ) == _serialized_tokens("after-crash")
        _assert_legacy_tokenstore_blocked("token-user")
        assert not os.path.exists(root + ".migration")
    finally:
        db.close()
        engine.dispose()


def test_blocker_install_failure_leaves_no_partial_root(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes import sync as sync_mod

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    def fail_replace(source: str, destination: str) -> None:
        del source, destination
        raise OSError("atomic install failed")

    monkeypatch.setattr(sync_mod.os, "replace", fail_replace)

    with pytest.raises(OSError, match="atomic install failed"):
        sync_mod._write_legacy_garmin_root_blocker()

    root = Path(_garmin_token_root())
    assert not root.exists()
    assert list(root.parent.glob(".garmin_tokens.blocker-*")) == []


def test_startup_prefers_current_generation_disk_refresh(
    tmp_path,
    monkeypatch,
) -> None:
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens
    from db.models import UserConnection

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    connection = db.query(UserConnection).one()
    generation = connection_credentials_generation(connection)
    stage_garmin_tokens(
        db,
        user_id="token-user",
        serialized_tokens=_serialized_tokens("database"),
        expected_generation=generation,
    )
    db.commit()
    generation_dir = _garmin_token_dir("token-user", generation)
    os.makedirs(generation_dir, exist_ok=True)
    Path(generation_dir, "garmin_tokens.json").write_text(
        _serialized_tokens("disk"),
        encoding="utf-8",
    )

    try:
        migrate_legacy_garmin_tokenstores()
        db.expire_all()

        assert load_garmin_tokens(
            db,
            user_id="token-user",
        ) == _serialized_tokens("disk")
        _assert_legacy_tokenstore_blocked("token-user")
    finally:
        db.close()
        engine.dispose()


def test_startup_blocks_orphaned_legacy_tokenstore(
    tmp_path,
    monkeypatch,
) -> None:
    from db import session as db_session

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    orphan_dir = _garmin_token_dir("deleted-user")
    os.makedirs(orphan_dir, exist_ok=True)
    Path(orphan_dir, "garmin_tokens.json").write_text(
        _serialized_tokens("orphan"),
        encoding="utf-8",
    )

    try:
        migrate_legacy_garmin_tokenstores()

        _assert_legacy_tokenstore_blocked("deleted-user")
    finally:
        db.close()
        engine.dispose()


def test_startup_preserves_plaintext_when_encryption_key_is_ephemeral(
    tmp_path,
    monkeypatch,
) -> None:
    from db import crypto
    from db import session as db_session

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    legacy = _garmin_token_dir("token-user")
    os.makedirs(legacy, exist_ok=True)
    token_path = Path(legacy, "garmin_tokens.json")
    token_path.write_text(_serialized_tokens("ephemeral"), encoding="utf-8")
    monkeypatch.delenv("PRAXYS_LOCAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("LOCAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("KEY_VAULT_URL", raising=False)
    monkeypatch.setattr(crypto, "_vault", None)

    try:
        with pytest.raises(
            RuntimeError,
            match="persistent encryption key",
        ):
            migrate_legacy_garmin_tokenstores()

        quarantined = Path(
            _garmin_token_root() + ".migration",
            "token-user",
            "garmin_tokens.json",
        )
        assert quarantined.is_file()
        _assert_legacy_tokenstore_blocked("token-user")
    finally:
        db.close()
        engine.dispose()


def test_startup_preserves_plaintext_on_read_error(
    tmp_path,
    monkeypatch,
) -> None:
    from api.routes import sync as sync_mod
    from db import session as db_session

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    engine, Session, db = _token_db(monkeypatch)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    legacy = _garmin_token_dir("token-user")
    os.makedirs(legacy, exist_ok=True)
    token_path = Path(legacy, "garmin_tokens.json")
    token_path.write_text(_serialized_tokens("read-error"), encoding="utf-8")
    monkeypatch.setattr(
        sync_mod,
        "_read_legacy_garmin_tokens",
        lambda path: (_ for _ in ()).throw(OSError("storage unavailable")),
    )

    try:
        with pytest.raises(OSError, match="storage unavailable"):
            migrate_legacy_garmin_tokenstores()

        quarantined = Path(
            _garmin_token_root() + ".migration",
            "token-user",
            "garmin_tokens.json",
        )
        assert quarantined.is_file()
        _assert_legacy_tokenstore_blocked("token-user")
    finally:
        db.close()
        engine.dispose()


def test_sync_garmin_never_passes_a_filesystem_tokenstore(
    tmp_path,
    monkeypatch,
) -> None:
    """A first login must not give garminconnect a persistent path."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    recorded_login: list[tuple[str, str]] = []

    class _FakeGarminClient:
        def __init__(self, email: str, password: str, is_cn: bool = False):
            self.email = email

        def login(self, serialized_tokens) -> None:
            recorded_login.append((self.email, serialized_tokens))

        def get_activities_by_date(self, start, end, activitytype=None):
            return []

        def get_activity_splits(self, aid):
            return {}

        def get_lactate_threshold(self, latest=False, start_date=None, end_date=None):
            return []

        def get_user_profile(self):
            return {}

        def get_training_status(self, d):
            return {}

        def get_training_readiness(self, d):
            return None

        def get_race_predictions(self):
            return None

        def get_hrv_data(self, d):
            return None

        def get_sleep_data(self, d):
            return None

    monkeypatch.setattr("garminconnect.Garmin", _FakeGarminClient)

    # Stub DB-touching helpers so we don't need a full session
    monkeypatch.setattr("db.sync_writer.write_activities", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_splits", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_lactate_threshold", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_daily_metrics", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_recovery", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_profile_thresholds", lambda *a, **k: 0)

    class _FakeConfig:
        source_options = {"garmin_activity_categories": ["running"]}

    monkeypatch.setattr(
        "analysis.config.load_config_from_db", lambda user_id, db: _FakeConfig()
    )

    from api.routes.sync import _sync_garmin

    class _NullDB:
        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return _Q()

        def commit(self):
            pass

        def begin_nested(self):
            return contextlib.nullcontext()

    creds_a = {"email": "a@example.com", "password": "pw"}
    creds_b = {"email": "b@example.com", "password": "pw"}
    _sync_garmin("user-a", creds_a, None, _NullDB())
    _sync_garmin("user-b", creds_b, None, _NullDB())

    assert len(recorded_login) == 2
    email_a, tokens_a = recorded_login[0]
    email_b, tokens_b = recorded_login[1]
    assert (email_a, email_b) == ("a@example.com", "b@example.com")
    assert tokens_a.strip() == "{}"
    assert tokens_b.strip() == "{}"
    assert len(tokens_a) > 512
    assert len(tokens_b) > 512


def test_sync_garmin_first_time_login_uses_credentials_only(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    login_args: list[object] = []

    class _FakeGarminClient:
        def __init__(self, email: str, password: str, is_cn: bool = False):
            pass

        def login(self, serialized_tokens) -> None:
            login_args.append(serialized_tokens)

        def get_activities_by_date(self, *a, **k):
            return []

        def get_activity_splits(self, aid):
            return {}

        def get_lactate_threshold(self, **kwargs):
            return []

        def get_user_profile(self):
            return {}

        def get_training_status(self, d):
            return {}

        def get_training_readiness(self, d):
            return None

        def get_race_predictions(self):
            return None

        def get_hrv_data(self, d):
            return None

        def get_sleep_data(self, d):
            return None

    monkeypatch.setattr("garminconnect.Garmin", _FakeGarminClient)
    for name in (
        "write_activities", "write_splits", "write_lactate_threshold",
        "write_daily_metrics", "write_recovery", "write_profile_thresholds",
    ):
        monkeypatch.setattr(f"db.sync_writer.{name}", lambda *a, **k: 0)

    class _FakeConfig:
        source_options = {"garmin_activity_categories": ["running"]}

    monkeypatch.setattr(
        "analysis.config.load_config_from_db", lambda user_id, db: _FakeConfig()
    )

    from api.routes.sync import _sync_garmin

    class _NullDB:
        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return _Q()

        def commit(self):
            pass

        def begin_nested(self):
            return contextlib.nullcontext()

    _sync_garmin(
        "first-time-user", {"email": "x@example.com", "password": "pw"},
        None, _NullDB(),
    )

    assert len(login_args) == 1
    assert len(login_args) == 1
    assert login_args[0].strip() == "{}"
    assert len(login_args[0]) > 512


def test_sync_garmin_region_prefers_source_options_over_creds(tmp_path, monkeypatch) -> None:
    """Regression: region toggle in Settings UI (source_options.garmin_region)
    must win over the legacy is_cn baked into encrypted credentials.

    Before the fix, users who changed region in Settings saw the UI value
    update but the sync still used the stale is_cn from encrypted_credentials,
    so the client would hit the wrong Garmin SSO — in the worst case rate-
    limiting the account because every retry was against the wrong endpoint.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    recorded_is_cn: list[bool] = []

    class _FakeGarth:
        def dump(self, path): pass

    class _FakeClient:
        def __init__(self, email, password, is_cn=False):
            recorded_is_cn.append(is_cn)
            self.garth = _FakeGarth()

        def login(self, token_dir): pass
        def get_activities_by_date(self, *a, **k): return []
        def get_activity_splits(self, aid): return {}
        def get_lactate_threshold(self, **kwargs): return []
        def get_user_profile(self): return {}
        def get_training_status(self, d): return {}
        def get_training_readiness(self, d): return None
        def get_race_predictions(self): return None
        def get_hrv_data(self, d): return None
        def get_sleep_data(self, d): return None

    monkeypatch.setattr("garminconnect.Garmin", _FakeClient)
    for name in (
        "write_activities", "write_splits", "write_lactate_threshold",
        "write_daily_metrics", "write_recovery", "write_profile_thresholds",
    ):
        monkeypatch.setattr(f"db.sync_writer.{name}", lambda *a, **k: 0)

    class _FakeConfig:
        """source_options says cn, mimicking a user who toggled region to CN."""
        source_options = {
            "garmin_activity_categories": ["running"],
            "garmin_region": "cn",
        }

    monkeypatch.setattr(
        "analysis.config.load_config_from_db", lambda user_id, db: _FakeConfig()
    )

    from api.routes.sync import _sync_garmin

    class _NullDB:
        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k): return self
                def first(self): return None
            return _Q()
        def commit(self): pass
        def begin_nested(self): return contextlib.nullcontext()

    # Creds say is_cn=False (stale). Settings says cn. Settings must win.
    _sync_garmin(
        "u1", {"email": "x@example.com", "password": "pw", "is_cn": False},
        None, _NullDB(),
    )
    assert recorded_is_cn == [True], (
        f"source_options.garmin_region='cn' must override creds.is_cn=False, "
        f"got is_cn={recorded_is_cn!r}"
    )


def test_sync_garmin_region_falls_back_to_creds_when_source_options_missing(
    tmp_path, monkeypatch,
) -> None:
    """Legacy path: connections that predate the region toggle stored is_cn
    in creds only. Without a garmin_region in source_options, use creds.is_cn.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    recorded_is_cn: list[bool] = []

    class _FakeGarth:
        def dump(self, path): pass

    class _FakeClient:
        def __init__(self, email, password, is_cn=False):
            recorded_is_cn.append(is_cn)
            self.garth = _FakeGarth()

        def login(self, token_dir): pass
        def get_activities_by_date(self, *a, **k): return []
        def get_activity_splits(self, aid): return {}
        def get_lactate_threshold(self, **kwargs): return []
        def get_user_profile(self): return {}
        def get_training_status(self, d): return {}
        def get_training_readiness(self, d): return None
        def get_race_predictions(self): return None
        def get_hrv_data(self, d): return None
        def get_sleep_data(self, d): return None

    monkeypatch.setattr("garminconnect.Garmin", _FakeClient)
    for name in (
        "write_activities", "write_splits", "write_lactate_threshold",
        "write_daily_metrics", "write_recovery", "write_profile_thresholds",
    ):
        monkeypatch.setattr(f"db.sync_writer.{name}", lambda *a, **k: 0)

    class _FakeConfig:
        """No garmin_region in source_options — legacy connection shape."""
        source_options = {"garmin_activity_categories": ["running"]}

    monkeypatch.setattr(
        "analysis.config.load_config_from_db", lambda user_id, db: _FakeConfig()
    )

    from api.routes.sync import _sync_garmin

    class _NullDB:
        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k): return self
                def first(self): return None
            return _Q()
        def commit(self): pass
        def begin_nested(self): return contextlib.nullcontext()

    _sync_garmin(
        "u2", {"email": "x@example.com", "password": "pw", "is_cn": True},
        None, _NullDB(),
    )
    assert recorded_is_cn == [True]


def test_sync_garmin_recovery_loop_survives_a_malformed_day(tmp_path, monkeypatch) -> None:
    """Regression: one corrupt Garmin payload must not skip remaining days.

    Before the per-day try/except was added in _sync_garmin's recovery loop,
    an AttributeError inside parse_garmin_recovery (e.g. from Garmin
    returning a present-but-null nested key that .get() couldn't default
    away) propagated to the outer try/except and aborted the whole window,
    writing zero recovery rows. This test simulates that: day 0 returns a
    payload that makes parse_garmin_recovery raise; day 1 returns a valid
    payload; write_recovery must still receive the day-1 row.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    day_calls: dict[str, list[str]] = {"hrv": [], "sleep": []}
    recovery_write_calls: list[list[dict]] = []

    class _FakeGarth:
        def dump(self, path): pass

    class _FakeClient:
        def __init__(self, email, password, is_cn=False):
            self.garth = _FakeGarth()

        def login(self, token_dir): pass
        def get_activities_by_date(self, *a, **k): return []
        def get_activity_splits(self, aid): return {}
        def get_lactate_threshold(self, **kwargs): return []
        def get_user_profile(self): return {}
        def get_training_status(self, d): return {}
        def get_training_readiness(self, d): return None
        def get_race_predictions(self): return None

        def get_hrv_data(self, d):
            day_calls["hrv"].append(d)
            # First iteration (today) → malformed. Later iterations → valid.
            if len(day_calls["hrv"]) == 1:
                # Make float() blow up inside parse_garmin_recovery
                return {"hrvSummary": {"lastNightAvg": "not-a-number"}}
            return {"hrvSummary": {"lastNightAvg": 42}}

        def get_sleep_data(self, d):
            day_calls["sleep"].append(d)
            return {"dailySleepDTO": {"sleepScore": 80, "restingHeartRate": 50}}

    monkeypatch.setattr("garminconnect.Garmin", _FakeClient)
    monkeypatch.setattr("db.sync_writer.write_activities", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_splits", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_lactate_threshold", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_daily_metrics", lambda *a, **k: 0)
    monkeypatch.setattr("db.sync_writer.write_profile_thresholds", lambda *a, **k: 0)

    def _fake_write_recovery(user_id, readiness, sleep, hrv, db, *, garmin_recovery=None):
        recovery_write_calls.append(list(garmin_recovery or []))
        return len(garmin_recovery or [])

    monkeypatch.setattr("db.sync_writer.write_recovery", _fake_write_recovery)

    class _FakeConfig:
        source_options = {"garmin_activity_categories": ["running"]}

    monkeypatch.setattr(
        "analysis.config.load_config_from_db", lambda user_id, db: _FakeConfig()
    )

    from api.routes.sync import _sync_garmin

    class _NullDB:
        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k): return self
                def first(self): return None
            return _Q()
        def commit(self): pass
        def begin_nested(self): return contextlib.nullcontext()

    result = _sync_garmin(
        "bad-day-user",
        {"email": "x@example.com", "password": "pw"},
        None, _NullDB(),
    )

    # Default window is today..today-7 inclusive (8 days). Day 0 is corrupt,
    # remaining 7 produce rows — the loop must not abort on the first failure.
    expected_days = len(day_calls["hrv"])
    assert expected_days >= 7, f"Loop aborted early: {day_calls}"
    assert len(recovery_write_calls) == 1, (
        "write_recovery should be called exactly once with the surviving rows"
    )
    good_rows = recovery_write_calls[0]
    assert len(good_rows) == expected_days - 1, (
        f"Expected {expected_days - 1} good rows (day 0 skipped), "
        f"got {len(good_rows)}"
    )
    assert result.get("recovery") == len(good_rows)
