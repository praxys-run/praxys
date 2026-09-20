import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { checkNavigationWorker } from './check-navigation-worker.mjs';

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist');
const manifest = JSON.parse(await readFile(path.join(dist, '.vite/manifest.json'), 'utf8'));
const visited = new Set();
function visit(key) {
  if (visited.has(key)) return;
  visited.add(key);
  for (const dependency of manifest[key].imports ?? []) visit(dependency);
}
// Every document loads the bootstrap before its dynamic public/application entry.
visit('index.html');
visit('src/public-main.tsx');
assert.ok(!visited.has('src/app-main.tsx'), 'Public boot must not import the application entry');
for (const key of visited) {
  assert.doesNotMatch(manifest[key].file, /recharts-|messages-/, `App-only dependency in public boot: ${key}`);
}
visited.clear();
visit('index.html');
visit('src/app-main.tsx');
for (const key of visited) assert.doesNotMatch(manifest[key].file, /recharts-/, 'Initial application boot must not import chart code');
for (const route of ['', 'en', 'zh', 'product', 'faq', 'zh/product', 'zh/faq']) {
  const html = await readFile(path.join(dist, route, 'index.html'), 'utf8');
  assert.match(html, /data-praxys-public-page=/);
  assert.match(html, /class="landing-root/);
  assert.match(html, /<h1/);
  assert.doesNotMatch(html, /seo-fallback/);
}
const shell = await readFile(path.join(dist, 'app-shell.html'), 'utf8');
assert.match(shell, /class="app-loading-shell"/);
assert.doesNotMatch(shell, /class="landing-root|seo-fallback|data-praxys-public-page/);
assert.match(shell, /name="robots" content="noindex, nofollow"/);
const worker = await readFile(path.join(dist, 'sw.js'), 'utf8');
await checkNavigationWorker(worker);
assert.match(worker, /app-shell\.html/, 'Offline navigation must have the application shell');
for (const name of ['index.html', 'app-shell.html', ...['login', 'terms', 'privacy', 'status', 'verify'].map(route => `${route}/index.html`)]) {
  const html = await readFile(path.join(dist, name), 'utf8');
  if (name !== 'index.html') {
    assert.match(html, /class="app-loading-shell"/);
    assert.match(html, /name="robots" content="noindex, nofollow"/);
    if (html.includes('praxys-deployment-region') && name !== 'app-shell.html') {
      assert.match(html, /data-praxys-cn-compliance="icp" aria-label=/);
    }
  }
  const revision = createHash('md5').update(await readFile(path.join(dist, name))).digest('hex');
  assert.ok(worker.includes(`url:"${name}",revision:"${revision}"`), `Service worker revision must include final ${name} content`);
}
console.log('Public build: formal HTML, app shell, and isolated public module graph passed.');
