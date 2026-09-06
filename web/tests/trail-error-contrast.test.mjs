import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import * as React from 'react';
import {
  numericInputsFromDraft,
  requestFromDraft,
} from '../src/components/trail-course-review/model.ts';
import {
  byId,
  createWorkbenchHarness,
  findElements,
  loadTrailComponents,
  markupNodes,
  markupTree,
  renderLocalized,
  textContent,
} from './helpers/trail-component-harness.mjs';
import { compileTrailStyles, setSSRTheme } from './helpers/trail-css-cascade.mjs';

const fixture = JSON.parse(await readFile(
  new URL('./fixtures/trail-readiness-service-contract.json', import.meta.url), 'utf8',
));
const load = loadTrailComponents();
const { Alert, AlertTitle, AlertDescription } = load('components/ui/alert.tsx');
const { Button } = load('components/ui/button.tsx');
const { FieldShell } = load('components/trail-course-review/controls.tsx');
const { TrailPendingComparison } = load('components/trail-course-review/comparison.tsx');
const { TrailCourseReviewLoadError, TrailUnknownVersion } = load('components/trail-course-review/states.tsx');
const { useTrailCourseReviewCopy } = load('components/trail-course-review/copy.tsx');
const slotOverrides = 'dark:*:data-[slot=alert-title]:text-foreground dark:*:data-[slot=alert-description]:text-foreground';
const render = (Component, props, locale = 'en') => markupTree(
  renderLocalized(React.createElement(Component, props), locale),
);
const slot = (root, name) => markupNodes(root, (node) => node.attributes['data-slot'] === name)[0];
const alertByText = (root, text) => markupNodes(root, (node) => node.attributes['data-slot'] === 'alert'
  && textContent(node).includes(text))[0];
const destructive = (colorMix) => colorMix
  ? 'color-mix(in oklab, var(--destructive) 90%, transparent)' : 'var(--destructive)';
function copyFor(locale) {
  let result;
  function Probe() { result = useTrailCourseReviewCopy().copy; return null; }
  render(Probe, {}, locale);
  return result;
}

function assertAlertContrast(root, alert) {
  assert.ok(alert, 'actual Trail Alert is rendered');
  assert.equal(alert.attributes.role, 'alert');
  const description = slot(alert, 'alert-description');
  const title = slot(alert, 'alert-title');
  assert.ok(description);
  assert.equal(description.parent, alert, 'description is the shared direct-child slot');
  if (title) assert.equal(title.parent, alert);
  const css = compileTrailStyles(root);
  for (const colorMix of [false, true]) {
    setSSRTheme(root, false);
    assert.equal(css.style(alert, 'color', { colorMix }).value, 'var(--destructive)');
    assert.equal(css.style(alert, 'background-color', { colorMix }).value, 'var(--card)');
    assert.equal(css.style(description, 'color', { colorMix }).value, destructive(colorMix),
      'light Alert description keeps the shared destructive treatment');
    if (title) assert.equal(css.style(title, 'color', { colorMix }).value, 'var(--destructive)');
    setSSRTheme(root, true);
    assert.equal(css.style(alert, 'color', { colorMix }).value, 'var(--destructive)',
      'do not recolor the Alert root or inherited icons');
    assert.equal(css.style(alert, 'background-color', { colorMix }).value, 'var(--card)');
    for (const target of [title, description].filter(Boolean)) {
      const winner = css.style(target, 'color', { colorMix });
      assert.equal(winner.value, 'var(--foreground)', 'dark error slot needs full-opacity foreground');
      assert.equal(winner.element, target, 'slot needs its own matching rule, not root inheritance');
      assert.deepEqual(winner.specificity, [0, 3, 0]);
      assert.equal(winner.important, false);
    }
    const rules = css.matchingRules(description, 'color', { colorMix });
    const defaultRule = rules.find((rule) => rule.value === destructive(colorMix));
    const winner = rules.at(-1);
    assert.ok(defaultRule, 'shared destructive description rule still matches');
    assert.deepEqual(defaultRule.specificity, [0, 2, 0]);
    assert.ok(winner.order > defaultRule.order, 'real compiled order also favors the dark slot rule');
    assert.ok(rules.some((rule) => rule.value === 'var(--muted-foreground)'),
      'actual AlertDescription default text utility participates in the cascade');
  }
  for (const override of slotOverrides.split(' ')) {
    assert.ok(alert.attributes.class.split(/\s+/).includes(override),
      'each caller retains both accepted slot overrides, even without a current title');
  }
}

