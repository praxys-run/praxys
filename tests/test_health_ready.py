"""DB-backed readiness probe /api/health/ready (issue #350).

Mirrors the fresh-DB TestClient setup used by tests/test_version.py.
"""
import pytest

from api.china_client_boundary import CN_PRIVACY_CONTRACT_VERSION
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION


@pytest.fixture
def ready_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    for name in (
        "PRAXYS_DISABLE_CN_PROCESSING",
        "PRAXYS_DISABLE_MINIAPP_PROCESSING",
        "PRAXYS_DISABLE_BACKGROUND_AI",
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
    ):
        monkeypatch.delenv(name, raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as client:
        yield client, db_session


def test_health_ready_ok(ready_env, monkeypatch):
    from fastapi import HTTPException
    from api import activity_dfa

    def inactive_policy():
        raise HTTPException(503, 'DFA_SCIENCE_POLICY_INACTIVE')

    monkeypatch.setattr(activity_dfa, 'require_policy', inactive_policy)
    client, _ = ready_env
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert r.json() == {
        "status": "ready",
        "database": "ok",
        "dfa_policy": {"policy_active": False, "contract_digest": None},
        "optional_processing": {
            "background_ai_enabled": False,
            "background_ai_kill_switch": True,
            "feedback_publication_enabled": False,
            "feedback_publication_positive_enable": False,
            "feedback_publication_kill_switch": True,
        },
        "china_processing": {
            "enabled": False,
            "disabled": True,
            "notice_version": TERMS_VERSION,
            "legal_digest": TERMS_CONTENT_DIGEST,
            "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        },
        "miniapp_processing": {
            "enabled": False,
            "disabled": True,
        },
    }


def test_ai_emergency_stop_does_not_fail_core_readiness(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json()["optional_processing"]["background_ai_enabled"] is False
    assert response.json()["optional_processing"]["background_ai_kill_switch"] is True


def test_health_ready_reports_malformed_cn_switch_fail_closed(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "malformed")

    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["china_processing"]["enabled"] is False
    assert r.json()["china_processing"]["disabled"] is True


def test_health_ready_allows_cn_processing_without_registry(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "false")
    from api.channel_processing_authority import (
        reconcile_channel_processing_authority,
    )

    with ready_env[1].SessionLocal() as db:
        reconcile_channel_processing_authority(db)

    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert r.json()["china_processing"]["enabled"] is True
    assert r.json()["china_processing"]["disabled"] is False


def test_health_live_does_not_touch_db(ready_env):
    client, _ = ready_env
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready_503_when_db_unavailable(ready_env, monkeypatch):
    client, db_session = ready_env

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("simulated database outage")

        def close(self):
            pass

    monkeypatch.setattr(db_session, "SessionLocal", lambda: _BrokenSession())
    r = client.get("/api/health/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable", "database": "error"}


def test_health_ready_exposes_only_bounded_dfa_policy(ready_env, monkeypatch):
    from fastapi import HTTPException
    from api import activity_dfa
    client, _ = ready_env
    digest = 'sha256:' + 'a' * 64
    monkeypatch.setattr(activity_dfa, 'require_policy', lambda: digest)
    response = client.get('/api/health/ready')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['dfa_policy'] == {'policy_active': True, 'contract_digest': digest}
    def denied_policy():
        raise HTTPException(503, 'DFA_SCIENCE_POLICY_INACTIVE')
    monkeypatch.setattr(activity_dfa, 'require_policy', denied_policy)
    response = client.get('/api/health/ready')
    assert response.status_code == 200
    assert response.json()['dfa_policy'] == {'policy_active': False, 'contract_digest': None}
    def broken_policy():
        raise RuntimeError('private diagnostic must not leak')
    monkeypatch.setattr(activity_dfa, 'require_policy', broken_policy)
    response = client.get('/api/health/ready')
    assert response.status_code == 200
    assert response.json()['dfa_policy'] == {'policy_active': False, 'contract_digest': None}
    assert 'private diagnostic' not in response.text


@pytest.fixture
def timed_ready(monkeypatch):
    """No service calls: preserve the real adapter, worker and response logic."""
    import threading
    from api import main, activity_dfa, channel_processing_authority, telemetry
    from db import session

    calls, emissions = [], []
    class Session:
        def __init__(self):
            calls.append(('create', threading.get_ident()))
        def connection(self):
            calls.append(('acquire', threading.get_ident()))
        def execute(self, statement):
            assert str(statement) == 'SELECT 1'
            calls.append(('select', threading.get_ident()))
        def close(self):
            calls.append(('close', threading.get_ident()))
    monkeypatch.setattr(session, 'SessionLocal', Session)
    monkeypatch.setattr(channel_processing_authority, 'expected_channel_processing_status', lambda: {'synthetic': False})
    def authority(db):
        calls.append(('authority', threading.get_ident()))
        return {'synthetic': False}
    monkeypatch.setattr(channel_processing_authority, 'shared_channel_processing_snapshot', authority)
    def policy():
        calls.append(('policy', threading.get_ident()))
        raise RuntimeError('private-policy-canary')
    monkeypatch.setattr(activity_dfa, 'require_policy', policy)
    monkeypatch.setattr(telemetry, 'record_readiness_timing', lambda samples, **kw: emissions.append((samples, kw)))
    return main, calls, emissions, Session


def test_readiness_one_dispatch_same_worker_and_fixed_timing_shape(timed_ready, monkeypatch):
    import asyncio
    import threading
    from fastapi import Response
    main, calls, emissions, _ = timed_ready
    original = main.run_in_threadpool
    cpu_clock = main.time.thread_time_ns
    cpu_workers = []
    def worker_cpu():
        cpu_workers.append(threading.get_ident())
        return cpu_clock()
    monkeypatch.setattr(main.time, 'thread_time_ns', worker_cpu)
    dispatched = []
    async def dispatch(*args, **kwargs):
        dispatched.append(threading.get_ident())
        return await original(*args, **kwargs)
    monkeypatch.setattr(main, 'run_in_threadpool', dispatch)
    response = Response()
    result = asyncio.run(main.health_ready(response))
    assert result['status'] == 'ready'
    assert result['dfa_policy'] == {'policy_active': False, 'contract_digest': None}
    assert response.headers['cache-control'] == 'no-store'
    assert len(dispatched) == 1
    assert [name for name, _ in calls] == ['create', 'acquire', 'select', 'authority', 'close', 'policy']
    worker_ids = {identity for _, identity in calls}
    assert len(worker_ids) == 1 and dispatched[0] not in worker_ids
    assert set(cpu_workers) == worker_ids
    assert len(emissions) == 1
    samples, labels = emissions[0]
    assert len(samples) == 10
    assert {stage for stage, _, _, _ in samples} == {
        'dispatch_queue', 'db_acquire', 'db_select', 'shared_authority',
        'db_close', 'controls', 'dfa_policy', 'handler_total'}
    assert {stage for stage, clock, _, _ in samples if clock == 'thread_cpu'} == {'dfa_policy', 'handler_total'}
    assert all(value >= 0 for _, _, value, _ in samples)
    assert labels['parser'] in {'c_safe', 'python_safe'}
    assert {outcome for stage, _, _, outcome in samples if stage == 'dfa_policy'} == {'denied_or_error'}
    assert 'private-policy-canary' not in repr(result) + repr(emissions)


@pytest.mark.parametrize('failing_stage', ['acquire', 'select', 'authority', 'close'])
def test_timed_db_failures_preserve_503_and_finally_cleanup(timed_ready, monkeypatch, failing_stage):
    import asyncio
    from fastapi import Response
    from api import channel_processing_authority
    main, calls, emissions, Session = timed_ready
    def fail(*args):
        raise RuntimeError('private-db-canary')
    if failing_stage == 'authority':
        monkeypatch.setattr(channel_processing_authority, 'shared_channel_processing_snapshot', fail)
    else:
        name = {'acquire': 'connection', 'select': 'execute', 'close': 'close'}[failing_stage]
        original = getattr(Session, name)
        def broken(*args):
            original(*args)
            fail()
        monkeypatch.setattr(Session, name, broken)
    response = Response()
    result = asyncio.run(main.health_ready(response))
    assert response.status_code == 503
    assert result == {'status': 'unavailable', 'database': 'error'}
    assert [name for name, _ in calls].count('close') == 1
    assert 'policy' not in [name for name, _ in calls]
    assert 'private-db-canary' not in repr(result) + repr(emissions)


@pytest.mark.parametrize('failure', ['wall_clock', 'cpu_clock', 'recorder'])
def test_timing_failures_do_not_change_response(timed_ready, monkeypatch, failure):
    import asyncio
    from fastapi import Response
    from api import telemetry
    main, calls, _, _ = timed_ready
    def broken(*args, **kwargs):
        raise RuntimeError('timing-canary')
    if failure == 'recorder':
        monkeypatch.setattr(telemetry, 'record_readiness_timing', broken)
    else:
        monkeypatch.setattr(main.time, 'perf_counter_ns' if failure == 'wall_clock' else 'thread_time_ns', broken)
    response = Response()
    result = asyncio.run(main.health_ready(response))
    assert result['status'] == 'ready' and response.status_code == 200
    assert result['dfa_policy'] == {'policy_active': False, 'contract_digest': None}
    assert [name for name, _ in calls].count('close') == 1


def test_acquisition_query_policy_and_cpu_are_distinct(timed_ready, monkeypatch):
    import asyncio
    from fastapi import Response
    from api import activity_dfa
    main, _, emissions, Session = timed_ready
    ticks = {'wall': 0, 'cpu': 0}
    monkeypatch.setattr(main.time, 'perf_counter_ns', lambda: ticks['wall'] * 1_000_000)
    monkeypatch.setattr(main.time, 'thread_time_ns', lambda: ticks['cpu'] * 1_000_000)
    original_connection, original_execute = Session.connection, Session.execute
    def acquire(self):
        ticks['wall'] += 20
        return original_connection(self)
    def query(self, statement):
        ticks['wall'] += 3
        return original_execute(self, statement)
    def policy():
        ticks['wall'] += 17
        ticks['cpu'] += 4
        raise RuntimeError('inactive')
    monkeypatch.setattr(Session, 'connection', acquire)
    monkeypatch.setattr(Session, 'execute', query)
    monkeypatch.setattr(activity_dfa, 'require_policy', policy)
    asyncio.run(main.health_ready(Response()))
    samples = {(stage, clock): value for stage, clock, value, _ in emissions[0][0]}
    assert samples['db_acquire', 'wall'] == 20
    assert samples['db_select', 'wall'] == 3
    assert samples['dfa_policy', 'wall'] == 17
    assert samples['dfa_policy', 'thread_cpu'] == 4
    assert samples['handler_total', 'thread_cpu'] == 4


def test_running_cancellation_keeps_worker_cleanup_and_other_requests_responsive(timed_ready, monkeypatch):
    import anyio
    import threading
    from fastapi import Response
    main, calls, emissions, Session = timed_ready
    entered, release = threading.Event(), threading.Event()
    original = Session.connection
    owner = []
    def acquire(self):
        original(self)
        if not owner:
            owner.append(threading.get_ident())
            entered.set()
            assert release.wait(5)
    monkeypatch.setattr(Session, 'connection', acquire)
    async def scenario():
        scope = anyio.CancelScope()
        async def request():
            with scope:
                await main.health_ready(Response())
        async with anyio.create_task_group() as group:
            group.start_soon(request)
            try:
                with anyio.fail_after(3):
                    while not entered.is_set():
                        await anyio.sleep(0.001)
                    scope.cancel()
                    # A second request completes while the cancelled worker is
                    # still inside its synchronous DB operation.
                    result = await main.health_ready(Response())
                    assert result['status'] == 'ready'
                    assert not release.is_set()
            finally:
                release.set()
    anyio.run(scenario)
    assert ('close', owner[0]) in calls
    assert len(emissions) == 2


def test_queued_cancellation_never_creates_a_session(timed_ready):
    import anyio
    import threading
    from fastapi import Response
    main, calls, emissions, _ = timed_ready
    entered, release = threading.Event(), threading.Event()
    def occupy():
        entered.set()
        assert release.wait(5)
    async def scenario():
        limiter = anyio.to_thread.current_default_thread_limiter()
        original = limiter.total_tokens
        limiter.total_tokens = 1
        scope = anyio.CancelScope()
        queued = anyio.Event()
        async def request():
            with scope:
                queued.set()
                await main.health_ready(Response())
        try:
            async with anyio.create_task_group() as group:
                group.start_soon(anyio.to_thread.run_sync, occupy)
                try:
                    with anyio.fail_after(3):
                        while not entered.is_set():
                            await anyio.sleep(0.001)
                        group.start_soon(request)
                        await queued.wait()
                        await anyio.sleep(0)
                        scope.cancel()
                        await anyio.sleep(0)
                        assert calls == []
                finally:
                    release.set()
        finally:
            limiter.total_tokens = original
    anyio.run(scenario)
    assert calls == [] and emissions == []


def test_timing_adds_no_database_queries_or_checkouts(ready_env, monkeypatch):
    import threading
    from api import main
    from sqlalchemy import event
    client, db_session = ready_env
    statements, checkouts, checkins, other_workers = [], [], [], []
    context = threading.local()
    original = main._health_ready_worker
    def marked_worker(*args):
        context.probe = True
        try:
            return original(*args)
        finally:
            context.probe = False
    monkeypatch.setattr(main, '_health_ready_worker', marked_worker)
    def before(_conn, _cursor, statement, _parameters, _context, _many):
        if getattr(context, 'probe', False):
            statements.append(statement)
    def checkout(*args):
        if getattr(context, 'probe', False):
            checkouts.append(threading.get_ident())
        else:
            other_workers.append(threading.get_ident())
    def checkin(*args):
        if getattr(context, 'probe', False):
            checkins.append(threading.get_ident())
    event.listen(db_session.engine, 'before_cursor_execute', before)
    event.listen(db_session.engine, 'checkout', checkout)
    event.listen(db_session.engine, 'checkin', checkin)
    try:
        # Prove that unrelated fixture activity is visible to the event hook
        # but excluded by actual worker execution scope, not by query text.
        unrelated_entered, release_unrelated = threading.Event(), threading.Event()
        def unrelated():
            from sqlalchemy import text
            with db_session.SessionLocal() as db:
                db.execute(text('SELECT 2'))
            unrelated_entered.set()
            assert release_unrelated.wait(5)
        other = threading.Thread(target=unrelated)
        other.start()
        try:
            assert unrelated_entered.wait(3)
            response = client.get('/api/health/ready')
        finally:
            release_unrelated.set()
            other.join(timeout=3)
            assert not other.is_alive()
    finally:
        event.remove(db_session.engine, 'before_cursor_execute', before)
        event.remove(db_session.engine, 'checkout', checkout)
        event.remove(db_session.engine, 'checkin', checkin)
    assert response.status_code == 200
    assert len(checkouts) == 1 and checkins == checkouts
    assert other_workers and checkouts[0] not in other_workers
    assert len(statements) == 2
    assert statements[0] == 'SELECT 1'
    assert 'app_config' in statements[1]


def test_real_limiter_queue_delay_is_separate_from_acquisition(timed_ready, monkeypatch):
    import anyio
    import threading
    from fastapi import Response
    main, calls, emissions, _ = timed_ready
    entered, release = threading.Event(), threading.Event()
    ticks = [0]
    monkeypatch.setattr(main.time, 'perf_counter_ns', lambda: ticks[0])
    def occupy():
        entered.set()
        assert release.wait(5)
    async def scenario():
        limiter = anyio.to_thread.current_default_thread_limiter()
        original_tokens = limiter.total_tokens
        limiter.total_tokens = 1
        queued = anyio.Event()
        original_dispatch = main.run_in_threadpool
        async def dispatch(*args, **kwargs):
            queued.set()
            return await original_dispatch(*args, **kwargs)
        monkeypatch.setattr(main, 'run_in_threadpool', dispatch)
        try:
            async with anyio.create_task_group() as group:
                group.start_soon(anyio.to_thread.run_sync, occupy)
                try:
                    with anyio.fail_after(3):
                        while not entered.is_set():
                            await anyio.sleep(.001)
                        group.start_soon(main.health_ready, Response())
                        await queued.wait()
                        await anyio.sleep(0)
                        assert calls == []
                        ticks[0] = 25_000_000
                finally:
                    release.set()
        finally:
            limiter.total_tokens = original_tokens
    anyio.run(scenario)
    samples = {(stage, clock): value for stage, clock, value, _ in emissions[0][0]}
    assert samples['dispatch_queue', 'wall'] == 25
    assert samples['db_acquire', 'wall'] == 0
    assert samples['handler_total', 'wall'] == 0


@pytest.mark.parametrize('failure', ['wall_clock','cpu_clock','recorder'])
def test_timing_failure_cannot_mask_database_failure(timed_ready, monkeypatch, failure):
    import asyncio
    from fastapi import Response
    from api import telemetry
    main, calls, _, Session = timed_ready
    def broken(*args, **kwargs):
        raise RuntimeError('synthetic unavailable dependency')
    monkeypatch.setattr(Session, 'connection', broken)
    if failure == 'recorder':
        monkeypatch.setattr(telemetry, 'record_readiness_timing', broken)
    else:
        monkeypatch.setattr(main.time, 'perf_counter_ns' if failure == 'wall_clock' else 'thread_time_ns', broken)
    response = Response()
    result = asyncio.run(main.health_ready(response))
    assert response.status_code == 503
    assert result == {'status':'unavailable','database':'error'}
    assert [name for name, _ in calls].count('close') == 1
