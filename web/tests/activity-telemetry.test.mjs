import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
import { ApplicationInsights as RealApplicationInsights } from '@microsoft/applicationinsights-web';
import { matchRoutes } from 'react-router-dom';
import { redactActivityUrl } from '../src/lib/activity-telemetry.ts';

const ROUTE_PREFIXES = [
  ['/history/', '/api/history/'],
  ['/HISTORY/', '/API/HISTORY/'],
  ['/%68istory/', '/api/%68istory/'],
  ['/%48ISTory/', '/%61pi/%68istory/'],
  ['/h%69story/', '/api%2Fhistory/'],
];

test('activity URL minimization handles prefixes, encoding and both route templates', () => {
  for (const prefix of ['', 'https://example.test', 'GET ', 'POST https://example.test']) {
    for (const identifier of ['synthetic-secret', 'synthetic%20secret', 'synthetic%2Fsecret']) {
      for (const suffix of ['', '?token=synthetic-secret', '#synthetic-secret', '?token=secret#secret']) {
        assert.equal(redactActivityUrl(`${prefix}/history/${identifier}${suffix}`), `${prefix}/history/{activity_id}`);
        assert.equal(redactActivityUrl(`${prefix}/api/history/${identifier}/detail${suffix}`), `${prefix}/api/history/{activity_id}/detail`);
      }
    }
  }
  assert.equal(redactActivityUrl('/history?year=2026'), '/history?year=2026');
  assert.equal(redactActivityUrl('/api/settings?tab=source'), '/api/settings?tab=source');
  for (const path of ['synthetic-secret%2Fencoded', 'synthetic-secret encoded', 'synthetic-secret?encoded', 'synthetic-secret#encoded', 'synthetic-secret/detail/synthetic-secret']) {
    assert.equal(redactActivityUrl(`/api/history/${path}/detail?marker=secret#secret`), '/api/history/{activity_id}/detail');
  }
  assert.equal(redactActivityUrl('/api/history/synthetic-secret/detail/synthetic-secret'), '/api/history/{activity_id}/detail');
  assert.equal(redactActivityUrl('/api/history/synthetic-secret'), '/api/history/{activity_id}');
  for (const [pagePrefix, apiPrefix] of ROUTE_PREFIXES) {
    assert.ok(matchRoutes([{ path: '/history/:activityId' }], `${pagePrefix}synthetic-secret`));
    for (const prefix of ['', 'https://example.test', 'GET ']) {
      assert.equal(redactActivityUrl(`${prefix}${pagePrefix}synthetic-secret?token=private#fragment`), `${prefix}/history/{activity_id}`);
      assert.equal(redactActivityUrl(`${prefix}${apiPrefix}synthetic-secret/detail?token=private#fragment`), `${prefix}/api/history/{activity_id}/detail`);
    }
  }
  assert.equal(redactActivityUrl('/%68istory/synthetic-secret%ZZ?token=private'), '/history/{activity_id}');
  for (const value of ['/settings?label=%68ello#%20', '/%73ettings/synthetic-secret', '/%2568istory/synthetic-secret', '/%ZZistory/synthetic-secret', '/%E0%A4/historyless?token=private']) {
    assert.equal(redactActivityUrl(value), value);
  }
});

