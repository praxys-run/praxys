import assert from 'node:assert/strict';
import test from 'node:test';
import { SERVICE_WORKER_UPDATE_INTERVAL_MS, watchServiceWorkerUpdates } from '../src/lib/service-worker-update.ts';

function harness(update = async () => {}) {
  const document = new EventTarget();
  document.visibilityState = 'visible';
  const window = new EventTarget();
  const navigator = { onLine: true };
  let now = 0;
  let calls = 0;
  const stop = watchServiceWorkerUpdates({ update() { calls++; return update(); } }, {
    document, window, navigator, now: () => now,
  });
  return {
    document, window, navigator, stop,
    calls: () => calls,
    advance: () => { now += SERVICE_WORKER_UPDATE_INTERVAL_MS; },
    emit: (target, event) => target.dispatchEvent(new Event(event)),
  };
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('mobile tab resume checks for a replacement worker without a page reload', async () => {
  const h = harness();
  assert.equal(h.calls(), 0);
  h.document.visibilityState = 'hidden';
  h.emit(h.document, 'visibilitychange');
  await settle();
  assert.equal(h.calls(), 0);
  h.document.visibilityState = 'visible';
  h.emit(h.document, 'visibilitychange');
  await settle();
  assert.equal(h.calls(), 1);
  h.advance();
  h.emit(h.window, 'pageshow');
  await settle();
  assert.equal(h.calls(), 2);
});

test('offline resume preserves the current bundle and reconnect retries', async () => {
  const h = harness();
  h.navigator.onLine = false;
  h.emit(h.window, 'pageshow');
  await settle();
  assert.equal(h.calls(), 0);
  h.navigator.onLine = true;
  h.emit(h.window, 'online');
  await settle();
  assert.equal(h.calls(), 1);
});

test('resume events are throttled and concurrent checks do not overlap', async () => {
  let finish;
  const h = harness(() => new Promise(resolve => { finish = resolve; }));
  h.emit(h.window, 'pageshow');
  h.emit(h.document, 'visibilitychange');
  await settle();
  h.advance();
  h.emit(h.window, 'online');
  await settle();
  assert.equal(h.calls(), 1);
  finish();
  await settle();
  h.emit(h.window, 'pageshow');
  await settle();
  assert.equal(h.calls(), 2);
  finish();
  await settle();
  h.emit(h.window, 'online');
  await settle();
  assert.equal(h.calls(), 2);
});

test('a rejected or synchronously failing update can be retried on later resume', async () => {
  for (const update of [async () => { throw new Error('offline'); }, () => { throw new Error('offline'); }]) {
    const h = harness(update);
    h.emit(h.window, 'pageshow');
    await settle();
    h.advance();
    h.emit(h.window, 'pageshow');
    await settle();
    assert.equal(h.calls(), 2);
  }
});

test('cleanup removes resume hooks', async () => {
  const h = harness();
  h.stop();
  h.emit(h.window, 'pageshow');
  h.emit(h.window, 'online');
  h.emit(h.document, 'visibilitychange');
  await settle();
  assert.equal(h.calls(), 0);
});
