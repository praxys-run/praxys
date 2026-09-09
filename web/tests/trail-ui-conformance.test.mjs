import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import * as React from 'react';
import {
  buildValidatedRequest,
  emptyDraftRequest,
  NUMERIC_INPUT_KEYS_BY_ENVELOPE,
  numericInputsFromDraft,
  reapplyPendingTrailEdits,
  requestFromDraft,
} from '../src/components/trail-course-review/model.ts';
import { known, unknown } from '../src/components/trail-course-review/transitions.ts';
import { parseTrailDraftResponse } from '../src/components/trail-course-review/validation.ts';
import {
  accessibleName,
  byId,
  createWorkbenchHarness,
  findElements,
  loadTrailComponents,
  markupNodes,
  markupTree,
  renderLocalized,
  textContent,
} from './helpers/trail-component-harness.mjs';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');
const fixture = JSON.parse(await read('./fixtures/trail-readiness-service-contract.json'));
const SHA = `sha256:${'e'.repeat(64)}`;
const absent = {
  state: 'absent',
  composite_revision: 'sha256:8adaaec35fb1a6ff05f212e69fc57c9e41bceaa30b65b95a8b3f90120ef5a321',
};
const serverValue = (value) => ({
  ...known(value), provenance: 'athlete_stated', source_revision: SHA,
});
const serverUnknown = () => ({
  ...unknown(), provenance: 'unknown', source_revision: SHA,
});
function currentDraft() {
  const draft = structuredClone(fixture.cases.ordinary_confirmed.response.draft);
  draft.course_demand.fields.distance_meters = serverValue(24700);
  draft.course_demand.fields.total_ascent_m = serverValue(618);
  return draft;
}
function newerDraft(base) {
  const latest = structuredClone(base);
  latest.composite_revision = SHA;
  latest.revision_bindings.composite_revision = SHA;
  latest.course_demand.fields.total_ascent_m = serverValue(1850);
  assert.equal(parseTrailDraftResponse(latest)?.state, 'current');
  return latest;
}
const load = loadTrailComponents();
const controls = load('components/trail-course-review/controls.tsx');
const { useTrailCourseReviewCopy } = load('components/trail-course-review/copy.tsx');

function localeCopy(locale = 'en') {
  let labels;
  function Probe() {
    labels = useTrailCourseReviewCopy();
    return null;
  }
  renderLocalized(React.createElement(Probe), locale);
  return labels;
}
function renderControl(Component, props, locale = 'en') {
  return markupTree(renderLocalized(React.createElement(Component, props), locale));
}
function comparisonModel(base, pending, inputs, latest) {
  return load('components/trail-course-review/comparison-model.ts')
    .buildTrailComparison(base, pending, inputs, latest);
}
function comparisonMarkup(base, pending, inputs, latest, locale = 'en') {
  const { TrailPendingComparison } = load('components/trail-course-review/comparison.tsx');
  return renderControl(TrailPendingComparison, {
    baseDraft: base, pendingRequest: pending, pendingInputs: inputs, latestDraft: latest,
  }, locale);
}
function comparisonRow(markup, label) {
  const heading = markupNodes(markup, (node) => node.tag === 'h3'
    && textContent(node) === label)[0];
  assert.ok(heading, `comparison row: ${label}`);
  return heading.parent;
}
function comparisonValues(row) {
  const pairs = markupNodes(row, (node) => node.tag === 'dl')[0];
  assert.ok(pairs, 'comparison has ordered labeled pairs');
  return pairs.children.filter((node) => typeof node !== 'string')
    .map((pair) => textContent(pair.children.find((node) => node.tag === 'dd')));
}
function selectedText(markup, id) {
  const value = markupNodes(byId(markup, id), (node) => node.attributes['data-slot'] === 'select-value')[0];
  assert.ok(value);
  return textContent(value);
}