function initialize(region, acknowledged = true, configured = true, sdk = null) {
  let instance;
  class ApplicationInsights {
    constructor(options) { this.options = options; this.initializers = []; instance = this; }
    loadAppInsights() {}
    addTelemetryInitializer(initializer) { this.initializers.push(initializer); }
    trackPageView() { this.pageViews = (this.pageViews ?? 0) + 1; }
  }
  const modules = {
    '@microsoft/applicationinsights-web': { ApplicationInsights: sdk ?? ApplicationInsights },
    'web-vitals': Object.fromEntries(['onCLS', 'onFCP', 'onINP', 'onLCP', 'onTTFB'].map(name => [name, () => {}])),
    './runtime-region': { isAppInsightsAllowed: Boolean, isChinaFrontendDeployment: () => region === 'cn' },
    './china-processing': { hasAcknowledgedChinaProcessingNotice: () => acknowledged },
    './activity-telemetry': { redactActivityUrl },
  };
  const source = readFileSync(new URL('../src/lib/appinsights.ts', import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING', JSON.stringify(configured ? 'synthetic-connection' : ''));
  const code = ts.transpileModule(source, { compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
  } }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'navigator', code)(
    name => { assert.ok(name in modules, name); return modules[name]; }, module, module.exports,
    { connection: { effectiveType: '4g', rtt: 50 } },
  );
  const result = module.exports.initAppInsights();
  assert.equal(module.exports.initAppInsights(), result);
  return { result, instance };
}

for (const region of ['global', 'cn']) {
  test(`registered App Insights initializer minimizes emitted activity envelopes (${region})`, () => {
    const { instance } = initialize(region);
    assert.equal(instance.pageViews, 1);
    assert.equal(instance.options.config.disableExceptionTracking, region === 'cn');
    assert.equal(instance.options.config.enableCorsCorrelation, true);
    assert.equal(instance.options.config.disableFetchTracking, false);
    for (const [pagePrefix, apiPrefix] of ROUTE_PREFIXES) {
      for (const status of [200, 401, 404, 405, 500]) {
        for (const identifier of ['synthetic-secret', 'synthetic-secret%20encoded', 'synthetic-secret%2Fencoded']) {
          const url = `https://example.test${apiPrefix}${identifier}/detail?marker=synthetic-secret#fragment`;
          const page = `https://example.test${pagePrefix}${identifier}?marker=synthetic-secret#fragment`;
          const envelope = {
            baseType: 'RemoteDependencyData',
            baseData: {
              name: `GET ${url}`, data: url, target: url, uri: page, url: page,
              refUri: page, referrerUri: page, duration: 241, responseCode: status,
              success: status === 200, id: 'correlation-span',
              properties: { requestUrl: url, referrer: page, data: url, method: 'GET', count: 2 },
            },
            data: { sourceUrl: url }, ext: { trace: { traceID: 'correlation-trace', name: page } },
            tags: { 'ai.operation.name': page },
          };
          for (const initializer of instance.initializers) initializer(envelope);
          assert.doesNotMatch(JSON.stringify(envelope), /synthetic-secret|marker=|#fragment/);
          assert.equal(envelope.baseData.name, 'GET https://example.test/api/history/{activity_id}/detail');
          assert.equal(envelope.baseData.refUri, 'https://example.test/history/{activity_id}');
          assert.equal(envelope.baseData.duration, 241);
          assert.equal(envelope.baseData.responseCode, status);
          assert.equal(envelope.baseData.success, status === 200);
          assert.equal(envelope.baseData.id, 'correlation-span');
          assert.equal(envelope.ext.trace.traceID, 'correlation-trace');
          assert.equal(envelope.baseData.properties.netinfo_effectiveType, '4g');
          assert.equal(envelope.baseData.properties.method, 'GET');
          assert.equal(envelope.baseData.properties.count, 2);
          assert.ok(url.includes(identifier));
        }
      }
    }
    const unrelated = { baseData: { name: 'GET /api/settings?tab=source#section', properties: { requestUrl: '/settings?tab=source' } } };
    for (const initializer of instance.initializers) initializer(unrelated);
    assert.equal(unrelated.baseData.name, region === 'cn' ? 'GET /api/settings' : 'GET /api/settings?tab=source#section');
    assert.equal(unrelated.baseData.properties.requestUrl, region === 'cn' ? '/settings' : '/settings?tab=source');
  });
}

test('initialization retains China acknowledgement and unconfigured gates', () => {
  assert.equal(initialize('cn', false).result, null);
  assert.equal(initialize('global', true, false).result, null);
  assert.ok(initialize('global', false).result);
});

test('actual SDK pipeline emits sanitized page/dependency envelopes in both regions', () => {
  for (const region of ['global', 'cn']) {
    const captured = [];
    class CapturedApplicationInsights extends RealApplicationInsights {
      constructor(options) {
        super({ config: {
          ...options.config,
          connectionString: 'InstrumentationKey=00000000-0000-0000-0000-000000000001;IngestionEndpoint=http://127.0.0.1:1',
          disableCookiesUsage: true,
          channels: [[{
            identifier: 'LocalCapture', priority: 1001,
            initialize() {},
            flush(_async, callback) { callback?.(true); },
            teardown() {},
            processTelemetry(envelope) { captured.push(structuredClone(envelope)); },
          }]],
        } });
      }
    }
    const { result } = initialize(region, true, true, CapturedApplicationInsights);
    try {
      for (const [pagePrefix, apiPrefix] of ROUTE_PREFIXES) {
        captured.length = 0;
        const pagePath = `${pagePrefix}synthetic-secret?token=synthetic-secret#fragment`;
        const apiPath = `${apiPrefix}synthetic-secret/detail?token=synthetic-secret#fragment`;
        result.core.getTraceCtx().setName(pagePath);
        result.trackPageView({ name: pagePath, uri: `https://example.test${pagePath}`, refUri: `https://example.test${pagePath}` });
        result.trackDependencyData({
          id: 'synthetic-correlation.', name: `GET ${apiPath}`,
          target: 'https://example.test', data: `https://example.test${apiPath}`,
          duration: 123, responseCode: 200, success: true, type: 'Fetch',
        });
        result.core.track({
          name: 'Microsoft.ApplicationInsights.Event', baseType: 'EventData',
          baseData: { name: 'Synthetic event' },
          ext: { trace: { traceID: '1234567890abcdef1234567890abcdef', name: pagePath } },
        });
        const items = captured.filter(item => ['PageviewData', 'RemoteDependencyData'].includes(item.baseType));
        assert.ok(items.some(item => item.baseType === 'PageviewData'));
        assert.ok(items.some(item => item.baseType === 'RemoteDependencyData'));
        assert.doesNotMatch(JSON.stringify(captured), /synthetic-secret|token=/);
        const page = items.find(item => item.baseType === 'PageviewData');
        assert.equal(page.baseData.uri, 'https://example.test/history/{activity_id}');
        assert.equal(page.baseData.refUri, 'https://example.test/history/{activity_id}');
        const dependency = items.find(item => item.baseType === 'RemoteDependencyData');
        assert.equal(dependency.baseData.duration, 123);
        assert.equal(dependency.baseData.responseCode, 200);
        assert.equal(dependency.baseData.id, 'synthetic-correlation.');
        const event = captured.find(item => item.baseType === 'EventData');
        assert.equal(event.ext.trace.name, '/history/{activity_id}');
        assert.equal(event.ext.trace.traceID, '1234567890abcdef1234567890abcdef');
        assert.ok(pagePath.includes('synthetic-secret?token='));
        assert.ok(apiPath.includes('synthetic-secret/detail?token='));
      }
    } finally {
      result.unload(false);
    }
  }
});