function assertStandaloneContrast(root, node) {
  assert.ok(node, 'actual standalone error/navigation text exists');
  const css = compileTrailStyles(root);
  setSSRTheme(root, false);
  assert.equal(css.style(node, 'color').value, 'var(--destructive)');
  setSSRTheme(root, true);
  const winner = css.style(node, 'color');
  assert.equal(winner.value, 'var(--foreground)');
  assert.equal(winner.element, node);
  assert.deepEqual(winner.specificity, [0, 2, 0]);
  assert.equal(winner.important, false);
}

test('UI6 CSS control: actual shared Alert rejects root-only recoloring and targets only direct slots', () => {
  function Probe() {
    return React.createElement('section', null,
      ...['dark:text-foreground', slotOverrides].map((className, index) => React.createElement(
        Alert, { key: className, id: `control-${index}`, variant: 'destructive', className },
        React.createElement('svg', { 'aria-hidden': true }),
        React.createElement(AlertTitle, null, 'Title'),
        React.createElement(AlertDescription, null, 'Description',
          React.createElement('span', { 'data-slot': 'alert-description', className: 'text-destructive' }, 'Nested')),
      )),
    );
  }
  const root = render(Probe, {});
  const css = compileTrailStyles(root);
  const rootOnly = byId(root, 'control-0');
  const corrected = byId(root, 'control-1');
  setSSRTheme(root, true);
  assert.equal(css.style(rootOnly, 'color').value, 'var(--foreground)');
  assert.equal(css.style(slot(rootOnly, 'alert-description'), 'color').value, destructive(true),
    'root-only foreground must NOT be accepted as the repair');
  assertAlertContrast(root, corrected);
  const svg = markupNodes(corrected, (node) => node.tag === 'svg')[0];
  assert.equal(css.style(svg, 'color').declaredValue, 'currentcolor');
  assert.equal(css.style(svg, 'color').value, 'var(--destructive)');
  const nested = markupNodes(corrected, (node) => node.tag === 'span')[0];
  assert.equal(css.style(nested, 'color').value, 'var(--destructive)',
    'caller override does not blanket-recolor descendants');
});

