"""SQLAlchemy ORM models for the Praxys database.

The on-disk SQLite filename is still `trainsight.db` — we keep the legacy
filename to avoid user-data migration risk. Only the codebase-level brand
references have been renamed.
"""
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DDL,
    Index,
    String,
    Float,
    Integer,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    JSON,
    LargeBinary,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """User model for FastAPI-Users."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email = Column(String(320), unique=True, index=True, nullable=False)
    hashed_password = Column(String(1024), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_demo = Column(Boolean, default=False, nullable=False)
    # ondelete=SET NULL is a DB-level safety net: the account-deletion path
    # removes a deleted user's demo mirror, but SET NULL guarantees a raw delete
    # can't strand a dangling demo_of reference (issue #366).
    demo_of = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Throttled last-activity timestamp powering the WAU/DAU admin gauge.
    # Written by api/auth.py on authenticated requests, but only when stale
    # (see LAST_SEEN_THROTTLE) so it is not a per-request write. Admin-only
    # aggregate display; never exposed per-user to non-admins.
    last_seen_at = Column(DateTime, nullable=True, index=True)

    # EULA acceptance recorded at registration: proves which Terms/EULA
    # version each user agreed to and when. See api/legal.py::TERMS_VERSION.
    terms_version = Column(String(20), nullable=True)
    terms_accepted_at = Column(DateTime, nullable=True)

    # WeChat Mini Program identity. openid is per-app, unionid spans apps under the
    # same WeChat Open Platform account. We keep email NOT NULL for FastAPI-Users
    # compatibility; WeChat-only users get the synthetic sentinel "wechat:<openid>"
    # (see api/routes/wechat.py::_synthetic_email — unquoted colon cannot collide
    # with a real RFC-5322 address).
    wechat_openid = Column(String(64), unique=True, index=True, nullable=True)
    wechat_unionid = Column(String(64), index=True, nullable=True)
    wechat_nickname = Column(String(100), nullable=True)
    wechat_avatar_url = Column(String(500), nullable=True)

    config = relationship("UserConfig", back_populates="user", uselist=False)
    connections = relationship("UserConnection", back_populates="user")


class Invitation(Base):
    """One-time invitation codes for registration."""

    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(12), unique=True, nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # NOTE: intentionally NO ondelete=SET NULL here. Invitation validity is
    # "is_active AND used_by IS NULL" (see api/invitations.py), so nulling
    # used_by alone would recycle a consumed code. The account-deletion path
    # nulls used_by AND deactivates the code together; a bare DB SET NULL can't
    # flip is_active, so it is deliberately omitted (issue #366).
    used_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    # Optional expiry for emailed invitations (waitlist-invite flow). NULL =
    # never expires (admin-generated codes). Enforced in api/invitations.py so
    # an expired code cannot be claimed even though it is still is_active.
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    note = Column(String(200), default="")


class UserConfig(Base):
    """Per-user configuration (mirrors analysis.config.UserConfig dataclass)."""

    __tablename__ = "user_config"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    display_name = Column(String(100), default="")
    unit_system = Column(String(10), default="metric")
    training_base = Column(String(10), default="power")
    preferences = Column(JSON, default=dict)
    plan_management = Column(JSON, default=dict)
    plan_execution_target = Column(String(20), nullable=True)
    thresholds = Column(JSON, default=dict)
    zones = Column(JSON, default=dict)
    goal = Column(JSON, default=dict)
    science = Column(JSON, default=dict)
    zone_labels = Column(String(50), default="standard")
    activity_routing = Column(JSON, default=dict)
    source_options = Column(JSON, default=dict)
    language = Column(String(10), nullable=True)
    today_decision_check_claimed_at = Column(DateTime, nullable=True)
    today_decision_check_shown_at = Column(DateTime, nullable=True)
    today_decision_check_submitted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="config")


class UserConnection(Base):
    """Per-user platform connections with encrypted credentials and sessions."""

    __tablename__ = "user_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    platform = Column(String(20), nullable=False)  # garmin, stryd, oura
    encrypted_credentials = Column(LargeBinary, nullable=True)
    wrapped_dek = Column(LargeBinary, nullable=True)
    encrypted_garmin_tokens = Column(LargeBinary, nullable=True)
    wrapped_token_dek = Column(LargeBinary, nullable=True)
    garmin_token_generation = Column(String(160), nullable=True)
    tokens_updated_at = Column(DateTime, nullable=True)
    preferences = Column(JSON, default=dict)  # {"activities": True, "recovery": True, ...}
    last_sync = Column(DateTime, nullable=True)
    status = Column(
        String(20), default="disconnected"
    )  # connected, error, auth_required, expired, disconnected

    # Scheduler backoff state. Without this, a stuck connection (expired
    # token, account-locked, CAPTCHA-gated) made the scheduler retry every
    # 10 min indefinitely, which on 2026-04-25 escalated Garmin's bot
    # mitigation from transient 429s to a persistent CAPTCHA flag against
    # the App Service outbound IP. consecutive_failures drives exponential
    # backoff; next_retry_at gates the scheduler (skip while in future);
    # last_error captures a short tag for the UI. All three reset on
    # successful sync or when the user reconnects credentials.
    consecutive_failures = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    # Legacy column name; this is now an internal account-generation fence,
    # not a user-facing consent bit. The durable execution target records the
    # user's choice. Reconnect or region changes invalidate this hash so an old
    # Garmin account can never inherit delivery authorization.
    plan_delivery_consent = Column(String(64), nullable=True)

    user = relationship("User", back_populates="connections")
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_user_platform"),
    )


class Activity(Base):
    """Activity data (merged from Garmin/Stryd/etc.)."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    activity_id = Column(String(100), nullable=False)
    date = Column(Date, nullable=False, index=True)
    activity_type = Column(String(50), default="running")
    distance_km = Column(Float, nullable=True)
    duration_sec = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    relative_humidity_pct = Column(Float, nullable=True)
    environment_source = Column(String(40), nullable=True)
    avg_power = Column(Float, nullable=True)
    max_power = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)
    avg_pace_min_km = Column(String(20), nullable=True)
    avg_pace_sec_km = Column(Float, nullable=True)
    elevation_gain_m = Column(Float, nullable=True)
    avg_cadence = Column(Float, nullable=True)
    training_effect = Column(Float, nullable=True)
    rss = Column(Float, nullable=True)
    trimp = Column(Float, nullable=True)
    rtss = Column(Float, nullable=True)
    cp_estimate = Column(Float, nullable=True)
    load_score = Column(Float, nullable=True)
    start_time = Column(String(50), nullable=True)
    source = Column(String(20), default="garmin")

    __table_args__ = (
        UniqueConstraint("user_id", "activity_id", name="uq_user_activity"),
    )


class ActivitySplit(Base):
    """Per-interval split data within activities."""

    __tablename__ = "activity_splits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    activity_id = Column(String(100), nullable=False)
    split_num = Column(Integer, nullable=False)
    distance_km = Column(Float, nullable=True)
    duration_sec = Column(Float, nullable=True)
    avg_power = Column(Float, nullable=True)
    power_source = Column(String(20), nullable=True)
    avg_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)
    avg_pace_min_km = Column(String(20), nullable=True)
    avg_pace_sec_km = Column(Float, nullable=True)
    avg_cadence = Column(Float, nullable=True)
    elevation_change_m = Column(Float, nullable=True)


class ActivitySample(Base):
    """Per-second time-series data for an activity.

    One row per second per activity. Columns cover the union of all connector
    field sets; connector-specific fields are NULL for other sources. The
    unique constraint on (user_id, activity_id, t_sec) makes re-syncs idempotent —
    duplicate writes are silently ignored via INSERT OR IGNORE.

    Storage estimate: ~3,600 rows/hour of running. At SQLite scale for
    personal use this is negligible; multi-user growth is managed by the
    user_id index enabling efficient per-user pruning.
    """

    __tablename__ = "activity_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    activity_id = Column(String(100), nullable=False)
    source = Column(String(20), nullable=False)  # stryd | garmin | coros | strava

    # Seconds since epoch — the time axis for all other fields
    t_sec = Column(Integer, nullable=False)

    # Core — present across all connectors
    power_watts = Column(Float, nullable=True)
    hr_bpm = Column(Float, nullable=True)
    speed_ms = Column(Float, nullable=True)
    pace_sec_km = Column(Float, nullable=True)
    cadence_spm = Column(Float, nullable=True)
    altitude_m = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)  # cumulative from activity start

    # GPS — Garmin, Strava, COROS
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    grade_pct = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)

    # Stryd running dynamics
    ground_time_ms = Column(Float, nullable=True)
    oscillation_mm = Column(Float, nullable=True)
    leg_spring_kn_m = Column(Float, nullable=True)
    vertical_ratio = Column(Float, nullable=True)
    form_power_watts = Column(Float, nullable=True)

    # Garmin-specific
    respiration_rate = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "activity_id", "t_sec", name="uq_sample_user_activity_t"),
        Index("ix_sample_activity", "activity_id"),
    )


class RecoveryData(Base):
    """Sleep and readiness data (from Oura, Garmin, etc.)."""

    __tablename__ = "recovery_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    readiness_score = Column(Float, nullable=True)
    hrv_avg = Column(Float, nullable=True)
    resting_hr = Column(Float, nullable=True)
    sleep_score = Column(Float, nullable=True)
    total_sleep_sec = Column(Float, nullable=True)
    deep_sleep_sec = Column(Float, nullable=True)
    rem_sleep_sec = Column(Float, nullable=True)
    body_temp_delta = Column(Float, nullable=True)
    source = Column(String(20), default="oura")

    __table_args__ = (
        UniqueConstraint("user_id", "date", "source", name="uq_user_date_recovery"),
    )


class FitnessData(Base):
    """Per-metric fitness data (VO2max, LTHR, CP estimate, etc.)."""

    __tablename__ = "fitness_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    metric_type = Column(String(30), nullable=False)
    value = Column(Float, nullable=True)
    value_str = Column(String(100), nullable=True)
    source = Column(String(20), default="garmin")
    power_source = Column(String(20), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "metric_type", "source", name="uq_user_date_metric"
        ),
    )


class AiInsight(Base):
    """AI-generated insights — written by the post-sync LLM runner
    (``api/insights_runner.py``) and the legacy CLI / MCP push paths."""

    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    insight_type = Column(String(30), nullable=False)  # training_review, daily_brief, race_forecast
    headline = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)
    findings = Column(JSON, default=list)  # [{type, text}, ...]
    recommendations = Column(JSON, default=list)  # [str, ...]
    meta = Column(JSON, default=dict)  # data_range, training_base, dataset_hash, etc.
    # Issue #103: bilingual payload. Top-level fields stay English so legacy
    # CLI/MCP push paths keep working; the frontend reads
    # translations[locale] when present and falls back to top-level English.
    translations = Column(JSON, default=dict)
    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "insight_type", name="uq_user_insight_type"),
    )


