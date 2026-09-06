import { TrailOperationCancelledError } from './mutation-error.ts';

type PrivateDraftFetcher = (signal: AbortSignal) => Promise<unknown>;

export async function requestPrivateTrailDraft(
  fetcher: PrivateDraftFetcher,
  signal: AbortSignal,
): Promise<unknown> {
  try {
    return await fetcher(signal);
  } catch (error) {
    if (signal.aborted) throw new TrailOperationCancelledError();
    throw error;
  }
}