for (const locale of ['en', 'zh']) {
  const copy = copyFor(locale);
  for (const status of [500, 404, null]) {
    test(`UI6 ${locale}: load error ${status} uses compiled dark slot overrides and preserves private/error semantics`, () => {
      const root = render(TrailCourseReviewLoadError, {
        status, onRetry: () => assert.fail('SSR must not make a request'),
      }, locale);
      const alert = slot(root, 'alert');
      const title = textContent(slot(alert, 'alert-title'));
      assert.equal(title, status === 404
        ? locale === 'en' ? 'This private Trail course review was not found' : '未找到此私密越野赛道核对'
        : locale === 'en' ? 'Trail course review could not be loaded' : '暂时无法加载越野赛道核对');
      if (status === 404) {
        assert.equal(textContent(slot(alert, 'alert-description')), locale === 'en'
          ? 'Sign in as the owner of the event goal. Praxys does not reveal whether another account has this data.'
          : '请确认已登录赛事目标的所有者账号。Praxys 不会透露其他账号是否有此数据。');
        assert.equal(markupNodes(root, (node) => node.tag === 'button').length, 0);
      } else {
        assert.equal(textContent(slot(root, 'button')), copy.retry);
        assert.match(slot(root, 'button').attributes.class, /\bmin-h-11\b/);
      }
      assertAlertContrast(root, alert);
    });
  }

  test(`UI6 ${locale}: unsupported-version Alert uses compiled slots without recoloring Delete`, () => {
    const root = render(TrailUnknownVersion, {
      draft: { state: 'unknown_schema', composite_revision: fixture.cases.ordinary_confirmed.response.draft.composite_revision },
      onReload: () => assert.fail('SSR must not reload'),
      onClearData: () => assert.fail('SSR must not clear'),
      onRejectData: () => assert.fail('SSR must not reject'),
    }, locale);
    assert.equal(textContent(slot(root, 'alert-title')), locale === 'en'
      ? 'This course review uses an unsupported version' : '此赛道核对使用了不受支持的版本');
    const deletion = markupNodes(root, (node) => node.tag === 'button'
      && textContent(node) === copy.delete)[0];
    const reference = render(Button, { variant: 'destructive', className: 'min-h-11', children: copy.delete });
    assert.equal(deletion.attributes.class, slot(reference, 'button').attributes.class);
    assert.doesNotMatch(deletion.attributes.class, /dark:text-foreground/);
    const css = compileTrailStyles(root);
    for (const dark of [false, true]) {
      setSSRTheme(root, dark);
      assert.equal(css.style(deletion, 'color').value, 'var(--destructive)');
      for (const hover of [false, true]) {
        const opacity = (dark ? 20 : 10) + (hover ? 10 : 0);
        assert.equal(css.style(deletion, 'background-color', { hover }).value,
          `color-mix(in oklab, var(--destructive) ${opacity}%, transparent)`);
      }
    }
    assertAlertContrast(root, slot(root, 'alert'));
  });

  for (const [name, title] of [
    ['validation-summary', copy.errorSummary],
    ['operation-error', locale === 'en' ? 'Trail action did not complete' : '越野操作未完成'],
  ]) {
    test(`UI6 ${locale}: ${name} Alert has compiled slot precedence`, async () => {
      const h = createWorkbenchHarness(fixture.cases.ordinary_confirmed.response.draft, { locale });
      await h.invoke(h.find((node) => node.props?.id === 'trail-race-distance'
        && typeof node.props.onValueChange === 'function').props.onValueChange, 'invalid .');
      await h.invoke(h.find((node) => node.props?.children === copy.save).props.onClick);
      assert.equal(h.calls.length, 0);
      assert.equal(h.focused.at(-1).tag, 'h2');
      assertAlertContrast(h.markup, alertByText(h.markup, title));
    });
  }

  test(`UI6 ${locale}: validation field-jump buttons retain light red, compiled dark foreground, and real focus`, async () => {
    const h = createWorkbenchHarness(fixture.cases.ordinary_confirmed.response.draft, { locale });
    await h.invoke(h.find((node) => node.props?.id === 'trail-race-distance'
      && typeof node.props.onValueChange === 'function').props.onValueChange, 'invalid .');
    await h.invoke(h.find((node) => node.props?.children === copy.save).props.onClick);
    const summary = alertByText(h.markup, copy.errorSummary);
    const links = markupNodes(summary, (node) => node.tag === 'button');
    assert.ok(links.length > 0);
    for (const link of links) {
      assert.ok(textContent(link).includes(copy.fieldError));
      assert.match(link.attributes.class, /\bmin-h-11\b/);
      assertStandaloneContrast(h.markup, link);
    }
    await h.invoke(h.find((node) => node.props?.variant === 'link'
      && node.props?.children?.includes?.(copy.fieldError)).props.onClick);
    assert.equal(h.focused.at(-1).attributes.id, 'trail-race-distance');
    assert.equal(h.focused.at(-1).tag, 'input');
    assert.equal(h.calls.length, 0);
  });

  test(`UI6 ${locale}: export failure Alert uses compiled slots with the unchanged generic copy`, async (t) => {
    const h = createWorkbenchHarness(fixture.cases.ordinary_confirmed.response.draft, { locale });
    const fetch = t.mock.method(globalThis, 'fetch', async (url, init) => {
      assert.equal(url, '/api/me/export');
      assert.equal(init.method, 'GET');
      assert.equal(init.body, undefined);
      return new Response('synthetic server detail must not be exposed', { status: 503 });
    });
    await h.invoke(h.find((node) => node.props?.closeOnClick === false).props.onClick);
    assert.equal(fetch.mock.callCount(), 1);
    assert.equal(h.calls.length, 0);
    const alert = alertByText(h.markup, copy.exportError);
    assert.equal(textContent(alert), copy.exportError);
    assert.equal(slot(alert, 'alert-title'), undefined);
    assert.doesNotMatch(textContent(h.markup), /synthetic server detail/);
    assertAlertContrast(h.markup, alert);
  });

  test(`UI6 ${locale}: FieldShell error retains associations and compiled light/dark treatment`, () => {
    const root = render(FieldShell, {
      id: 'contrast-field', label: copy.raceDistance, description: 'Synthetic help',
      invalidMessage: copy.fieldError, children: React.createElement('input', { id: 'contrast-input' }),
    }, locale);
    const error = byId(root, 'contrast-field-error');
    assert.equal(textContent(error), copy.fieldError);
    const group = markupNodes(root, (node) => node.attributes.role === 'group')[0];
    assert.equal(group.attributes['aria-invalid'], 'true');
    assert.equal(group.attributes['aria-labelledby'], 'contrast-field-label');
    assert.equal(group.attributes['aria-describedby'], 'contrast-field-description contrast-field-error');
    assertStandaloneContrast(root, error);
  });

  test(`UI6 ${locale}: comparison invalid/incomplete buffers have compiled dark error foreground`, () => {
    const draft = fixture.cases.ordinary_confirmed.response.draft;
    for (const distanceKm of ['invalid .', '']) {
      const root = render(TrailPendingComparison, {
        baseDraft: draft, pendingRequest: requestFromDraft(draft),
        pendingInputs: { ...numericInputsFromDraft(draft), distanceKm }, latestDraft: draft,
      }, locale);
      const errors = markupNodes(root, (node) => node.tag === 'p' && textContent(node) === copy.fieldError);
      assert.ok(errors.length > 0, 'invalid or incomplete buffer retains its error');
      assert.ok(textContent(root).includes(distanceKm || '—'));
      for (const error of errors) assertStandaloneContrast(root, error);
    }
  });

  test(`UI6 ${locale}: receipt fail-closed error retains alert/focus behavior and compiled dark foreground`, async () => {
    const response = fixture.cases.contradictory_preferred_weekday.response;
    const h = createWorkbenchHarness(response.draft, {
      locale, respond: () => new Response(JSON.stringify(response)),
    });
    await h.invoke(h.find((node) => node.props?.id === 'trail-readiness-action-mobile').props.onClick);
    const action = locale === 'en' ? 'Resolve the first conflict' : '处理首个冲突';
    await h.invoke(h.find((node) => node.props?.variant === 'link'
      && node.props?.children?.includes?.(action)).props.onClick);
    assert.equal(h.calls.length, 1, 'fail-closed navigation does not issue another request');
    const error = byId(h.markup, 'trail-receipt-error');
    assert.equal(error.attributes.role, 'alert');
    assert.equal(error.attributes.tabindex, '-1');
    assert.equal(h.focused.at(-1), error);
    assert.equal(textContent(error), locale === 'en'
      ? 'Praxys did not provide a safe destination for this action. Review the receipt and retry after reloading.'
      : 'Praxys 未提供可安全跳转的目标。请查看回执并重新加载后重试。');
    assertStandaloneContrast(h.markup, error);
  });
}

