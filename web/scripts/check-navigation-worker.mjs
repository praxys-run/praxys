import assert from 'node:assert/strict';
import { runInNewContext } from 'node:vm';

/** Exercise the emitted worker's routing/handler, with synthetic network/cache IO. */
export async function checkNavigationWorker(source) {
  const routes = [];
  let precacheOptions;
  let precacheEntries;
  let offline = false;
  const requests = [];
  const cacheReads = [];
  const networkResponse = Response.redirect('https://cn.example.test/faq', 302);
  const cachedResponse = new Response('cached public document');
  const workbox = {
    clientsClaim() {},
    cleanupOutdatedCaches() {},
    precacheAndRoute(entries, options) { precacheEntries = entries; precacheOptions = options; },
    createHandlerBoundToURL(url) { return url; },
    NavigationRoute: class {
      constructor(handler, options) { this.handler = handler; this.options = options; }
    },
    registerRoute(...args) { routes.push(args); },
  };
  const define = (_dependencies, factory) => factory(workbox);
  runInNewContext(source, {
    self: { define, skipWaiting() {} }, define,
    fetch: async request => {
      requests.push(request);
      if (offline) throw new Error('synthetic offline');
      return networkResponse;
    },
    caches: { match: async url => { cacheReads.push(url); return cachedResponse; } },
  });
  assert.equal(precacheOptions.directoryIndex, null, 'Precache must not intercept canonical / URLs');
  assert.equal(precacheOptions.ignoreURLParametersMatching.length, 0);
  const fallback = routes.find(([route]) => route instanceof workbox.NavigationRoute)[0];
  const [matches, handle] = routes.find(([route]) => typeof route === 'function');
  for (const pathname of ['/', '/en', '/zh', '/faq/', '/product', '/zh/product/', '/zh/faq', '/login', '/terms/', '/privacy', '/status', '/verify']) {
    assert.ok(!precacheEntries.some(entry => `/${entry.url}` === pathname || `/${entry.url}` === `${pathname}.html`), 'No precache canonical or clean-URL alias');
    for (const search of ['', '?utm_source=test', '?lang=en']) {
      const url = new URL(`https://run.example.test${pathname}${search}`);
      const request = { mode: 'navigate', url: url.href };
      assert.ok(fallback.options.denylist.some(pattern => pattern.test(url.pathname + url.search)), url.href);
      assert.ok(matches({ request, url }));
      offline = false;
      const cacheCount = cacheReads.length;
      assert.equal(await handle({ request, url }), networkResponse, 'Preserve network redirect response');
      assert.equal(requests.at(-1), request, 'Preserve the original query-bearing navigation');
      assert.equal(cacheReads.length, cacheCount, 'Online navigation must not use cached HTML');
      offline = true;
      assert.equal(await handle({ request, url }), cachedResponse);
      assert.equal(cacheReads.at(-1), `${url.origin}${pathname.replace(/\/+$/, '')}/index.html`);
    }
  }
  for (const pathname of ['/today', '/training', '/settings', '/api/status', '/faq/unknown']) {
    assert.equal(matches({ request: { mode: 'navigate' }, url: new URL(`https://run.example.test${pathname}`) }), false);
  }
}