class AiInsightFeedback(Base):
    """Durable, dataset-scoped feedback for generated Coach insights."""

    __tablename__ = "ai_insight_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight_type = Column(String(30), nullable=False)
    dataset_hash = Column(String(64), nullable=False)
    vote = Column(String(4), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("vote IN ('up', 'down')", name="ck_ai_insight_feedback_vote"),
        UniqueConstraint(
            "user_id",
            "insight_type",
            "dataset_hash",
            name="uq_ai_insight_feedback_dataset",
        ),
    )


class LabsExperimentEnrollment(Base):
    """Active opt-in and processing state for one Labs experiment."""

    __tablename__ = "labs_experiment_enrollments"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    experiment_id = Column(String(80), primary_key=True)
    consent_version = Column(String(40), nullable=False)
    consented_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    adult_attested_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    model_version = Column(String(80), nullable=False)
    source_revision = Column(String(100), nullable=False)
    correlation_id = Column(String(36), nullable=False)
    availability_reason = Column(JSON, nullable=True)
    queued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','processing','available','unavailable','failed','stale')",
            name="ck_labs_enrollment_status",
        ),
    )


class LabsExperimentResult(Base):
    """Aggregate-only output for one consented Labs experiment."""

    __tablename__ = "labs_experiment_results"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    experiment_id = Column(String(80), primary_key=True)
    model_version = Column(String(80), nullable=False)
    source_revision = Column(String(100), nullable=False)
    result_state = Column(String(40), nullable=False)
    eligibility_counts = Column(JSON, nullable=False, default=dict)
    aggregate_curve_points = Column(JSON, nullable=False, default=list)
    aggregate_uncertainty = Column(JSON, nullable=False, default=dict)
    gate_statuses = Column(JSON, nullable=False, default=dict)
    prediction_status = Column(String(40), nullable=False)
    power_regime = Column(String(60), nullable=False)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LabsDeletionTombstone(Base):
    """Withdrawal marker replayed after backup restores."""

    __tablename__ = "labs_deletion_tombstones"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    experiment_id = Column(String(80), primary_key=True)
    deleted_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LabsAnalysisJob(Base):
    """Durable execution record for one isolated Labs analysis generation."""

    __tablename__ = "labs_analysis_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_id = Column(String(80), nullable=False)
    trigger = Column(String(24), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    model_version = Column(String(80), nullable=False)
    source_revision = Column(String(100), nullable=False)
    correlation_id = Column(String(36), nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    failure_code = Column(String(64), nullable=True)
    retryable_failure = Column(Boolean, nullable=False, default=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dispatched_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "trigger IN ('enrollment','manual_recompute')",
            name="ck_labs_analysis_job_trigger",
        ),
        CheckConstraint(
            "status IN ("
            "'queued','dispatched','processing','retrying',"
            "'succeeded','failed','cancelled','dead_lettered'"
            ")",
            name="ck_labs_analysis_job_status",
        ),
        UniqueConstraint(
            "user_id",
            "experiment_id",
            "trigger",
            "idempotency_key",
            name="uq_labs_analysis_job_idempotency",
        ),
        Index(
            "uq_labs_analysis_job_active",
            "user_id",
            "experiment_id",
            unique=True,
            sqlite_where=text(
                "status IN ('queued','dispatched','processing','retrying')"
            ),
            postgresql_where=text(
                "status IN ('queued','dispatched','processing','retrying')"
            ),
        ),
        Index(
            "ix_labs_analysis_job_requested",
            "user_id",
            "experiment_id",
            "requested_at",
        ),
    )


class LabsAnalysisOutbox(Base):
    """Payload-free transactional outbox entry for one Labs job."""

    __tablename__ = "labs_analysis_outbox"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id = Column(
        String(36),
        ForeignKey("labs_analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status = Column(String(16), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    lease_expires_at = Column(DateTime, nullable=True)
    last_error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dispatched_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','dispatching','dispatched','cancelled')",
            name="ck_labs_analysis_outbox_status",
        ),
        Index(
            "ix_labs_analysis_outbox_dispatch",
            "status",
            "available_at",
        ),
    )


class McpAccessHandoff(Base):
    """Opaque, short-lived first-party approval handoff for MCP access."""

    __tablename__ = "mcp_access_handoffs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    state_digest = Column(String(64), nullable=False, unique=True)
    exchange_digest = Column(String(64), nullable=False, unique=True)
    request_type = Column(String(16), nullable=False)
    audience = Column(String(64), nullable=False)
    actor_id = Column(String(120), nullable=False)
    requested_scopes = Column(JSON, nullable=False, default=list)
    requested_purposes = Column(JSON, nullable=False, default=list)
    requested_kinds = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False, default="pending")
    expires_at = Column(DateTime, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    exchanged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "request_type IN ('session','context')",
            name="ck_mcp_access_handoff_request_type",
        ),
        CheckConstraint(
            "audience = 'praxys-coach-plugin'",
            name="ck_mcp_access_handoff_audience",
        ),
        CheckConstraint(
            "status IN ('pending','approved','denied','exchanged')",
            name="ck_mcp_access_handoff_status",
        ),
        CheckConstraint(
            "request_type = 'session' OR user_id IS NOT NULL",
            name="ck_mcp_access_handoff_context_owner",
        ),
        Index(
            "ix_mcp_access_handoff_expiry",
            "status",
            "expires_at",
        ),
    )


class McpAccessToken(Base):
    """Hashed, revocable MCP session or structured-context capability."""

    __tablename__ = "mcp_access_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_digest = Column(String(64), nullable=False, unique=True)
    token_type = Column(String(16), nullable=False)
    audience = Column(String(64), nullable=False)
    actor_type = Column(String(16), nullable=False, default="mcp")
    actor_id = Column(String(120), nullable=False)
    scopes = Column(JSON, nullable=False, default=list)
    purposes = Column(JSON, nullable=False, default=list)
    kinds = Column(JSON, nullable=False, default=list)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    write_consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "token_type IN ('session','context')",
            name="ck_mcp_access_token_type",
        ),
        CheckConstraint(
            "audience = 'praxys-coach-plugin'",
            name="ck_mcp_access_token_audience",
        ),
        CheckConstraint(
            "actor_type = 'mcp'",
            name="ck_mcp_access_token_actor_type",
        ),
        Index(
            "ix_mcp_access_token_owner_status",
            "user_id",
            "token_type",
            "expires_at",
            "revoked_at",
        ),
    )


class PersonalContextItem(Base):
    """One encrypted, versioned athlete-provided planning-context item."""

    __tablename__ = "personal_context_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey("personal_context_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind = Column(String(32), nullable=False)
    purpose = Column(String(32), nullable=False)
    state = Column(String(20), nullable=False, default="active")
    encrypted_payload = Column(LargeBinary, nullable=False)
    wrapped_dek = Column(LargeBinary, nullable=False)
    payload_schema_version = Column(Integer, nullable=False, default=1)
    has_narrative = Column(Boolean, nullable=False, default=False)
    source_actor_type = Column(String(32), nullable=False)
    source_actor_id = Column(String(120), nullable=True)
    linked_subject_type = Column(String(32), nullable=True)
    linked_subject_id = Column(String(120), nullable=True)
    processing_mode = Column(
        String(24),
        nullable=False,
        default="deterministic_only",
    )
    idempotency_key = Column(String(128), nullable=True)
    # This reference is deliberately not a database FK: consent receipts point
    # back to the item with ON DELETE CASCADE, and a reverse FK would create a
    # DDL cycle. The lifecycle service validates the exact owner/item receipt.
    consent_receipt_id = Column(String(36), nullable=True)
    starts_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    narrative_purge_at = Column(DateTime, nullable=True)
    narrative_purged_at = Column(DateTime, nullable=True)
    purge_after = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_personal_context_lineage_version",
        ),
        UniqueConstraint(
            "id",
            "user_id",
            name="uq_personal_context_item_owner",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_personal_context_item_idempotency",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_personal_context_version_positive",
        ),
        CheckConstraint(
            "payload_schema_version >= 1",
            name="ck_personal_context_payload_schema_positive",
        ),
        CheckConstraint(
            "kind IN ("
            "'durable_preference','temporary_constraint',"
            "'execution_explanation'"
            ")",
            name="ck_personal_context_kind",
        ),
        CheckConstraint(
            "purpose IN ("
            "'plan_generation','execution_interpretation','plan_adjustment',"
            "'goal_review','outcome_review'"
            ")",
            name="ck_personal_context_purpose",
        ),
        CheckConstraint(
            "state IN ('active','expired','withdrawn','deleting')",
            name="ck_personal_context_state",
        ),
        CheckConstraint(
            "processing_mode IN ('deterministic_only','ai_allowed')",
            name="ck_personal_context_processing_mode",
        ),
        CheckConstraint(
            "processing_mode != 'ai_allowed' OR consent_receipt_id IS NOT NULL",
            name="ck_personal_context_ai_consent",
        ),
        CheckConstraint(
            "has_narrative = false OR narrative_purge_at IS NOT NULL",
            name="ck_personal_context_narrative_purge",
        ),
        CheckConstraint(
            "kind = 'durable_preference' OR "
            "(expires_at IS NOT NULL AND purge_after IS NOT NULL)",
            name="ck_personal_context_bounded_lifetime",
        ),
        CheckConstraint(
            "kind != 'durable_preference' OR "
            "(expires_at IS NULL AND purge_after IS NULL "
            "AND has_narrative = false)",
            name="ck_personal_context_durable_lifetime",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > starts_at",
            name="ck_personal_context_expiry_order",
        ),
        CheckConstraint(
            "purge_after IS NULL OR expires_at IS NULL "
            "OR purge_after >= expires_at",
            name="ck_personal_context_purge_order",
        ),
        Index(
            "ix_personal_context_user_lineage_state",
            "user_id",
            "lineage_id",
            "state",
            "version",
        ),
        Index(
            "ix_personal_context_expiry",
            "state",
            "expires_at",
        ),
        Index(
            "ix_personal_context_narrative_purge",
            "has_narrative",
            "narrative_purge_at",
        ),
        Index(
            "ix_personal_context_retention_purge",
            "state",
            "purge_after",
        ),
    )


