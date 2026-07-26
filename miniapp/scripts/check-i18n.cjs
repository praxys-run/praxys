#!/usr/bin/env node
/*
 * i18n coverage detector for the mini program.
 *
 * Four passes; each prints findings, exit non-zero if anything fires:
 *
 *   1. Hardcoded text in WXML — element body text plus a known set of
 *      user-visible attribute values (title, placeholder, aria-label,
 *      confirm-text, cancel-text, x-label, y-label, …). Anything
 *      containing ASCII letters that isn't a single `{{…}}` binding
 *      gets reported. Allowlist below covers brand tokens, glyphs, etc.
 *
 *   2. `t(…)` / `tFmt(…)` / `tNamed(…)` keys whose zh translation is missing. Looks
 *      up in `utils/i18n-extra.ts` (mini-only overrides) and
 *      `utils/i18n-catalog.ts` (synced from web's lingui .po). Both
 *      missing → report.
 *
 *   3. Hardcoded English-looking string literals in TS files — only
 *      flagged when the literal looks like prose (length >= 6, has a
 *      space, has a 4+ letter word) and is NOT inside a t()/tFmt()/tNamed() call
 *      and NOT in the allowlist. Heuristic; same-line `// i18n-allow`
 *      silences a false positive.
 *
 *   4. Native-Chinese quality for mini-only catalog entries — EN/ZH key and
 *      placeholder parity, shared glossary terminology/tone/typography rules,
 *      and zero unexplained drift when a key also exists in the web catalog.
 *
 * Wired into `npm run typecheck` via `pretypecheck` so CI catches gaps.
 */

const fs = require('fs');
const path = require('path');
const ts = require('typescript');
const { parse: parseYaml } = require('yaml');

const ROOT = path.resolve(__dirname, '..');
const SCAN_DIRS = ['pages', 'components', 'custom-tab-bar', 'utils'];

const SKIP_FILES = new Set([
  path.join(ROOT, 'utils', 'i18n-catalog.ts'),
  // Auto-generated from web/src/lib/legal.ts; bilingual content lives inline
  // (en/zh) and is picked by locale at render time, not via the t() catalog.
  path.join(ROOT, 'utils', 'legal.ts'),
  path.join(ROOT, 'utils', 'i18n-extra.ts'),
  path.join(ROOT, 'utils', 'i18n.ts'),
  path.join(ROOT, 'types', 'api.ts'),
]);

const BRAND_LITERALS = new Set([
  'Praxys', 'Pra', 'ys',
  'EN', '中',
  '›', '‹', '×', '+', '−', '→', '·', '•', '✓', '○', '▾', '▸',
  'x',
  'km', 'W', 'bpm', 'min', 'mi', 'sec',
]);

const TS_SKIP_PATTERNS = [
  /^https?:\/\//,
  /^\/[a-z][a-zA-Z0-9_/-]*$/,
  /^[a-z_]+:[a-z_]+/,
  /^[A-Z_][A-Z0-9_]+$/,
  /^#[0-9a-fA-F]{3,8}$/,
  /^[\d.,\s%]+$/,
  /^\{[^}]*\}$/,
  /^[a-zA-Z][a-zA-Z0-9_-]*$/,
  /^\[[a-z-]+\]\s/,                     // console log prefixes: "[settings] foo"
  /^rgba?\(/,                            // color literals: rgba(...) / rgb(...)
  /^\d+(?:px|rem|em|%)\s/,               // CSS shorthand: "11px sans-serif"
  /^\d+\s+\d+px\s/,                      // CSS font shorthand: "500 52px ..."
  /sans-serif|monospace|BlinkMacSystem|-apple-system/, // font stacks
  // Comma-separated lists of identifiers (mini-program observer keys,
  // class name lists). All tokens are bare identifiers.
  /^[a-zA-Z][a-zA-Z0-9_-]*(?:\s*,\s*[a-zA-Z][a-zA-Z0-9_-]*)+$/,
  // Class name strings: tokens delimited by spaces, each kebab-case
  // (commonly with `--modifier` suffix from BEM).
  /^[a-zA-Z][a-zA-Z0-9-]*(?:\s+[a-zA-Z][a-zA-Z0-9-]*)+$/,
  // Class name strings with leading whitespace (concatenated suffixes).
  /^\s+[a-zA-Z][a-zA-Z0-9-]*(?:\s+[a-zA-Z][a-zA-Z0-9-]*)*$/,
];

