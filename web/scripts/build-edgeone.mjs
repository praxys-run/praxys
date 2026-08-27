import { spawn } from 'node:child_process';
import os from 'node:os';
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

function runPrivacyFloorPreflight(environment) {
  if (!environment.CN_PRIVACY_FLOOR_SHA?.trim()) {
    throw new Error(
      "CN_PRIVACY_FLOOR_SHA must be configured as a non-secret EdgeOne "
      + "build variable after the accepted floor reaches protected main.",
    );
  }
  const pythonCommand = process.platform === "win32" ? "python.exe" : "python3";
  const configuredOutput = environment.CN_PREFLIGHT_OUTPUT?.trim();
  const evidencePath = configuredOutput
    ? (
        path.isAbsolute(configuredOutput)
          ? configuredOutput
          : path.resolve(WEB_ROOT, "..", configuredOutput)
      )
    : path.join(os.tmpdir(), "praxys-edgeone-preflight.json");
  const args = [
    path.join(WEB_ROOT, "..", "scripts", "cn_release_preflight.py"),
    "--lane",
    "china-client",
    "--require-disabled-runtime",
    "--prepare-unpublished-client",
    "--output",
    evidencePath,
  ];
  // The EdgeOne build is a credential-free artifact-preparation path. Its
  // native Git integration supplies source access; it must never receive or
  // use a GitHub API token for release evidence.
  args.push("--skip-github-evidence");
  return new Promise((resolve, reject) => {
    const child = spawn(
      pythonCommand,
      args,
      {
        cwd: path.resolve(WEB_ROOT, ".."),
        env: environment,
        stdio: "inherit",
      },
    );
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (code === 0) {
        resolve(evidencePath);
        return;
      }
      reject(
        new Error(
          "EdgeOne privacy-floor preflight failed closed with code "
          + code + " and signal " + signal + ".",
        ),
      );
    });
  });
}

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
  "CN_PRIVACY_FLOOR_SHA",
  "CN_PREFLIGHT_OUTPUT",
]) {
  if (process.env[name] !== undefined) {
    environment[name] = process.env[name];
  }
}
Object.assign(environment, {
  CN_CANDIDATE_SHA: sourceSha,
  CN_CANDIDATE_CHANNEL: "cn-web",
  PRAXYS_DISABLE_CN_PROCESSING: "true",
  VITE_API_URL: "https://api.praxys.run",
  VITE_APP_VERSION: sourceSha.slice(0, 12),
  VITE_SOURCE_SHA: sourceSha,
  VITE_APPINSIGHTS_CONNECTION_STRING: "",
  VITE_STATSIG_CLIENT_KEY: "",
  VITE_STATSIG_ENV: "production",
});
// This explicit non-secret allowlist is shared by the privacy preflight and
// web build. Provider credentials and unrelated host variables never cross
// either subprocess boundary.
const preflightEvidencePath = await runPrivacyFloorPreflight(environment);
await runWebBuild(environment);
const result = await prepareEdgeOneArtifact(
  path.join(WEB_ROOT, 'dist'),
  sourceSha,
);
console.log(
  `Built EdgeOne artifact for ${result.sourceSha}: `
  + `${result.htmlCount} HTML files, ${result.fileCount} manifest entries.`,
);
console.log(`EdgeOne unpublished-preparation evidence: ${preflightEvidencePath}`);
