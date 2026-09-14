import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('shared Select opens beside its trigger rather than aligning an item over it', async () => {
  const source = await readFile(new URL('../src/components/ui/select.tsx', import.meta.url), 'utf8');
  assert.match(source, /side = "bottom"/);
  assert.match(source, /sideOffset = 4/);
  assert.match(source, /align = "start"/);
  assert.match(source, /alignItemWithTrigger = false/);
  assert.match(source, /<SelectPrimitive\.Positioner[\s\S]*?alignItemWithTrigger=\{alignItemWithTrigger\}/);
  assert.match(source, /max-h-\(--available-height\)/);
  assert.match(source, /<SelectPrimitive\.List>/);
  assert.match(source, /<SelectPrimitive\.ItemIndicator/);
});
