import { execFile } from 'node:child_process';
import {
  writeFile,
} from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { stampChinaCompliance } from './stamp-china-compliance.mjs';

const execFileAsync = promisify(execFile);
const SCRIPT_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const REPOSITORY_ROOT = path.resolve(SCRIPT_DIRECTORY, '..', '..');
const CN_NOTICE_VERSION = '2026.08.4';
const CN_LEGAL_DIGEST =
  'sha256:ce863ba3531157c50775509c8a8061654d24868cafe0b7f22ede02ca60c65aa1';
const CN_API_CONTRACT_VERSION = 'cn-privacy-v2';

export async function resolveSourceSha() {
  const { stdout } = await execFileAsync(
    'git',
    ['-C', REPOSITORY_ROOT, 'rev-parse', 'HEAD'],
    { encoding: 'utf8' },
  );
  return stdout.trim();
}

function validateSourceSha(sourceSha) {
  if (!/^[0-9a-f]{40}$/.test(sourceSha)) {
    throw new Error(`Invalid source commit SHA: ${sourceSha}`);
  }
  return sourceSha;
}

export async function prepareEdgeOneArtifact(directory, requestedSha) {
  const target = path.resolve(directory);
  const sourceSha = validateSourceSha(
    requestedSha ?? await resolveSourceSha(),
  );
  const stampedFiles = await stampChinaCompliance(target);

  await writeFile(
    path.join(target, 'deployed_sha.txt'),
    `${sourceSha}\n`,
    'utf8',
  );
  await writeFile(
    path.join(target, 'healthz'),
    `${JSON.stringify({
      ok: true,
      service: 'praxys-frontend-cn',
      deployed_sha: sourceSha,
      notice_version: CN_NOTICE_VERSION,
      legal_digest: CN_LEGAL_DIGEST,
      api_contract_version: CN_API_CONTRACT_VERSION,
    })}\n`,
    'utf8',
  );

  return {
    htmlCount: stampedFiles.length,
    sourceSha,
  };
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : '';
if (invokedPath === fileURLToPath(import.meta.url)) {
  const target = process.argv[2];
  if (!target) {
    throw new Error(
      'Usage: node scripts/prepare-edgeone-artifact.mjs '
      + '<dist-directory> [--sha <commit-sha>]',
    );
  }
  const shaFlag = process.argv.indexOf('--sha');
  const requestedSha = shaFlag >= 0 ? process.argv[shaFlag + 1] : undefined;
  if (shaFlag >= 0 && !requestedSha) {
    throw new Error('--sha requires a commit SHA.');
  }
  const result = await prepareEdgeOneArtifact(target, requestedSha);
  console.log(
    `Prepared EdgeOne artifact for ${result.sourceSha}: `
    + `${result.htmlCount} HTML files.`,
  );
}
