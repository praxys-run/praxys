#!/usr/bin/env node
/*
 * Generate miniapp/utils/legal.ts from web/src/lib/legal.ts so the mini
 * program renders the exact same EULA / Terms + Privacy content the web app
 * shows — single-sourced on the web side, same as sync-types / sync-i18n.
 *
 * Why transpile instead of copy? web/src/lib/legal.ts builds some section
 * bodies by string-concatenating the OPERATOR_NAME / JURISDICTION /
 * SUPPORT_EMAIL consts, so we can't just lift the arrays as JSON — we have to
 * evaluate the module. It has no imports, so transpiling to CommonJS and
 * requiring the output resolves every concatenation with zero dependency
 * wiring.
 *
 * Bound to npm script `pretypecheck` so any `npm run typecheck` re-syncs.
 */

const fs = require('fs');
const path = require('path');
const Module = require('module');

let ts;
try {
  ts = require('typescript');
} catch {
  console.error(
    '[sync-legal] the "typescript" devDependency is required; run `npm ci` in miniapp/.',
  );
  process.exit(1);
}

const SRC = path.resolve(__dirname, '..', '..', 'web', 'src', 'lib', 'legal.ts');
const OUT = path.resolve(__dirname, '..', 'utils', 'legal.ts');

/**
 * Transpile web's legal.ts to CommonJS and evaluate it in a throwaway module
 * so exported consts (including the string-concatenated section bodies) come
 * back fully resolved. Safe because legal.ts imports nothing.
 */
function loadLegalModule(srcPath) {
  const source = fs.readFileSync(srcPath, 'utf8');
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2019,
    },
  }).outputText;
  const mod = new Module(srcPath, null);
  mod.filename = srcPath;
  mod.paths = Module._nodeModulePaths(path.dirname(srcPath));
  mod._compile(transpiled, srcPath);
  return mod.exports;
}

function serialize(legal) {
  const jstr = (v) => JSON.stringify(v);
  const arr = (v) => JSON.stringify(v, null, 2);
  return (
    '// AUTO-GENERATED from web/src/lib/legal.ts by miniapp/scripts/sync-legal.cjs.\n' +
    '// Do not edit by hand — change web/src/lib/legal.ts (the canonical source)\n' +
    '// and re-run `npm run sync-legal` (also runs on `npm run typecheck`).\n\n' +
    'export interface LegalText { en: string; zh: string; }\n' +
    'export interface LegalSection { id: string; title: LegalText; body: LegalText[]; }\n\n' +
    `export const TERMS_VERSION = ${jstr(legal.TERMS_VERSION)};\n` +
    `export const EFFECTIVE_DATE = ${jstr(legal.EFFECTIVE_DATE)};\n` +
    `export const SUPPORT_EMAIL = ${jstr(legal.SUPPORT_EMAIL)};\n` +
    `export const OPERATOR_NAME = ${jstr(legal.OPERATOR_NAME)};\n` +
    `export const JURISDICTION = ${jstr(legal.JURISDICTION)};\n\n` +
    `export const TERMS_SECTIONS: LegalSection[] = ${arr(legal.TERMS_SECTIONS)};\n\n` +
    `export const PRIVACY_SECTIONS: LegalSection[] = ${arr(legal.PRIVACY_SECTIONS)};\n`
  );
}

function main() {
  if (!fs.existsSync(SRC)) {
    console.error(`[sync-legal] source missing: ${SRC}`);
    process.exit(1);
  }
  const legal = loadLegalModule(SRC);
  const required = [
    'TERMS_VERSION',
    'EFFECTIVE_DATE',
    'SUPPORT_EMAIL',
    'TERMS_SECTIONS',
    'PRIVACY_SECTIONS',
  ];
  for (const key of required) {
    if (legal[key] == null) {
      console.error(`[sync-legal] web/src/lib/legal.ts is missing export: ${key}`);
      process.exit(1);
    }
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, serialize(legal), 'utf8');
  console.log(
    `[sync-legal] wrote ${OUT} ` +
      `(${legal.TERMS_SECTIONS.length} terms + ${legal.PRIVACY_SECTIONS.length} privacy sections, ` +
      `v${legal.TERMS_VERSION})`,
  );
}

main();