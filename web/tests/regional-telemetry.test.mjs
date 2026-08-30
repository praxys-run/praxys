import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  CHINA_DEPLOYMENT_META_NAME,
  isBrowserTelemetryAllowed,
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

test('browser telemetry gate executes against the stamped HTML marker', () => {
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
    assert.equal(isBrowserTelemetryAllowed(true), false);

    setMarker(undefined);
    assert.equal(isChinaFrontendDeployment(), false);
    assert.equal(isBrowserTelemetryAllowed(true), true);
    assert.equal(isBrowserTelemetryAllowed(false), false);
  } finally {
    if (originalDocument) {
      Object.defineProperty(globalThis, 'document', originalDocument);
    } else {
      delete globalThis.document;
    }
  }
});

test('browser telemetry providers honor the stamped China deployment marker', async () => {
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
    /isBrowserTelemetryAllowed\(Boolean\(CONNECTION_STRING\)\)/,
  );
  assert.match(statsig, /isBrowserTelemetryAllowed\(Boolean\(CLIENT_KEY\)\)/);
});