test('UI6: destructive menu and confirmation callers keep existing variants, geometry, callbacks and disabled styles', async () => {
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  const h = createWorkbenchHarness(fixture.cases.ordinary_confirmed.response.draft, { respond: () => pending });
  const actions = findElements(h.tree, (node) => node.props?.variant === 'destructive');
  assert.equal(actions.length, 1, 'closed workbench exposes only the destructive Delete menu item');
  assert.equal(actions[0].props.className, 'min-h-11 whitespace-normal');
  assert.equal(typeof actions[0].props.onClick, 'function');
  const confirmation = h.find((node) => node.props?.children === copyFor('en').confirmDelete);
  assert.equal(confirmation.props.variant, 'outline', 'no destructive confirmation without a selected action');
  assert.equal(confirmation.props.disabled, true);
  assert.equal(confirmation.props.className, 'min-h-11 whitespace-normal');
  await h.invoke(actions[0].props.onClick);
  const selected = h.find((node) => node.props?.children === copyFor('en').confirmDelete);
  assert.equal(selected.props.variant, 'destructive');
  assert.equal(selected.props.disabled, false);
  assert.equal(selected.props.className, confirmation.props.className);
  await h.invoke(selected.props.onClick);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].init.method, 'DELETE');
  const busy = h.find((node) => node.props?.children === copyFor('en').confirmDelete);
  assert.equal(busy.props.disabled, true);
  const root = render(busy.type, busy.props);
  const button = slot(root, 'button');
  const css = compileTrailStyles(root);
  for (const dark of [false, true]) {
    setSSRTheme(root, dark);
    assert.equal(css.style(button, 'color').value, 'var(--destructive)');
    assert.equal(css.style(button, 'opacity').value, '50%');
    assert.equal(css.style(button, 'pointer-events').value, 'none');
  }
  finish(new Response(JSON.stringify({ detail: 'Changed' }), { status: 412 }));
  await h.invoke(() => {});
});