const TS_LITERAL_ALLOWLIST = new Set([
  'ts-warning', 'ts-primary', 'ts-destructive', 'ts-muted', 'ts-value', 'ts-section-label',
  'success', 'fail', 'none', 'shareAppMessage', 'shareTimeline', 'next', 'done',
  'auto', 'light', 'dark', 'theme-light', 'theme-dark', 'simple', 'advanced',
  'race', 'continuous', 'race_date', 'cp_milestone',
  'UNAUTHENTICATED', 'WECHAT_NO_LOGIN_CODE', 'WECHAT_NOT_CONFIGURED',
  'no-console', 'no-explicit-any',
]);

const USER_VISIBLE_ATTRS = new Set([
  'title', 'placeholder', 'aria-label', 'confirm-text', 'cancel-text',
  'x-label', 'y-label', 'headline', 'detail', 'tap-label',
  'right-text', 'subtitle', 'cta', 'data-label',
]);

function walk(dir, exts, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
      walk(full, exts, out);
    } else if (entry.isFile()) {
      if (SKIP_FILES.has(full)) continue;
      if (exts.includes(path.extname(entry.name))) out.push(full);
    }
  }
  return out;
}

function relish(file) {
  return path.relative(ROOT, file).replace(/\\/g, '/');
}

function lineNumberOf(text, offset) {
  let line = 1;
  for (let i = 0; i < offset && i < text.length; i++) if (text[i] === '\n') line++;
  return line;
}

/**
 * For each match of `openRe` (an opener like `t(`), find the balanced
 * closing `)` while skipping string literals and nested parens, then
 * replace the entire span with whitespace (newlines preserved).
 *
 * Single forward pass — masking the outer call wipes nested calls in
 * place, so we never need to revisit an earlier offset.
 */
function maskBalancedCalls(text, openRe) {
  const re = new RegExp(openRe.source, 'g');
  const out = text.split('');
  let m;
  while ((m = re.exec(text))) {
    // If this opener was already masked by a prior outer call, skip.
    if (out[m.index] === ' ' || out[m.index] === '\n') continue;
    let i = m.index + m[0].length;
    let depth = 1;
    while (i < text.length && depth > 0) {
      const c = text[i];
      if (c === "'" || c === '"') {
        const quote = c;
        i++;
        while (i < text.length && text[i] !== quote) {
          if (text[i] === '\\') i += 2;
          else i++;
        }
        i++;
        continue;
      }
      if (c === '`') {
        i++;
        while (i < text.length && text[i] !== '`') {
          if (text[i] === '\\') i += 2;
          else i++;
        }
        i++;
        continue;
      }
      if (c === '(') depth++;
      else if (c === ')') depth--;
      i++;
    }
    if (depth !== 0) continue;
    for (let j = m.index; j < i; j++) {
      if (out[j] !== '\n') out[j] = ' ';
    }
  }
  return out.join('');
}

function unescapeStr(s) {
  return s
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\'/g, "'")
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\');
}

