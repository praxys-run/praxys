import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const html = await readFile(new URL('../public/api/frontend-recovery.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function harness({ online = true, language = 'en', registrations = [] } = {}) {
  const elements = Object.fromEntries(['heading', 'description', 'update', 'status'].map(id => [id, {textContent:'',disabled:false,addEventListener(_event,callback){this.click=callback;}}]));
  const location = {origin:'https://praxys.run',replace(path){this.destination=path;}};
  const context = {
    document: {documentElement:{lang:'zh-CN'},getElementById(id){return elements[id];}},
    navigator: {onLine:online,language,serviceWorker:{async getRegistrations(){return registrations;}}},
    location, URL, Error,
    localStorage: new Proxy({}, {get(){throw new Error('storage must remain untouched');}}),
    caches: new Proxy({}, {get(){throw new Error('caches must remain untouched');}}),
  };
  vm.runInNewContext(script, context);
  return {elements,location,context,click:()=>elements.update.click()};
}

function registration(scope, scriptURL, reject = false) {
  return {scope,active:{scriptURL},calls:0,async unregister(){this.calls++;if(reject)throw new Error('blocked');return true;}};
}

test('recovery targets only the same-origin root Praxys worker and preserves site storage', async () => {
  const root = registration('https://praxys.run/', 'https://praxys.run/sw.js');
  const other = registration('https://praxys.run/other/', 'https://praxys.run/other/sw.js');
  const foreign = registration('https://other.invalid/', 'https://other.invalid/sw.js');
  const h=harness({registrations:[root,other,foreign]});
  await h.click();
  assert.equal(root.calls,1);assert.equal(other.calls,0);assert.equal(foreign.calls,0);
  assert.equal(h.location.destination,'/settings');
});

test('offline recovery retains the current registration and offers retry', async () => {
  const root=registration('https://praxys.run/','https://praxys.run/sw.js');
  const h=harness({online:false,registrations:[root],language:'zh-CN'});
  await h.click();
  assert.equal(root.calls,0);assert.equal(h.location.destination,undefined);
  assert.equal(h.elements.status.textContent,'连接网络后再试。');
  assert.equal(h.elements.update.disabled,false);
});

test('failed unregister shows an accessible retry state without navigation', async () => {
  const root=registration('https://praxys.run/','https://praxys.run/sw.js',true);
  const h=harness({registrations:[root]});await h.click();
  assert.equal(h.location.destination,undefined);assert.equal(h.elements.update.disabled,false);
  assert.equal(h.elements.status.textContent,'The update did not finish. Please try again.');
  assert.match(html,/role="status" aria-live="polite"/);
  assert.match(html,/name="robots" content="noindex, nofollow"/);
});

test('browsers without service worker support still open the current settings document', async () => {
  const h=harness();delete h.context.navigator.serviceWorker;await h.click();
  assert.equal(h.location.destination,'/settings');
});
