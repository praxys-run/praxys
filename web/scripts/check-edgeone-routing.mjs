import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';

// EdgeOne applies configured rewrites BEFORE checking whether an asset exists.
export function rewrittenPath(pathname, rules) {
  for (const { source, destination } of rules) {
    assert.ok(!source.includes('*') || source.endsWith('/*'), `Unsupported rewrite pattern: ${source}`);
    if (pathname === source || (source.endsWith('/*') && pathname.startsWith(source.slice(0, -1)))) {
      return destination;
    }
  }
  return pathname;
}

export async function checkEdgeOneRouting(dist) {
  const { rewrites } = JSON.parse(await readFile(new URL('../edgeone.json', import.meta.url), 'utf8'));
  const files = await readdir(dist, { recursive: true, withFileTypes: true });
  for (const file of files.filter(entry => entry.isFile())) {
    const pathname = '/' + path.relative(dist, path.join(file.parentPath, file.name)).split(path.sep).join('/');
    assert.equal(rewrittenPath(pathname, rewrites), pathname, `Rewrite shadows deployed file ${pathname}`);
    if (/\.(?:js|css|woff2)$/.test(pathname) && pathname.startsWith('/assets/')) {
      assert.ok(pathname.startsWith('/assets/client/'), 'Use fresh asset URLs after the cached-HTML incident');
    }
  }
  for (const route of ['', 'en', 'zh', 'product', 'faq', 'zh/product', 'zh/faq', 'login', 'terms', 'privacy', 'status', 'verify']) {
    const destination = route ? `/${route}/index.html` : '/index.html';
    for (const suffix of route ? ['', '/'] : ['']) {
      assert.equal(rewrittenPath(`/${route}${suffix}`, rewrites), destination);
    }
    await readFile(path.join(dist, destination));
  }
  for (const route of ['today', 'setup', 'training', 'analysis', 'goal', 'history', 'science', 'labs', 'labs/environment-response', 'settings', 'admin', 'admin/ops', 'admin/users', 'admin/feedback', 'admin/incidents', 'admin/communications', 'mcp/authorize']) {
    for (const suffix of ['', '/']) assert.equal(rewrittenPath(`/${route}${suffix}`, rewrites), '/app-shell.html');
  }
  for (const resource of ['/assets/missing.js', '/api/status', '/unknown', '/healthz', '/deployed_sha.txt', '/sw.js']) {
    assert.equal(rewrittenPath(resource, rewrites), resource, `Must not rewrite ${resource}`);
  }
}