function loadCatalogKeys() {
  const collected = new Set();
  // i18n-catalog.ts: scoped to the `zh: {…}` block (catalog has both en
  //   and zh under a single I18N_CATALOG export, and we only care about zh).
  // i18n-extra.ts: follow only the sections actually spread into the
  // exported I18N_EXTRA.zh object. Dead declarations must not make a key
  // appear available when runtime lookup cannot reach it.
  const catalogPath = path.join(ROOT, 'utils', 'i18n-catalog.ts');
  if (fs.existsSync(catalogPath)) {
    const txt = fs.readFileSync(catalogPath, 'utf8');
    const zhStart = txt.search(/(?:^|[^A-Za-z0-9_])(?:"zh"|zh)\s*:\s*\{/m);
    if (zhStart >= 0) extractKeysFromBlock(txt, zhStart, collected);
  }
  for (const key of loadExtraCatalog('zh').keys()) {
    collected.add(key);
  }
  return collected;
}

function extractKeysFromBlock(txt, anchor, out) {
  const blockStart = txt.indexOf('{', anchor);
  if (blockStart < 0) return;
  let depth = 0;
  let blockEnd = -1;
  for (let i = blockStart; i < txt.length; i++) {
    const c = txt[i];
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth === 0) { blockEnd = i; break; }
    }
  }
  if (blockEnd < 0) return;
  const block = txt.slice(blockStart, blockEnd + 1);
  const keyRe = /(?:^|\n|,|\{)\s*(?:'([^'\\]*(?:\\.[^'\\]*)*)'|"([^"\\]*(?:\\.[^"\\]*)*)"|([A-Za-z_$][A-Za-z0-9_$]*))\s*:/g;
  let m;
  while ((m = keyRe.exec(block))) {
    const key = unescapeStr(m[1] ?? m[2] ?? m[3] ?? '');
    if (key) out.add(key);
  }
}

function propertyName(node) {
  if (ts.isIdentifier(node) || ts.isStringLiteralLike(node)) return node.text;
  return null;
}

function loadExtraCatalog(locale) {
  const file = path.join(ROOT, 'utils', 'i18n-extra.ts');
  const text = fs.readFileSync(file, 'utf8');
  const source = ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const entries = new Map();
  const objects = new Map();

  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name)) continue;
      if (!declaration.initializer || !ts.isObjectLiteralExpression(declaration.initializer)) continue;
      objects.set(declaration.name.text, declaration.initializer);
    }
  }

  const exported = objects.get('I18N_EXTRA');
  if (exported == null) throw new Error('I18N_EXTRA export is missing');
  const localeProperty = exported.properties.find((property) => (
    ts.isPropertyAssignment(property) && propertyName(property.name) === locale
  ));
  if (
    localeProperty == null ||
    !ts.isPropertyAssignment(localeProperty) ||
    !ts.isObjectLiteralExpression(localeProperty.initializer)
  ) {
    throw new Error(`I18N_EXTRA.${locale} object is missing`);
  }

  for (const spread of localeProperty.initializer.properties) {
    if (!ts.isSpreadAssignment(spread) || !ts.isIdentifier(spread.expression)) {
      throw new Error(`I18N_EXTRA.${locale} must contain named object spreads only`);
    }
    const sectionName = spread.expression.text;
    const section = objects.get(sectionName);
    if (section == null) {
      throw new Error(`I18N_EXTRA.${locale} spreads missing section ${sectionName}`);
    }
    for (const property of section.properties) {
      if (!ts.isPropertyAssignment(property)) continue;
      const key = propertyName(property.name);
      if (key == null || !ts.isStringLiteralLike(property.initializer)) continue;
      if (entries.has(key)) {
        throw new Error(`I18N_EXTRA.${locale} contains duplicate key ${key}`);
      }
      const position = source.getLineAndCharacterOfPosition(property.getStart(source));
      entries.set(key, {
        value: property.initializer.text,
        line: position.line + 1,
        file,
      });
    }
  }
  return entries;
}

function loadSyncedZhCatalog() {
  const file = path.join(ROOT, 'utils', 'i18n-catalog.ts');
  const text = fs.readFileSync(file, 'utf8');
  const source = ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const entries = new Map();
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || declaration.name.text !== 'I18N_CATALOG') continue;
      const initializer = declaration.initializer;
      if (!initializer || !ts.isObjectLiteralExpression(initializer)) continue;
      const zhProperty = initializer.properties.find((property) => (
        ts.isPropertyAssignment(property) && propertyName(property.name) === 'zh'
      ));
      if (
        !zhProperty ||
        !ts.isPropertyAssignment(zhProperty) ||
        !ts.isObjectLiteralExpression(zhProperty.initializer)
      ) {
        continue;
      }
      for (const property of zhProperty.initializer.properties) {
        if (!ts.isPropertyAssignment(property)) continue;
        const key = propertyName(property.name);
        if (key == null || !ts.isStringLiteralLike(property.initializer)) continue;
        entries.set(key, property.initializer.text);
      }
    }
  }
  return entries;
}