class PersonalContextConsentReceipt(Base):
    """Append-only receipt for one personal-context processing decision."""

    __tablename__ = "personal_context_consent_receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_item_id = Column(
        String(36),
        nullable=False,
        index=True,
    )
    context_version = Column(Integer, nullable=False)
    purpose = Column(String(32), nullable=False)
    consent_scope = Column(
        String(24),
        nullable=False,
        default="ai_processing",
    )
    provider = Column(String(80), nullable=True)
    disclosed_fields = Column(JSON, nullable=False, default=list)
    narrative_disclosed = Column(Boolean, nullable=False, default=False)
    consent_text_version = Column(String(64), nullable=False)
    decision = Column(String(16), nullable=False)
    client = Column(String(32), nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        ForeignKeyConstraint(
            ["context_item_id", "user_id"],
            ["personal_context_items.id", "personal_context_items.user_id"],
            ondelete="CASCADE",
            name="fk_personal_context_consent_item_owner",
        ),
        UniqueConstraint(
            "id",
            "user_id",
            name="uq_personal_context_consent_owner",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_personal_context_consent_idempotency",
        ),
        CheckConstraint(
            "decision IN ('granted','denied','withdrawn')",
            name="ck_personal_context_consent_decision",
        ),
        CheckConstraint(
            "consent_scope IN ('purpose_confirmation','ai_processing')",
            name="ck_personal_context_consent_scope",
        ),
        CheckConstraint(
            "purpose IN ("
            "'plan_generation','execution_interpretation','plan_adjustment',"
            "'goal_review','outcome_review'"
            ")",
            name="ck_personal_context_consent_purpose",
        ),
        CheckConstraint(
            "(consent_scope != 'purpose_confirmation' OR provider IS NULL) "
            "AND (consent_scope != 'ai_processing' "
            "OR decision != 'granted' OR provider IS NOT NULL)",
            name="ck_personal_context_consent_provider",
        ),
        CheckConstraint(
            "context_version >= 1",
            name="ck_personal_context_consent_version_positive",
        ),
        Index(
            "ix_personal_context_consent_item_decided",
            "context_item_id",
            "decided_at",
        ),
    )


class PersonalContextCommand(Base):
    """Payload-free idempotency state that survives context deletion."""

    __tablename__ = "personal_context_commands"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key = Column(String(128), nullable=False)
    operation = Column(String(24), nullable=False)
    target_item_id = Column(String(36), nullable=True)
    lineage_id = Column(String(36), nullable=True)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    retired_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_personal_context_command_idempotency",
        ),
        CheckConstraint(
            "operation IN ('confirm','correct','ai_consent')",
            name="ck_personal_context_command_operation",
        ),
        CheckConstraint(
            "status IN ('active','retired')",
            name="ck_personal_context_command_status",
        ),
        CheckConstraint(
            "(status = 'active' AND target_item_id IS NOT NULL "
            "AND lineage_id IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'retired' AND target_item_id IS NULL "
            "AND lineage_id IS NULL AND retired_at IS NOT NULL)",
            name="ck_personal_context_command_lifecycle",
        ),
        Index(
            "ix_personal_context_command_user_status",
            "user_id",
            "status",
        ),
    )


class PersonalContextUseReceipt(Base):
    """Payload-free record of one bounded context use."""

    __tablename__ = "personal_context_use_receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_item_id = Column(
        String(36),
        nullable=False,
        index=True,
    )
    context_version = Column(Integer, nullable=False)
    purpose = Column(String(32), nullable=False)
    consumer_type = Column(String(32), nullable=False)
    consumer_name = Column(String(100), nullable=False)
    disclosed_fields = Column(JSON, nullable=False, default=list)
    narrative_disclosed = Column(Boolean, nullable=False, default=False)
    policy_version = Column(String(100), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    consent_receipt_id = Column(
        String(36),
        nullable=True,
    )
    used_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        ForeignKeyConstraint(
            ["context_item_id", "user_id"],
            ["personal_context_items.id", "personal_context_items.user_id"],
            ondelete="CASCADE",
            name="fk_personal_context_use_item_owner",
        ),
        ForeignKeyConstraint(
            ["consent_receipt_id", "user_id"],
            [
                "personal_context_consent_receipts.id",
                "personal_context_consent_receipts.user_id",
            ],
            ondelete="CASCADE",
            name="fk_personal_context_use_consent_owner",
        ),
        CheckConstraint(
            "context_version >= 1",
            name="ck_personal_context_use_version_positive",
        ),
        CheckConstraint(
            "purpose IN ("
            "'plan_generation','execution_interpretation','plan_adjustment',"
            "'goal_review','outcome_review'"
            ")",
            name="ck_personal_context_use_purpose",
        ),
        CheckConstraint(
            "consumer_type IN ("
            "'deterministic_policy','planning_ai','provider_adapter'"
            ")",
            name="ck_personal_context_use_consumer",
        ),
        Index(
            "ix_personal_context_use_item_used",
            "context_item_id",
            "used_at",
        ),
    )


class PersonalContextDeletionJob(Base):
    """Payload-free, retryable cleanup state for one context lineage."""

    __tablename__ = "personal_context_deletion_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation = Column(String(24), nullable=False)
    lineage_id = Column(String(36), nullable=True)
    target_item_id = Column(String(36), nullable=True)
    reason = Column(String(24), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    failure_code = Column(String(64), nullable=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "reason IN ('withdrawal','expiry','retention','account_deletion')",
            name="ck_personal_context_deletion_reason",
        ),
        CheckConstraint(
            "operation IN ("
            "'delete_owner_context','delete_lineage',"
            "'delete_version','purge_narrative'"
            ")",
            name="ck_personal_context_deletion_operation",
        ),
        CheckConstraint(
            "(operation = 'delete_owner_context' "
            "AND lineage_id IS NULL AND target_item_id IS NULL) OR "
            "(operation = 'delete_lineage' "
            "AND lineage_id IS NOT NULL AND target_item_id IS NULL) OR "
            "(operation IN ('delete_version','purge_narrative') "
            "AND lineage_id IS NOT NULL AND target_item_id IS NOT NULL)",
            name="ck_personal_context_deletion_target",
        ),
        CheckConstraint(
            "status IN ('pending','running','failed','completed')",
            name="ck_personal_context_deletion_status",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_personal_context_deletion_attempts",
        ),
        CheckConstraint(
            "status != 'running' OR started_at IS NOT NULL",
            name="ck_personal_context_deletion_started",
        ),
        CheckConstraint(
            "status != 'completed' OR completed_at IS NOT NULL",
            name="ck_personal_context_deletion_completed",
        ),
        Index(
            "ix_personal_context_deletion_user_target",
            "user_id",
            "operation",
            "lineage_id",
            "target_item_id",
            "status",
        ),
    )


class GoalBaselineConfirmation(Base):
    """Append-only athlete confirmation for one history candidate."""

    __tablename__ = "goal_baseline_confirmations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_signature = Column(String(64), nullable=False)
    goal_snapshot = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey("goal_baseline_confirmations.id", ondelete="SET NULL"),
        nullable=True,
    )
    activity_id = Column(String(100), nullable=False)
    response = Column(String(24), nullable=False)
    measured_5k = Column(Boolean, nullable=False, default=False)
    elapsed_timing_confirmed = Column(Boolean, nullable=False, default=False)
    request_fingerprint = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_goal_baseline_confirmation_lineage_version",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_goal_baseline_confirmation_idempotency",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_goal_baseline_confirmation_version_positive",
        ),
        CheckConstraint(
            "response IN ('race','intentional_all_out','not_all_out','deleted')",
            name="ck_goal_baseline_confirmation_response",
        ),
        Index(
            "ix_goal_baseline_confirmation_user_goal_activity",
            "user_id",
            "goal_signature",
            "activity_id",
            "created_at",
        ),
    )


class GoalBaselineTestRecord(Base):
    """Append-only optional-test lifecycle state for one goal baseline."""

    __tablename__ = "goal_baseline_test_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_signature = Column(String(64), nullable=False)
    goal_snapshot = Column(JSON, nullable=False, default=dict)
    purpose_source = Column(String(30), nullable=True)
    source_goal_id = Column(String(36), nullable=True)
    source_goal_revision = Column(String(64), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey("goal_baseline_test_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    state = Column(String(24), nullable=False)
    protocol_id = Column(String(64), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    scheduled_date = Column(Date, nullable=True)
    plan_canonical_id = Column(String(36), nullable=True)
    activity_id = Column(String(100), nullable=True)
    observed_date = Column(Date, nullable=True)
    measured_5k = Column(Boolean, nullable=True)
    elapsed_timing_confirmed = Column(Boolean, nullable=True)
    protocol_followed = Column(Boolean, nullable=True)
    reason_code = Column(String(64), nullable=True)
    safety_stop = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_goal_baseline_test_lineage_version",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_goal_baseline_test_idempotency",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_goal_baseline_test_version_positive",
        ),
        CheckConstraint(
            "state IN ('offered','scheduled','declined','stopped','completed','invalidated','deleted')",
            name="ck_goal_baseline_test_state",
        ),
        CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('acute_illness','injury_or_pain_altering_running','chest_pain_or_pressure','fainting_or_near_fainting','unusual_severe_breathlessness','confusion_or_loss_of_coordination','other_red_flag_symptom','known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing','self_reported_inadequate_recovery_or_unresolved_substantial_fatigue','unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course','protocol_or_provenance_unresolved')",
            name="ck_goal_baseline_test_reason_code",
        ),
        Index(
            "ix_goal_baseline_test_user_goal_created",
            "user_id",
            "goal_signature",
            "created_at",
        ),
    )


class GoalBaselineSnapshot(Base):
    """Versioned evidence snapshot retained for export and audit."""

    __tablename__ = "goal_baseline_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_signature = Column(String(64), nullable=False)
    goal_snapshot = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey("goal_baseline_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_kind = Column(String(24), nullable=False)
    source_id = Column(String(100), nullable=True)
    provenance = Column(String(24), nullable=False)
    observed_date = Column(Date, nullable=True)
    distance_km = Column(Float, nullable=True)
    elapsed_time_sec = Column(Float, nullable=True)
    measured_5k = Column(Boolean, nullable=False, default=False)
    elapsed_timing_confirmed = Column(Boolean, nullable=False, default=False)
    qualification_status = Column(String(24), nullable=False)
    change_comparability = Column(String(24), nullable=False, default="not_assessed")
    invalidators = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_goal_baseline_snapshot_lineage_version",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_goal_baseline_snapshot_version_positive",
        ),
        CheckConstraint(
            "source_kind IN ('history_confirmation','pilot_test')",
            name="ck_goal_baseline_snapshot_source_kind",
        ),
        CheckConstraint(
            "provenance IN ('race','intentional_all_out','pilot_test','unqualified')",
            name="ck_goal_baseline_snapshot_provenance",
        ),
        CheckConstraint(
            "qualification_status IN ('direct_current','incomparable','invalidated','deleted')",
            name="ck_goal_baseline_snapshot_qualification_status",
        ),
        CheckConstraint(
            "change_comparability IN ('not_assessed','supporting','incomparable','directly_comparable')",
            name="ck_goal_baseline_snapshot_change_comparability",
        ),
        Index(
            "ix_goal_baseline_snapshot_user_goal_created",
            "user_id",
            "goal_signature",
            "created_at",
        ),
    )


