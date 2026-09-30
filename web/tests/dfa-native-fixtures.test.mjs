import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, linkSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { FIXTURE_NAMES, normalizeFixtureSource } from '../scripts/prepare-dfa-native-fixtures.mjs';

const source = name => readFileSync(new URL('../../tests/fixtures/dfa/' + name, import.meta.url), 'utf8');
const FixedDate = class extends Date {
  constructor(...args) { super(...(args.length ? args : [Date.UTC(2026, 8, 27)])); }
};
function runtime(normalized, pages = []) {
  const app = { globalData: {} };
  const functions = Object.fromEntries(FIXTURE_NAMES.map(name => {
    const text = normalized ? normalizeFixtureSource(source(name)) : source(name);
    return [name, new Function('getApp', 'getCurrentPages', 'Date', 'return (' + text + ');')(
      () => app, () => pages, FixedDate,
    )];
  }));
  return { app, functions };
}

function requestJourney(normalized, state, locale, theme) {
  const { app, functions } = runtime(normalized);
  const setup = functions['native-setup.js'];
  const storage = functions['native-storage-mock.js'];
  const request = functions['native-request-mock.js'];
  const results = [];
  const prefix = '/api/activities/dfa-synthetic-running/dfa-alpha1';
  const send = (path = prefix, method = 'GET', data) => {
    const value = request({ url: 'https://example.invalid' + path, method, data });
    results.push(structuredClone(value));
    return value;
  };
  assert.equal(send().statusCode, 503);
  results.push(setup(state, locale, theme));
  results.push(['praxys-auth-token', 'praxys.cn-processing-notice', 'praxys-theme', 'praxys-language', 'other'].map(storage));
  assert.equal(send('/api/settings', 'POST').statusCode, 503);
  send('/api/history');
  const catalog = send().data;
  const input = catalog.inputs.at(-1).input;
  const prepare = send(prefix, 'POST', { input }).data;
  send(prefix + '/runs/' + prepare.id);
  send(prefix + '/runs/' + prepare.id);
  const proof = send(prefix + '/source-confirmations', 'POST').data;
  const compute = send(prefix, 'POST', JSON.stringify({ input, source_confirmation_id: proof.id })).data;
  send(prefix + '/runs/' + compute.id);
  send(prefix + '/runs/' + compute.id);
  send(prefix + '/runs/' + compute.id + '?offset=120');
  send(prefix + '/runs/' + compute.id + '/context?offset=120');
  send(prefix + '/runs/' + compute.id + '/cancel', 'POST');
  send(prefix + '/source-confirmations/' + proof.id, 'DELETE');
  send();
  send(prefix, 'DELETE');
  return { results, app };
}

test('normalized request/setup/storage preserve every synthetic state and locale/theme journey', () => {
  for (const state of ['prepare', 'complete', 'expired', 'multiple', 'unavailable', 'no_valid', 'withdrawn']) {
    for (const locale of ['en', 'zh']) for (const theme of ['light', 'dark']) {
      assert.deepEqual(requestJourney(true, state, locale, theme), requestJourney(false, state, locale, theme));
    }
  }
});

function componentJourney(normalized) {
  const calls = [];
  const component = {
    properties: { activityId: 'dfa-synthetic-running' },
    data: { loading: false, checked: false, active: true, hasResult: true, comparator: 1, rows: [{}, {}], comparatorSeries: [{ label: 'Power' }] },
  };
  for (const method of ['onComparator', 'onCheck', 'confirm', 'deletePrompt', 'erase', 'action', 'refresh']) {
    component[method] = (...args) => { calls.push({ method, args }); return { method, count: calls.length }; };
  }
  const page = { route: 'pages/analysis/index', selectComponent: selector => selector === '#analysis-dfa' ? component : null };
  const { functions } = runtime(normalized, [page]);
  const action = functions['native-component-action.js'];
  const returns = [action('comparator', 2), action('source-check', true), action('source-check', false),
    ...['confirm', 'revoke', 'delete', 'erase', 'cancel', 'refresh', 'state'].map(name => action(name))];
  assert.throws(() => action('other'), /unknown_fixture_action/);
  component.properties.activityId = 'personal-activity';
  assert.throws(() => action('state'), /synthetic_dfa_component_required/);
  page.route = 'pages/login/index';
  assert.throws(() => action('state'), /expected_existing_analysis_page/);
  return { calls, returns };
}

test('normalized component actions preserve method arguments, state and synthetic-owner refusals', () => {
  assert.deepEqual(componentJourney(true), componentJourney(false));
});

test('normalized setup retains validation failures and makes no state change on invalid options', () => {
  for (const normalized of [false, true]) {
    const { app, functions } = runtime(normalized);
    const setup = functions['native-setup.js'];
    for (const args of [['other', 'en', 'dark'], ['prepare', 'fr', 'dark'], ['prepare', 'zh', 'other']]) {
      assert.throws(() => setup(...args), /invalid_fixture_options/);
      assert.deepEqual(app, { globalData: {} });
    }
  }
});

test('literal contents including spaces, escaped newlines, regexes and template raw text survive', () => {
  const value = String.raw`function literals() {
    const word = 'a  b\nnext';
    const pattern = /a  b[\r\n]/g;
    const raw = String.raw\`a  b\nnext\`;
    const template = \`x  \${word}  z\`;
    return [word, pattern.source, pattern.flags, raw, template];
  }`.replaceAll('\\`', '`').replaceAll('\\${', '${');
  const normalized = normalizeFixtureSource(value);
  assert.ok(!/[\r\n\u2028\u2029]/u.test(normalized));
  assert.deepEqual(new Function('return (' + normalized + ')();')(), new Function('return (' + value + ')();')());
});