function loadChineseQualityRules() {
  const glossary = path.resolve(ROOT, '..', 'scripts', 'i18n_glossary.yaml');
  const data = parseYaml(fs.readFileSync(glossary, 'utf8')) ?? {};
  const style = data.style ?? {};
  const forbidden = (style.forbidden_target ?? [])
    .filter((item) => (
      item && typeof item.term === 'string' && typeof item.prefer === 'string'
    ))
    .map((item) => ({ term: item.term, prefer: item.prefer }));
  const exact = new Map(
    (style.exact_translations ?? [])
      .filter((item) => (
        item && typeof item.source === 'string' && typeof item.target === 'string'
      ))
      .map((item) => [item.source, item.target]),
  );
  return { forbidden, exact };
}

function placeholderNames(text) {
  return [...text.matchAll(/\{([A-Za-z_][A-Za-z0-9_]*|\d+)\}/g)]
    .map((match) => match[1])
    .sort();
}

// A shared key normally must use web's canonical Chinese. Add an entry only
// when the mobile interaction genuinely requires different copy, and explain
// why so the exception is reviewable rather than silent terminology drift.
const MINI_TRANSLATION_OVERRIDES = new Map([
  // ['English key', 'Reason the mobile interaction needs different wording'],
]);

function scanExtraCatalogQuality(findings) {
  const en = loadExtraCatalog('en');
  const zh = loadExtraCatalog('zh');
  const syncedZh = loadSyncedZhCatalog();
  const rules = loadChineseQualityRules();

  for (const [key, entry] of en) {
    if (!zh.has(key)) {
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'missing-zh-extra',
        text: key,
      });
    }
  }
  for (const [key, entry] of zh) {
    if (!en.has(key)) {
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'orphan-zh-extra',
        text: key,
      });
      continue;
    }
    const source = key;
    const translation = entry.value;
    const sourcePlaceholders = placeholderNames(source);
    const targetPlaceholders = placeholderNames(translation);
    if (JSON.stringify(sourcePlaceholders) !== JSON.stringify(targetPlaceholders)) {
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'zh-structure',
        text: `${source} -> ${translation}`,
      });
    }
    const expected = rules.exact.get(source);
    if (expected != null && translation !== expected) {
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'zh-canonical',
        text: `${source} -> ${translation}; expected ${expected}`,
      });
    }
    for (const rule of rules.forbidden) {
      if (!translation.includes(rule.term)) continue;
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'zh-style',
        text: `${source} -> contains ${rule.term}; prefer ${rule.prefer}`,
      });
    }
    if (/[\u3400-\u9fff]/.test(translation)) {
      if (translation.includes('...')) {
        findings.push({
          file: entry.file,
          line: entry.line,
          kind: 'zh-typography',
          text: `${source} -> use …`,
        });
      }
      if (/\s[—–]\s/.test(translation)) {
        findings.push({
          file: entry.file,
          line: entry.line,
          kind: 'zh-typography',
          text: `${source} -> replace spaced dash with Chinese punctuation`,
        });
      }
      if (/(?<![A-Za-z])vs\.?(?![A-Za-z])/i.test(translation)) {
        findings.push({
          file: entry.file,
          line: entry.line,
          kind: 'zh-typography',
          text: `${source} -> translate literal vs`,
        });
      }
    }
    const canonical = syncedZh.get(source);
    const overrideReason = MINI_TRANSLATION_OVERRIDES.get(source);
    if (canonical != null && canonical !== translation && !overrideReason) {
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'zh-override-drift',
        text: `${source} -> mini ${translation}; web ${canonical}`,
      });
    }
    if (canonical != null && canonical === translation && overrideReason) {
      findings.push({
        file: entry.file,
        line: entry.line,
        kind: 'zh-stale-override',
        text: `${source} no longer differs from web; remove its override rationale`,
      });
    }
  }
  for (const [key, reason] of MINI_TRANSLATION_OVERRIDES) {
    if (!reason.trim() || !zh.has(key) || !syncedZh.has(key)) {
      findings.push({
        file: path.join(ROOT, 'scripts', 'check-i18n.cjs'),
        line: 0,
        kind: 'zh-invalid-override',
        text: `${key} must overlap both catalogs and include a non-empty rationale`,
      });
    }
  }
}

