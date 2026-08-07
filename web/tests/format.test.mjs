import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { formatPace, formatStoredPace, shouldShowMetricProvenance } from '../src/lib/format.ts';

test('formats stored pace values from sec/km and M:SS', () => {
  assert.equal(formatStoredPace('425'), '7:05 /km');
  assert.equal(formatStoredPace('5:00'), '5:00 /km');
  assert.equal(formatStoredPace('not-a-pace'), '—');
  assert.equal(formatPace(359.6), '6:00 /km');
});

test('suppresses metric provenance when it repeats the page date', () => {
  assert.equal(shouldShowMetricProvenance('2026-08-06', '2026-08-06'), false);
  assert.equal(shouldShowMetricProvenance('2026-08-05', '2026-08-06'), true);
  assert.equal(shouldShowMetricProvenance('2026-08-06T04:00:00Z', '2026-08-06'), false);
  assert.equal(shouldShowMetricProvenance(null, '2026-08-06'), false);
  assert.equal(shouldShowMetricProvenance('2026-08-06', null), true);
});

test('History activity cards use the stored pace formatter', async () => {
  const source = await readFile(
    new URL('../src/components/ActivityCard.tsx', import.meta.url),
    'utf8',
  );

  assert.match(source, /formatStoredPace\(activity\.avg_pace_min_km\)/);
  assert.doesNotMatch(source, />\{activity\.avg_pace_min_km\}</);
});

test('feedback decision records wrap within their table cell', async () => {
  const source = await readFile(
    new URL('../src/pages/admin/AdminFeedback.tsx', import.meta.url),
    'utf8',
  );

  assert.match(source, /<TableCell className="min-w-\[290px\] whitespace-normal">/);
});
