import assert from 'node:assert/strict';
import {
  mkdtemp,
  mkdir,
  readFile,
  rm,
  writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { prepareEdgeOneArtifact } from '../scripts/prepare-edgeone-artifact.mjs';
import { rewrittenPath } from '../scripts/check-edgeone-routing.mjs';

const SOURCE_SHA = '0123456789abcdef0123456789abcdef01234567';

test('EdgeOne serves nested and encoded activity history links from the app shell', async () => {
  const { rewrites } = JSON.parse(await readFile(new URL('../edgeone.json', import.meta.url), 'utf8'));
  for (const request of [
    '/history/synthetic-id',
    '/history/synthetic-id/',
    '/history/synthetic-id/nested',
    '/history/synthetic%2Fid?metric=power%20watts&next=%2Fhistory%2Fother',
    '/history/%E6%B5%8B%E8%AF%95?metric=hr#cursor-10',
    '/history/synthetic%3Fid%23part?metric=pace',
  ]) {
    const { pathname } = new URL(request, 'https://praxys.cn');
    assert.equal(rewrittenPath(pathname, rewrites), '/app-shell.html', request);
  }
});

test('EdgeOne history fallback preserves static resources and API routes', async () => {
  const { rewrites } = JSON.parse(await readFile(new URL('../edgeone.json', import.meta.url), 'utf8'));
  for (const request of [
    '/assets/client/app.js?v=synthetic',
    '/assets/client/app.css?v=synthetic',
    '/assets/client/data.woff2',
    '/fonts/display.woff2',
    '/sw.js?version=synthetic',
    '/healthz',
    '/deployed_sha.txt',
    '/api',
    '/api/history/synthetic-id/detail?metric=hr',
    '/api/history',
    '/api/status',
    '/historyish/synthetic-id',
    '/history.json',
  ]) {
    const { pathname } = new URL(request, 'https://praxys.cn');
    assert.equal(rewrittenPath(pathname, rewrites), pathname, request);
  }
});

test('EdgeOne artifact preparation stamps health and ICP metadata', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'praxys-edgeone-'));
  try {
    await mkdir(path.join(directory, 'today'));
    await writeFile(
      path.join(directory, 'index.html'),
      '<html><head></head><body><div id="root"></div></body></html>',
    );
    await writeFile(
      path.join(directory, 'today', 'index.html'),
      '<html><head></head><body><div id="root"></div></body></html>',
    );
    await writeFile(path.join(directory, 'asset.txt'), 'regional artifact\n');

    const result = await prepareEdgeOneArtifact(directory, SOURCE_SHA);

    assert.deepEqual(result, {
      htmlCount: 2,
      sourceSha: SOURCE_SHA,
    });
    assert.equal(
      await readFile(path.join(directory, 'deployed_sha.txt'), 'utf8'),
      `${SOURCE_SHA}\n`,
    );
    assert.deepEqual(
      JSON.parse(await readFile(path.join(directory, 'healthz'), 'utf8')),
      {
        ok: true,
        service: 'praxys-frontend-cn',
        deployed_sha: SOURCE_SHA,
        notice_version: '2026.09.1',
        legal_digest:
          'sha256:0fc1448a81e97b5ea0d1fdc9ed831b72d49e0dfae851ff731cfdbe12a8b11805',
        api_contract_version: 'cn-privacy-v2',
      },
    );

    for (const relativePath of ['index.html', 'today/index.html']) {
      const html = await readFile(path.join(directory, relativePath), 'utf8');
      assert.equal(
        html.match(/data-praxys-cn-compliance="icp"/g)?.length,
        1,
      );
      assert.equal(
        html.match(/name="praxys-deployment-region" content="cn"/g)?.length,
        1,
      );
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});


test('EdgeOne artifact rejects non-canonical source SHAs', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'praxys-edgeone-sha-'));
  try {
    await writeFile(
      path.join(directory, 'index.html'),
      '<html><head></head><body><div id="root"></div></body></html>',
    );
    for (const invalid of [SOURCE_SHA.toUpperCase(), SOURCE_SHA.slice(0, 12)]) {
      await assert.rejects(
        prepareEdgeOneArtifact(directory, invalid),
        /Invalid source commit SHA/,
      );
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
test('regional preparation rejects a prerendered global English home', async (t) => {
  const directory = await mkdtemp(path.join(tmpdir(), 'praxys-wrong-region-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  await writeFile(path.join(directory, 'index.html'), '<div id="root" data-praxys-public-page="home" data-praxys-public-locale="en">English</div>');
  await assert.rejects(prepareEdgeOneArtifact(directory, 'a'.repeat(40)), /regional public-page build/);
});
