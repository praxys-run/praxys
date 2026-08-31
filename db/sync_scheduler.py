"""Background sync scheduler — per-user, staggered.

Runs as a daemon thread started on app boot. Every CHECK_INTERVAL seconds,
scans user_connections for stale entries and triggers sync for each.
Syncs are staggered (one at a time, small delay between) to avoid rate limits.
"""
from contextlib import nullcontext
from collections.abc import Callable
import logging
import os
import threading
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db.connection_credentials import CredentialAccessError
from sync.garmin_errors import garmin_http_status

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 600  # Check every 10 minutes
DEFAULT_SYNC_INTERVAL_HOURS = 6
ALLOWED_SYNC_INTERVAL_HOURS = (6, 12, 24)
DELAY_BETWEEN_SYNCS_SEC = 5  # Stagger between user/platform syncs

# Exponential backoff for failed connections: 1h, 2h, 4h, 8h, 16h, then
# capped at 24h. Without backoff, a stuck Garmin connection retried every
# 10 min triggered Garmin's bot mitigation to escalate from transient
# 429s to a persistent CAPTCHA flag against our outbound IP — see the
# 2026-04-25 lockout postmortem.
BACKOFF_BASE_SEC = 3600
BACKOFF_MAX_SEC = 86400

# Connection-status enums grouped by intent. Two distinct queries hit
# user_connections.status throughout the app and mean different things,
# so we name them explicitly to keep them from drifting:
#
# * SCHEDULABLE_STATUSES — what _check_and_sync attempts to retry.
#   ``auth_required`` is intentionally excluded; the user has to
#   reconnect credentials before we touch the connection again.
# * ACTIVE_CONNECTION_STATUSES — "the user has a configured connection
#   for this platform." Used by analysis/config and the connections
#   listing endpoints to keep an auth-locked user's source preferences
#   and platform list stable while they're stuck in auth_required.
#   Without this, a CAPTCHA-locked Garmin user's analysis would
#   silently fall back to a different (or no) provider on every
#   request, until they reconnect — invisible to them.
SCHEDULABLE_STATUSES: tuple[str, ...] = ("connected", "error")
ACTIVE_CONNECTION_STATUSES: tuple[str, ...] = (
    "connected", "error", "auth_required",
)

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def backoff_seconds(consecutive_failures: int) -> int:
    """Return the retry delay (seconds) after N consecutive failures.

    1h, 2h, 4h, 8h, 16h, 24h, 24h, … — doubles up to BACKOFF_MAX_SEC.
    consecutive_failures is the count *including* the current failure
    (so 1 means "first failure, wait 1h"; 0 is treated as 1).
    """
    n = max(consecutive_failures, 1)
    return min(BACKOFF_BASE_SEC * (2 ** (n - 1)), BACKOFF_MAX_SEC)


def classify_sync_failure(exc: BaseException) -> tuple[str, bool]:
    """Map a sync exception to (connection_status, terminal).

    ``terminal=True`` means we should not auto-retry — only the user
    re-uploading credentials clears it. We use this for two cases:

    * ``GarminConnectAuthenticationError`` — wrong password, or the CN
      "JWT_WEB cookie not set" path that already gets a portal-fallback
      retry inside ``_login_garmin_with_cn_fallback``; if it still
      bubbles up to here, no amount of waiting fixes it.
    * ``CAPTCHA_REQUIRED`` — Garmin's portal login returns this in JSON
      when an account/IP has been flagged for human verification. Our
      headless login has no way to satisfy a CAPTCHA, so we have to
      stop retrying and tell the user to clear the flag in a real
      browser before reconnecting. The marker survives the library's
      "All login strategies exhausted: …" wrapping because the wrapped
      response dict is preserved in the message.
    * ``CredentialAccessError`` — the encrypted connection exists but its
      envelope cannot be opened or decoded. Waiting cannot repair stored
      ciphertext; the user must reconnect to replace it.

    Anything else is treated as transient — the caller applies exponential
    backoff and tries again later.
    """
    cls_name = type(exc).__name__
    msg = str(exc) or ""

    if cls_name in {
        "GarminConnectAuthenticationError",
        "ProviderAuthenticationRequiredError",
    }:
        return ("auth_required", True)
    if garmin_http_status(exc) == 401:
        return ("auth_required", True)
    if isinstance(exc, CredentialAccessError):
        return ("auth_required", True)
    if "CAPTCHA_REQUIRED" in msg:
        return ("auth_required", True)
    return ("error", False)


