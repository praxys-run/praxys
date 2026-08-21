import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  prepareEdgeOneArtifact,
  resolveSourceSha,
} from './prepare-edgeone-artifact.mjs';

const WEB_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
);

function runWebBuild(environment) {
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  return new Promise((resolve, reject) => {
    const child = spawn(npmCommand, ['run', 'build'], {
      cwd: WEB_ROOT,
      env: environment,
      stdio: 'inherit',
    });
    child.on('error', reject);
    child.on('exit', (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(
        new Error(
          `EdgeOne web build failed with code ${code} and signal ${signal}.`,
        ),
      );
    });
  });
}

const sourceSha = await resolveSourceSha();
await runWebBuild({
  ...process.env,
  VITE_API_URL: 'https://api.praxys.run',
  VITE_APP_VERSION: sourceSha.slice(0, 12),
  VITE_APPINSIGHTS_CONNECTION_STRING: '',
  VITE_STATSIG_CLIENT_KEY: '',
  VITE_STATSIG_ENV: 'production',
});
const result = await prepareEdgeOneArtifact(
  path.join(WEB_ROOT, 'dist'),
  sourceSha,
);
console.log(
  `Built EdgeOne artifact for ${result.sourceSha}: `
  + `${result.htmlCount} HTML files, ${result.fileCount} manifest entries.`,
);
