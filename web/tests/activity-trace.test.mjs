import assert from 'node:assert/strict';
import test from 'node:test';
import {
  availableTraces,
  closestRecordedSample,
  formatElapsed,
  traceDomain,
  traceSegments,
  zoomTraceViewport,
} from '../src/lib/activity-trace.ts';

function point(offset_sec, power_watts, hr_bpm, power_watts_break = false) {
  return {
    offset_sec, power_watts, hr_bpm, pace_sec_km: null, source: 'garmin',
    power_watts_break, hr_bpm_break: false, pace_sec_km_break: false,
  };
}

test('only actually sampled traces can be selected', () => {
  assert.deepEqual(availableTraces([point(0, null, 140), point(1, null, 141)]), ['hr_bpm']);
  assert.deepEqual(availableTraces([]), []);
  const extended = [
    { ...point(0, null, null), altitude_m: -10, temperature_c: 0 },
    { ...point(1, null, null), altitude_m: null, temperature_c: null },
    { ...point(2, null, null), altitude_m: -8, altitude_m_break: true },
  ];
  assert.deepEqual(availableTraces(extended), ['altitude_m', 'temperature_c']);
  assert.deepEqual(traceSegments(extended, 'altitude_m', 0, 2).map((part) => part.length), [1, 1]);
  const [low, high] = traceDomain(traceSegments(extended, 'altitude_m', 0, 2), 'altitude_m');
  assert.ok(low < -10 && high > -8);
});

test('draws separate paths at recorded gaps and does not make up a cursor value', () => {
  const samples = [point(0, 210, 140, true), point(1, null, 141), point(20, 225, 145, true)];
  assert.deepEqual(traceSegments(samples, 'power_watts', 0, 20).map((segment) => segment.length), [1, 1]);
  assert.equal(closestRecordedSample(samples, 10, 'power_watts'), null);
  assert.equal(closestRecordedSample(samples, 20, 'power_watts')?.power_watts, 225);
  assert.equal(closestRecordedSample(samples, 1, 'power_watts')?.power_watts, null);
  assert.equal(closestRecordedSample([point(0, 210, 140), point(40, 220, 145)], 20, 'power_watts'), null);
});

test('axes derive from the visible recorded points, including pace', () => {
  const samples = [point(0, 190, null), point(10, 240, null)];
  const [low, high] = traceDomain(traceSegments(samples, 'power_watts', 0, 10), 'power_watts');
  assert.ok(low < 190 && high > 240);
  assert.equal(formatElapsed(3724), '1:02:04');
});

test('zooming into a selected kilometer never escapes its current interval', () => {
  assert.deepEqual(zoomTraceViewport([400, 800], 400, [0, 1320], .5, 30), [400, 600]);
  assert.deepEqual(zoomTraceViewport([400, 600], 500, [0, 1320], 2, 30), [300, 700]);
  assert.deepEqual(zoomTraceViewport([364, 451], 482, [0, 1320], .5, 30), [407, 451]);
});
