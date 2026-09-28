"""One bounded execution thread per API worker; SQL owns the global lease."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time

logger = logging.getLogger(__name__)
_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None
_pool: ThreadPoolExecutor | None = None


def wake():
    _wake.set()


def _loop():
    from db import session
    from api import activity_dfa as service
    pending = None
    last_cleanup = 0.
    manifests = None
    while not _stop.is_set():
        try:
            if pending is None or pending.done():
                if pending is not None:
                    finished, pending = pending, None
                    finished.result()
                with session.SessionLocal() as db:
                    try:
                        if manifests is None:
                            manifests = iter(service.storage.iter_manifests())
                        # Retain the cursor across ticks; expired records count
                        # toward the budget too. Owner preflights remain complete.
                        for _ in range(20):
                            value = next(manifests, None)
                            if value is None:
                                manifests = None
                                break
                            service.replay_manifest(db, value)
                    except Exception:
                        db.rollback()
                        manifests = None
                        logger.warning("DFA dispatcher erasure replay unavailable")
                    if time.monotonic()-last_cleanup > 3600:
                        owners = [r[0] for r in db.query(service.Run.user_id).distinct().all()]
                        for owner in owners:
                            with service.owner_write(db, owner):
                                service.cleanup(db, owner)
                                db.commit()
                        last_cleanup = time.monotonic()
                    claimed = service.claim(db)
                if claimed and _pool is not None:
                    pending = _pool.submit(service.execute, session.SessionLocal, *claimed)
        except Exception:
            # No personal values, FIT bytes, numerical results or sensor IDs.
            logger.warning("DFA dispatcher reconciliation unavailable")
        _wake.wait(5)
        _wake.clear()


def start():
    global _thread, _pool
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dfa-compute")
    _thread = threading.Thread(target=_loop, name="dfa-dispatch", daemon=True)
    _thread.start()


def stop():
    global _thread, _pool
    _stop.set()
    _wake.set()
    if _thread is not None:
        _thread.join(timeout=5)
        _thread = None
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None