function scanWxml(file, findings) {
  let txt = fs.readFileSync(file, 'utf8');
  txt = txt.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, ' '));

  const bodyRe = />([^<>{}]*?(?:\{\{[^}]*\}\}[^<>{}]*?)*)</g;
  let m;
  while ((m = bodyRe.exec(txt))) {
    const raw = m[1];
    if (!raw) continue;
    const stripped = raw.replace(/\{\{[^}]*\}\}/g, '').trim();
    if (!stripped) continue;
    if (!/[A-Za-z]{2,}/.test(stripped)) continue;
    if (BRAND_LITERALS.has(stripped)) continue;
    if (/^[\s·•›‹×→·\-_+]+$/.test(stripped)) continue;
    // Brand URLs — never translated.
    if (/^(?:www\.)?praxys\.run$/i.test(stripped)) continue;
    findings.push({
      file,
      line: lineNumberOf(txt, m.index + 1),
      kind: 'wxml-body',
      text: stripped,
    });
  }

  const attrRe = /([a-zA-Z][a-zA-Z0-9-]*)\s*=\s*"([^"]*)"/g;
  while ((m = attrRe.exec(txt))) {
    const name = m[1];
    if (!USER_VISIBLE_ATTRS.has(name)) continue;
    const value = m[2];
    if (!value) continue;
    if (/^\s*\{\{[\s\S]*\}\}\s*$/.test(value)) continue;
    if (!/[A-Za-z]{2,}/.test(value)) continue;
    if (BRAND_LITERALS.has(value.trim())) continue;
    const stripped = value.replace(/\{\{[^}]*\}\}/g, '').trim();
    if (!stripped) continue;
    if (!/[A-Za-z]{2,}/.test(stripped)) continue;
    if (BRAND_LITERALS.has(stripped)) continue;
    findings.push({
      file,
      line: lineNumberOf(txt, m.index),
      kind: 'wxml-attr',
      attr: name,
      text: value,
    });
  }
}

