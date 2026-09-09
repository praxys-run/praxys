import assert from 'node:assert/strict';
import test from 'node:test';

import {
  TrailTransportError,
} from '../src/components/trail-course-review/mutation-error.ts';
import {
  requestPrivateTrailDraft,
} from '../src/components/trail-course-review/private-draft-request.ts';

test('private draft request keeps successful-response JSON decoding failures hard', async () => {
  const controller = new AbortController();
  await assert.rejects(
    requestPrivateTrailDraft(
      async () => {
        const response = new Response('{', {
          status: 200,
          headers: { 'content-type': 'application/json' },
        });
        return response.json();
      },
      controller.signal,
    ),
    (error) => error instanceof SyntaxError
      && !(error instanceof TrailTransportError),
  );
});

test('private draft request leaves unproven read failures hard', async () => {
  const controller = new AbortController();
  await assert.rejects(
    requestPrivateTrailDraft(
      async () => { throw new TypeError('unproven read failure'); },
      controller.signal,
    ),
    (error) => error instanceof TypeError
      && !(error instanceof TrailTransportError),
  );
});

test('private draft request maps only an explicitly aborted lifetime to cancellation', async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    requestPrivateTrailDraft(
      async () => { throw new TypeError('aborted fetch'); },
      controller.signal,
    ),
    { name: 'TrailOperationCancelledError' },
  );
});