class Road10KBaselineConfirmation(Base):
    """Append-only athlete confirmation for one direct 10K candidate."""

    __tablename__ = "road_10k_baseline_confirmations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_signature = Column(String(64), nullable=False)
    goal_snapshot = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey(
            "road_10k_baseline_confirmations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    activity_id = Column(String(100), nullable=False)
    response = Column(String(24), nullable=False)
    measured_10k = Column(Boolean, nullable=False, default=False)
    elapsed_timing_confirmed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime, nullable=False)
    elapsed_time_sec = Column(Float, nullable=False)
    surface_or_protocol = Column(String(64), nullable=True)
    route_or_venue_identifier = Column(String(200), nullable=True)
    assistance_status = Column(String(32), nullable=False)
    source_provider = Column(String(20), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_road_10k_baseline_confirmation_lineage_version",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_road_10k_baseline_confirmation_idempotency",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_road_10k_baseline_confirmation_version_positive",
        ),
        CheckConstraint(
            "response IN ('race','intentional_all_out','not_all_out','deleted')",
            name="ck_road_10k_baseline_confirmation_response",
        ),
        CheckConstraint(
            "elapsed_time_sec > 0",
            name="ck_road_10k_baseline_confirmation_elapsed_positive",
        ),
        CheckConstraint(
            "surface_or_protocol IS NULL OR "
            "surface_or_protocol IN "
            "('organized_outdoor_road_10k_race',"
            "'standardized_outdoor_road_10k_time_trial',"
            "'standardized_track_10k_time_trial')",
            name="ck_road_10k_baseline_confirmation_surface_protocol",
        ),
        CheckConstraint(
            "assistance_status IN "
            "('unassisted','assisted','unknown_or_unreported')",
            name="ck_road_10k_baseline_confirmation_assistance_status",
        ),
        Index(
            "ix_road_10k_baseline_confirmation_user_goal_activity",
            "user_id",
            "goal_signature",
            "activity_id",
            "created_at",
        ),
    )


class Road10KBaselineSnapshot(Base):
    """Versioned direct 10K evidence snapshot retained for audit and export."""

    __tablename__ = "road_10k_baseline_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_signature = Column(String(64), nullable=False)
    goal_snapshot = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey("road_10k_baseline_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_kind = Column(String(24), nullable=False)
    source_id = Column(String(100), nullable=True)
    provenance = Column(String(24), nullable=False)
    observed_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=False)
    distance_km = Column(Float, nullable=True)
    elapsed_time_sec = Column(Float, nullable=True)
    measured_10k = Column(Boolean, nullable=False, default=False)
    elapsed_timing_confirmed = Column(Boolean, nullable=False, default=False)
    surface_or_protocol = Column(String(64), nullable=True)
    route_or_venue_identifier = Column(String(200), nullable=True)
    assistance_status = Column(String(32), nullable=False)
    source_provider = Column(String(20), nullable=False)
    qualification_status = Column(String(24), nullable=False)
    change_comparability = Column(
        String(24),
        nullable=False,
        default="not_assessed",
    )
    invalidators = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_road_10k_baseline_snapshot_lineage_version",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_road_10k_baseline_snapshot_version_positive",
        ),
        CheckConstraint(
            "source_kind IN ('history_confirmation')",
            name="ck_road_10k_baseline_snapshot_source_kind",
        ),
        CheckConstraint(
            "provenance IN ('race','intentional_all_out','unqualified')",
            name="ck_road_10k_baseline_snapshot_provenance",
        ),
        CheckConstraint(
            "surface_or_protocol IS NULL OR "
            "surface_or_protocol IN "
            "('organized_outdoor_road_10k_race',"
            "'standardized_outdoor_road_10k_time_trial',"
            "'standardized_track_10k_time_trial')",
            name="ck_road_10k_baseline_snapshot_surface_protocol",
        ),
        CheckConstraint(
            "assistance_status IN "
            "('unassisted','assisted','unknown_or_unreported')",
            name="ck_road_10k_baseline_snapshot_assistance_status",
        ),
        CheckConstraint(
            "qualification_status IN ('direct_current','incomparable','deleted')",
            name="ck_road_10k_baseline_snapshot_qualification_status",
        ),
        CheckConstraint(
            "change_comparability IN ('not_assessed','supporting','incomparable','directly_comparable')",
            name="ck_road_10k_baseline_snapshot_change_comparability",
        ),
        Index(
            "ix_road_10k_baseline_snapshot_user_goal_created",
            "user_id",
            "goal_signature",
            "created_at",
        ),
    )


class GoalBaselineAssessment(Base):
    """Append-only rendered assessment retained for audit and export."""

    __tablename__ = "goal_baseline_assessments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    lineage_id = Column(String(36), nullable=False)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_signature = Column(String(64), nullable=False)
    goal_snapshot = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(
        String(36),
        ForeignKey("goal_baseline_assessments.id", ondelete="SET NULL"),
        nullable=True,
    )
    policy_version = Column(String(64), nullable=False)
    science_decision_id = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False)
    readiness = Column(String(40), nullable=False)
    evidence_snapshot_id = Column(String(36), nullable=True)
    test_record_id = Column(String(36), nullable=True)
    candidate_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_goal_baseline_assessment_lineage_version",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_goal_baseline_assessment_version_positive",
        ),
        CheckConstraint(
            "status IN ('current','stale','incomparable','missing','not_required','pending_test')",
            name="ck_goal_baseline_assessment_status",
        ),
        CheckConstraint(
            "readiness IN ('sufficient_baseline','insufficient_evidence','non_diagnostic_safety_stop')",
            name="ck_goal_baseline_assessment_readiness",
        ),
        Index(
            "ix_goal_baseline_assessment_user_goal_created",
            "user_id",
            "goal_signature",
            "created_at",
        ),
    )


class CacheRevision(Base):
    """Per-(user, scope) monotonic counter for HTTP cache revalidation (issue #147).

    A scope groups one or more underlying tables that an endpoint pack reads;
    sync writers and config-mutation routes bump the relevant scopes after a
    commit. The ETag for each /api/* response is built from the revisions of
    the scopes that endpoint actually consumes, so a goal edit won't bust the
    Today page's ETag and a sync writing only activities won't bust the
    Science page's ETag.

    A counter is preferred over a timestamp because two writes within the same
    second still produce distinct revisions — no risk of a 304 hiding a fresh
    write that landed in the same wall-clock second as the prior request.
    """

    __tablename__ = "cache_revisions"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    scope = Column(String(20), primary_key=True)
    revision = Column(Integer, nullable=False, default=0)
    bumped_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DashboardCache(Base):
    """Per-(user, section) materialized response payload (issue #148 / L3).

    Each row stores one endpoint's full JSON response, tagged with the
    ``source_version`` it was computed from — a pipe-separated string of
    the L2 revision counters for the scopes the endpoint reads, with
    scopes sorted alphabetically so two callers produce byte-identical
    strings. Example for ``today`` on 2026-04-26 with all-zero revisions:
    ``"activities=0|config=0|fitness=0|plans=0|recovery=0|d=2026-04-26"``.

    Read path is two-step:

      1. ``SELECT payload_json, source_version FROM dashboard_cache``
         keyed on ``(user_id, section)``. If ``source_version`` matches the
         currently-computed value, return ``payload_json`` directly —
         sub-50 ms cache hit.
      2. On mismatch (post-write or first visit), fall through to the
         original pack-based compute path; write the result back keyed on
         the snapshot taken BEFORE the compute. A concurrent write that
         lands mid-compute leaves the cache row labelled with the older
         revisions; the very next read sees fresh revisions, mismatches,
         and recomputes — never wrong, just sometimes a wasted compute.

    Why a single table instead of one-per-section (the issue's literal
    spec): same correctness, half the schema. ``section`` is a small
    closed enum (enforced by the CHECK constraint below), the PK
    ``(user_id, section)`` has one row per pair, and SQLite's
    database-level write lock means per-section tables wouldn't even
    reduce contention. Documented in the PR for #148.

    The CHECK constraint on ``section`` makes the closed enum
    storage-layer enforced: a buggy writer that bypasses
    ``api.dashboard_cache.write_cache`` cannot leave an orphan row
    keyed on a typo'd section name.
    """

    __tablename__ = "dashboard_cache"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    section = Column(String(32), primary_key=True)
    source_version = Column(String(255), nullable=False)
    payload_json = Column(LargeBinary, nullable=False)
    computed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "section IN ('today','training','goal')",
            name="ck_dashboard_cache_section",
        ),
    )


class AdaptivePlanGoalSnapshot(Base):
    """Immutable owner-scoped goal target and horizon captured for one plan."""

    __tablename__ = "adaptive_plan_goal_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    state = Column(String(20), nullable=False, default="draft")
    purpose_source = Column(String(30), nullable=True)
    source_goal_id = Column(String(36), nullable=True)
    source_goal_revision = Column(String(64), nullable=True)
    goal_kind = Column(String(40), nullable=False)
    target = Column(JSON, nullable=False, default=dict)
    horizon_start = Column(Date, nullable=False)
    horizon_end = Column(Date, nullable=False)
    snapshot = Column(JSON, nullable=False, default=dict)
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "id",
            name="uq_adaptive_goal_snapshot_owner",
        ),
        CheckConstraint("version >= 1", name="ck_adaptive_goal_version_positive"),
        CheckConstraint(
            "state IN ('draft','active','superseded')",
            name="ck_adaptive_goal_state",
        ),
        CheckConstraint(
            "horizon_end >= horizon_start",
            name="ck_adaptive_goal_horizon_order",
        ),
        Index("ix_adaptive_goal_user_created", "user_id", "created_at"),
    )


class AdaptivePlan(Base):
    """Aggregate identity and lifecycle for an athlete-owned adaptive plan."""

    __tablename__ = "adaptive_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_snapshot_id = Column(
        String(36),
        ForeignKey("adaptive_plan_goal_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discipline = Column(String(30), nullable=False)
    lifecycle = Column(String(20), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=0)
    active_proposal_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_adaptive_plan_owner"),
        CheckConstraint("version >= 0", name="ck_adaptive_plan_version_nonnegative"),
        CheckConstraint(
            "lifecycle IN ('draft','active','completed','archived')",
            name="ck_adaptive_plan_lifecycle",
        ),
        CheckConstraint(
            "discipline IN ('running','trail_running')",
            name="ck_adaptive_plan_discipline",
        ),
        Index(
            "uq_adaptive_plan_one_active",
            "user_id",
            unique=True,
            sqlite_where=text("lifecycle IN ('draft','active')"),
            postgresql_where=text("lifecycle IN ('draft','active')"),
        ),
        Index("ix_adaptive_plan_user_lifecycle", "user_id", "lifecycle"),
    )