def _short_error(exc: BaseException) -> str:
    """Compact "<ClassName>: <truncated message>" tag for the connection row.

    Stored on the connection so the UI can show why a sync stopped without
    leaking a full stack trace. Capped well under the column's 500 chars.
    """
    msg = (str(exc) or "").strip()
    if len(msg) > 400:
        msg = msg[:400] + "…"
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


def _record_sync_failure(
    conn,
    exc: BaseException,
    db,
    trigger: str = "unknown",
    expected_credential_generation: str | None = None,
    authorize_commit: Callable[[Session], bool] | None = None,
) -> bool:
    """Update a connection row after a sync failure with classification + backoff.

    Rolls back any pending state from the failed sync, then writes the
    new status, ``consecutive_failures``, ``next_retry_at`` and
    ``last_error`` in a fresh transaction. Best-effort: a write failure
    here just drops the bookkeeping — the next tick will re-classify.
    """
    try:
        db.rollback()
    except Exception:
        pass

    if str(exc) == "SYNC_USER_DELETED":
        return False

    fresh = None
    if expected_credential_generation is not None:
        try:
            from db.connection_credentials import (
                connection_credentials_generation,
            )
            from db.models import UserConnection

            fresh = db.query(UserConnection).filter(
                UserConnection.id == conn.id,
            ).with_for_update().first()
            if (
                fresh is None
                or connection_credentials_generation(fresh)
                != expected_credential_generation
            ):
                db.rollback()
                logger.info(
                    "Ignoring stale sync failure after credential change: "
                    "user=%s platform=%s",
                    getattr(conn, "user_id", "?"),
                    getattr(conn, "platform", "?"),
                )
                return False
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to fence stale sync failure for user=%s platform=%s",
                getattr(conn, "user_id", "?"),
                getattr(conn, "platform", "?"),
            )
            return False

    # Without a live processing-authorization callback this is the legacy
    # scheduler path: preserve fleet-level failure visibility even when the
    # metadata transaction below cannot be opened. Callers that do supply an
    # authorization callback emit only after the fenced commit succeeds.
    if authorize_commit is None:
        try:
            from api import telemetry
            telemetry.record_sync(
                platform=getattr(conn, "platform", "unknown"),
                outcome="failure",
                failure_class=telemetry.classify_platform_error(exc),
                trigger=trigger,
                user_id=getattr(conn, "user_id", "") or "",
            )
        except Exception:
            pass

    try:
        # Re-fetch in case rollback detached state from the prior session.
        from db.models import UserConnection

        if fresh is None:
            fresh = db.query(UserConnection).filter(
                UserConnection.id == conn.id,
            ).with_for_update().first()
        if fresh is None:
            return False
        if fresh.status not in SCHEDULABLE_STATUSES:
            db.rollback()
            logger.info(
                "Ignoring stale sync failure for non-schedulable "
                "connection: user=%s platform=%s status=%s",
                fresh.user_id,
                fresh.platform,
                fresh.status,
            )
            return False

        new_failures = (fresh.consecutive_failures or 0) + 1
        status, terminal = classify_sync_failure(exc)

        fresh.consecutive_failures = new_failures
        fresh.status = status
        fresh.last_error = _short_error(exc)
        if terminal:
            # Auth_required: stop scheduling entirely until reconnect clears
            # the gate. next_retry_at stays NULL; the scheduler skips on
            # status alone.
            fresh.next_retry_at = None
        else:
            delay = backoff_seconds(new_failures)
            fresh.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        if authorize_commit is not None and not authorize_commit(db):
            db.rollback()
            logger.info(
                "Skipped sync failure metadata after authorization loss: "
                "user=%s platform=%s",
                fresh.user_id,
                fresh.platform,
            )
            return False
        db.commit()
        logger.info(
            "Sync failure recorded: user=%s platform=%s status=%s "
            "consecutive=%d next_retry_at=%s",
            fresh.user_id, fresh.platform, status, new_failures,
            fresh.next_retry_at,
        )
        telemetry_authorized = False
        if authorize_commit is not None:
            try:
                telemetry_authorized = authorize_commit(db)
            except Exception:
                telemetry_authorized = False
        if telemetry_authorized:
            try:
                from api import telemetry
                telemetry.record_sync(
                    platform=getattr(conn, "platform", "unknown"),
                    outcome="failure",
                    failure_class=telemetry.classify_platform_error(exc),
                    trigger=trigger,
                    user_id=getattr(conn, "user_id", "") or "",
                )
            except Exception:
                pass
        else:
            logger.info(
                "Skipped sync failure telemetry after authorization loss: "
                "user=%s platform=%s",
                getattr(conn, "user_id", "?"),
                getattr(conn, "platform", "?"),
            )
        return True
    except Exception:
        logger.exception(
            "Failed to record sync failure metadata for user=%s platform=%s",
            getattr(conn, "user_id", "?"), getattr(conn, "platform", "?"),
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False


def reset_connection_backoff(conn) -> None:
    """Reset all retry-state fields on a connection row.

    Called when the user re-uploads credentials (the explicit "I fixed it,
    try again" signal) and after every successful sync. Does not commit —
    the caller commits as part of a larger transaction.
    """
    conn.consecutive_failures = 0
    conn.next_retry_at = None
    conn.last_error = None


def normalize_sync_interval_hours(value: object) -> int:
    """Validate and normalize sync frequency to one of the allowed options."""
    try:
        hours = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Sync interval must be an integer hour value.") from exc
    if hours not in ALLOWED_SYNC_INTERVAL_HOURS:
        raise ValueError(
            f"Sync interval must be one of {ALLOWED_SYNC_INTERVAL_HOURS} hours."
        )
    return hours


def get_user_sync_interval_hours(
    source_options: dict | None, *, user_id: str | None = None
) -> int:
    """Return effective sync interval from source_options with safe fallback.

    Invalid stored values fall back to the default rather than raising — the
    background scheduler must keep running for other users even if one row is
    corrupt — but bad input is logged so config drift is visible.
    """
    if source_options is None:
        return DEFAULT_SYNC_INTERVAL_HOURS
    if not isinstance(source_options, dict):
        logger.warning(
            "source_options for user=%s is %s, expected dict; using default %dh",
            user_id, type(source_options).__name__, DEFAULT_SYNC_INTERVAL_HOURS,
        )
        return DEFAULT_SYNC_INTERVAL_HOURS
    raw = source_options.get("sync_interval_hours")
    if raw is None:
        return DEFAULT_SYNC_INTERVAL_HOURS
    try:
        return normalize_sync_interval_hours(raw)
    except ValueError as exc:
        logger.warning(
            "Invalid sync_interval_hours=%r for user=%s; falling back to %dh: %s",
            raw, user_id, DEFAULT_SYNC_INTERVAL_HOURS, exc,
        )
        return DEFAULT_SYNC_INTERVAL_HOURS


def start_scheduler():
    """Start the background sync scheduler. Safe to call multiple times."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Sync scheduler started (check every %ds)", CHECK_INTERVAL_SEC)


def scheduler_running() -> bool:
    """Return True if the background sync scheduler thread is alive.

    Read by the public status page (``GET /api/status``) to report the
    Background Sync component's health. A ``None`` thread (never started) or a
    dead thread both read as not running.
    """
    return _scheduler_thread is not None and _scheduler_thread.is_alive()


def stop_scheduler():
    """Stop the background sync scheduler."""
    _stop_event.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
    logger.info("Sync scheduler stopped")


def _scheduler_loop():
    """Main scheduler loop — runs in a background thread."""
    # Wait a bit on startup to let the app fully initialize
    _stop_event.wait(30)

    while not _stop_event.is_set():
        try:
            _check_and_sync()
        except Exception:
            logger.exception("Scheduler tick failed")
        _run_personal_context_retention_tick()
        _run_managed_delivery_tick()
        _stop_event.wait(CHECK_INTERVAL_SEC)


def _run_personal_context_retention_tick() -> None:
    """Run private-context expiry and purge without disrupting sync."""
    try:
        from api.personal_context import run_scheduled_retention

        run_scheduled_retention()
    except Exception:
        logger.exception("Personal-context retention scheduler tick failed")


def _run_managed_delivery_tick() -> None:
    """Run managed-plan retries without disrupting regular platform sync."""
    try:
        from api.plan_delivery.rolling import run_scheduled_managed_deliveries

        run_scheduled_managed_deliveries()
    except Exception:
        logger.exception("Managed-plan delivery scheduler tick failed")


def _check_and_sync():
    """Check all user connections and sync stale ones."""
    from db.session import init_db, SessionLocal
    from db.models import User, UserConnection, UserConfig
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION

    init_db()
    db = SessionLocal()
    try:
        # SCHEDULABLE_STATUSES intentionally excludes ``auth_required`` —
        # those connections are blocked on user action (re-upload
        # credentials after clearing whatever account-level gate Garmin
        # or Stryd flagged) and silently retrying just escalates the
        # gate further.
        connections = (
            db.query(UserConnection)
            .join(User, User.id == UserConnection.user_id)
            .filter(
                UserConnection.status.in_(SCHEDULABLE_STATUSES),
                User.is_active == True,  # noqa: E712
                User.terms_version == TERMS_VERSION,
                User.terms_digest == TERMS_CONTENT_DIGEST,
            )
            .all()
        )

        now = datetime.utcnow()
        sync_intervals_by_user: dict[str, int] = {}
        stryd_access_by_user: dict[str, bool] = {}
        for conn in connections:
            if conn.platform == "stryd":
                if conn.user_id not in stryd_access_by_user:
                    from api.stryd_access import stryd_connection_enabled

                    stryd_access_by_user[conn.user_id] = (
                        stryd_connection_enabled(
                            db,
                            user_id=conn.user_id,
                        )
                    )
                if not stryd_access_by_user[conn.user_id]:
                    continue
            # Skip connections still in their backoff window. ``next_retry_at``
            # is bumped after every transient failure (see _record_sync_failure)
            # and cleared on success or reconnect (reset_connection_backoff).
            if conn.next_retry_at and conn.next_retry_at > now:
                continue

            if conn.user_id not in sync_intervals_by_user:
                # Isolate per-user config lookup so one bad row can't skip every
                # remaining user this tick.
                try:
                    config = (
                        db.query(UserConfig.source_options)
                        .filter(UserConfig.user_id == conn.user_id)
                        .first()
                    )
                    source_options = config[0] if config else None
                    sync_intervals_by_user[conn.user_id] = get_user_sync_interval_hours(
                        source_options, user_id=conn.user_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to load sync interval for user=%s; using default %dh",
                        conn.user_id, DEFAULT_SYNC_INTERVAL_HOURS,
                    )
                    sync_intervals_by_user[conn.user_id] = DEFAULT_SYNC_INTERVAL_HOURS
            interval_hours = sync_intervals_by_user[conn.user_id]
            last = conn.last_sync
            if last and (now - last) < timedelta(hours=interval_hours):
                continue  # Not stale yet

            logger.info(
                "Scheduled sync: user=%s platform=%s (last=%s interval=%sh "
                "consecutive_failures=%d)",
                conn.user_id, conn.platform, last, interval_hours,
                conn.consecutive_failures or 0,
            )
            expected_connection_generation = None
            if conn.platform == "garmin":
                from db.connection_credentials import (
                    connection_credentials_generation,
                )

                expected_connection_generation = (
                    connection_credentials_generation(conn)
                )
            try:
                _sync_connection(
                    conn.user_id,
                    conn.platform,
                    db,
                    expected_connection_generation=(
                        expected_connection_generation
                    ),
                )
                time.sleep(DELAY_BETWEEN_SYNCS_SEC)
            except Exception as exc:
                from db.connection_credentials import (
                    ConnectionGenerationChanged,
                )
                from api.legal_receipts import (
                    user_background_processing_authorized,
                )

                if isinstance(exc, ConnectionGenerationChanged):
                    db.rollback()
                    logger.info(
                        "Cancelled stale scheduled sync: user=%s platform=%s",
                        conn.user_id,
                        conn.platform,
                    )
                    continue
                logger.exception(
                    "Scheduled sync failed: user=%s platform=%s",
                    conn.user_id, conn.platform,
                )
                _record_sync_failure(
                    conn,
                    exc,
                    db,
                    trigger="scheduled",
                    expected_credential_generation=(
                        expected_connection_generation
                    ),
                    authorize_commit=lambda check_db: (
                        user_background_processing_authorized(
                            check_db,
                            conn.user_id,
                        )
                    ),
                )
    finally:
        db.close()


def _sync_connection(
    user_id: str,
    platform: str,
    db: Session,
    *,
    expected_connection_generation: str | None = None,
) -> None:
    """Run one scheduled sync inside the shared background-sync fence."""
    from api.routes.sync import (
        BackgroundProcessingAuthorizationLost,
        _begin_background_sync_execution,
        _end_background_sync_execution,
        _require_background_processing_authorized,
    )

    context_token = _begin_background_sync_execution(user_id, db)
    try:
        try:
            _sync_connection_authorized(
                user_id,
                platform,
                db,
                expected_connection_generation=(
                    expected_connection_generation
                ),
            )
        except BackgroundProcessingAuthorizationLost:
            db.rollback()
            logger.info(
                "Cancelled scheduled sync after processing authorization "
                "was withdrawn: user=%s platform=%s",
                user_id,
                platform,
            )
        except Exception:
            db.rollback()
            try:
                _require_background_processing_authorized(user_id, db)
            except BackgroundProcessingAuthorizationLost:
                db.rollback()
                logger.info(
                    "Cancelled failed scheduled sync after processing "
                    "authorization was withdrawn: user=%s platform=%s",
                    user_id,
                    platform,
                )
                return
            raise
    finally:
        _end_background_sync_execution(context_token)


def _sync_connection_authorized(
    user_id: str,
    platform: str,
    db: Session,
    *,
    expected_connection_generation: str | None = None,
) -> None:
    """Sync a single user-platform connection using encrypted credentials.

    Uses the sync route's fetch + DB write functions (no CSV intermediate).
    """
    from api.legal_receipts import user_background_processing_authorized

    if not user_background_processing_authorized(db, user_id):
        logger.info(
            "Skipping scheduled sync outside the current processing "
            "boundary: user=%s",
            user_id,
        )
        return

    from db.connection_credentials import (
        ConnectionGenerationChanged,
        connection_credentials_generation,
        load_connection_credentials,
        require_connection_generation,
    )
    from db.models import UserConnection

    if platform == "stryd":
        from api.stryd_access import stryd_connection_enabled

        if not stryd_connection_enabled(db, user_id=user_id):
            logger.info(
                "Skipping private Stryd sync for ineligible user=%s",
                user_id,
            )
            return

    token_lease = nullcontext()
    if platform == "garmin":
        from api.routes.sync import _garmin_tokenstore_lease

        token_lease = _garmin_tokenstore_lease(user_id)

    with token_lease:
        if not user_background_processing_authorized(db, user_id):
            logger.info(
                "Skipping scheduled sync after lease acquisition outside "
                "the current processing boundary: user=%s",
                user_id,
            )
            return
        conn = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == platform,
        ).first()
        if not conn:
            logger.warning(
                "No credentials for user=%s platform=%s",
                user_id,
                platform,
            )
            return

        credentials = load_connection_credentials(
            db,
            user_id=user_id,
            platform=platform,
        )
        if credentials is None:
            logger.warning(
                "No credentials for user=%s platform=%s",
                user_id,
                platform,
            )
            return
        creds = credentials
        if platform == "garmin" and expected_connection_generation is None:
            expected_connection_generation = (
                connection_credentials_generation(conn)
            )
        if expected_connection_generation is not None:
            require_connection_generation(
                db,
                user_id=user_id,
                platform=platform,
                expected_generation=expected_connection_generation,
                allowed_statuses=SCHEDULABLE_STATUSES,
            )

        # Use the sync route's direct DB write functions.
        from api.routes.sync import (
            BackgroundProcessingAuthorizationLost,
            _commit_authorized_background_sync_changes,
            _persist_garmin_token_state_after_rollback,
            _require_background_processing_authorized,
            _sync_coros,
            _sync_garmin,
            _sync_oura,
            _sync_strava,
            _sync_stryd,
        )
        garmin_token_state: dict[str, object] = {}

        if not user_background_processing_authorized(db, user_id):
            logger.info(
                "Skipping scheduled provider call outside the current "
                "processing boundary: user=%s platform=%s",
                user_id,
                platform,
            )
            return
        if platform == "garmin":
            counts = _sync_garmin(
                user_id,
                creds,
                None,
                db,
                credential_generation=expected_connection_generation,
                _token_state=garmin_token_state,
            )
        elif platform == "strava":
            counts = _sync_strava(user_id, creds, None, db)
        elif platform == "coros":
            counts = _sync_coros(user_id, creds, None, db)
        elif platform == "stryd":
            counts = _sync_stryd(user_id, creds, None, db)
        elif platform == "oura":
            counts = _sync_oura(user_id, creds, None, db)
        else:
            logger.warning("Unknown platform: %s", platform)
            return

        try:
            if expected_connection_generation is not None:
                require_connection_generation(
                    db,
                    user_id=user_id,
                    platform=platform,
                    expected_generation=expected_connection_generation,
                    allowed_statuses=SCHEDULABLE_STATUSES,
                    lock=True,
                )
            _commit_authorized_background_sync_changes(user_id, db)
        except ConnectionGenerationChanged:
            db.rollback()
            raise
        except BackgroundProcessingAuthorizationLost:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            if (
                platform == "garmin"
                and expected_connection_generation is not None
            ):
                try:
                    persisted = _persist_garmin_token_state_after_rollback(
                        db,
                        user_id=user_id,
                        credential_generation=expected_connection_generation,
                        token_state=garmin_token_state,
                        allowed_statuses=SCHEDULABLE_STATUSES,
                    )
                    if not persisted:
                        logger.warning(
                            "Skipped stale Garmin token publication after "
                            "scheduled commit failure for user=%s",
                            user_id,
                        )
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Failed to persist Garmin OAuth tokens after scheduled "
                        "commit failure for user=%s",
                        user_id,
                    )
            raise

    # Refresh activity-derived CP after the sync — best-effort, never break
    # the scheduled sync if the fit fails. Skipped for Oura since it writes
    # no activity power.
    if platform in ("garmin", "strava", "stryd", "coros"):
        try:
            from db.sync_writer import update_cp_from_activities
            fit = update_cp_from_activities(user_id, db)
            if fit is not None:
                if expected_connection_generation is not None:
                    require_connection_generation(
                        db,
                        user_id=user_id,
                        platform=platform,
                        expected_generation=(
                            expected_connection_generation
                        ),
                        allowed_statuses=SCHEDULABLE_STATUSES,
                        lock=True,
                    )
                _commit_authorized_background_sync_changes(user_id, db)
                logger.info(
                    "Activity-derived CP for user=%s: %.1fW (r²=%.2f, %d points)",
                    user_id, fit["cp_watts"], fit["r_squared"], fit["point_count"],
                )
        except ConnectionGenerationChanged:
            raise
        except BackgroundProcessingAuthorizationLost:
            db.rollback()
            raise
        except Exception:
            logger.exception("Activity-derived CP refresh failed: user=%s", user_id)
            db.rollback()

    # Update last_sync and clear any prior backoff state — a successful
    # sync is the strongest possible signal that the connection is healthy.
    current_connection = (
        require_connection_generation(
            db,
            user_id=user_id,
            platform=platform,
            expected_generation=expected_connection_generation,
            allowed_statuses=SCHEDULABLE_STATUSES,
            lock=True,
        )
        if expected_connection_generation is not None
        else conn
    )
    current_connection.last_sync = datetime.utcnow()
    current_connection.status = "connected"
    reset_connection_backoff(current_connection)
    _commit_authorized_background_sync_changes(user_id, db)
    logger.info("Sync complete: user=%s platform=%s counts=%s", user_id, platform, counts)

    # Scheduled-path success telemetry (the manual path emits from _run_sync).
    _require_background_processing_authorized(user_id, db)
    try:
        from api import telemetry
        telemetry.record_sync(
            platform=platform, outcome="success", failure_class="none",
            trigger="scheduled", user_id=user_id,
        )
    except Exception:
        pass

    # Conservative plan changes are separately consented and deterministic.
    # Run before generated insights so both surfaces observe the same plan.
    try:
        from api.plan_adjustments import run_plan_adjustment_for_user

        _require_background_processing_authorized(user_id, db)
        adjustment_result = run_plan_adjustment_for_user(
            user_id,
            trigger=f"scheduled_sync:{platform}",
        )
        logger.info(
            "Plan adjustment for user=%s platform=%s: %s",
            user_id,
            platform,
            adjustment_result.get("status"),
        )
    except BackgroundProcessingAuthorizationLost:
        raise
    except Exception:
        logger.exception(
            "Post-sync plan adjustment failed for user=%s platform=%s",
            user_id,
            platform,
        )

    # Post-sync LLM insight generation. Best-effort; never raises.
    try:
        _require_background_processing_authorized(user_id, db)
        from api.insights_runner import run_insights_for_user
        insight_results = run_insights_for_user(user_id, db, counts)
        logger.info("Insight generation for user=%s: %s", user_id, insight_results)
    except BackgroundProcessingAuthorizationLost:
        raise
    except Exception:
        # No rollback: the runner uses its own session, and the caller's
        # session has nothing pending past the prior db.commit().
        logger.exception("Insight generation failed for user=%s", user_id)
