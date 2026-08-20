import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  ICP_FILING_NUMBER,
  MIIT_FILING_URL,
  stampChinaCompliance,
  stampHtml,
} from '../scripts/stamp-china-compliance.mjs';

test('China compliance uses the approved service filing record', () => {
  assert.equal(ICP_FILING_NUMBER, '沪ICP备2025109616号-2');
  assert.equal(MIIT_FILING_URL, 'https://beian.miit.gov.cn/');
});

test('stamping adds one linked ICP footer and is idempotent', () => {
  const source = '<!doctype html><html><body><div id="root"></div></body></html>';
  const stamped = stampHtml(source);
  const stampedAgain = stampHtml(stamped);

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
  await writeFile(path.join(root, 'index.html'), '<html><body>home</body></html>');
  await writeFile(path.join(root, 'zh', 'product', 'index.html'), '<html><body>产品</body></html>');
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
