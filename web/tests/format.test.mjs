import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { formatPace, formatStoredPace } from '../src/lib/format.ts';

test('formats stored pace values from sec/km and M:SS', () => {
  assert.equal(formatStoredPace('425'), '7:05 /km');
  assert.equal(formatStoredPace('5:00'), '5:00 /km');
  assert.equal(formatStoredPace('not-a-pace'), '—');
  assert.equal(formatPace(359.6), '6:00 /km');
  assert.equal(formatStoredPace(300, 'imperial'), '8:03 /mi');
});

test('activity pace cards respect the configured unit system', async () => {
  const components = [
    ['ActivityCard.tsx', 'activity.avg_pace_min_km'],
    ['LastActivityCard.tsx', 'activity.avg_pace_min_km'],
    ['SplitBreakdown.tsx', 's.avg_pace_min_km'],
  ];

  for (const [component, pace] of components) {
    const source = await readFile(
      new URL(`../src/components/${component}`, import.meta.url),
      'utf8',
    );
    assert.match(source, new RegExp(`formatStoredPace\\(${pace}, unitSystem\\)`));
    assert.match(source, /useSettings/);
  }
});
