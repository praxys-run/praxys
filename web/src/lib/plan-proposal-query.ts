import { ApiResponseError } from './api-error.ts';
import { shouldRetryApiRequest } from './request-timeout.ts';

export function shouldRetryCurrentPlanProposal(
  failureCount: number,
  error: Error,
): boolean {
  // Absence is a terminal, expected response, not a transient service failure.
  if (
    error instanceof ApiResponseError
    && error.status === 404
    && error.code === 'PLAN_PROPOSAL_NOT_FOUND'
  ) return false;

  return shouldRetryApiRequest(failureCount, error);
}
