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

const SOURCE_SHA = '0123456789abcdef0123456789abcdef01234567';

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
