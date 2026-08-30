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
const environment = {};
for (const name of [
  "PATH",
  "HOME",
  "USERPROFILE",
  "SYSTEMROOT",
  "COMSPEC",
  "PATHEXT",
  "TEMP",
  "TMP",
  "TMPDIR",
  "CI",
]) {
  if (process.env[name] !== undefined) {
    environment[name] = process.env[name];
  }
}
Object.assign(environment, {
  VITE_API_URL: "https://api.praxys.run",
  VITE_APP_VERSION: sourceSha.slice(0, 12),
  VITE_SOURCE_SHA: sourceSha,
  VITE_APPINSIGHTS_CONNECTION_STRING: "",
  VITE_STATSIG_CLIENT_KEY: "",
  VITE_STATSIG_ENV: "production",
});
// Only these fixed public build inputs cross into the EdgeOne subprocess.
// Provider credentials and unrelated host variables are never inherited.
await runWebBuild(environment);
const result = await prepareEdgeOneArtifact(
  path.join(WEB_ROOT, 'dist'),
  sourceSha,
);
console.log(
  `Built EdgeOne artifact for ${result.sourceSha}: `
  + `${result.htmlCount} HTML files.`,
);
