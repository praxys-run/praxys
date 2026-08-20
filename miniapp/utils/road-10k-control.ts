export const ROAD_10K_ROLLOUT_STATES = [
  'invited', 'reauth-required', 'notice-unavailable', 'enrolled',
  'enrollment-closed', 'hold', 'withdrawn', 'removed', 'paused', 'killed',
  'rollback', 'stopped', 'revision',
] as const;

export const ROAD_10K_PLAN_STATES = [
  'none', 'checking', 'baseline-required', 'limited-guidance', 'safety-stop',
  'generating', 'generation-failed', 'proposal-ready', 'review-later',
  'rejected', 'successor-requested', 'expired', 'active', 'paused-by-owner',
  'ended-by-owner', 'completed', 'deleted',
] as const;

export const ROAD_10K_NETWORK_STATES = [
  'offline', 'slow', 'stale', 'conflict', 'unknown-control', 'session-expired',
] as const;

export const ROAD_10K_SCREENSHOT_AVAILABLE = false as const;
