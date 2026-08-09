import assert from 'node:assert/strict';
import test from 'node:test';

import {
  choosePlanDeliveryTarget,
} from '../src/lib/plan-delivery.ts';

const options = [
  { platform: 'garmin', selectable: false, reason: 'account_not_eligible' },
  { platform: 'stryd', selectable: true, reason: null },
  { platform: 'strava', selectable: false, reason: 'delivery_not_supported' },
];

test('explicit choice wins when it remains selectable', () => {
  assert.equal(
    choosePlanDeliveryTarget(options, 'stryd', 'garmin', null),
    'stryd',
  );
});

test('primary activity source is the default when selectable', () => {
  assert.equal(
    choosePlanDeliveryTarget(options, null, 'stryd', null),
    'stryd',
  );
});

test('valid configured target survives when primary is unsupported', () => {
  assert.equal(
    choosePlanDeliveryTarget(options, null, 'strava', 'stryd'),
    'stryd',
  );
});

test('single selectable target is chosen without an implicit unsupported target', () => {
  assert.equal(
    choosePlanDeliveryTarget(options, null, 'strava', null),
    'stryd',
  );
});

test('multiple selectable targets require a choice without a usable default', () => {
  assert.equal(
    choosePlanDeliveryTarget(
      [
        ...options,
        { platform: 'coros', selectable: true, reason: null },
      ],
      null,
      'strava',
      null,
    ),
    null,
  );
});
