import assert from 'node:assert/strict';
import test from 'node:test';

import {
  choosePlanDeliveryTarget,
  planTargetSelection,
} from '../src/lib/plan-delivery.ts';
import {
  planTargetSelection as miniappPlanTargetSelection,
} from '../../miniapp/utils/managed-plan.ts';

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

test('paused management can select another eligible target without resuming', () => {
  const connected = [
    { platform: 'stryd', selectable: true, reason: null },
    { platform: 'garmin', selectable: true, reason: null },
  ];

  assert.equal(
    planTargetSelection('paused', connected, 'garmin', 'stryd', 'stryd'),
    'garmin',
  );
  assert.equal(
    miniappPlanTargetSelection(
      'paused',
      connected.map(({ platform, selectable }) => ({
        key: platform,
        selectable,
      })),
      'garmin',
      'stryd',
      'stryd',
    ),
    'garmin',
  );
});

test('active management keeps the durable target read-only', () => {
  const connected = [
    { platform: 'stryd', selectable: true, reason: null },
    { platform: 'garmin', selectable: true, reason: null },
  ];

  assert.equal(
    planTargetSelection('active', connected, 'garmin', 'garmin', 'stryd'),
    'stryd',
  );
  assert.equal(
    miniappPlanTargetSelection(
      'active',
      connected.map(({ platform, selectable }) => ({
        key: platform,
        selectable,
      })),
      'garmin',
      'garmin',
      'stryd',
    ),
    'stryd',
  );
});
