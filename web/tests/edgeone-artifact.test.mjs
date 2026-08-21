import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
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

test('EdgeOne artifact preparation is deterministic and self-verifying', async () => {
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

    const first = await prepareEdgeOneArtifact(directory, SOURCE_SHA);
    const firstManifest = await readFile(
      path.join(directory, 'SHA256SUMS'),
      'utf8',
    );
    const second = await prepareEdgeOneArtifact(directory, SOURCE_SHA);
    const secondManifest = await readFile(
      path.join(directory, 'SHA256SUMS'),
      'utf8',
    );

    assert.deepEqual(first, {
      fileCount: 5,
      htmlCount: 2,
      sourceSha: SOURCE_SHA,
    });
    assert.deepEqual(second, first);
    assert.equal(secondManifest, firstManifest);
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
      },
    );

    const lines = firstManifest.trim().split('\n');
    assert.deepEqual(lines, [...lines].sort((left, right) => (
      left.slice(66).localeCompare(right.slice(66))
    )));
    const assetDigest = createHash('sha256')
      .update('regional artifact\n')
      .digest('hex');
    assert.ok(lines.includes(`${assetDigest}  ./asset.txt`));

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
