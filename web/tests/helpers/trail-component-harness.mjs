import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { transformSync } from '@swc/core';
import { setupI18n } from '@lingui/core';
import { I18nProvider } from '@lingui/react';
import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const sourceRoot = fileURLToPath(new URL('../../src/', import.meta.url));
const workbenchPath = path.join(sourceRoot, 'components/TrailCourseReview.tsx');

// No browser, server, file generation, or extra dependency. Compile the real
// components and shared Base UI wrappers with the installed Vite/Lingui compiler.
// Only the workbench's state scheduler and network boundary are test doubles.
export function loadTrailComponents({ hooks = {}, apiFetch = async () => {
  throw new Error('Unexpected API request');
} } = {}) {
  const cache = new Map();
  const load = (relative) => {
    let filename = path.resolve(sourceRoot, relative);
    if (!existsSync(filename)) {
      filename = ['.tsx', '.ts'].map((extension) => `${filename}${extension}`)
        .find(existsSync) ?? filename;
    }
    if (cache.has(filename)) return cache.get(filename).exports;
    const source = readFileSync(filename, 'utf8')
      + (filename === workbenchPath ? '\nexport { TrailCourseReviewWorkbench };' : '');
    const module = { exports: {} };
    cache.set(filename, module);
    const { code } = transformSync(source, {
      filename,
      jsc: {
        parser: { syntax: 'typescript', tsx: filename.endsWith('.tsx') },
        target: 'es2022',
        transform: { react: { runtime: 'automatic' } },
        experimental: {
          plugins: [[require.resolve('@lingui/swc-plugin'), {
            descriptorFields: 'message',
          }]],
        },
      },
      module: { type: 'commonjs' },
    });
    const localRequire = (specifier) => {
      if (specifier === 'react' && filename === workbenchPath) {
        return { ...React, ...hooks };
      }
      if (specifier === '@/hooks/useApi') {
        return {
          apiFetch,
          getAuthCacheScope: () => 'synthetic-owner',
          getAuthHeaders: () => ({}),
          extractErrorMessage: async (response, fallback) => (
            (await response.json()).detail ?? fallback
          ),
        };
      }
      if (specifier === './trail-course-review/use-private-draft') {
        return { usePrivateTrailDraft: () => {
          throw new Error('Use the isolated workbench, not the remote read hook');
        } };
      }
      if (specifier.startsWith('@/')) return load(specifier.slice(2));
      if (specifier.startsWith('.')) {
        return load(path.resolve(path.dirname(filename), specifier));
      }
      return require(specifier);
    };
    // The compiled input is checked-in source, not a fixture or user string.
    new Function('require', 'module', 'exports', code)(localRequire, module, module.exports);
    return module.exports;
  };
  return load;
}

export function renderLocalized(element, locale = 'en') {
  const i18n = setupI18n({ locale, messages: { [locale]: {} } });
  return renderToStaticMarkup(React.createElement(I18nProvider, { i18n }, element));
}

export function elementChildren(node) {
  if (!node || typeof node !== 'object') return [];
  return React.Children.toArray(node.props?.children);
}

export function findElements(node, predicate) {
  if (!node || typeof node !== 'object') return [];
  return [
    ...(predicate(node) ? [node] : []),
    ...elementChildren(node).flatMap((child) => findElements(child, predicate)),
  ];
}

