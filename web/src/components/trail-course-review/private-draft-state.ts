import type { TrailDraftResponse } from '../../types/trail-plan.ts';

export interface PrivateTrailDraftState {
  data: TrailDraftResponse | null;
  loading: boolean;
  error: string | null;
  errorStatus: number | null;
}

export type PrivateTrailDraftAction =
  | { type: 'begin' }
  | { type: 'success'; data: TrailDraftResponse }
  | { type: 'failure'; message: string; status: number | null }
  | { type: 'clear' };

export const INITIAL_PRIVATE_TRAIL_DRAFT_STATE: PrivateTrailDraftState = {
  data: null,
  loading: true,
  error: null,
  errorStatus: null,
};

export function reducePrivateTrailDraftState(
  _state: PrivateTrailDraftState,
  action: PrivateTrailDraftAction,
): PrivateTrailDraftState {
  if (action.type === 'begin') {
    return { data: null, loading: true, error: null, errorStatus: null };
  }
  if (action.type === 'success') {
    return {
      data: action.data,
      loading: false,
      error: null,
      errorStatus: null,
    };
  }
  if (action.type === 'failure') {
    return {
      data: null,
      loading: false,
      error: action.message,
      errorStatus: action.status,
    };
  }
  return { data: null, loading: false, error: null, errorStatus: null };
}