test('UI1: real Base UI enum triggers show localized labels on the first render and locale change', () => {
  for (const [key, optionKey] of [
    ['single_day', 'eventFormatOptions'],
    ['non_ultra', 'distanceFamilyOptions'],
    ['performance', 'planningIntentOptions'],
  ]) {
    let selected = known(key);
    for (const locale of ['en', 'zh', 'en']) {
      const labels = localeCopy(locale);
      const props = {
        id: 'test-enum', envelope: selected, options: labels[optionKey],
        unknownLabel: labels.copy.unknown, placeholder: labels.copy.choose,
        onChange: (next) => { selected = next; },
      };
      const markup = renderControl(controls.EnumEditor, props, locale);
      const trigger = byId(markup, 'test-enum');
      assert.equal(selectedText(markup, 'test-enum'), labels[optionKey].find((option) => option.value === key).label);
      assert.match(trigger.attributes.class, /min-h-11/);
      assert.deepEqual(selected, known(key));
    }
  }
  const labels = localeCopy();
  const props = {
    id: 'test-enum', envelope: unknown(), options: labels.eventFormatOptions,
    unknownLabel: labels.copy.unknown, placeholder: labels.copy.choose,
    onChange: () => assert.fail('rendering must not manufacture a value'),
  };
  assert.equal(selectedText(renderControl(controls.EnumEditor, props), 'test-enum'), labels.copy.choose);
});

test('UI1: preferred weekday is localized while canonical selection and omission survive rerender', async () => {
  const draft = currentDraft();
  draft.constraints.preferred_longest_weekday = 6;
  const h = createWorkbenchHarness(draft);
  for (const [locale, expected] of [['en', 'Saturday'], ['zh', '星期六'], ['en', 'Saturday']]) {
    assert.equal(selectedText(h.render(locale), 'trail-preferred-day'), expected);
  }
  const select = h.find((node) => typeof node.props?.onValueChange === 'function'
    && node.props.value === '6');
  await h.invoke(select.props.onValueChange, 'none');
  assert.equal(selectedText(h.markup, 'trail-preferred-day'), 'No preference');
  await h.invoke(h.find((node) => node.props?.children === 'Save changes').props.onClick);
  const submitted = JSON.parse(h.calls.find((call) => call.kind === 'api').init.body);
  assert.equal(Object.hasOwn(submitted.constraints, 'preferred_longest_weekday'), false);
});

test('UI2: 412 shows actual latest versus restore values before request-free field-level restore', async () => {
  const base = currentDraft();
  const latest = newerDraft(base);
  const h = createWorkbenchHarness(base, { latest });
  await h.invoke(h.find((node) => node.type === h.load('components/trail-course-review/controls.tsx').NumberEditor
    && node.props.id === 'trail-race-distance').props.onValueChange, '25');
  await h.invoke(h.find((node) => node.props?.children === 'Save changes').props.onClick);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, '/api/plan/trail/draft');
  assert.equal(h.calls[0].init.method, 'PUT');
  assert.equal(byId(h.markup, 'trail-pending-comparison'), undefined, 'no fabricated latest data before read');
  await h.invoke(h.find((node) => node.props?.children === 'Review latest version').props.onClick);
  const comparison = byId(h.markup, 'trail-pending-comparison');
  assert.ok(comparison, 'default-visible inline comparison after validated latest');
  const distance = comparisonRow(comparison, 'Race distance');
  assert.deepEqual(comparisonValues(distance), ['24.7 km', '25 km']);
  assert.match(textContent(distance), /Pending changes/);
  const ascent = comparisonRow(comparison, 'Total ascent');
  assert.deepEqual(comparisonValues(ascent), ['1850 m', '1850 m']);
  assert.match(textContent(ascent), /Changed on server/);
  assert.doesNotMatch(textContent(ascent), /Pending changes|618/);
  assert.doesNotMatch(textContent(comparison), /sha256:|event_id|source_revision|history_statistics/);
  const before = h.calls.length;
  await h.invoke(h.find((node) => node.props?.children === 'Restore pending changes').props.onClick);
  assert.equal(h.calls.length, before, 'restore neither requests, saves, nor confirms');
  assert.equal(byId(h.markup, 'trail-race-distance').attributes.value, '25');
  assert.equal(byId(h.markup, 'trail-total-ascent').attributes.value, '1850');
  assert.equal(Object.hasOwn(byId(h.markup, 'trail-readiness-action-mobile').attributes, 'disabled'), true);
  assert.equal(h.focused.length, 0, 'comparison and restore do not move focus');
});

