import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
import { compactEnglishCatalog, parsePo, serializeCatalog } from '../../miniapp/scripts/sync-i18n.cjs';

const read = relative => readFileSync(new URL(relative, import.meta.url), 'utf8');

function compile(source, modules = {}, wx = {}) {
  const code = ts.transpileModule(source, { compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
  } }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'wx', code)(name => {
    assert.ok(Object.hasOwn(modules, name), name);
    return modules[name];
  }, module, module.exports, wx);
  return module.exports;
}

const original = Object.fromEntries(['en', 'zh'].map(locale => [
  locale, parsePo(read(`../src/locales/${locale}/messages.po`)),
]));
const compact = { en: compactEnglishCatalog(original.en), zh: original.zh };
const extra = compile(read('../../miniapp/utils/i18n-extra.ts')).I18N_EXTRA;
const runtimeSource = read('../../miniapp/utils/i18n.ts');
const generated = read('../../miniapp/utils/i18n-catalog.ts');
const shipped = compile(generated).I18N_CATALOG;

function runtime(catalogs, preference, language, overrides = extra) {
  return compile(runtimeSource, {
    './i18n-catalog': { I18N_CATALOG: catalogs },
    './i18n-extra': { I18N_EXTRA: overrides },
  }, {
    getStorageSync: () => preference,
    getAppBaseInfo: () => ({ language }),
  });
}

test('miniapp catalog omits only safe English identities and retains every Chinese entry', () => {
  assert.equal(generated.replace(/\r\n/g, '\n'), serializeCatalog(compact));
  assert.deepEqual(shipped.zh, original.zh);
  assert.ok(Object.keys(compact.en).length < Object.keys(original.en).length);
  assert.ok(Buffer.byteLength(generated) < Buffer.byteLength(serializeCatalog(original)));
  for (const [key, value] of Object.entries(original.en)) {
    assert.equal(shipped.en[key] ?? key, value, key);
    if (key !== value) assert.equal(shipped.en[key], value, key);
  }
});

test('all current translations and placeholders resolve identically through the real runtime', () => {
  const keys = new Set([
    ...Object.keys(original.en), ...Object.keys(original.zh),
    ...Object.keys(extra.en), ...Object.keys(extra.zh),
    '', 'Missing synthetic {0} {name}', 'Unsupported synthetic {count, plural, one {run} other {runs}}',
    ...Object.getOwnPropertyNames(Object.prototype),
  ]);
  for (const [preference, language] of [
    ['en', 'zh_CN'], ['zh', 'en_US'], ['auto', 'en_GB'],
    ['auto', 'fr_FR'], ['unsupported', ''],
  ]) {
    const before = runtime(original, preference, language);
    const after = runtime(shipped, preference, language);
    for (const key of keys) {
      assert.equal(after.t(key), before.t(key), key);
      if (typeof before.t(key) !== 'string') continue;
      const names = Object.fromEntries([...key.matchAll(/\{([A-Za-z_]\w*)\}/g)]
        .map(match => [match[1], `值-${match[1]}`]));
      assert.equal(after.tFmt(key, 0, '值', 2), before.tFmt(key, 0, '值', 2), key);
      assert.equal(after.tFmt(key), before.tFmt(key), key);
      assert.equal(after.tNamed(key, names), before.tNamed(key, names), key);
      assert.equal(after.tNamed(key, {}), before.tNamed(key, {}), key);
    }
  }
});

test('English overrides, untranslated and unsupported messages keep their fallback behavior', () => {
  const source = [
    'msgid "Identity {0} {name}"\nmsgstr "Identity {0} {name}"',
    'msgid "Different {0} {name}"\nmsgstr "Translated {0} {name}"',
    'msgid "Untranslated"\nmsgstr ""',
    'msgid "One run"\nmsgid_plural "Many runs"\nmsgstr[0] "One run"\nmsgstr[1] "Many runs"',
  ].join('\n\n');
  const catalog = parsePo(source);
  const overrides = { en: { 'Identity {0} {name}': 'Override {0} {name}' }, zh: {} };
  const before = runtime({ en: catalog, zh: {} }, 'en', '', overrides);
  const after = runtime({ en: compactEnglishCatalog(catalog), zh: {} }, 'en', '', overrides);
  for (const key of ['Identity {0} {name}', 'Different {0} {name}', 'Untranslated', 'One run', 'Many runs', 'Missing']) {
    assert.equal(after.t(key), before.t(key), key);
    assert.equal(after.tFmt(key, 0), before.tFmt(key, 0), key);
    assert.equal(after.tNamed(key, { name: '值' }), before.tNamed(key, { name: '值' }), key);
  }
  assert.equal(after.t('Identity {0} {name}'), 'Override {0} {name}');
  assert.equal(after.t('Different {0} {name}'), 'Translated {0} {name}');
  assert.equal(after.t('Untranslated'), 'Untranslated');
  assert.equal(after.t('One run'), 'One run');
});

test('prototype-reserved English keys remain explicit so inherited lookup cannot replace them', () => {
  const keys = Object.getOwnPropertyNames(Object.prototype);
  const catalog = Object.fromEntries(keys.map(key => [key, key]));
  const compacted = compactEnglishCatalog(catalog);
  const overrides = { en: Object.create(null), zh: Object.create(null) };
  const before = runtime({ en: catalog, zh: {} }, 'en', '', overrides);
  const after = runtime({ en: compacted, zh: {} }, 'en', '', overrides);
  for (const key of keys) {
    assert.ok(Object.hasOwn(compacted, key), key);
    assert.equal(after.t(key), before.t(key), key);
    assert.equal(after.t(key), key);
  }
  const missingBefore = runtime({ en: {}, zh: {} }, 'en', '', overrides);
  const missingAfter = runtime({ en: compactEnglishCatalog({}), zh: {} }, 'en', '', overrides);
  for (const key of keys) assert.equal(missingAfter.t(key), missingBefore.t(key), key);
});