class PlanProposal(Base):
    """Immutable structured proposal that is not canonical until adopted."""

    __tablename__ = "plan_proposals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adaptive_plan_id = Column(
        String(36),
        ForeignKey("adaptive_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_snapshot_id = Column(
        String(36),
        ForeignKey("adaptive_plan_goal_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    discipline = Column(String(30), nullable=False)
    version = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False, default="draft")
    origin = Column(String(80), nullable=False)
    actor_type = Column(String(20), nullable=False)
    actor_id = Column(String(100), nullable=True)
    base_plan_version = Column(Integer, nullable=False)
    supersedes_proposal_id = Column(
        String(36),
        ForeignKey("plan_proposals.id", ondelete="SET NULL"),
        nullable=True,
    )
    policy_version = Column(String(80), nullable=True)
    model_version = Column(String(80), nullable=True)
    science_version = Column(String(80), nullable=True)
    assumptions = Column(JSON, nullable=False, default=list)
    unknowns = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=False, default=list)
    alternatives = Column(JSON, nullable=False, default=list)
    expires_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    idempotency_fingerprint = Column(String(64), nullable=True)
    decision_idempotency_key = Column(String(128), nullable=True)
    workout_snapshot = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "id", name="uq_plan_proposal_owner"),
        UniqueConstraint(
            "adaptive_plan_id",
            "version",
            name="uq_plan_proposal_plan_version",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_plan_proposal_idempotency",
        ),
        CheckConstraint("version >= 1", name="ck_plan_proposal_version_positive"),
        CheckConstraint(
            "base_plan_version >= 0",
            name="ck_plan_proposal_base_version_nonnegative",
        ),
        CheckConstraint(
            "state IN ('draft','superseded','rejected','adopted','expired')",
            name="ck_plan_proposal_state",
        ),
        CheckConstraint(
            "actor_type IN ('user','agent','system')",
            name="ck_plan_proposal_actor_type",
        ),
        CheckConstraint(
            "discipline IN ('running','trail_running')",
            name="ck_plan_proposal_discipline",
        ),
        Index("ix_plan_proposal_user_state", "user_id", "state", "created_at"),
        Index(
            "ix_plan_proposal_plan_state",
            "adaptive_plan_id",
            "state",
            "version",
        ),
    )


class Outdoor5KPlanGeneration(Base):
    """Immutable audit record for one deterministic outdoor-road 5K proposal."""

    __tablename__ = "outdoor_5k_plan_generations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposal_id = Column(
        String(36),
        ForeignKey("plan_proposals.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    policy_version = Column(String(80), nullable=False)
    generator_version = Column(String(80), nullable=False)
    science_decision_id = Column(String(120), nullable=False)
    evidence_review_ids = Column(JSON, nullable=False, default=list)
    evidence_claim_ids = Column(JSON, nullable=False, default=list)
    ai_explanation_present = Column(Boolean, nullable=False, default=False)
    baseline_snapshot_id = Column(String(36), nullable=True)
    source_revision = Column(String(64), nullable=False)
    deterministic_input_hash = Column(String(64), nullable=False)
    request_kind = Column(String(20), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    predecessor_proposal_id = Column(String(36), nullable=True)
    predecessor_version = Column(Integer, nullable=True)
    observed_input_snapshot = Column(JSON, nullable=False, default=dict)
    constraint_snapshot = Column(JSON, nullable=False, default=dict)
    derived_history_statistics = Column(JSON, nullable=False, default=dict)
    validation_results = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "proposal_id",
            name="uq_outdoor_5k_generation_proposal_owner",
        ),
        Index(
            "ix_outdoor_5k_generation_user_revision",
            "user_id",
            "source_revision",
        ),
    )


class Road10KTrainingPatternSnapshot(Base):
    """Append-only owner-scoped aggregate provenance for road 10K replay."""

    __tablename__ = "road_10k_training_pattern_snapshots"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        primary_key=True,
    )
    version = Column(String(67), nullable=False, primary_key=True)
    schema_version = Column(String(80), nullable=False)
    policy_version = Column(String(80), nullable=False)
    usable_completed_weeks = Column(Integer, nullable=False)
    recent_modal_running_frequency = Column(Integer, nullable=False)
    recent_median_usable_weekly_minutes = Column(Integer, nullable=False)
    recent_maximum_usable_weekly_minutes = Column(Integer, nullable=False)
    recent_maximum_session_minutes = Column(Integer, nullable=False)
    recent_maximum_session_distance_km = Column(Float, nullable=False)
    latest_run_date = Column(Date, nullable=False)
    history_observation_count = Column(Integer, nullable=False)
    history_provenance_fingerprint = Column(String(64), nullable=False)
    intensity_observation_count = Column(Integer, nullable=False)
    intensity_provenance_fingerprint = Column(String(64), nullable=False)
    reserved_date_count = Column(Integer, nullable=False)
    reservation_fingerprint = Column(String(64), nullable=False)
    canonical_fingerprint = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "version = 'v1:' || canonical_fingerprint",
            name="ck_road_10k_training_pattern_version",
        ),
        CheckConstraint(
            "schema_version = 'road-10k-training-pattern-v1'",
            name="ck_road_10k_training_pattern_schema",
        ),
        CheckConstraint(
            "policy_version = 'road-10k-plan-generation-policy-v2'",
            name="ck_road_10k_training_pattern_policy",
        ),
        CheckConstraint(
            "usable_completed_weeks >= 0 AND usable_completed_weeks <= 8",
            name="ck_road_10k_training_pattern_usable_weeks",
        ),
        CheckConstraint(
            "recent_modal_running_frequency >= 0",
            name="ck_road_10k_training_pattern_frequency",
        ),
        CheckConstraint(
            "recent_median_usable_weekly_minutes >= 0",
            name="ck_road_10k_training_pattern_median_minutes",
        ),
        CheckConstraint(
            "recent_maximum_usable_weekly_minutes >= 0",
            name="ck_road_10k_training_pattern_max_weekly_minutes",
        ),
        CheckConstraint(
            "recent_maximum_session_minutes >= 0",
            name="ck_road_10k_training_pattern_max_session_minutes",
        ),
        CheckConstraint(
            "recent_maximum_session_distance_km > 0",
            name="ck_road_10k_training_pattern_max_distance",
        ),
        CheckConstraint(
            "history_observation_count >= 0 "
            "AND history_observation_count <= 1000",
            name="ck_road_10k_training_pattern_history_count",
        ),
        CheckConstraint(
            "intensity_observation_count >= 0 "
            "AND intensity_observation_count <= 1000",
            name="ck_road_10k_training_pattern_intensity_count",
        ),
        CheckConstraint(
            "reserved_date_count >= 0 AND reserved_date_count <= 14",
            name="ck_road_10k_training_pattern_reservation_count",
        ),
        CheckConstraint(
            "length(history_provenance_fingerprint) = 64 "
            "AND length(intensity_provenance_fingerprint) = 64 "
            "AND length(reservation_fingerprint) = 64 "
            "AND length(canonical_fingerprint) = 64",
            name="ck_road_10k_training_pattern_fingerprints",
        ),
        Index(
            "ix_road_10k_training_pattern_owner_created",
            "user_id",
            "created_at",
        ),
    )


event.listen(
    Road10KTrainingPatternSnapshot.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_training_pattern_snapshots_immutable "
        "BEFORE UPDATE ON road_10k_training_pattern_snapshots "
        "BEGIN "
        "SELECT RAISE(ABORT, 'road 10K training pattern snapshots are immutable'); "
        "END"
    ).execute_if(dialect="sqlite"),
)


@event.listens_for(Road10KTrainingPatternSnapshot, "before_update")
def _reject_road_10k_training_pattern_snapshot_update(
    _mapper: object,
    _connection: object,
    _target: Road10KTrainingPatternSnapshot,
) -> None:
    raise ValueError("road 10K training pattern snapshots are immutable")


class Road10KStageCounter(Base):
    """Monotonic, non-identifying counters for one controlled Road 10K stage."""

    __tablename__ = "road_10k_stage_counters"

    stage_id = Column(String(80), primary_key=True)
    schema_version = Column(Integer, nullable=False, default=2)
    capability_id = Column(String(80), nullable=False)
    invitation_slots_consumed = Column(Integer, nullable=False, default=0)
    distinct_exposed_owners_consumed = Column(Integer, nullable=False, default=0)
    invitation_ceiling = Column(Integer, nullable=False, default=60)
    exposure_ceiling = Column(Integer, nullable=False, default=30)
    aggregate = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "schema_version = 2",
            name="ck_road_10k_stage_counter_schema",
        ),
        CheckConstraint(
            "capability_id = 'outdoor_road_10k_performance_v1'",
            name="ck_road_10k_stage_counter_capability",
        ),
        CheckConstraint(
            "invitation_slots_consumed >= 0 AND invitation_slots_consumed <= 60",
            name="ck_road_10k_stage_counter_invitations",
        ),
        CheckConstraint(
            "distinct_exposed_owners_consumed >= 0 "
            "AND distinct_exposed_owners_consumed <= 30",
            name="ck_road_10k_stage_counter_exposures",
        ),
        CheckConstraint(
            "invitation_ceiling = 60 AND exposure_ceiling = 30",
            name="ck_road_10k_stage_counter_ceilings",
        ),
    )