const decode = (text) => text
  .replace(/&#x([0-9a-f]+);/gi, (_, value) => String.fromCodePoint(parseInt(value, 16)))
  .replace(/&#(\d+);/g, (_, value) => String.fromCodePoint(Number(value)))
  .replaceAll('&quot;', '"').replaceAll('&#x27;', "'")
  .replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&amp;', '&');

// Inspect trusted React SSR output structurally, not copy-presence alone.
// This deliberately does not claim a browser DOM, layout, or AX-tree execution.
export function markupTree(html) {
  const root = { tag: 'root', attributes: {}, children: [] };
  const stack = [root];
  const voidTags = new Set(['input', 'img', 'br', 'hr', 'meta', 'link', 'wbr']);
  for (const token of html.matchAll(/<!--[\s\S]*?-->|<\/?([a-z][\w-]*)\b([^>]*?)>|([^<]+)/gi)) {
    if (token[0].startsWith('<!--')) continue;
    if (token[3]) {
      stack.at(-1).children.push(decode(token[3]));
    } else if (token[0].startsWith('</')) {
      assert.equal(stack.at(-1).tag, token[1], `balanced SSR ${token[0]}`);
      stack.pop();
    } else {
      const attributes = Object.fromEntries(
        [...token[2].matchAll(/([^\s=]+)(?:="([^"]*)")?/g)]
          .map((match) => [match[1], decode(match[2] ?? '')]),
      );
      const node = { tag: token[1], attributes, children: [], parent: stack.at(-1) };
      stack.at(-1).children.push(node);
      if (!voidTags.has(node.tag)) stack.push(node);
    }
  }
  assert.equal(stack.length, 1);
  return root;
}

export function markupNodes(root, predicate = () => true) {
  if (typeof root === 'string') return [];
  return [
    ...(predicate(root) ? [root] : []),
    ...root.children.flatMap((child) => markupNodes(child, predicate)),
  ];
}

export function textContent(node) {
  return typeof node === 'string' ? node : node.children.map(textContent).join('');
}

export function byId(root, id) {
  return markupNodes(root, (node) => node.attributes.id === id)[0];
}

export function accessibleName(root, node) {
  if (node.attributes['aria-labelledby']) {
    return node.attributes['aria-labelledby'].split(' ')
      .map((id) => textContent(byId(root, id))).join(' ');
  }
  if (node.attributes['aria-label']) return node.attributes['aria-label'];
  const labels = markupNodes(root, (candidate) => candidate.tag === 'label'
    && candidate.attributes.for === node.attributes.id);
  return labels.length ? labels.map(textContent).join(' ') : textContent(node);
}

export function createWorkbenchHarness(draft, { locale = 'en', latest = draft, online = true } = {}) {
  let cursor = 0;
  let tree;
  let markup;
  const slots = [];
  const frames = [];
  const focused = [];
  const calls = [];
  const props = {
    remoteDraft: draft,
    onFetchLatest: async () => { calls.push({ kind: 'latest' }); return latest; },
    onRefetch: async () => { throw new Error('Unexpected refetch'); },
    onReplaceRemote: (next) => { props.remoteDraft = next; },
    onClearRemote: () => { throw new Error('Unexpected clear'); },
    onRejectRemote: (message) => { throw new Error(`Unexpected rejection: ${message}`); },
  };
  const stateSlot = (initial) => {
    const index = cursor++;
    if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial;
    return [slots[index], (next) => {
      slots[index] = typeof next === 'function' ? next(slots[index]) : next;
    }];
  };
  const load = loadTrailComponents({
    hooks: {
      useState: stateSlot,
      useRef: (initial) => stateSlot(() => ({ current: initial }))[0],
      useCallback: (callback) => callback,
      useMemo: (callback) => callback(),
      useEffect: () => {},
    },
    apiFetch: async (url, init) => {
      calls.push({ kind: 'api', url, init });
      return new Response(JSON.stringify({ detail: 'Changed' }), { status: 412 });
    },
  });
  const { TrailCourseReviewWorkbench: Workbench } = load('components/TrailCourseReview.tsx');
  const focus = (node) => {
    assert.ok(node, 'focus destination exists in actual SSR output');
    assert.ok(['button', 'input', 'a'].includes(node.tag)
      || node.attributes.tabindex === '-1', `focus destination must be interactive: ${node.tag}`);
    focused.push(node);
  };
  const render = (nextLocale = locale) => {
    locale = nextLocale;
    function Probe() {
      cursor = 0;
      tree = Workbench(props);
      return tree;
    }
    const previousNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { onLine: online } });
    try {
      markup = markupTree(renderLocalized(React.createElement(Probe), locale));
    } finally {
      if (previousNavigator) Object.defineProperty(globalThis, 'navigator', previousNavigator);
      else delete globalThis.navigator;
    }
    for (const node of findElements(tree, (item) => typeof item.props?.ref === 'object')) {
      if (!node.props.ref) continue;
      const target = node.props.id ? byId(markup, node.props.id) : {
        tag: node.type, attributes: { tabindex: String(node.props.tabIndex) }, children: [],
      };
      node.props.ref.current = { focus: () => focus(target) };
    }
    return markup;
  };
  const invoke = async (callback, ...args) => {
    const saved = new Map(['window', 'document', 'requestAnimationFrame']
      .map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
    Object.assign(globalThis, {
      window: { setTimeout: () => 1, clearTimeout: () => {} },
      document: { getElementById: (id) => ({ focus: () => focus(byId(markup, id)) }) },
      requestAnimationFrame: (callback) => { frames.push(callback); },
    });
    try {
      await callback(...args);
      // Click handlers intentionally return void while starting async actions.
      // Let the mocked Response/read promises settle before the next render.
      await new Promise(setImmediate);
      render();
      while (frames.length) frames.shift()();
    } finally {
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    }
  };
  render();
  return {
    load, render, invoke, calls, focused,
    get tree() { return tree; },
    get markup() { return markup; },
    find: (predicate) => {
      const result = findElements(tree, predicate)[0];
      assert.ok(result, 'expected component/control exists');
      return result;
    },
  };
}