test('UI2: comparison uses the existing restore result including buffer-only and same-field conflicts', () => {
  const base = currentDraft();
  const latest = newerDraft(base);
  latest.course_demand.fields.distance_meters = serverValue(26000);
  const pending = requestFromDraft(base);
  const inputs = { ...numericInputsFromDraft(base), distanceKm: '25' };
  const result = comparisonModel(base, pending, inputs, latest);
  assert.deepEqual(result.restored, reapplyPendingTrailEdits(base, pending, inputs, latest));
  assert.deepEqual(result.rows.map(({ key, pending, changedOnServer }) => ({
    key, pending, changedOnServer,
  })), [
    { key: 'course.distance_meters', pending: true, changedOnServer: true },
    { key: 'course.total_ascent_m', pending: false, changedOnServer: true },
  ]);
  const markup = comparisonMarkup(base, pending, inputs, latest);
  assert.deepEqual(comparisonValues(comparisonRow(markup, 'Race distance')), ['26 km', '25 km']);
});

test('UI2: every numeric buffer participates in the union and retains its exact text through restore', () => {
  for (const base of [currentDraft(), absent]) {
    const pending = requestFromDraft(base);
    const baseInputs = numericInputsFromDraft(base);
    const seen = new Set();
    for (const [fieldKey, keys] of Object.entries(NUMERIC_INPUT_KEYS_BY_ENVELOPE)) {
      for (const key of keys) {
        seen.add(key);
        const inputs = { ...baseInputs, [key]: 'invalid .' };
        const result = comparisonModel(base, pending, inputs, base);
        assert.deepEqual(result.rows, [{ key: fieldKey, pending: true, changedOnServer: false }], key);
        assert.deepEqual(result.restored, reapplyPendingTrailEdits(base, pending, inputs, base), key);
        const markup = comparisonMarkup(base, pending, inputs, base);
        assert.ok(textContent(markup).includes('invalid .'), key);
        assert.ok(textContent(markup).includes(localeCopy().copy.fieldError), key);
      }
    }
    assert.deepEqual([...seen].sort(), Object.keys(baseInputs).sort());
  }
});

