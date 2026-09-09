import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

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

test('Training keeps status and recovery while routine controls live in Settings', async () => {
  const web = await readFile(new URL('../src/components/ManagedPlanSettingsCard.tsx', import.meta.url), 'utf8');
  assert.match(web, /compact = false/);
  assert.doesNotMatch(web, /Collapsible|settingsExpanded|Delivery and adjustments/);
  assert.match(web, /compact \? \([\s\S]*?<Link to="\/settings#plan-management"/);
  const summary = web.slice(web.indexOf('{showSummary && (compact ? ('), web.indexOf('<Card className="mb-8">'));
  assert.match(summary, /Delivery to \{targetLabel\} is enabled/);
  assert.doesNotMatch(summary, /Sending workouts to/);
  assert.match(summary, /gap-x-4 gap-y-1 text-xs text-foreground/);
  assert.match(summary, /nativeButton=\{false\} render=\{<Link to="\/settings#plan-management"/);
  assert.match(summary, /onClick=\{pauseDelivery\}/);
  assert.match(summary, /onClick=\{openCleanupRecovery\}/);
  assert.match(summary, /resetLeaveDialog\(true\)/);
  assert.match(summary, /planError/);
  assert.match(summary, /refetchPlan/);
  assert.match(summary, /\{actionAlerts\}/);
  assert.match(summary, /\{adjustmentAlerts\}/);
  assert.doesNotMatch(summary, /previewWorkouts\.map|setConfirmMode|setAdjustmentConsentOpen/);
  assert.match(web, /actionableAdjustments\.slice\(0, 5\)\.map\(renderAdjustment\)/);
  assert.match(web, /adjustment\.status === 'active' && adjustment\.can_undo/);
  assert.ok(web.indexOf('</Card>') < web.indexOf('<Dialog\n'));
});

test('the plan-settings deep link waits for data and restores focus once', async () => {
  const settings = await readFile(new URL('../src/pages/Settings.tsx', import.meta.url), 'utf8');
  assert.match(settings, /location\.hash !== '#plan-management'/);
  assert.match(settings, /focusedPlanLocation\.current === location\.key/);
  assert.match(settings, /\|\| loading\s*\|\| !config\s*\|\| error/);
  assert.match(settings, /target\.scrollIntoView\(\{ block: 'start' \}\)/);
  assert.match(settings, /target\.focus\(\{ preventScroll: true \}\)/);
  assert.match(settings, /focusedPlanLocation\.current = location\.key/);
  assert.match(settings, /id="plan-management" ref=\{planManagementAnchor\} tabIndex=\{-1\}/);
});

test('compact management retains the fixed preview and separate delivery and adjustment consent', async () => {
  const web = await readFile(new URL('../src/components/ManagedPlanSettingsCard.tsx', import.meta.url), 'utf8');
  assert.match(web, /const planUrl = managedPlanPreviewUrl\(\)/);
  assert.match(web, /const expectedWindow = managedPlanWindow\(\)/);
  assert.match(web, /plan\.window\.start !== expectedWindow\.start/);
  assert.match(web, /plan\.window\.end !== expectedWindow\.end/);
  assert.match(web, /open=\{confirmMode != null\}/);
  assert.match(web, /open=\{adjustmentConsentOpen\}/);
  assert.match(web, /open=\{leaveOpen\}/);
  assert.match(web, /open=\{targetSwitchOpen\}/);
  assert.match(web, /leaveChoice === 'remove'/);
  assert.match(web, /openCleanupRecovery/);
  assert.match(web, /previewWorkouts\.map/);
});
