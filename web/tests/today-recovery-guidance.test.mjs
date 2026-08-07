import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('Today coach shows recovery context alongside canonical training advice', async () => {
  const [webToday, miniToday, miniTemplate] = await Promise.all([
    read('../src/pages/Today.tsx'),
    read('../../miniapp/pages/today/index.ts'),
    read('../../miniapp/pages/today/index.wxml'),
  ]);

  assert.match(webToday, /summary:\s*localizedRecoverySummary\(ra,\s*i18n\)/);
  assert.match(webToday, /recommendations:\s*localizedAlternatives/);
  assert.match(webToday, /fetchInsight=\{false\}/);

  assert.match(
    miniToday,
    /summary:\s*localizedRecoverySummary\(response\.recovery_analysis\)/,
  );
  assert.match(miniToday, /recommendations,\s*\n\s*attribution,/);
  assert.match(miniTemplate, /class="coach-summary">\{\{coach\.summary\}\}/);
});
