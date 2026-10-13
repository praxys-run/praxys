import assert from 'node:assert/strict';
import test from 'node:test';
import { createDailyCoachRefetchInterval, needsCoachSnapshotRefresh } from '../src/lib/coach-refresh.ts';

const query = (content_status, ai_available = true) => ({
  state: { data: { content_status, ai_available }, error: null },
});

test('server snapshot changes refresh Today; invalid content at the same snapshot does not loop', () => {
  assert.equal(needsCoachSnapshotRefresh({ ai_available: true, content_status: 'stale', snapshot: 'new' }, 'old'), true);
  assert.equal(needsCoachSnapshotRefresh({ ai_available: true, content_status: 'stale', snapshot: null }, 'old'), true);
  assert.equal(needsCoachSnapshotRefresh({ ai_available: true, content_status: 'stale', snapshot: 'old' }, 'old'), false);
  assert.equal(needsCoachSnapshotRefresh({ ai_available: false, content_status: 'stale', snapshot: 'new' }, 'old'), false);
  assert.equal(needsCoachSnapshotRefresh({ ai_available: true, content_status: 'ready', snapshot: 'new' }, 'old'), false);
});

test('pending Coach is reread while post-sync generation finishes, with a bounded wait', t => {
  let now = 0;
  t.mock.method(Date, 'now', () => now);
  const interval = createDailyCoachRefetchInterval();
  assert.equal(interval(query('pending')), 3_000);
  now = 59_999;
  assert.equal(interval(query('pending')), 3_000);
  now = 60_000;
  assert.equal(interval(query('pending')), false);
  assert.equal(interval(query('ready')), 60_000);
  // A replacement training snapshot starts its own bounded wait.
  assert.equal(createDailyCoachRefetchInterval()(query('pending')), 3_000);
});

test('unavailable, stale and failed reads stop automatic polling', () => {
  const interval = createDailyCoachRefetchInterval();
  for (const state of [
    query('ready', false), query('unavailable'), query('stale'),
    { state: { data: undefined, error: null } },
    { state: { data: query('pending').state.data, error: new Error('HTTP 503') } },
  ]) assert.equal(interval(state), false);
});

test('slow first read and a later pending episode each get a full bounded window', t => {
  let now = 0;
  t.mock.method(Date, 'now', () => now);
  const interval = createDailyCoachRefetchInterval();
  now = 120_000;
  assert.equal(interval(query('pending')), 3_000);
  now = 179_999;
  assert.equal(interval(query('pending')), 3_000);
  now = 180_000;
  assert.equal(interval(query('pending')), false);
  assert.equal(interval(query('ready')), 60_000);
  now = 300_000;
  assert.equal(interval(query('pending')), 3_000);
  now = 360_000;
  assert.equal(interval(query('pending')), false);
});

test('explicit refresh and same-snapshot sync rearm an exhausted pending window', t => {
  let now = 0;
  t.mock.method(Date, 'now', () => now);
  const interval = createDailyCoachRefetchInterval();
  assert.equal(interval(query('pending')), 3_000);
  now = 60_000;
  assert.equal(interval(query('pending')), false);
  interval.restart();
  assert.equal(interval(query('pending')), 3_000);
  now = 120_000;
  assert.equal(interval(query('pending')), false);
  const invalidated = query('pending');
  invalidated.state.isInvalidated = true;
  assert.equal(interval(invalidated), 3_000);
  now = 180_000;
  assert.equal(interval(invalidated), false, 'Repeated callbacks while invalidated must not extend the window');
  assert.equal(interval(query('pending')), false);
});