test('UI2: an emptied known numeric buffer remains visibly missing rather than an old or latest number', () => {
  const base = currentDraft();
  const latest = newerDraft(base);
  latest.course_demand.fields.distance_meters = serverValue(26000);
  const pending = requestFromDraft(base);
  const inputs = { ...numericInputsFromDraft(base), distanceKm: '' };
  const markup = comparisonMarkup(base, pending, inputs, latest);
  const after = comparisonValues(comparisonRow(markup, 'Race distance'))[1];
  assert.ok(after.startsWith('— km'));
  assert.ok(after.includes(localeCopy().copy.fieldError));
  assert.doesNotMatch(after, /24\.7|26|I don't know yet/);
});

test('UI2: known-empty, known-null, unknown and omitted preference stay distinct', () => {
  const base = currentDraft();
  base.constraints.preferred_longest_weekday = 6;
  const latest = newerDraft(base);
  latest.course_demand.fields.optional_context.support.max_aid_station_gap_m = serverValue(2000);
  const pending = requestFromDraft(base);
  pending.constraints.unavailable_dates = known([]);
  base.constraints.unavailable_dates = serverUnknown();
  pending.constraints.preferred_longest_weekday = undefined;
  pending.course_demand.fields.optional_context.support.mandatory_gear = known([]);
  base.course_demand.fields.optional_context.support.mandatory_gear = serverUnknown();
  pending.course_demand.fields.optional_context.support.max_aid_station_gap_m = known(null);
  base.course_demand.fields.optional_context.support.max_aid_station_gap_m = serverUnknown();
  const inputs = numericInputsFromDraft(base);
  const result = comparisonModel(base, pending, inputs, latest);
  assert.deepEqual(result.restored, reapplyPendingTrailEdits(base, pending, inputs, latest));
  for (const locale of ['en', 'zh']) {
    const { copy } = localeCopy(locale);
    const markup = comparisonMarkup(base, pending, inputs, latest, locale);
    assert.equal(comparisonValues(comparisonRow(markup, copy.unavailableDates))[1], copy.noDates);
    assert.equal(comparisonValues(comparisonRow(markup, copy.requiredEquipment))[1], copy.noEquipment);
    assert.equal(comparisonValues(comparisonRow(markup, copy.aidGap))[1], copy.notApplicable);
    assert.equal(comparisonValues(comparisonRow(markup, copy.preferredDay))[1], copy.noPreference);
    base.course_demand.fields.optional_context.support.max_aid_station_gap_m = serverValue(null);
    pending.course_demand.fields.optional_context.support.max_aid_station_gap_m = unknown();
    const unknownMarkup = comparisonMarkup(base, pending, inputs, latest, locale);
    assert.equal(comparisonValues(comparisonRow(unknownMarkup, copy.aidGap))[1], copy.unknown);
    base.course_demand.fields.optional_context.support.max_aid_station_gap_m = serverUnknown();
    pending.course_demand.fields.optional_context.support.max_aid_station_gap_m = known(null);
  }
});

test('UI2: incomplete and invalid buffers are displayed verbatim with existing validation copy', () => {
  const base = currentDraft();
  const latest = newerDraft(base);
  const pending = requestFromDraft(base);
  const inputs = {
    ...numericInputsFromDraft(base),
    distanceKm: 'abc',
    planningMinimumHours: '1',
    planningMinimumMinutes: '',
    gradeBelowNeg10: '1.',
    temperatureMinimumC: '-',
    aidStationGapKm: '2e3',
    fuelingHours: '',
    fuelingMinutes: '5',
  };
  for (const locale of ['en', 'zh']) {
    const { copy, gradeLabels } = localeCopy(locale);
    const markup = comparisonMarkup(base, pending, inputs, latest, locale);
    const distance = comparisonRow(markup, copy.raceDistance);
    assert.match(comparisonValues(distance)[1], /abc km/);
    assert.ok(textContent(distance).includes(copy.fieldError));
    const allText = textContent(markup);
    for (const raw of ['1.', '-', '2e3']) assert.ok(allText.includes(raw), raw);
    for (const label of [copy.planningMinimum, copy.planningMaximum, copy.hours, copy.minutes, ...Object.values(gradeLabels)]) {
      assert.ok(allText.includes(label), label);
    }
    const result = comparisonModel(base, pending, inputs, latest);
    assert.deepEqual(result.restored, reapplyPendingTrailEdits(base, pending, inputs, latest));
    assert.ok(buildValidatedRequest(result.restored.request, result.restored.numericInputs).issues.length > 0);
  }
});

test('UI2: source/revision-only changes are not field changes; absence and unsupported latest fail closed', () => {
  const base = currentDraft();
  const latest = structuredClone(base);
  latest.composite_revision = SHA;
  latest.revision_bindings.composite_revision = SHA;
  latest.revision_bindings.section_confirmations[0].current_revision = SHA;
  latest.course_demand.fields.total_ascent_m.source_revision = SHA;
  latest.course_demand.fields.total_ascent_m.provenance = 'course_verified';
  const pending = requestFromDraft(base);
  const inputs = numericInputsFromDraft(base);
  assert.deepEqual(comparisonModel(base, pending, inputs, latest).rows, []);
  for (const locale of ['en', 'zh']) {
    const { copy } = localeCopy(locale);
    assert.ok(textContent(comparisonMarkup(base, pending, inputs, latest, locale))
      .includes(copy.noEditableChanges));
  }
  for (const unavailable of [null, { state: 'unknown_schema', namespace: {}, composite_revision: SHA }]) {
    assert.equal(comparisonModel(base, pending, inputs, unavailable), null);
  }
  const result = comparisonModel(absent, emptyDraftRequest(), numericInputsFromDraft(absent), latest);
  assert.ok(result.rows.length > 0);
  assert.deepEqual(result.restored, reapplyPendingTrailEdits(absent, emptyDraftRequest(), numericInputsFromDraft(absent), latest));
  const deleted = comparisonModel(base, pending, inputs, absent);
  assert.ok(deleted.rows.length > 0);
  assert.deepEqual(deleted.restored, reapplyPendingTrailEdits(base, pending, inputs, absent));
});

test('UI2: comparison pairs have mobile-first DOM order, units, no table, editors or focus side effects', async () => {
  const base = currentDraft();
  const inputs = { ...numericInputsFromDraft(base), distanceKm: '25' };
  const markup = comparisonMarkup(base, requestFromDraft(base), inputs, newerDraft(base));
  const row = comparisonRow(markup, 'Race distance');
  assert.deepEqual(markupNodes(row, (node) => node.tag === 'dt').map(textContent), [
    'Latest saved', 'After restore (unsaved)',
  ]);
  assert.equal(markupNodes(markup, (node) => ['input', 'button', 'select', 'table'].includes(node.tag)).length, 0);
  assert.ok(markupNodes(markup, (node) => node.attributes.class?.includes('sm:grid-cols-2')).length > 0);
  const source = await read('../src/components/trail-course-review/comparison.tsx');
  assert.doesNotMatch(source, /autoFocus|\.focus\(|truncate|line-clamp|whitespace-nowrap/);
});

test('UI2: pending offline Save stays memory-only and makes no API request', async () => {
  const h = createWorkbenchHarness(currentDraft(), { online: false });
  const number = h.find((node) => node.props?.id === 'trail-race-distance'
    && typeof node.props.onValueChange === 'function');
  await h.invoke(number.props.onValueChange, '25');
  await h.invoke(h.find((node) => node.props?.children === 'Save changes').props.onClick);
  assert.deepEqual(h.calls, []);
  assert.equal(byId(h.markup, 'trail-race-distance').attributes.value, '25');
  assert.ok(textContent(h.markup).includes(localeCopy().copy.offline));
});

test('UI2: comparison adds only the four exact accepted EN/zh labels', () => {
  const pairs = {
    latestSaved: ['Latest saved', '最新保存值'],
    afterRestore: ['After restore (unsaved)', '恢复后（未保存）'],
    changedOnServer: ['Changed on server', '服务端已更改'],
    noEditableChanges: ['No editable values changed.', '可编辑值未发生变化。'],
  };
  for (const [locale, index] of [['en', 0], ['zh', 1]]) {
    const { copy } = localeCopy(locale);
    for (const [key, values] of Object.entries(pairs)) assert.equal(copy[key], values[index]);
  }
});

test('UI3: affected local muted text and portal descriptions retain dark foreground contrast guards', async () => {
  for (const filename of ['controls.tsx', 'states.tsx', '../TrailCourseReview.tsx']) {
    const source = await read(`../src/components/trail-course-review/${filename}`);
    const localMutedClasses = [...source.matchAll(/className="([^"]*\btext-muted-foreground\b[^"]*)"/g)];
    assert.ok(localMutedClasses.length > 0);
    for (const [, classes] of localMutedClasses) {
      assert.match(classes, /dark:(?:data-placeholder:)?text-foreground\/80/, `${filename}: ${classes}`);
    }
    for (const [, classes] of source.matchAll(/<DialogDescription className="([^"]*)"/g)) {
      assert.match(classes, /dark:text-foreground\/80/, `${filename}: dialog portal text`);
    }
  }
  const component = await read('../src/components/TrailCourseReview.tsx');
  const stale = component.slice(component.indexOf('{staleConflict ? ('), component.indexOf('{readinessSummary('));
  assert.match(stale, /<AlertDescription className="[^"]*dark:text-foreground\/80/);
});

