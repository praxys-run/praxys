import assert from 'node:assert/strict';
import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  CHINA_DEPLOYMENT_REGION,
  ICP_FILING_NUMBER,
  MIIT_FILING_URL,
  PUBLIC_SECURITY_FILING_NUMBER,
  PUBLIC_SECURITY_FILING_URL,
  PUBLIC_SECURITY_ICON_PATH,
  stampChinaCompliance,
  stampHtml,
} from '../scripts/stamp-china-compliance.mjs';
import { isChinaFilingPublicPath } from '../src/lib/china-compliance.ts';

test('China compliance uses the approved service filing record', () => {
  assert.equal(ICP_FILING_NUMBER, '沪ICP备2025109616号-2');
  assert.equal(MIIT_FILING_URL, 'https://beian.miit.gov.cn/');
  assert.equal(CHINA_DEPLOYMENT_REGION, 'cn');
  assert.equal(PUBLIC_SECURITY_FILING_NUMBER, '沪公网安备31011802006255号');
  assert.equal(PUBLIC_SECURITY_FILING_URL, 'https://beian.mps.gov.cn/#/query/webSearch?code=31011802006255');
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
  assert.match(stamped, /<img [^>]+alt="" \/>沪公网安备31011802006255号<\/a>/);
  assert.equal(stamped.match(/沪公网安备31011802006255号/g)?.length, 1);
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
  assert.deepEqual(
    await readFile(path.join(root, PUBLIC_SECURITY_ICON_PATH.slice(1))),
    await readFile(new URL('../scripts/assets/public-security-filing.png', import.meta.url)),
  );
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
  assert.doesNotMatch(azureHtml, /praxys-deployment-region|公网安备|beian.mps/);
  await assert.rejects(readFile(path.join(azureRoot, PUBLIC_SECURITY_ICON_PATH.slice(1))), { code: 'ENOENT' });
  assert.match(edgeOneHtml, /沪ICP备2025109616号-2/);
  assert.match(edgeOneHtml, /praxys-deployment-region/);
});

test('filing visibility follows public routes, including trailing slashes', () => {
  for (const route of ['/', '/zh', '/zh/', '/product', '/faq', '/zh/product', '/zh/faq', '/login', '/terms', '/privacy', '/status', '/verify']) {
    assert.equal(isChinaFilingPublicPath(route), true, route);
  }
  for (const route of ['/today', '/training', '/settings/', '/analysis', '/admin/users', '/mcp/authorize', '/unknown', '/zh/settings']) {
    assert.equal(isChinaFilingPublicPath(route), false, route);
  }
});
