import { useCallback, useEffect, useReducer, useRef } from 'react';
import { apiFetcher } from '@/hooks/useApi';
import { ApiResponseError } from '@/lib/api-error';
import { TRAIL_API_ENDPOINTS, type TrailDraftResponse } from '@/types/trail-plan';
import { parseTrailDraftResponse } from './validation';
import {
  INITIAL_PRIVATE_TRAIL_DRAFT_STATE,
  reducePrivateTrailDraftState,
} from './private-draft-state';

interface PrivateTrailDraftResult {
  data: TrailDraftResponse | null;
  loading: boolean;
  error: string | null;
  errorStatus: number | null;
  refetch: () => Promise<void>;
  fetchLatest: () => Promise<TrailDraftResponse>;
  replaceData: (value: TrailDraftResponse) => void;
  clearData: () => void;
  rejectData: (message: string) => void;
}

export function usePrivateTrailDraft(): PrivateTrailDraftResult {
  const mountedRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const [state, dispatch] = useReducer(
    reducePrivateTrailDraftState,
    INITIAL_PRIVATE_TRAIL_DRAFT_STATE,
  );

  const replaceData = useCallback((value: TrailDraftResponse) => {
    dispatch({ type: 'success', data: value });
  }, []);

  const clearData = useCallback(() => {
    dispatch({ type: 'clear' });
  }, []);

  const rejectData = useCallback((message: string) => {
    dispatch({ type: 'failure', message, status: null });
  }, []);

  const fetchLatest = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const raw = await apiFetcher<unknown>(
      TRAIL_API_ENDPOINTS.draft,
      controller.signal,
      15_000,
    );
    const result = parseTrailDraftResponse(raw);
    if (!result) throw new Error('The Trail draft response was not recognized.');
    return result;
  }, []);

  const refetch = useCallback(async () => {
    dispatch({ type: 'begin' });
    try {
      const result = await fetchLatest();
      if (!mountedRef.current) return;
      replaceData(result);
    } catch (reason) {
      if (!mountedRef.current) return;
      const responseError = reason instanceof ApiResponseError ? reason : null;
      dispatch({
        type: 'failure',
        message: reason instanceof Error
          ? reason.message
          : 'Trail course review could not be loaded.',
        status: responseError?.status ?? null,
      });
      throw reason;
    }
  }, [fetchLatest, replaceData]);

  useEffect(() => {
    mountedRef.current = true;
    queueMicrotask(() => {
      if (mountedRef.current) void refetch().catch(() => undefined);
    });
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [refetch]);

  return {
    ...state,
    refetch,
    fetchLatest,
    replaceData,
    clearData,
    rejectData,
  };
}
