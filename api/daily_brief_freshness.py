"""Compatibility constants for deterministic Today responses."""

# Strip this server-owned key from legacy persisted daily-brief metadata.
DAILY_BRIEF_FRESHNESS_KEY = "daily_brief_freshness"

# Cache/ETag salt for the deterministic /api/today representation.
TODAY_RESPONSE_VERSION = "private-plan-boundary-today-v14"
TRAINING_RESPONSE_VERSION = "private-plan-boundary-training-v14"
GOAL_RESPONSE_VERSION = "history-first-5k-baseline-v1"
SCIENCE_RESPONSE_VERSION = "fixed-heat-model-v2"
PLAN_RESPONSE_VERSION = "workout-management-v7"