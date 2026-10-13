import assert from 'node:assert/strict';
import test from 'node:test';
import { todayAdviceKey as webAdvice } from '../src/lib/today-advice.ts';
import { todayAdviceKey as miniAdvice } from '../../miniapp/utils/today-advice.ts';

for (const [surface, advice] of [['web', webAdvice], ['miniapp', miniAdvice]]) {
  test(`${surface}: no scheduled workout still has bounded training guidance`, () => {
    const signal = { recommendation: 'unscheduled', reason_code: 'unscheduled_open', plan: {} };
    const recovery = { status: 'normal', hrv: { today_ms: 47 }, hrv_is_stale: false };
    assert.equal(advice(signal, recovery), 'unscheduled_go');
    assert.equal(advice({ ...signal, reason_code: 'unscheduled_hrv_caution' }, recovery), 'unscheduled_rest');
    assert.equal(advice({ ...signal, reason_code: 'unscheduled_high_load' }, recovery), 'unscheduled_easy');
    for (const limited of [null, { status: 'insufficient_data' }, { ...recovery, hrv: null },
      ...[null, 0, Number.NaN].map(today_ms => ({ ...recovery, hrv: { today_ms } })),
      { ...recovery, hrv_is_stale: true }, { ...recovery, classification_reason: 'zero_variance' }]) {
      assert.equal(advice(signal, limited), 'unscheduled_unknown');
    }
    assert.deepEqual(signal.plan, {}, 'A guidance badge must not create a workout');
    assert.equal(advice({ ...signal, recommendation: 'rest', reason_code: 'rest_scheduled' }, recovery), 'rest');
  });
}
