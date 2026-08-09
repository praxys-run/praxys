import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web Labs covers consent, result, calculator, and withdrawal states', async () => {
  const [catalog, page, app, sidebar, main] = await Promise.all([
    read('../src/pages/Labs.tsx'),
    read('../src/pages/LabsEnvironment.tsx'),
    read('../src/App.tsx'),
    read('../src/components/AppSidebar.tsx'),
    read('../src/main.tsx'),
  ]);

  assert.match(app, /path="labs"/);
  assert.match(app, /path="labs\/environment-response"/);
  assert.match(sidebar, /to: '\/labs'/);
  assert.match(sidebar, /to: '\/science', icon: BookOpen/);
  assert.match(sidebar, /to: '\/labs', icon: FlaskConical/);
  assert.match(catalog, /Available experiments/);
  assert.match(catalog, /to="\/labs\/environment-response"/);
  assert.match(catalog, /environment-response\/preflight/);
  assert.match(catalog, /Needs data/);
  assert.match(catalog, /Check required/);
  assert.match(page, /adult_attested: adultAttested/);
  assert.match(page, /consent_version: state\.consent_version/);
  assert.match(page, /environment-response\/preflight/);
  assert.match(page, /consent_version_stale/);
  assert.match(page, /Enough source data to attempt the experiment/);
  assert.match(page, /historical_association_only/);
  assert.match(page, /Historical association; not predictively validated/);
  assert.match(page, /environment-response\/wet-bulb/);
  assert.match(page, /Withdraw and delete result/);
  assert.match(page, /ScienceNote/);
  assert.match(main, /vite:preloadError/);
  assert.match(app, /RouteChunkSkeleton/);
});

test('miniapp Labs preserves the web experiment lifecycle', async () => {
  const [catalog, controller, template, app, settings] = await Promise.all([
    read('../../miniapp/pages/labs/index.ts'),
    read('../../miniapp/pages/labs/environment-response/index.ts'),
    read('../../miniapp/pages/labs/environment-response/index.wxml'),
    read('../../miniapp/app.json'),
    read('../../miniapp/pages/settings/index.wxml'),
  ]);

  assert.match(app, /pages\/labs\/index/);
  assert.match(app, /pages\/labs\/environment-response\/index/);
  assert.match(settings, /onNavigateToLabs/);
  assert.match(catalog, /pages\/labs\/environment-response\/index/);
  assert.match(catalog, /environment-response\/preflight/);
  assert.match(catalog, /Needs data/);
  assert.match(catalog, /Check required/);
  assert.match(controller, /adult_attested: true/);
  assert.match(controller, /consent_version:/);
  assert.match(controller, /environment-response\/preflight/);
  assert.match(controller, /consent_version_stale/);
  assert.match(controller, /environment-response\/recompute/);
  assert.match(controller, /environment-response\/wet-bulb/);
  assert.match(controller, /provider_alignment_requires_full_analysis/);
  assert.match(controller, /recompute\.retry_after_seconds/);
  assert.match(controller, /retryDelayMs/);
  assert.match(controller, /\['queued', 'dispatched', 'processing', 'retrying'\]/);
  assert.match(controller, /LABS_ENVIRONMENT_NOT_ENROLLED/);
  assert.match(controller, /resetConsentControls/);
  assert.match(controller, /previousState\.consent_version !== state\.consent_version/);
  assert.match(controller, /adultAttested: false/);
  assert.match(controller, /consentConfirmed: false/);
  assert.match(controller, /apiDelete<void>\('\/api\/labs\/environment-response'\)/);
  assert.match(template, /line-chart/);
  assert.match(template, /calculatorResult/);
  assert.match(template, /preflightUncertain/);
});

test('web and miniapp share the strict Labs API contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const markers = [
    'interface LabsEnvironmentResponseState',
    'interface LabsEnvironmentPreflightResponse',
    'type LabsEnvironmentMutationError',
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
