export class TrailMutationResponseError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'TrailMutationResponseError';
    this.status = status;
  }
}

export class TrailTransportError extends Error {
  constructor() {
    super('The Trail request could not reach the server.');
    this.name = 'TrailTransportError';
  }
}

export class TrailOperationCancelledError extends Error {
  constructor() {
    super('The Trail request was cancelled.');
    this.name = 'TrailOperationCancelledError';
  }
}

export type TrailMutationFailureDisposition =
  | 'stale'
  | 'retryable'
  | 'cancelled'
  | 'hard';

export async function requestTrailMutation(
  fetcher: (url: string, init: RequestInit) => Promise<Response>,
  url: string,
  init: RequestInit,
  signal: AbortSignal,
): Promise<Response> {
  try {
    return await fetcher(url, { ...init, signal });
  } catch {
    if (signal.aborted) throw new TrailOperationCancelledError();
    throw new TrailTransportError();
  }
}

export function classifyTrailMutationFailure(
  error: unknown,
): TrailMutationFailureDisposition {
  if (error instanceof TrailOperationCancelledError) return 'cancelled';
  if (error instanceof TrailTransportError) return 'retryable';
  if (
    error instanceof TrailMutationResponseError
    || error instanceof ApiResponseError
  ) {
    if (error.status === 412) return 'stale';
    if (error.status >= 500 && error.status <= 599) return 'retryable';
  }
  return 'hard';
}

export function preservesPendingTrailEdits(error: unknown): boolean {
  const disposition = classifyTrailMutationFailure(error);
  return disposition === 'stale' || disposition === 'retryable';
}
import { ApiResponseError } from '../../lib/api-error.ts';