class Road10KOwnerStageReceipt(Base):
    """Owner/stage control receipt.

    ``user_id`` is nullable solely for account deletion.  A null owner link
    retains the consumed receipt without creating a pseudonym or allowing a
    future account to inherit it.
    """

    __tablename__ = "road_10k_owner_stage_receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage_id = Column(String(80), nullable=False, index=True)
    capability_id = Column(String(80), nullable=False)
    schema_version = Column(Integer, nullable=False, default=2)
    policy_version = Column(String(80), nullable=False)
    authority_digest = Column(String(64), nullable=False)
    notice_digest = Column(String(64), nullable=False)
    cohort_rule_digest = Column(String(64), nullable=False)
    sampling_run_evidence_digest = Column(String(64), nullable=False)
    invitation_idempotency_key = Column(String(128), nullable=False)
    state = Column(String(24), nullable=False, default="invited_only")
    invitation_issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    enrolled_at = Column(DateTime, nullable=True)
    first_exposed_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "stage_id",
            name="uq_road_10k_owner_stage_receipt_owner_stage",
        ),
        UniqueConstraint(
            "stage_id",
            "invitation_idempotency_key",
            name="uq_road_10k_owner_stage_receipt_invitation_key",
        ),
        CheckConstraint(
            "capability_id = 'outdoor_road_10k_performance_v1'",
            name="ck_road_10k_owner_stage_receipt_capability",
        ),
        CheckConstraint(
            "schema_version = 2",
            name="ck_road_10k_owner_stage_receipt_schema",
        ),
        CheckConstraint(
            "length(authority_digest) = 64 "
            "AND length(notice_digest) = 64 "
            "AND length(cohort_rule_digest) = 64 "
            "AND length(sampling_run_evidence_digest) = 64",
            name="ck_road_10k_owner_stage_receipt_digests",
        ),
        CheckConstraint(
            "state IN ('invited_only','enrolled_unexposed','exposed',"
            "'withdrawn','deleted')",
            name="ck_road_10k_owner_stage_receipt_state",
        ),
        CheckConstraint(
            "(state = 'invited_only' AND enrolled_at IS NULL AND first_exposed_at IS NULL AND withdrawn_at IS NULL AND deleted_at IS NULL) OR "
            "(state = 'enrolled_unexposed' AND enrolled_at IS NOT NULL AND first_exposed_at IS NULL AND withdrawn_at IS NULL AND deleted_at IS NULL) OR "
            "(state = 'exposed' AND enrolled_at IS NOT NULL AND first_exposed_at IS NOT NULL AND withdrawn_at IS NULL AND deleted_at IS NULL) OR "
            "(state = 'withdrawn' AND withdrawn_at IS NOT NULL AND deleted_at IS NULL) OR "
            "(state = 'deleted' AND deleted_at IS NOT NULL)",
            name="ck_road_10k_owner_stage_receipt_lifecycle",
        ),
        CheckConstraint(
            "created_at = invitation_issued_at AND updated_at >= invitation_issued_at AND "
            "(enrolled_at IS NULL OR enrolled_at >= invitation_issued_at) AND "
            "(first_exposed_at IS NULL OR (enrolled_at IS NOT NULL AND first_exposed_at >= enrolled_at)) AND "
            "(withdrawn_at IS NULL OR withdrawn_at >= invitation_issued_at) AND "
            "(deleted_at IS NULL OR deleted_at >= invitation_issued_at)",
            name="ck_road_10k_owner_stage_receipt_timestamps",
        ),
        Index(
            "ix_road_10k_owner_stage_receipt_stage_state",
            "stage_id",
            "state",
        ),
    )


class Road10KExposureReceipt(Base):
    """First-result exposure receipt, committed before any result bytes escape."""

    __tablename__ = "road_10k_exposure_receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    stage_id = Column(String(80), nullable=False, index=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_stage_receipt_id = Column(
        String(36),
        ForeignKey("road_10k_owner_stage_receipts.id"),
        nullable=False,
    )
    authority_digest = Column(String(64), nullable=False)
    exposed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "stage_id",
            "user_id",
            name="uq_road_10k_exposure_owner_stage",
        ),
        CheckConstraint(
            "length(authority_digest) = 64",
            name="ck_road_10k_exposure_authority_digest",
        ),
    )


event.listen(
    Road10KStageCounter.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_stage_counters_monotonic "
        "BEFORE UPDATE ON road_10k_stage_counters "
        "WHEN NEW.invitation_slots_consumed < OLD.invitation_slots_consumed "
        "OR NEW.distinct_exposed_owners_consumed "
        "< OLD.distinct_exposed_owners_consumed "
        "OR NEW.invitation_ceiling != OLD.invitation_ceiling "
        "OR NEW.exposure_ceiling != OLD.exposure_ceiling "
        "OR NEW.capability_id != OLD.capability_id "
        "OR NEW.schema_version != OLD.schema_version "
        "BEGIN "
        "SELECT RAISE(ABORT, 'road 10K counters cannot decrement'); "
        "END"
    ).execute_if(dialect="sqlite"),
)

event.listen(
    Road10KOwnerStageReceipt.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_owner_stage_receipts_no_delete "
        "BEFORE DELETE ON road_10k_owner_stage_receipts "
        "BEGIN "
        "SELECT RAISE(ABORT, 'road 10K owner receipts cannot be deleted'); "
        "END"
    ).execute_if(dialect="sqlite"),
)

event.listen(
    Road10KOwnerStageReceipt.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_owner_stage_receipts_immutable "
        "BEFORE UPDATE ON road_10k_owner_stage_receipts "
        "WHEN NEW.id != OLD.id OR NEW.stage_id != OLD.stage_id "
        "OR NEW.capability_id != OLD.capability_id "
        "OR NEW.schema_version != OLD.schema_version "
        "OR NEW.policy_version != OLD.policy_version "
        "OR NEW.authority_digest != OLD.authority_digest "
        "OR NEW.notice_digest != OLD.notice_digest "
        "OR NEW.cohort_rule_digest != OLD.cohort_rule_digest "
        "OR NEW.sampling_run_evidence_digest != OLD.sampling_run_evidence_digest "
        "OR NEW.invitation_idempotency_key != OLD.invitation_idempotency_key "
        "OR NEW.invitation_issued_at != OLD.invitation_issued_at "
        "OR NEW.created_at != OLD.created_at "
        "OR (OLD.user_id IS NULL AND NEW.user_id IS NOT NULL) "
        "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state != 'deleted') "
        "OR NOT (NEW.state = OLD.state "
        "OR (OLD.state = 'invited_only' AND NEW.state IN ('enrolled_unexposed','withdrawn')) "
        "OR (OLD.state = 'enrolled_unexposed' AND NEW.state IN ('exposed','withdrawn')) "
        "OR (OLD.state = 'exposed' AND NEW.state = 'withdrawn') "
        "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state = 'deleted')) "
        "BEGIN SELECT RAISE(ABORT, 'road 10K owner receipt immutable'); END"
    ).execute_if(dialect="sqlite"),
)

event.listen(
    Road10KOwnerStageReceipt.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_owner_stage_receipts_lifecycle "
        "BEFORE UPDATE ON road_10k_owner_stage_receipts "
        "WHEN NOT ("
        "(OLD.state = 'invited_only' AND NEW.state = 'enrolled_unexposed' "
        "AND NEW.user_id IS OLD.user_id AND NEW.enrolled_at IS NOT NULL "
        "AND NEW.first_exposed_at IS OLD.first_exposed_at AND NEW.withdrawn_at IS OLD.withdrawn_at "
        "AND NEW.deleted_at IS OLD.deleted_at AND NEW.updated_at = NEW.enrolled_at) "
        "OR (OLD.state = 'enrolled_unexposed' AND NEW.state = 'exposed' "
        "AND NEW.user_id IS OLD.user_id AND NEW.enrolled_at IS OLD.enrolled_at "
        "AND NEW.first_exposed_at IS NOT NULL AND NEW.withdrawn_at IS OLD.withdrawn_at "
        "AND NEW.deleted_at IS OLD.deleted_at AND NEW.updated_at = NEW.first_exposed_at) "
        "OR (OLD.state IN ('invited_only','enrolled_unexposed','exposed') AND NEW.state = 'withdrawn' "
        "AND NEW.user_id IS OLD.user_id AND NEW.enrolled_at IS OLD.enrolled_at "
        "AND NEW.first_exposed_at IS OLD.first_exposed_at AND NEW.withdrawn_at IS NOT NULL "
        "AND NEW.deleted_at IS OLD.deleted_at AND NEW.updated_at = NEW.withdrawn_at) "
        "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state = 'deleted' "
        "AND NEW.enrolled_at IS OLD.enrolled_at AND NEW.first_exposed_at IS OLD.first_exposed_at "
        "AND NEW.withdrawn_at IS OLD.withdrawn_at AND NEW.deleted_at IS NOT NULL "
        "AND NEW.updated_at = NEW.deleted_at)"
        ") "
        "BEGIN SELECT RAISE(ABORT, "
        "'road 10K owner receipt lifecycle invalid'); END"
    ).execute_if(dialect="sqlite"),
)


event.listen(
    Road10KExposureReceipt.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_exposure_receipts_immutable "
        "BEFORE UPDATE ON road_10k_exposure_receipts "
        "WHEN NOT ("
        "OLD.user_id IS NOT NULL AND NEW.user_id IS NULL "
        "AND NEW.id = OLD.id "
        "AND NEW.stage_id = OLD.stage_id "
        "AND NEW.owner_stage_receipt_id = OLD.owner_stage_receipt_id "
        "AND NEW.authority_digest = OLD.authority_digest "
        "AND NEW.exposed_at = OLD.exposed_at"
        ") "
        "BEGIN "
        "SELECT RAISE(ABORT, 'road 10K exposure receipts are immutable'); "
        "END"
    ).execute_if(dialect="sqlite"),
)

event.listen(
    Road10KExposureReceipt.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_exposure_receipts_no_delete "
        "BEFORE DELETE ON road_10k_exposure_receipts "
        "BEGIN "
        "SELECT RAISE(ABORT, 'road 10K exposure receipts cannot be deleted'); "
        "END"
    ).execute_if(dialect="sqlite"),
)


class Road10KDeletionObligation(Base):
    """DB-durable private-object deletion replay obligation."""

    __tablename__ = "road_10k_deletion_obligations"

    id = Column(String(36), primary_key=True)
    stage_id = Column(String(80), nullable=False)
    reason = Column(String(32), nullable=False)
    manifest_digest = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="committed")
    requested_at = Column(DateTime, nullable=False)
    committed_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "reason IN ('withdrawal','account_deletion','retention')",
            name="ck_road_10k_deletion_obligation_reason",
        ),
        CheckConstraint(
            "length(manifest_digest) = 64",
            name="ck_road_10k_deletion_obligation_manifest_digest",
        ),
        CheckConstraint(
            "status IN ('committed','completed')",
            name="ck_road_10k_deletion_obligation_status",
        ),
        CheckConstraint(
            "(status = 'committed' AND completed_at IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL)",
            name="ck_road_10k_deletion_obligation_completion",
        ),
        CheckConstraint(
            "requested_at <= committed_at",
            name="ck_road_10k_deletion_obligation_commit_order",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= committed_at",
            name="ck_road_10k_deletion_obligation_complete_order",
        ),
        Index(
            "ix_road_10k_deletion_obligation_status",
            "status",
        ),
    )


event.listen(
    Road10KDeletionObligation.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_deletion_obligations_no_delete "
        "BEFORE DELETE ON road_10k_deletion_obligations "
        "BEGIN SELECT RAISE(ABORT, "
        "'road 10K deletion obligations cannot be deleted'); END"
    ).execute_if(dialect="sqlite"),
)

