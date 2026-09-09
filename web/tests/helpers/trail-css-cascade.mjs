import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { compile } from '@tailwindcss/node';
import postcss from 'postcss';
import selectorParser from 'postcss-selector-parser';
import { markupNodes } from './trail-component-harness.mjs';

// Compile the real entry point and installed Tailwind imports in memory.
// This is a bounded utility-selector/cascade model over React SSR, NOT a
// browser, computed style, contrast measurement, or media-emulation result.
const compiler = await compile(
  await readFile(new URL('../../src/index.css', import.meta.url), 'utf8'),
  { base: fileURLToPath(new URL('../../src/', import.meta.url)), onDependency() {} },
);
const properties = new Set(['color', 'background-color', 'border-color', 'opacity', 'pointer-events']);
const compare = (left, right) => {
  for (let index = 0; index < left.length; index++) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
};

function specificity(selector) {
  return selector.nodes.reduce((total, node) => {
    let part = [0, 0, 0];
    if (node.type === 'id') part = [1, 0, 0];
    else if (['class', 'attribute'].includes(node.type)) part = [0, 1, 0];
    else if (node.type === 'tag') part = [0, 0, 1];
    else if (node.type === 'pseudo' && node.value !== ':where') {
      part = [':is', ':not', ':has'].includes(node.value)
        ? node.nodes.map(specificity).sort(compare).at(-1)
        : node.value.startsWith('::') ? [0, 0, 1] : [0, 1, 0];
    }
    return total.map((value, index) => value + part[index]);
  }, [0, 0, 0]);
}

function matchesSimple(node, element, state) {
  const attributes = element.attributes;
  switch (node.type) {
    case 'universal': return true;
    case 'tag': return node.value === element.tag;
    case 'id': return attributes.id === node.value;
    case 'class': return (attributes.class ?? '').split(/\s+/).includes(node.value);
    case 'attribute': {
      if (!Object.hasOwn(attributes, node.attribute)) return false;
      if (!node.operator) return true;
      const actual = node.insensitive ? attributes[node.attribute].toLowerCase() : attributes[node.attribute];
      const expected = node.insensitive ? node.value.toLowerCase() : node.value;
      switch (node.operator) {
        case '=': return actual === expected;
        case '~=': return actual.split(/\s+/).includes(expected);
        case '*=': return actual.includes(expected);
        case '^=': return actual.startsWith(expected);
        case '$=': return actual.endsWith(expected);
        case '|=': return actual === expected || actual.startsWith(`${expected}-`);
        default: assert.fail(`Unsupported attribute operator: ${node.operator}`);
      }
      break;
    }
    case 'pseudo':
      if ([':is', ':where'].includes(node.value)) {
        return node.nodes.some((selector) => matches(selector, element, state));
      }
      if (node.value === ':not') return !node.nodes.some((selector) => matches(selector, element, state));
      if (node.value.startsWith('::')) return false; // Not the element's own style.
      if (node.value === ':disabled') return Object.hasOwn(attributes, 'disabled');
      if ([':hover', ':focus', ':focus-visible', ':active'].includes(node.value)) {
        return element === state.target && state[node.value.slice(1)] === true;
      }
      assert.fail(`Unsupported matching pseudo-class: ${node.value}`);
      break;
    default: assert.fail(`Unsupported selector node: ${node.type}`);
  }
}

function matches(selector, element, state) {
  const nodes = selector.nodes;
  const matchAt = (end, candidate) => {
    if (!candidate) return false;
    let start = end;
    while (start >= 0 && nodes[start].type !== 'combinator') start--;
    const compound = nodes.slice(start + 1, end + 1);
    // Reject unrelated classes/tags before evaluating their state predicates.
    if (!compound.filter((node) => node.type !== 'pseudo')
      .every((node) => matchesSimple(node, candidate, state))
      || !compound.filter((node) => node.type === 'pseudo')
        .every((node) => matchesSimple(node, candidate, state))) return false;
    if (start < 0) return true;
    const combinator = nodes[start].value.trim();
    if (combinator === '>') return matchAt(start - 1, candidate.parent);
    if (combinator === '') {
      for (let ancestor = candidate.parent; ancestor; ancestor = ancestor.parent) {
        if (matchAt(start - 1, ancestor)) return true;
      }
      return false;
    }
    assert.fail(`Unsupported matching combinator: ${combinator}`);
  };
  return matchAt(nodes.length - 1, element);
}

function conditionApplies(condition, state) {
  if (condition.name === 'supports') {
    assert.equal(condition.params, '(color: color-mix(in lab, red, red))');
    return state.colorMix;
  }
  assert.equal(condition.name, 'media');
  assert.equal(condition.params, '(hover: hover)');
  return state.hoverCapable;
}

export function compileTrailStyles(...roots) {
  const candidates = new Set(roots.flatMap((root) => markupNodes(root)
    .flatMap((node) => (node.attributes.class ?? '').split(/\s+/).filter(Boolean))));
  const css = postcss.parse(compiler.build([...candidates]));
  const rules = [];
  for (const layer of css.nodes.filter((node) => node.type === 'atrule'
    && node.name === 'layer' && node.params === 'utilities')) {
    layer.walkDecls((declaration) => {
      if (!properties.has(declaration.prop)) return;
      let rule;
      const conditions = [];
      for (let parent = declaration.parent; parent !== layer; parent = parent.parent) {
        if (parent.type === 'rule' && !rule) rule = parent;
        else if (parent.type === 'atrule') conditions.push(parent);
      }
      assert.ok(rule, 'utility declaration has a real compiled selector');
      for (const selector of selectorParser().astSync(rule.selector).nodes) {
        rules.push({
          selector: selector.toString(),
          ast: selector,
          specificity: specificity(selector),
          property: declaration.prop,
          value: declaration.value,
          important: Boolean(declaration.important),
          order: rules.length,
          conditions,
        });
      }
    });
  }
  assert.ok(rules.length, 'the real Tailwind entry point produced utility declarations');
  const matchingRules = (element, property, options = {}) => {
    const state = { target: element, colorMix: true, hoverCapable: true, ...options };
    return rules.filter((rule) => rule.property === property
      && matches(rule.ast, element, state)
      && rule.conditions.every((condition) => conditionApplies(condition, state)))
      .sort((left, right) => Number(left.important) - Number(right.important)
        || compare(left.specificity, right.specificity) || left.order - right.order);
  };
  const style = (element, property, options = {}) => {
    const state = { target: element, ...options };
    const winner = matchingRules(element, property, state).at(-1);
    if (property === 'color' && (!winner || winner.value === 'currentcolor') && element.parent) {
      const inherited = style(element.parent, property, state);
      if (winner) return { ...winner, value: inherited?.value, element, declaredValue: winner.value };
      return inherited;
    }
    return winner ? { ...winner, element } : undefined;
  };
  return { style, matchingRules };
}

// An explicit synthetic ancestor tests the compiled `.dark *` relationship.
// Toggling this SSR-tree attribute does not emulate a browser/theme or media.
export function setSSRTheme(root, dark) {
  assert.equal(root.tag, 'root');
  root.attributes.class = dark ? 'dark' : '';
}
