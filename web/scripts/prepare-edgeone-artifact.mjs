import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
  readFile,
  readdir,
  rm,
  writeFile,
} from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { stampChinaCompliance } from './stamp-china-compliance.mjs';

const execFileAsync = promisify(execFile);
const SCRIPT_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const REPOSITORY_ROOT = path.resolve(SCRIPT_DIRECTORY, '..', '..');

async function findArtifactFiles(directory, root = directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return findArtifactFiles(entryPath, root);
    if (!entry.isFile() || entry.name === 'SHA256SUMS') return [];
    return [path.relative(root, entryPath).split(path.sep).join('/')];
  }));
  return nested.flat().sort();
}

export async function resolveSourceSha() {
  const { stdout } = await execFileAsync(
    'git',
    ['-C', REPOSITORY_ROOT, 'rev-parse', 'HEAD'],
    { encoding: 'utf8' },
  );
  return stdout.trim();
}

function validateSourceSha(sourceSha) {
  const normalized = sourceSha.trim().toLowerCase();
  if (!/^[0-9a-f]{40,64}$/.test(normalized)) {
    throw new Error(`Invalid source commit SHA: ${sourceSha}`);
  }
  return normalized;
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
    })}\n`,
    'utf8',
  );

  const manifestPath = path.join(target, 'SHA256SUMS');
  await rm(manifestPath, { force: true });
  const files = await findArtifactFiles(target);
  const manifestLines = await Promise.all(files.map(async (relativePath) => {
    const contents = await readFile(path.join(target, relativePath));
    const digest = createHash('sha256').update(contents).digest('hex');
    return `${digest}  ./${relativePath}`;
  }));
  await writeFile(manifestPath, `${manifestLines.join('\n')}\n`, 'utf8');

  return {
    fileCount: files.length,
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
    + `${result.htmlCount} HTML files, ${result.fileCount} manifest entries.`,
  );
}
