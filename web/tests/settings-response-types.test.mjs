import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web and miniapp settings types include sync interval metadata', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);

  for (const source of [webTypes, miniTypes]) {
    assert.match(source, /sync_interval_options_hours: number\[\];/);
    assert.match(source, /default_sync_interval_hours: number;/);
  }
});