test('automatic semicolon insertion and adjacent operators retain their behavior', () => {
  for (const value of [
    'function asi() { let x = 1; return\n++x; }',
    'function operators() { let x=1\nx++\nreturn x + +2; }',
  ]) {
    assert.deepEqual(new Function('return (' + normalizeFixtureSource(value) + ')();')(), new Function('return (' + value + ')();')());
  }
});

test('unsupported shapes and physical literal line breaks fail instead of changing semantics', () => {
  for (const value of [
    '', '() => 1', 'function () {}', 'async function f() {}', 'function* f() {}',
    'function f() {}\ngetApp().secret = true;', 'function f(x: number) { return x; }',
    'function f() { return `first\nsecond`; }', 'function f() { return "a\\\nb"; }',
    'function f() { throw\nnew Error(); }', 'function f() { return "\0"; }',
    'function f() {' + ' '.repeat(65536) + '}',
  ]) assert.throws(() => normalizeFixtureSource(value));
});

test('CLI reproducibly emits four single-line copies from any cwd without changing sources', () => {
  const temporary = mkdtempSync(join(tmpdir(), 'dfa-native-normalize-'));
  try {
    const original = Object.fromEntries(FIXTURE_NAMES.map(name => [name, source(name)]));
    const script = fileURLToPath(new URL('../scripts/prepare-dfa-native-fixtures.mjs', import.meta.url));
    const args = [script, '--output-dir', join(temporary, 'generated')];
    const run = spawnSync(process.execPath, args, { cwd: temporary, encoding: 'utf8' });
    assert.equal(run.status, 0, run.stderr);
    const files = JSON.parse(run.stdout);
    assert.deepEqual(files.map(file => file.name), [...FIXTURE_NAMES]);
    for (const file of files) {
      const text = readFileSync(file.path, 'utf8');
      assert.equal(text, normalizeFixtureSource(original[file.name]));
      assert.equal(Buffer.byteLength(text), file.bytes);
      assert.ok(!/[\r\n\u2028\u2029]/u.test(text));
      assert.equal(source(file.name), original[file.name]);
    }
    const second = spawnSync(process.execPath, args, { cwd: temporary, encoding: 'utf8' });
    assert.equal(second.status, 0, second.stderr);
    assert.equal(second.stdout, run.stdout);
  } finally { rmSync(temporary, { recursive: true, force: true }); }
});

for (const alias of ['directory', 'ancestor-directory', 'file-symlink', 'source-inode']) {
  test(`CLI rejects ${alias} source aliases before writing any generated payload`, () => {
    const temporary = mkdtempSync(join(tmpdir(), 'dfa-native-alias-'));
    try {
      // Copy the unchanged implementation and synthetic sources so a failing
      // regression can never overwrite the checkout's actual fixture files.
      const script = join(temporary, 'web/scripts/prepare-dfa-native-fixtures.mjs');
      const fixtures = join(temporary, 'tests/fixtures/dfa');
      mkdirSync(join(temporary, 'web/scripts'), { recursive: true });
      mkdirSync(fixtures, { recursive: true });
      copyFileSync(fileURLToPath(new URL('../scripts/prepare-dfa-native-fixtures.mjs', import.meta.url)), script);
      symlinkSync(fileURLToPath(new URL('../node_modules', import.meta.url)), join(temporary, 'web/node_modules'), 'dir');
      for (const name of FIXTURE_NAMES) {
        copyFileSync(fileURLToPath(new URL('../../tests/fixtures/dfa/' + name, import.meta.url)), join(fixtures, name));
      }
      const before = Object.fromEntries(FIXTURE_NAMES.map(name => [name, readFileSync(join(fixtures, name))]));
      let output = join(temporary, 'generated');
      if (alias === 'directory' || alias === 'ancestor-directory') {
        symlinkSync(fixtures, output, 'dir');
        if (alias === 'ancestor-directory') output = join(output, 'new-output');
      } else {
        mkdirSync(output);
        if (alias === 'file-symlink') {
          symlinkSync(join(fixtures, FIXTURE_NAMES[0]), join(output, FIXTURE_NAMES[0]));
        } else {
          // A later output aliases a different source inode: all targets must
          // be checked before even the first ordinary output is written.
          linkSync(join(fixtures, FIXTURE_NAMES[0]), join(output, FIXTURE_NAMES.at(-1)));
        }
      }
      const run = spawnSync(process.execPath, [script, '--output-dir', output], { encoding: 'utf8' });
      assert.notEqual(run.status, 0);
      assert.match(run.stderr, /fixture sources/);
      for (const name of FIXTURE_NAMES) assert.deepEqual(readFileSync(join(fixtures, name)), before[name]);
      assert.deepEqual(readdirSync(fixtures).sort(), [...FIXTURE_NAMES].sort());
      if (alias === 'file-symlink' || alias === 'source-inode') {
        assert.deepEqual(readdirSync(output), [alias === 'file-symlink' ? FIXTURE_NAMES[0] : FIXTURE_NAMES.at(-1)]);
      }
    } finally { rmSync(temporary, { recursive: true, force: true }); }
  });
}
