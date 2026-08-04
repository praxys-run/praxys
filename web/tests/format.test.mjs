import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { formatPace, formatStoredPace } from '../src/lib/format.ts';

test('formats stored pace values from sec/km and M:SS', () => {
  assert.equal(formatStoredPace('425'), '7:05 /km');
  assert.equal(formatStoredPace('5:00'), '5:00 /km');
  assert.equal(formatStoredPace('not-a-pace'), '—');
  assert.equal(formatPace(359.6), '6:00 /km');
});

test('History activity cards use the stored pace formatter', async () => {
  const source = await readFile(
    new URL('../src/components/ActivityCard.tsx', import.meta.url),
    'utf8',
  );

  assert.match(source, /formatStoredPace\(activity\.avg_pace_min_km\)/);
  assert.doesNotMatch(source, />\{activity\.avg_pace_min_km\}</);
});
