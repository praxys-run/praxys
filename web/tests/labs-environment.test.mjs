import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { QueryClient } from '@tanstack/react-query';

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
  assert.doesNotMatch(catalog, /environment-response\/preflight/);
  assert.match(catalog, /Open to check/);
  assert.match(page, /adult_attested: adultAttested/);
  assert.match(page, /consent_version: state\.consent_version/);
  assert.match(page, /environment-response\/preflight/);
  assert.match(page, /timeoutMs: 15000/);
  assert.doesNotMatch(page, /refetchOnMount: 'always', timeoutMs: 15000/);
  assert.match(page, /adult_eligibility_not_confirmed/);
  assert.match(page, /consent_version_stale/);
  assert.match(page, /onRetryPreflight/);
  assert.match(page, /Checking data requirements/);
  assert.match(page, /before showing enrollment consent or starting analysis/);
  assert.match(page, /!preflightLoading && !preflightError && preflight/);
  assert.match(page, /Enough source data to attempt the experiment/);
  assert.match(page, /historical_association_only/);
  assert.match(page, /Historical association; not predictively validated/);
  assert.match(page, /one="# activity"/);
  assert.match(page, /environment-response\/wet-bulb/);
  assert.match(page, /Withdraw and delete result/);
  assert.match(page, /ScienceNote/);
  assert.match(main, /vite:preloadError/);
  assert.match(main, /PRELOAD_RELOAD_WINDOW_MS/);
  assert.doesNotMatch(
    main,
    /addEventListener\('load', \(\) => \{\s*sessionStorage\.removeItem/,
  );
  assert.match(app, /RouteChunkSkeleton/);
  assert.match(app, /LabsRouteBoundary/);
  assert.match(app, /Reload Labs/);
});

test('Labs chart keeps calculator markers inside the displayed bin domain', async () => {
  const {
    getMarkerLabelPosition,
    getWetBulbChartDomain,
    getWetBulbPointDomain,
  } = await import('../src/lib/labs-environment-chart.ts');
  const domain = getWetBulbChartDomain([
    { lower_wet_bulb_c: 5.7, upper_wet_bulb_c: 9.9 },
    { lower_wet_bulb_c: 22.7, upper_wet_bulb_c: 26.9 },
  ]);

  assert.deepEqual(domain, [5.7, 26.9]);
  assert.deepEqual(
    getWetBulbPointDomain([{ wet_bulb_c: 7.8 }, { wet_bulb_c: 24.8 }]),
    [7.8, 24.8],
  );
  assert.equal(getMarkerLabelPosition(25.8, domain), 'insideTopRight');
  assert.equal(getMarkerLabelPosition(8.0, domain), 'insideTopLeft');
});

test('a timed-out Labs preflight aborts once and leaves its query in error', async () => {
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  let requests = 0;
  let aborts = 0;

  globalThis.window = {
    setTimeout,
    clearTimeout,
    location: { origin: 'https://praxys.test' },
  };
  globalThis.fetch = (_url, { signal }) => new Promise((_resolve, reject) => {
    requests += 1;
    signal.addEventListener('abort', () => {
      aborts += 1;
      reject(new DOMException('Aborted', 'AbortError'));
    }, { once: true });
  });

  try {
    const {
      ApiTimeoutError,
      fetchWithTimeout,
      shouldRetryApiRequest,
    } = await import('../src/lib/request-timeout.ts');
    const queryClient = new QueryClient();
    const queryKey = ['labs-preflight-timeout'];

    await assert.rejects(
      () => queryClient.fetchQuery({
        queryKey,
        queryFn: () => fetchWithTimeout(
          (signal) => fetch('/api/labs/environment-response/preflight', { signal }),
          undefined,
          1,
        ),
        retry: shouldRetryApiRequest,
      }),
      ApiTimeoutError,
    );

    assert.equal(requests, 1);
    assert.equal(aborts, 1);
    assert.equal(queryClient.getQueryState(queryKey)?.status, 'error');
  } finally {
    globalThis.window = originalWindow;
    globalThis.fetch = originalFetch;
  }
});

test('stale Labs chunks reload once instead of looping', async () => {
  const {
    PRELOAD_RELOAD_WINDOW_MS,
    isActivePreloadReload,
    parsePreloadReloadMarker,
  } = await import('../src/lib/preload-recovery.ts');
  const attemptedAt = 1_000;
  const marker = parsePreloadReloadMarker(JSON.stringify({
    pathname: '/labs/environment-response',
    attemptedAt,
  }));

  assert.equal(
    isActivePreloadReload(
      marker,
      '/labs/environment-response',
      attemptedAt + 1,
    ),
    true,
  );
  assert.equal(
    isActivePreloadReload(
      marker,
      '/labs/environment-response',
      attemptedAt + PRELOAD_RELOAD_WINDOW_MS,
    ),
    false,
  );
  assert.equal(
    isActivePreloadReload(marker, '/labs', attemptedAt + 1),
    false,
  );
  assert.equal(parsePreloadReloadMarker('not-json'), null);
});

test('miniapp Labs preserves the web experiment lifecycle', async () => {
  const [catalog, controller, template, app, me] = await Promise.all([
    read('../../miniapp/pages/labs/index.ts'),
    read('../../miniapp/pages/labs/environment-response/index.ts'),
    read('../../miniapp/pages/labs/environment-response/index.wxml'),
    read('../../miniapp/app.json'),
    read('../../miniapp/pages/me/index.wxml'),
  ]);

  assert.match(app, /pages\/labs\/index/);
  assert.match(app, /pages\/labs\/environment-response\/index/);
  assert.match(me, /onOpenLabs/);
  assert.match(catalog, /pages\/labs\/environment-response\/index/);
  assert.doesNotMatch(catalog, /environment-response\/preflight/);
  assert.match(catalog, /Open to check/);
  assert.match(controller, /adult_attested: true/);
  assert.match(controller, /consent_version:/);
  assert.match(controller, /environment-response\/preflight/);
  assert.match(controller, /adult_eligibility_not_confirmed/);
  assert.match(controller, /consent_version_stale/);
  assert.match(controller, /environment-response\/recompute/);
  assert.match(controller, /environment-response\/wet-bulb/);
  assert.match(controller, /provider_alignment_requires_full_analysis/);
  assert.match(controller, /PREFLIGHT_REQUEST_TIMEOUT_MS = 15000/);
  assert.match(controller, /preflightLoading: true/);
  assert.match(template, /preflightChecking/);
  assert.match(template, /preflightError/);
  assert.match(controller, /recompute\.retry_after_seconds/);
  assert.match(controller, /activityUnit: bin\.reference_power_activity_count === 1/);
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
    "'adult_eligibility_not_confirmed'",
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
