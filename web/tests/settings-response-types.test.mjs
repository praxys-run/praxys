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

function declarationBlock(source, name) {
  const start = source.search(new RegExp(`export (?:interface|type) ${name}\\b`));
  assert.notEqual(start, -1, `missing ${name}`);
  const next = source.indexOf('\nexport ', start + 1);
  return source.slice(start, next === -1 ? source.length : next).trim();
}

test('web and miniapp share strict China and legal API contracts', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const names = [
    'ChinaProcessingStatus',
    'HealthReadyResponse',
    'ClientPrivacyUpdateRequiredDetail',
    'ChinaClientUnavailableErrorDetail',
    'ChinaClientBoundaryErrorResponse',
    'TermsAcceptanceRequiredErrorDetail',
    'TermsBundleMismatchErrorDetail',
    'LegalContractErrorResponse',
  ];

  for (const name of names) {
    assert.equal(declarationBlock(webTypes, name), declarationBlock(miniTypes, name));
  }

  const clientPrivacy = declarationBlock(webTypes, 'ClientPrivacyUpdateRequiredDetail');
  assert.match(clientPrivacy, /client: 'cn-web';[\s\S]*?notice_version: string;[\s\S]*?client: 'wechat-miniapp';[\s\S]*?minimum_version: string;/);
  assert.equal((clientPrivacy.match(/minimum_version:/g) ?? []).length, 1);

  const readiness = declarationBlock(webTypes, 'HealthReadyResponse');
  assert.match(readiness, /china_processing: ChinaProcessingStatus;/);
  assert.match(readiness, /privacy_controls: 'invalid';/);
  assert.match(readiness, /database: 'error'/);

  const unavailable = declarationBlock(webTypes, 'ChinaClientUnavailableErrorDetail');
  assert.match(unavailable, /'CN_PROCESSING_DISABLED' \| 'CN_CLIENT_REGISTRY_UNAVAILABLE'/);

  const legal = declarationBlock(webTypes, 'LegalContractErrorResponse');
  assert.match(legal, /TermsAcceptanceRequiredErrorDetail/);
  assert.match(legal, /TermsBundleMismatchErrorDetail/);
});