test('UI4: all actual SSR label-for associations resolve to real single controls', async () => {
  for (const draft of [currentDraft(), absent]) {
    const h = createWorkbenchHarness(draft);
    await h.invoke(h.find((node) => node.props?.sectionKey === 'section.optional-context'
      && typeof node.props.onOpenChange === 'function').props.onOpenChange, true);
    const labels = markupNodes(h.markup, (node) => node.tag === 'label' && node.attributes.for);
    assert.ok(labels.length > 10);
    for (const label of labels) {
      const target = byId(h.markup, label.attributes.for);
      assert.ok(target, `${textContent(label)} must have an existing target`);
      assert.ok(['button', 'input', 'select', 'textarea', 'output', 'meter', 'progress'].includes(target.tag),
        `${textContent(label)} labels ${target.tag}, not a single control`);
    }
    assert.equal(byId(h.markup, 'trail-event-identity-label').tag, 'h3');
    for (const input of markupNodes(h.markup, (node) => node.tag === 'input'
      && node.attributes.id?.startsWith('trail-grade-'))) {
      assert.equal(markupNodes(h.markup, (node) => node.tag === 'label'
        && node.attributes.for === input.attributes.id).length, 1, input.attributes.id);
    }
  }
});

test('UI4: compound groups retain per-control names, descriptions, selected states and targets', () => {
  const { copy, footingOptions } = localeCopy();
  for (const [Component, id, label, props] of [
    [controls.TriStateEditor, 'tri-state', copy.hands, {
      envelope: known(true), yesLabel: copy.yes, noLabel: copy.no, unknownLabel: copy.notSure,
    }],
    [controls.DurationEditor, 'duration', copy.weeklyTime, {
      unknown: false, hours: '1', minutes: '30', hoursLabel: copy.hours, minutesLabel: copy.minutes,
      unknownLabel: copy.unknown,
    }],
    [controls.MultiSelectEditor, 'footing', copy.footing, {
      envelope: known(['firm_smooth']), options: footingOptions, unknownLabel: copy.unknown,
    }],
  ]) {
    const markup = renderControl(controls.FieldShell, {
      id, label, description: 'Visible help', invalidMessage: copy.fieldError,
      children: React.createElement(Component, { id, ...props, onChange: () => {} }),
    });
    const group = markupNodes(markup, (node) => node.attributes.role === 'group'
      && node.attributes['aria-describedby']?.includes(`${id}-error`))[0];
    assert.ok(group);
    assert.equal(accessibleName(markup, group), label);
    assert.ok(textContent(byId(markup, `${id}-error`)).includes(copy.fieldError));
    assert.ok(group.attributes['aria-describedby'].includes(`${id}-description`));
    const target = byId(markup, id);
    assert.ok(['button', 'input'].includes(target.tag), 'group focus resolves to an actual choice/input');
    if (Component === controls.TriStateEditor) {
      const buttons = markupNodes(markup, (node) => node.tag === 'button');
      assert.deepEqual(buttons.map((node) => accessibleName(markup, node)), [copy.yes, copy.no, copy.notSure]);
      assert.equal(buttons[0].attributes['aria-pressed'], 'true');
    }
    if (Component === controls.DurationEditor) {
      assert.equal(accessibleName(markup, target), copy.hours);
      assert.equal(accessibleName(markup, byId(markup, `${id}-minutes`)), copy.minutes);
    }
  }
});

