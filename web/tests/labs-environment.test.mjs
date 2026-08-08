import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web Labs covers consent, result, calculator, and withdrawal states', async () => {
  const [page, app, sidebar] = await Promise.all([
    read('../src/pages/Labs.tsx'),
    read('../src/App.tsx'),
    read('../src/components/AppSidebar.tsx'),
  ]);

  assert.match(app, /path="labs"/);
  assert.match(sidebar, /to: '\/labs'/);
  assert.match(page, /adult_attested: adultAttested/);
  assert.match(page, /consent_version: state\.consent_version/);
  assert.match(page, /historical_association_only/);
  assert.match(page, /Historical association; not predictively validated/);
  assert.match(page, /environment-response\/wet-bulb/);
  assert.match(page, /Withdraw and delete result/);
  assert.match(page, /ScienceNote/);
});

test('miniapp Labs preserves the web experiment lifecycle', async () => {
  const [controller, template, app, settings] = await Promise.all([
    read('../../miniapp/pages/labs/index.ts'),
    read('../../miniapp/pages/labs/index.wxml'),
    read('../../miniapp/app.json'),
    read('../../miniapp/pages/settings/index.wxml'),
  ]);

  assert.match(app, /pages\/labs\/index/);
  assert.match(settings, /onNavigateToLabs/);
  assert.match(controller, /adult_attested: true/);
  assert.match(controller, /consent_version:/);
  assert.match(controller, /environment-response\/recompute/);
  assert.match(controller, /environment-response\/wet-bulb/);
  assert.match(controller, /apiDelete<void>\('\/api\/labs\/environment-response'\)/);
  assert.match(template, /line-chart/);
  assert.match(template, /calculatorResult/);
});

test('web and miniapp share the strict Labs API contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const markers = [
    'interface LabsEnvironmentResponseState',
    'interface LabsEnvironmentResult',
    'interface LabsEnvironmentWetBulbResponse',
    "'historical_association_only'",
    "'stale'",
    "'stull_psychrometric'",
  ];

  for (const marker of markers) {
    const escaped = marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(webTypes, new RegExp(escaped));
    assert.match(miniTypes, new RegExp(escaped));
  }
});
