import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { QueryClient } from '@tanstack/react-query';

import { ApiResponseError } from '../src/lib/api-error.ts';
import { shouldRetryCurrentPlanProposal } from '../src/lib/plan-proposal-query.ts';
import {
  ApiTimeoutError,
  shouldRetryApiRequest,
} from '../src/lib/request-timeout.ts';

test('expected current-proposal absence settles after one request with its typed error intact', async () => {
  const error = new ApiResponseError({
    status: 404,
    code: 'PLAN_PROPOSAL_NOT_FOUND',
    message: 'No active plan proposal exists.',
  });
  const client = new QueryClient();
  const queryKey = ['/api/plan/proposals/current', 'synthetic-user'];
  let requests = 0;

  try {
    await assert.rejects(client.fetchQuery({
      queryKey,
      queryFn: () => {
        requests += 1;
        throw error;
      },
      retry: shouldRetryCurrentPlanProposal,
      retryDelay: 0,
    }), (actual) => actual === error);

    assert.equal(requests, 1);
    assert.equal(client.getQueryState(queryKey)?.status, 'error');
    assert.equal(client.getQueryState(queryKey)?.fetchStatus, 'idle');
    assert.equal(client.getQueryState(queryKey)?.error, error);
    assert.equal(client.getQueryData(queryKey), undefined);
  } finally {
    client.clear();
  }
});

test('transient proposal failures keep the existing two-retry recovery', async () => {
  const error = new ApiResponseError({
    status: 503,
    code: 'SERVICE_UNAVAILABLE',
    message: 'Temporarily unavailable.',
  });
  const client = new QueryClient();
  let requests = 0;

  try {
    const result = await client.fetchQuery({
      queryKey: ['/api/plan/proposals/current', 'synthetic-user'],
      queryFn: () => {
        requests += 1;
        if (requests < 3) throw error;
        return { id: 'synthetic-proposal', state: 'draft' };
      },
      retry: shouldRetryCurrentPlanProposal,
      retryDelay: 0,
    });

    assert.equal(requests, 3);
    assert.equal(result.id, 'synthetic-proposal');
  } finally {
    client.clear();
  }
});

test('only the exact typed status and code skip proposal retries', () => {
  for (const error of [
    new ApiResponseError({ status: 404, message: 'Not found.' }),
    new ApiResponseError({ status: 404, code: 'OTHER_NOT_FOUND', message: 'Not found.' }),
    new ApiResponseError({ status: 503, code: 'PLAN_PROPOSAL_NOT_FOUND', message: 'Unavailable.' }),
    new TypeError('Failed to fetch'),
    new Error('PLAN_PROPOSAL_NOT_FOUND'),
  ]) {
    assert.equal(shouldRetryCurrentPlanProposal(0, error), true);
    assert.equal(shouldRetryCurrentPlanProposal(1, error), true);
    assert.equal(shouldRetryCurrentPlanProposal(2, error), false);
  }
  assert.equal(shouldRetryCurrentPlanProposal(0, new ApiTimeoutError()), false);
});

test('the proposal-specific override leaves other queries and the loading guard unchanged', async () => {
  const expectedAbsence = new ApiResponseError({
    status: 404,
    code: 'PLAN_PROPOSAL_NOT_FOUND',
    message: 'No active plan proposal exists.',
  });
  assert.equal(shouldRetryApiRequest(0, expectedAbsence), true);

  const [hook, planStart] = await Promise.all([
    readFile(new URL('../src/hooks/useApi.ts', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/PlanStart.tsx', import.meta.url), 'utf8'),
  ]);
  assert.match(hook, /options\?\.retry\s*\? \{ retry: options\.retry \}\s*:\s*options\?\.timeoutMs\s*\? \{ retry: shouldRetryApiRequest \}\s*:\s*\{\}/);
  assert.match(planStart, /'\/api\/plan\/proposals\/current',\s*\{ timeoutMs: 12_000, retry: shouldRetryCurrentPlanProposal \}/);
  assert.match(planStart, /currentProposalLoading && !displayedProposal/);
  assert.match(planStart, /currentProposalErrorCode === 'PLAN_PROPOSAL_NOT_FOUND'/);
});