event.listen(
    Road10KDeletionObligation.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_deletion_obligations_immutable "
        "BEFORE UPDATE ON road_10k_deletion_obligations "
        "WHEN NOT ((OLD.status = 'committed' AND NEW.status = 'completed' "
        "AND NEW.id = OLD.id AND NEW.stage_id = OLD.stage_id "
        "AND NEW.reason = OLD.reason AND NEW.manifest_digest = OLD.manifest_digest "
        "AND NEW.requested_at = OLD.requested_at AND NEW.committed_at = OLD.committed_at "
        "AND NEW.completed_at IS NOT NULL "
        "AND NEW.completed_at >= OLD.committed_at) "
        "OR (OLD.status = 'completed' AND NEW.status = 'completed' "
        "AND NEW.id = OLD.id AND NEW.stage_id = OLD.stage_id "
        "AND NEW.reason = OLD.reason AND NEW.manifest_digest = OLD.manifest_digest "
        "AND NEW.requested_at = OLD.requested_at AND NEW.committed_at = OLD.committed_at "
        "AND NEW.completed_at = OLD.completed_at)) "
        "BEGIN SELECT RAISE(ABORT, "
        "'road 10K deletion obligation immutable'); END"
    ).execute_if(dialect="sqlite"),
)


class Road10KEvaluation(Base):
    """Owner-scoped, deletable evaluation payload and result record."""

    __tablename__ = "road_10k_evaluations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage_id = Column(String(80), nullable=False, index=True)
    result_code = Column(String(80), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deletion_reason = Column(String(32), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "expires_at >= created_at",
            name="ck_road_10k_evaluation_expiry_after_creation",
        ),
        CheckConstraint(
            "result_code IN ('eligible_rolling_proposal',"
            "'eligible_taper_proposal','missing_or_stale_direct_baseline',"
            "'insufficient_recent_history','limited_guidance_event_conflict',"
            "'limited_near_term_guidance','safety_stop',"
            "'adult_scope_or_constraints_unconfirmed','contradictory_input',"
            "'unsupported_intent_distance_surface_or_population',"
            "'no_schedule_within_envelope','validation_failed')",
            name="ck_road_10k_evaluation_result",
        ),
    )


event.listen(
    Road10KEvaluation.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_evaluations_expiry_immutable "
        "BEFORE INSERT ON road_10k_evaluations "
        "WHEN julianday(NEW.expires_at) < julianday(NEW.created_at) "
        "OR julianday(NEW.expires_at) > julianday(NEW.created_at) + 30 "
        "BEGIN SELECT RAISE(ABORT, 'road 10K evaluation expiry invalid'); END"
    ).execute_if(dialect="sqlite"),
)

event.listen(
    Road10KEvaluation.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER IF NOT EXISTS "
        "trg_road_10k_evaluations_expiry_no_update "
        "BEFORE UPDATE ON road_10k_evaluations "
        "WHEN NEW.expires_at != OLD.expires_at "
        "BEGIN SELECT RAISE(ABORT, 'road 10K evaluation expiry immutable'); END"
    ).execute_if(dialect="sqlite"),
)


class Road10KScreenshotReference(Base):
    """Private screenshot reference; screenshot bytes never enter the DB."""

    __tablename__ = "road_10k_screenshot_references"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    evaluation_id = Column(
        String(36),
        ForeignKey("road_10k_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    object_key = Column(String(240), nullable=False, unique=True)
    content_type = Column(String(40), nullable=False)
    captured_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "object_key NOT LIKE '%@%' AND object_key NOT LIKE '%email%'",
            name="ck_road_10k_screenshot_key_private",
        ),
    )


class Road10KPlanGeneration(Base):
    """Immutable audit record for one deterministic road 10K proposal."""

    __tablename__ = "road_10k_plan_generations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposal_id = Column(
        String(36),
        ForeignKey("plan_proposals.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    capability_id = Column(String(80), nullable=False)
    policy_version = Column(String(80), nullable=False)
    generator_version = Column(String(80), nullable=False)
    science_decision_id = Column(String(120), nullable=False)
    source_decision_digest = Column(String(80), nullable=False)
    contract_digest = Column(String(80), nullable=False)
    baseline_snapshot_id = Column(String(36), nullable=True)
    baseline_source = Column(String(24), nullable=True)
    source_goal_id = Column(String(36), nullable=True)
    source_goal_revision = Column(String(64), nullable=True)
    history_cutoff_completed_days = Column(Integer, nullable=False)
    training_pattern_snapshot_version = Column(String(80), nullable=False)
    event_context_snapshot_version = Column(String(80), nullable=False)
    active_zone_model_id = Column(String(80), nullable=True)
    active_zone_model_version = Column(String(80), nullable=True)
    normalized_constraints = Column(JSON, nullable=False, default=dict)
    selected_template_ids = Column(JSON, nullable=False, default=list)
    source_revision = Column(String(64), nullable=False)
    deterministic_input_hash = Column(String(64), nullable=False)
    request_kind = Column(String(20), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    predecessor_proposal_id = Column(String(36), nullable=True)
    predecessor_version = Column(Integer, nullable=True)
    result_code = Column(String(80), nullable=False)
    validation_reason_code = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "proposal_id",
            name="uq_road_10k_generation_proposal_owner",
        ),
        Index(
            "ix_road_10k_generation_user_revision",
            "user_id",
            "source_revision",
        ),
        Index(
            "ix_road_10k_generation_owner_training_pattern",
            "user_id",
            "training_pattern_snapshot_version",
        ),
    )


class TrainingPlan(Base):
    """Planned workouts from Praxys or an external platform."""

    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    canonical_id = Column(
        String(36),
        nullable=False,
        default=lambda: str(uuid4()),
    )
    date = Column(Date, nullable=False)
    activity_type = Column(String(30), nullable=True)
    workout_type = Column(String(50), nullable=True)
    planned_duration_min = Column(Float, nullable=True)
    planned_distance_km = Column(Float, nullable=True)
    target_power_min = Column(Float, nullable=True)
    target_power_max = Column(Float, nullable=True)
    target_hr_min = Column(Float, nullable=True)
    target_hr_max = Column(Float, nullable=True)
    target_pace_min = Column(String(20), nullable=True)
    target_pace_max = Column(String(20), nullable=True)
    workout_description = Column(Text, nullable=True)
    workout_structure_version = Column(String(20), nullable=True)
    workout_structure = Column(JSON, nullable=True)
    # Ownership lane. ``ai`` remains a read-compatible legacy alias for
    # Praxys rows during rolling deployment.
    source = Column(String(20), default="stryd")
    # How the current workout content entered this row. Ownership and
    # provenance intentionally remain independent.
    workout_origin = Column(
        String(30),
        nullable=False,
        default="legacy",
        server_default="legacy",
    )
    # External platform's identifier for this workout, when the plan
    # row was imported from a platform calendar (e.g. Stryd's workout
    # `id`). NULL for Praxys-owned rows. Lets `/api/plan` join Praxys rows
    # against platform rows on date and detect mismatches: if Praxys
    # pushed a workout, we know its external_id from the push log; if
    # the platform has a workout with a different external_id on that
    # date, it's user-created (mismatch).
    external_id = Column(String(100), nullable=True)
    # Absolute UTC instant of the workout start, as Stryd serializes it
    # ("2026-06-29T16:00:00Z"). The canonical source for which calendar day
    # a workout belongs to: clients bucket it in the viewer's tz. `date` is
    # a server-truncated fallback for backend windowing and legacy rows.
    start_time = Column(DateTime, nullable=True)
    meta = Column(JSON, nullable=True)  # generation and provider provenance details
    adaptive_plan_id = Column(
        String(36),
        ForeignKey("adaptive_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "canonical_id",
            name="uq_training_plan_user_canonical",
        ),
    )


class PlanRevision(Base):
    """Append-only audit event for a canonical plan mutation."""

    __tablename__ = "plan_revisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation = Column(String(30), nullable=False)
    actor_type = Column(String(20), nullable=False)
    actor_id = Column(String(100), nullable=True)
    origin = Column(String(80), nullable=False)
    before_snapshot = Column(JSON, nullable=False, default=list)
    after_snapshot = Column(JSON, nullable=False, default=list)
    details = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_plan_revision_user_idempotency",
        ),
        Index("ix_plan_revisions_user_created", "user_id", "created_at"),
    )


class PlanDelivery(Base):
    """Current provider-neutral delivery state for one workout version."""

    __tablename__ = "plan_deliveries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_key = Column(String(120), nullable=False)
    # Durable UUID identity for modern Praxys workouts. ``canonical_key`` is
    # retained as a compatibility encoding for older deployed workers and
    # date-based legacy delivery rows.
    canonical_id = Column(String(36), nullable=True)
    workout_date = Column(Date, nullable=False)
    # Provider-payload fingerprint. This legacy column name is retained so
    # existing uniqueness constraints continue to fence duplicate writes.
    workout_version = Column(String(64), nullable=False)
    # Canonical Praxys plan-content version used by API sync-state projection.
    plan_version = Column(String(64), nullable=True)
    # Provider-normalized content fingerprint. Unlike workout_version, this
    # excludes volatile provider identifiers such as block UUIDs.
    provider_content_version = Column(String(64), nullable=True)
    target = Column(String(20), nullable=False)
    state = Column(String(20), nullable=False, default="pending")
    external_id = Column(String(200), nullable=True)
    # Provider-opaque durable identities needed in addition to external_id.
    # Garmin, for example, owns both a template_id and a scheduled instance.
    provider_references = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    provider_account_id = Column(String(200), nullable=True)
    last_error = Column(Text, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','delivering','synced','conflict','failed','removed')",
            name="ck_plan_deliveries_state",
        ),
        UniqueConstraint(
            "user_id",
            "target",
            "canonical_key",
            "workout_version",
            name="uq_plan_delivery_version_target",
        ),
        Index(
            "uq_plan_delivery_canonical_version_target",
            "user_id",
            "target",
            "canonical_id",
            "workout_version",
            unique=True,
        ),
        Index(
            "ix_plan_deliveries_user_target_date",
            "user_id",
            "target",
            "workout_date",
        ),
        Index(
            "ix_plan_deliveries_user_target_external",
            "user_id",
            "target",
            "external_id",
        ),
    )


class PlanDeliveryAttempt(Base):
    """Append-only attempt history for a plan delivery or removal."""

    __tablename__ = "plan_delivery_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(
        String(36),
        ForeignKey("plan_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number = Column(Integer, nullable=False)
    operation = Column(String(20), nullable=False)
    state = Column(String(20), nullable=False)
    external_id = Column(String(200), nullable=True)
    error = Column(Text, nullable=True)
    response = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "state IN ('pending','delivering','synced','conflict','failed','removed')",
            name="ck_plan_delivery_attempts_state",
        ),
        CheckConstraint(
            "operation IN ('deliver','remove','import')",
            name="ck_plan_delivery_attempts_operation",
        ),
        UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_plan_delivery_attempt_number",
        ),
    )


