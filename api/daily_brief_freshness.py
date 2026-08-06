"""Compatibility constants for deterministic Today responses."""

# Strip this server-owned key from legacy persisted daily-brief metadata.
DAILY_BRIEF_FRESHNESS_KEY = "daily_brief_freshness"

# Cache/ETag salt for the deterministic /api/today representation.
TODAY_RESPONSE_VERSION = "heat-adaptation-today-v13"
TRAINING_RESPONSE_VERSION = "peer-metric-volume-training-v13"
GOAL_RESPONSE_VERSION = "fixed-heat-model-goal-v2"
SCIENCE_RESPONSE_VERSION = "fixed-heat-model-v2"
PLAN_RESPONSE_VERSION = "workout-management-v6"