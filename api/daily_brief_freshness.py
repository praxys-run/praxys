"""Compatibility constants for deterministic Today responses."""

# Strip this server-owned key from legacy persisted daily-brief metadata.
DAILY_BRIEF_FRESHNESS_KEY = "daily_brief_freshness"

# Cache/ETag salt for the deterministic /api/today representation.
TODAY_RESPONSE_VERSION = "heat-adaptation-today-v9"
TRAINING_RESPONSE_VERSION = "heat-adaptation-training-v8"
PLAN_RESPONSE_VERSION = "connection-aware-plan-v2"