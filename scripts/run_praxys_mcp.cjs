#!/usr/bin/env node
"use strict";

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const configuredPython = process.env.PRAXYS_MCP_PYTHON?.trim();
const python = configuredPython
  ? path.resolve(root, configuredPython)
  : path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts" : "bin",
      process.platform === "win32" ? "python.exe" : "python",
    );

if (!fs.existsSync(python)) {
  console.error(
    `Praxys project virtualenv not found at ${python}. ` +
      "Create .venv and install the project requirements first, or set " +
      "PRAXYS_MCP_PYTHON to an absolute interpreter path.",
  );
  process.exit(1);
}

const child = spawn(
  python,
  ["-m", "scripts.run_praxys_mcp", ...process.argv.slice(2)],
  {
    cwd: root,
    env: process.env,
    stdio: "inherit",
    windowsHide: true,
  },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    try {
      child.kill(signal);
    } catch {
      process.exitCode = 1;
    }
  });
}

child.once("error", (error) => {
  console.error(`Could not start the Praxys MCP launcher: ${error.message}`);
  process.exitCode = 1;
});

child.once("exit", (code) => {
  process.exitCode = code ?? 1;
});
