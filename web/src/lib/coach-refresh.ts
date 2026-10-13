import type { AiInsightResponse } from '../types/api';

/** A changed server snapshot requires rereading Today before rereading Coach. */
export function needsCoachSnapshotRefresh(response: AiInsightResponse, snapshot: string | null | undefined): boolean {
  return response.ai_available !== false && response.content_status === 'stale'
    && Boolean(snapshot) && response.snapshot !== snapshot;
}

interface CoachQuery {
  state: { data: unknown; error: unknown; isInvalidated?: boolean };
}

interface CoachRefetchInterval {
  (query: CoachQuery): number | false;
  restart: () => void;
}

/** Revalidate visible daily content and briefly wait for a post-sync result. */
export function createDailyCoachRefetchInterval(): CoachRefetchInterval {
  let pendingDeadline: number | null = null;
  let invalidated = false;
  const interval: CoachRefetchInterval = ({ state }) => {
    if (state.isInvalidated && !invalidated) pendingDeadline = null;
    invalidated = state.isInvalidated === true;
    const response = state.data as AiInsightResponse | undefined;
    if (state.error || !response?.ai_available || response.content_status !== 'pending') {
      pendingDeadline = null;
      return !state.error && response?.ai_available && response.content_status === 'ready'
        ? 60_000 : false;
    }
    // Start when pending is first observed, and retain the deadline across
    // automatic reads. A later pending episode or explicit refresh re-arms it.
    pendingDeadline ??= Date.now() + 60_000;
    return Date.now() < pendingDeadline ? 3_000 : false;
  };
  interval.restart = () => { pendingDeadline = null; };
  return interval;
}
