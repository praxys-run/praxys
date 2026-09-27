/** Format the four synthetic native fixtures for the Windows .cmd boundary. */
import { createHash } from 'node:crypto';
import { lstatSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Script } from 'node:vm';
import ts from 'typescript';

const scriptPath = fileURLToPath(import.meta.url);
const fixtureDirectory = resolve(dirname(scriptPath), '../../tests/fixtures/dfa');
export const FIXTURE_NAMES = Object.freeze([
  'native-request-mock.js', 'native-storage-mock.js',
  'native-setup.js', 'native-component-action.js',
]);
const MAX_BYTES = 64 * 1024;
const lineBreak = /[\r\n\u2028\u2029]/u;

function parse(source) {
  const file = ts.createSourceFile('fixture.js', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const fn = file.statements[0];
  if (file.parseDiagnostics.length || file.statements.length !== 1 ||
      !ts.isFunctionDeclaration(fn) || !fn.name || !fn.body || fn.asteriskToken || fn.modifiers?.length) {
    throw new Error('Expected one named ordinary JavaScript function declaration.');
  }
  // Parsing only: no fixture or supplied function is executed here.
  new Script(`(${source}\n)`);
  return file;
}

function literalRanges(file) {
  const ranges = [];
  const visit = node => {
    if (ts.isStringLiteralLike(node) || ts.isRegularExpressionLiteral(node) || ts.isTemplateExpression(node)) {
      const start = node.getStart(file), end = node.getEnd();
      if (lineBreak.test(file.text.slice(start, end))) {
        throw new Error('Physical line breaks inside literals/templates are unsupported; source was not changed.');
      }
      ranges.push([start, end]);
      return;
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return ranges.sort((a, b) => a[0] - b[0]);
}

function structure(node) {
  const children = [];
  ts.forEachChild(node, child => { children.push(structure(child)); });
  const text = ts.isIdentifier(node) || ts.isPrivateIdentifier(node) || ts.isLiteralExpression(node) ||
    ts.isTemplateLiteralToken(node) ? node.text : null;
  const declarationFlags = ts.isVariableDeclarationList(node) ?
    node.flags & (ts.NodeFlags.Let | ts.NodeFlags.Const | ts.NodeFlags.Using | ts.NodeFlags.AwaitUsing) : 0;
  return [node.kind, text, node.rawText ?? null, declarationFlags, children];
}

export function normalizeFixtureSource(source) {
  if (typeof source !== 'string' || Buffer.byteLength(source) > MAX_BYTES || source.includes('\0')) {
    throw new Error('Fixture source must be a NUL-free string no larger than 64 KiB.');
  }
  const original = parse(source);
  literalRanges(original);
  const printed = ts.createPrinter({ removeComments: true, newLine: ts.NewLineKind.LineFeed }).printFile(original);
  const formatted = parse(printed);
  const ranges = literalRanges(formatted);
  const parts = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    parts.push(printed.slice(cursor, start).replace(/\s+/gu, ' '), printed.slice(start, end));
    cursor = end;
  }
  parts.push(printed.slice(cursor).replace(/\s+/gu, ' '));
  const result = parts.join('').trim();
  if (lineBreak.test(result) || Buffer.byteLength(result) > MAX_BYTES ||
      JSON.stringify(structure(original)) !== JSON.stringify(structure(parse(result)))) {
    throw new Error('Normalization changed parsed structure or exceeded the single-line source bounds.');
  }
  return result;
}

function resolveExistingAncestors(path) {
  if (lstatSync(path, { throwIfNoEntry: false })) return realpathSync(path);
  const parent = dirname(path);
  if (parent === path) throw new Error('Cannot resolve generated output directory.');
  return resolve(resolveExistingAncestors(parent), basename(path));
}

export function prepareFixtures(outputDirectory) {
  const target = resolveExistingAncestors(resolve(outputDirectory));
  const sourceDirectory = realpathSync(fixtureDirectory);
  if (target === sourceDirectory || target.startsWith(sourceDirectory + sep)) {
    throw new Error('Generated output must not overwrite or enter fixture sources.');
  }
  const prepared = FIXTURE_NAMES.map(name => {
    const path = resolve(fixtureDirectory, name);
    const source = readFileSync(path, 'utf8');
    return { name, source, sourceStat: statSync(path, { bigint: true }), normalized: normalizeFixtureSource(source) };
  });
  mkdirSync(target, { recursive: true });
  // Check every destination before writing any payload, including hard links to
  // any source fixture. Never follow a generated-file symlink, even to a safe path.
  for (const { name } of prepared) {
    const entry = lstatSync(resolve(target, name), { bigint: true, throwIfNoEntry: false });
    if (entry && (!entry.isFile() || prepared.some(({ sourceStat }) =>
      entry.dev === sourceStat.dev && entry.ino === sourceStat.ino))) {
      throw new Error('Generated destination is not a regular file or aliases fixture sources.');
    }
  }
  const staging = mkdtempSync(resolve(target, '.dfa-native-'));
  try {
    for (const { name, normalized } of prepared) {
      writeFileSync(resolve(staging, name), normalized); // No trailing newline.
    }
    // Replace directory entries instead of writing through an existing file alias.
    for (const { name } of prepared) renameSync(resolve(staging, name), resolve(target, name));
    return prepared.map(({ name, source, normalized }) => ({
      name, path: resolve(target, name), bytes: Buffer.byteLength(normalized),
      source_sha256: createHash('sha256').update(source).digest('hex'),
      generated_sha256: createHash('sha256').update(normalized).digest('hex'),
    }));
  } finally { rmSync(staging, { recursive: true, force: true }); }
}

if (process.argv[1] && resolve(process.argv[1]) === scriptPath) {
  const args = process.argv.slice(2);
  if (args.length !== 2 || args[0] !== '--output-dir' || !args[1]) {
    throw new Error('Usage: node web/scripts/prepare-dfa-native-fixtures.mjs --output-dir /tmp/dfa-native-sources');
  }
  process.stdout.write(JSON.stringify(prepareFixtures(args[1]), null, 2) + '\n');
}