test('UI4: validation summary opens a group and focuses its real choice, not its container', async () => {
  const h = createWorkbenchHarness(currentDraft());
  const multiselect = h.find((node) => node.props?.id === 'trail-course-footing'
    && typeof node.props.onChange === 'function');
  await h.invoke(multiselect.props.onChange, known([]));
  await h.invoke(h.find((node) => node.props?.children === 'Save changes').props.onClick);
  assert.equal(h.calls.length, 0);
  assert.equal(h.focused.at(-1).tag, 'h2');
  const errorLink = h.find((node) => node.props?.variant === 'link'
    && findElements(node, () => true).some((child) => child.props?.children?.includes?.('Course footing')));
  await h.invoke(errorLink.props.onClick);
  assert.equal(h.focused.at(-1).tag, 'button');
  assert.equal(h.focused.at(-1).attributes.id, 'trail-course-footing');
});

test('UI5: every actual Trail skeleton including mapped rows opts out of reduced-motion pulse', () => {
  const { TrailCourseReviewSkeleton } = load('components/trail-course-review/states.tsx');
  const markup = renderControl(TrailCourseReviewSkeleton, {});
  const skeletons = markupNodes(markup, (node) => node.attributes['data-slot'] === 'skeleton');
  assert.equal(skeletons.length, 20);
  for (const skeleton of skeletons) {
    assert.match(skeleton.attributes.class, /\banimate-pulse\b/);
    assert.match(skeleton.attributes.class, /\bmotion-reduce:animate-none\b/);
  }
  assert.equal(markupNodes(markup, (node) => node.attributes['aria-busy'] === 'true').length, 1);
});