class PlanTargetCalendarSync(Base):
    """Latest successful provider-calendar snapshot for one user and target."""

    __tablename__ = "plan_target_calendar_syncs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target = Column(String(20), nullable=False)
    provider_account_id = Column(String(200), nullable=False)
    provider_references = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    window_start = Column(Date, nullable=False)
    window_end = Column(Date, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "target",
            name="uq_plan_target_calendar_sync",
        ),
    )


class PlanTargetWorkout(Base):
    """One normalized workout observed on an execution-target calendar."""

    __tablename__ = "plan_target_workouts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target = Column(String(20), nullable=False)
    provider_account_id = Column(String(200), nullable=False)
    external_id = Column(String(200), nullable=False)
    provider_references = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    workout_date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=True)
    normalized_workout = Column(JSON, nullable=False, default=dict)
    content_fingerprint = Column(String(64), nullable=True)
    payload_fingerprint = Column(String(64), nullable=True)
    present = Column(Boolean, nullable=False, default=True)
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "target",
            "provider_account_id",
            "external_id",
            name="uq_plan_target_workout_external",
        ),
        Index(
            "ix_plan_target_workouts_user_target_date",
            "user_id",
            "target",
            "provider_account_id",
            "workout_date",
        ),
    )


class SystemAnnouncement(Base):
    """Admin-configurable site-wide notification banners.

    Active announcements are returned by GET /api/announcements to all
    authenticated users and rendered as dismissible banners in the web UI.
    Dismissed banner IDs are stored client-side (localStorage) so they
    don't re-appear after reload without server-side per-user tracking.
    """

    __tablename__ = "system_announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    type = Column(String(20), default="info", nullable=False)  # info | warning | success
    is_active = Column(Boolean, default=True, nullable=False)
    link_text = Column(String(100), nullable=True)
    link_url = Column(String(500), nullable=True)
    # Issue #355: bilingual payload. Top-level title/body/link_text stay the
    # canonical base (English) fallback; translations["zh"] = {title, body,
    # link_text} overrides per locale. Mirrors the AiInsight.translations
    # contract (#103): the frontend prefers translations[locale] and falls back
    # to the top-level fields, so single-language announcements keep working.
    translations = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WaitlistSignup(Base):
    """Private-alpha waitlist captures.

    Praxys is invitation-only during alpha; the login page lets prospective
    users drop their email + a one-line note so we can reach back when a
    slot opens. We store these locally rather than relying on the support
    inbox alone — that way a busy inbox can't lose a lead.
    """

    __tablename__ = "waitlist_signups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # unique=True is defense-in-depth: the route already does a check-then-
    # update for idempotent refresh, but a unique index closes the race
    # window for two near-simultaneous submits with the same address.
    email = Column(String(320), nullable=False, unique=True, index=True)
    note = Column(String(500), default="")
    locale = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    invited_at = Column(DateTime, nullable=True)
    # ondelete=SET NULL: a waitlist lead survives if the invitation it was sent
    # is later deleted (e.g. the inviting admin's account is removed); the link
    # is simply cleared rather than blocking the delete (issue #366).
    invitation_id = Column(Integer, ForeignKey("invitations.id", ondelete="SET NULL"), nullable=True)


class Feedback(Base):
    """User-submitted bug reports, feature requests, and general feedback.

    Canonical store for the in-app "Send feedback" entrance (web + mini
    program). The raw ``message`` is kept here (private, server-side only) so
    a human/admin can always see exactly what the user wrote. A background
    triage step (:mod:`api.feedback_triage`) then PII-scrubs + classifies the
    submission and — when GitHub is configured — opens an issue in the
    operator-chosen triage repo so an agent can pick it up. The scrubbed
    title/body that actually left the system are stored in ``ai_title`` /
    ``ai_body`` for auditability (what did we publish about this user?).

    Mirrors the WaitlistSignup pattern: store locally first so a lead/report
    survives even if the downstream (GitHub, support inbox) is unavailable.
    """

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Nullable + SET NULL on delete: a deleted user shouldn't cascade-delete
    # the feedback (it's operationally useful history), but we also don't want
    # a dangling FK. The submitter is always set at creation time.
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # bug | feature | other — validated at the route layer (Literal), stored
    # as a stable English string the frontend maps to a localized label.
    kind = Column(String(20), nullable=False, default="other")
    # Raw, unscrubbed user text. Never leaves the server verbatim — only the
    # scrubbed ai_body is published to GitHub.
    message = Column(Text, nullable=False)
    # Client-supplied diagnostic context (route, app version, user agent,
    # viewport, locale). Captured automatically so users don't have to
    # describe their environment. Scrubbed before publication.
    context_json = Column(JSON, nullable=True)
    locale = Column(String(10), nullable=True)
    # new | triaged | needs_review | issue_created | resolved | failed | rejected
    # ``resolved`` is set when the linked GitHub issue is closed (synced back via
    # the admin "Sync from GitHub" action); a reopen flips it to issue_created.
    status = Column(String(20), nullable=False, default="new", index=True)
    # Outputs of the triage step — the scrubbed, agent-ready title/body and
    # labels that were (or would be) published. Kept for audit + admin review.
    ai_title = Column(String(200), nullable=True)
    ai_body = Column(Text, nullable=True)
    ai_labels = Column(JSON, nullable=True)
    # LLM-suggested triage priority: low | medium | high | critical. NULL when
    # triaged without an LLM (the rule-based fallback doesn't guess a priority)
    # or not yet triaged. Mirrored to a ``priority: <value>`` GitHub label.
    priority = Column(String(10), nullable=True)
    github_issue_number = Column(Integer, nullable=True)
    github_issue_url = Column(String(500), nullable=True)
    # Last triage/publish error (truncated) so admins can see why a row is
    # stuck in "failed" without digging through server logs.
    error = Column(String(500), nullable=True)
    # --- Optional screenshot attachment (issue #337) ---
    # References (storage keys) for user-attached screenshots — private,
    # admin-only. The raw image never sits on this row or in a public issue;
    # only the key lives here (Azure Blob now, Tencent COS later). See
    # api/feedback_storage.py. A list of 0-3 keys, or NULL when none attached.
    image_keys = Column(JSON, nullable=True)
    # Vision-LLM-derived, PII-scrubbed textual description of the screenshot(s)
    # (UI state, visible error text). This is the ONLY image-derived text that
    # may be published to a (public) issue — never the image itself.
    image_description = Column(Text, nullable=True)
    # Vision sensitivity verdict feeding the same gate as the text path: True =
    # the model saw faces / emails / names / health-or-performance data. NULL =
    # not yet analysed (or no vision model), which the gate treats as "unsafe
    # to auto-publish" and parks for admin review.
    image_sensitive = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AgentDecision(Base):
    """Append-only, privacy-minimized record of an agent policy decision."""

    __tablename__ = "agent_decisions"
    __table_args__ = (
        Index("ix_agent_decisions_loop_created", "loop", "created_at"),
        Index(
            "ix_agent_decisions_subject",
            "subject_type",
            "subject_ref",
            "created_at",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    loop = Column(String(30), nullable=False)
    subject_type = Column(String(40), nullable=False)
    subject_ref = Column(String(120), nullable=False)
    policy_name = Column(String(100), nullable=False)
    policy_version = Column(String(100), nullable=False)
    prompt_version = Column(String(64), nullable=True)
    model = Column(String(100), nullable=True)
    mode = Column(String(20), nullable=False, default="active")
    input_sha256 = Column(String(64), nullable=False, index=True)
    input_json = Column(JSON, nullable=False, default=dict)
    output_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    outcomes = relationship(
        "AgentOutcome",
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="AgentOutcome.observed_at",
    )


class AgentOutcome(Base):
    """Append-only observation joined to the decision that produced an action."""

    __tablename__ = "agent_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "fingerprint",
            name="uq_agent_outcomes_decision_fingerprint",
        ),
        Index("ix_agent_outcomes_type_observed", "outcome_type", "observed_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(
        String(36),
        ForeignKey("agent_decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outcome_type = Column(String(60), nullable=False)
    source = Column(String(40), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    payload_json = Column(JSON, nullable=False, default=dict)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    decision = relationship("AgentDecision", back_populates="outcomes")


class AppConfig(Base):
    """System-wide operational config as a small key-value store.

    Praxys previously had only per-user config (UserConfig). This table holds
    a handful of operator-owned flags that are toggled at runtime from the
    Admin page (not env vars) — currently the self-registration gate and its
    seat cap. Values are stored as strings and parsed by api/app_config.py,
    which owns the typed getters/setters and the safe defaults for missing
    keys, so a fresh DB behaves identically to one that has never been touched.
    """

    __tablename__ = "app_config"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # ondelete=SET NULL: keep the operator flag row when the admin who last
    # toggled it is deleted; just drop the stale reference (issue #366).
    updated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ServiceIncident(Base):
    """An operator-declared service incident shown on the public status page.

    Models the Atlassian Statuspage-style lifecycle: an incident opens with an
    ``impact`` and moves through ``status`` states (investigating -> identified
    -> monitoring -> resolved) via a running timeline of
    :class:`ServiceIncidentUpdate` rows. Active (unresolved) incidents drive the
    overall banner on ``GET /api/status``; resolved ones remain as history.
    """

    __tablename__ = "service_incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    # investigating | identified | monitoring | resolved -- validated at the
    # route layer. An incident is "active" while status != 'resolved'.
    status = Column(String(20), nullable=False, default="investigating")
    # minor | major | critical -- maps to the public severity of the banner
    # (degraded / partial outage / major outage).
    impact = Column(String(20), nullable=False, default="minor")
    # When the incident began affecting users (operator-settable; defaults to
    # creation time). Distinct from created_at, the row's insert timestamp.
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Set when status flips to 'resolved'; NULL while the incident is open.
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    updates = relationship(
        "ServiceIncidentUpdate",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="ServiceIncidentUpdate.created_at",
    )


class ServiceIncidentUpdate(Base):
    """One timeline entry on a :class:`ServiceIncident`.

    Each post records the incident ``status`` at that moment plus the
    operator's ``body`` message, so the public status page can render a
    chronological narrative ("Identified -- we found the cause", "Resolved").
    """

    __tablename__ = "service_incident_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("service_incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The incident status as of this update (investigating | identified |
    # monitoring | resolved) -- lets the timeline show state transitions.
    status = Column(String(20), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("ServiceIncident", back_populates="updates")