function scanTsKeys(file, findings, knownKeys) {
  const txt = fs.readFileSync(file, 'utf8');
  const callRe = /\bt(?:Fmt|Named)?\s*\(\s*(?:'([^'\\]*(?:\\.[^'\\]*)*)'|"([^"\\]*(?:\\.[^"\\]*)*)")\s*[,)]/g;
  let m;
  while ((m = callRe.exec(txt))) {
    const key = unescapeStr(m[1] ?? m[2] ?? '');
    if (!key) continue;
    if (knownKeys.has(key)) continue;
    findings.push({
      file,
      line: lineNumberOf(txt, m.index),
      kind: 'missing-zh',
      text: key,
    });
  }
}

function scanTsLiterals(file, findings) {
  const txt = fs.readFileSync(file, 'utf8');
  let masked = txt;
  masked = masked.replace(/\/\*[\s\S]*?\*\//g, (s) => s.replace(/[^\n]/g, ' '));
  masked = masked.replace(/\/\/[^\n]*/g, (s) => s.replace(/[^\n]/g, ' '));
  // Mask `t(…)`, `tFmt(…)`, and `tNamed(…)` calls, including nested calls like
  // `tFmt('Sleep Score vs {0}', t('Avg Power'))`. We do a balanced-paren
  // walk by hand; a regex can't handle arbitrary nesting cleanly.
  masked = maskBalancedCalls(masked, /\bt(?:Fmt|Named)?\s*\(/g);
  masked = masked.replace(/^[\t ]*import[^;\n]*[;\n]/gm, (s) => s.replace(/[^\n]/g, ' '));
  masked = masked.replace(
    /^[\t ]*(?:type|interface)\s[\s\S]*?(?:^[\t ]*\}|\n;)/gm,
    (s) => s.replace(/[^\n]/g, ' '),
  );

  const litRe = /'((?:[^'\\\n]|\\[\s\S])*)'|"((?:[^"\\\n]|\\[\s\S])*)"/g;
  let m;
  while ((m = litRe.exec(masked))) {
    const value = unescapeStr(m[1] ?? m[2] ?? '');
    if (!value) continue;
    if (TS_LITERAL_ALLOWLIST.has(value)) continue;
    if (TS_SKIP_PATTERNS.some((re) => re.test(value))) continue;
    if (value.length < 4) continue;
    if (!/[A-Za-z]{4,}/.test(value)) continue;
    // Already-Chinese strings (CJK character anywhere) — these are
    // explicitly localized inline (typically `locale === 'zh' ? zh : en`
    // ternaries), so we don't expect them in the catalog.
    if (/[一-鿿]/.test(value)) continue;
    const looksProse =
      /\s/.test(value) || /[?!…]/.test(value) || /^[A-Z][a-z].*\s/.test(value);
    if (!looksProse) continue;
    const lineNum = lineNumberOf(masked, m.index);
    const lineText = txt.split('\n')[lineNum - 1] ?? '';
    if (/i18n-allow/.test(lineText)) continue;
    // Inline `locale === 'zh' ? '…zh…' : '…en…'` ternaries are common —
    // skip the en side if any of the 5 lines around (±2) contains a
    // CJK literal OR a `'zh' ?` ternary marker. Hand-written localized
    // fallbacks don't need catalog entries.
    const allLines = txt.split('\n');
    const lo = Math.max(0, lineNum - 3);
    const hi = Math.min(allLines.length, lineNum + 2);
    const window = allLines.slice(lo, hi).join('\n');
    if (/[一-鿿]/.test(window)) continue;
    if (/'zh'\s*\?/.test(window)) continue;
    // Throw new Error('…') — internal-only diagnostic, never displayed.
    if (/throw\s+new\s+\w*Error\s*\(/.test(lineText)) continue;
    findings.push({
      file,
      line: lineNum,
      kind: 'ts-literal',
      text: value,
    });
  }
}

function main() {
  const wxmlFiles = [];
  const tsFiles = [];
  for (const sub of SCAN_DIRS) {
    const full = path.join(ROOT, sub);
    walk(full, ['.wxml'], wxmlFiles);
    walk(full, ['.ts'], tsFiles);
  }

  const findings = [];
  for (const f of wxmlFiles) scanWxml(f, findings);
  const knownKeys = loadCatalogKeys();
  for (const f of tsFiles) scanTsKeys(f, findings, knownKeys);
  for (const f of tsFiles) scanTsLiterals(f, findings);
  scanExtraCatalogQuality(findings);

  const byKind = new Map();
  for (const f of findings) {
    if (!byKind.has(f.kind)) byKind.set(f.kind, []);
    byKind.get(f.kind).push(f);
  }

  let total = 0;
  for (const [kind, list] of byKind) {
    console.log(`\n[${kind}] ${list.length} finding(s):`);
    for (const f of list) {
      const where = `${relish(f.file)}:${f.line}`;
      const detail = f.attr ? `${f.attr}="${f.text}"` : f.text;
      console.log(`  ${where}  ${JSON.stringify(detail)}`);
      total++;
    }
  }

  if (total === 0) {
    console.log('[i18n-check] no findings — all surfaces translated.');
    process.exit(0);
  }
  console.log(`\n[i18n-check] ${total} finding(s) total. ` +
    `Fix coverage/copy in the web .po or miniapp i18n-extra.ts; shared rules live in scripts/i18n_glossary.yaml.`);
  process.exit(1);
}

main();
