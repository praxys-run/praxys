import assert from 'node:assert/strict';
import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  CHINA_DEPLOYMENT_REGION,
  ICP_FILING_NUMBER,
  MIIT_FILING_URL,
  stampChinaCompliance,
  stampHtml,
} from '../scripts/stamp-china-compliance.mjs';

test('China compliance uses the approved service filing record', () => {
  assert.equal(ICP_FILING_NUMBER, '沪ICP备2025109616号-2');
  assert.equal(MIIT_FILING_URL, 'https://beian.miit.gov.cn/');
  assert.equal(CHINA_DEPLOYMENT_REGION, 'cn');
});

test('stamping adds one linked ICP footer and is idempotent', () => {
  const source = '<!doctype html><html><head></head><body><div id="root"></div></body></html>';
  const stamped = stampHtml(source);
  const stampedAgain = stampHtml(stamped);

  assert.match(
    stamped,
    /<meta name="praxys-deployment-region" content="cn" \/>/,
  );
  assert.match(stamped, /data-praxys-cn-compliance="icp"/);
  assert.match(stamped, /href="https:\/\/beian\.miit\.gov\.cn\/"/);
  assert.match(stamped, /沪ICP备2025109616号-2/);
  assert.equal(stampedAgain, stamped);
  assert.equal(stamped.match(/data-praxys-cn-compliance="icp"/g)?.length, 1);
});

test('stamping covers route documents without changing capture templates or assets', async (t) => {
  const root = await mkdtemp(path.join(tmpdir(), 'praxys-cn-compliance-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(path.join(root, 'zh', 'product'), { recursive: true });
  await writeFile(path.join(root, 'index.html'), '<html><head></head><body>home</body></html>');
  await writeFile(path.join(root, 'zh', 'product', 'index.html'), '<html><head></head><body>产品</body></html>');
  await writeFile(path.join(root, 'og-card.html'), '<html><body>capture</body></html>');
  await writeFile(path.join(root, 'asset.txt'), 'unchanged');

  const stampedFiles = await stampChinaCompliance(root);

  assert.equal(stampedFiles.length, 2);
  for (const htmlPath of stampedFiles) {
    assert.match(await readFile(htmlPath, 'utf8'), /沪ICP备2025109616号-2/);
  }
  assert.doesNotMatch(
    await readFile(path.join(root, 'og-card.html'), 'utf8'),
    /沪ICP备2025109616号-2/,
  );
  assert.equal(await readFile(path.join(root, 'asset.txt'), 'utf8'), 'unchanged');
});

test('China artifact stamping never mutates the Azure source tree', async (t) => {
  const root = await mkdtemp(path.join(tmpdir(), 'praxys-regional-artifacts-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const azureRoot = path.join(root, 'azure');
  const edgeOneRoot = path.join(root, 'edgeone');
  await mkdir(azureRoot, { recursive: true });
  await writeFile(
    path.join(azureRoot, 'index.html'),
    '<html><head></head><body>shared build</body></html>',
  );
  await cp(azureRoot, edgeOneRoot, { recursive: true });

  await stampChinaCompliance(edgeOneRoot);

  const azureHtml = await readFile(path.join(azureRoot, 'index.html'), 'utf8');
  const edgeOneHtml = await readFile(path.join(edgeOneRoot, 'index.html'), 'utf8');
  assert.doesNotMatch(azureHtml, /沪ICP备2025109616号-2/);
  assert.doesNotMatch(azureHtml, /praxys-deployment-region/);
  assert.match(edgeOneHtml, /沪ICP备2025109616号-2/);
  assert.match(edgeOneHtml, /praxys-deployment-region/);
});
