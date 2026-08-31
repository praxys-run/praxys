import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  CHINA_DEPLOYMENT_META_NAME,
  isAppInsightsAllowed,
  isStatsigBrowserAllowed,
  isChinaFrontendDeployment,
  isChinaDeploymentRegion,
} from '../src/lib/runtime-region.ts';

test('China deployment marker is explicit and fail-closed', () => {
  assert.equal(CHINA_DEPLOYMENT_META_NAME, 'praxys-deployment-region');
  assert.equal(isChinaDeploymentRegion('cn'), true);
  assert.equal(isChinaDeploymentRegion(' CN '), true);
  assert.equal(isChinaDeploymentRegion('global'), false);
  assert.equal(isChinaDeploymentRegion(undefined), false);
});

test('regional browser-provider gates keep App Insights and block Statsig', () => {
  const originalDocument = Object.getOwnPropertyDescriptor(
    globalThis,
    'document',
  );
  const setMarker = (content) => {
    Object.defineProperty(globalThis, 'document', {
      configurable: true,
      value: {
        querySelector(selector) {
          assert.equal(
            selector,
            'meta[name="praxys-deployment-region"]',
          );
          return content === undefined ? null : { content };
        },
      },
    });
  };

  try {
    setMarker('cn');
    assert.equal(isChinaFrontendDeployment(), true);
    assert.equal(isAppInsightsAllowed(true), true);
    assert.equal(isStatsigBrowserAllowed(true), false);

    setMarker(undefined);
    assert.equal(isChinaFrontendDeployment(), false);
    assert.equal(isAppInsightsAllowed(false), false);
    assert.equal(isStatsigBrowserAllowed(true), true);
    assert.equal(isStatsigBrowserAllowed(false), false);
  } finally {
    if (originalDocument) {
      Object.defineProperty(globalThis, 'document', originalDocument);
    } else {
      delete globalThis.document;
    }
  }
});

test('browser telemetry providers apply their distinct regional boundaries', async () => {
  const appInsights = await readFile(
    new URL('../src/lib/appinsights.ts', import.meta.url),
    'utf8',
  );
  const statsig = await readFile(
    new URL('../src/contexts/StatsigContext.tsx', import.meta.url),
    'utf8',
  );

  assert.match(
    appInsights,
    /isAppInsightsAllowed\(Boolean\(CONNECTION_STRING\)\)/,
  );
  const edgeOneBuild = await readFile(
    new URL('../scripts/build-edgeone.mjs', import.meta.url),
    'utf8',
  );
  const productEvents = await readFile(
    new URL('../src/lib/product-events.ts', import.meta.url),
    'utf8',
  );
  const main = await readFile(
    new URL('../src/main.tsx', import.meta.url),
    'utf8',
  );
  assert.match(statsig, /isStatsigBrowserAllowed\(Boolean\(CLIENT_KEY\)\)/);
  assert.match(
    edgeOneBuild,
    /VITE_APPINSIGHTS_CONNECTION_STRING: regionalAppInsights/,
  );
  assert.match(edgeOneBuild, /EdgeOne requires VITE_APPINSIGHTS_CONNECTION_STRING/);
  assert.match(edgeOneBuild, /VITE_STATSIG_CLIENT_KEY: ""/);
  assert.doesNotMatch(productEvents, /isChinaFrontendDeployment/);
  assert.match(appInsights, /hasAcknowledgedChinaProcessingNotice\(\)/);
  assert.match(main, /CHINA_PROCESSING_NOTICE_ACKNOWLEDGED_EVENT/);
});

test('regional App Insights sanitizes URLs and suppresses exception capture', async () => {
  const appInsights = await readFile(
    new URL('../src/lib/appinsights.ts', import.meta.url),
    'utf8',
  );
  assert.match(appInsights, /disableExceptionTracking: chinaDeployment/);
  assert.match(appInsights, /sanitizeRegionalTelemetry/);
  assert.ok(appInsights.includes('replace(/[?#].*$/'));
});
