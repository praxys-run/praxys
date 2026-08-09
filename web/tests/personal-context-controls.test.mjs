import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  buildPersonalContextDraftRequest,
  createPersonalContextDraft,
  draftFromContextItem,
  personalContextEvidenceIds,
  personalContextNarrativeAvailable,
} from '../src/lib/personal-context.ts';
import {
  EXECUTION_CATEGORIES,
  TEMPORARY_CATEGORIES,
} from '../../miniapp/utils/personal-context.ts';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('temporary context builds the bounded API contract', () => {
  const draft = {
    ...createPersonalContextDraft(
      'temporary_constraint',
      new Date('2026-08-09T12:00:00Z'),
    ),
    category: 'caregiving',
    startDate: '2026-08-10',
    endDate: '2026-08-16',
    affectedDays: ['monday', 'wednesday'],
    maximumAvailableMinutes: '45',
    narrative: 'Availability changes this week.',
  };

  const request = buildPersonalContextDraftRequest(
    draft,
    new Date('2026-08-09T12:00:00Z'),
  );

  assert.equal(request.kind, 'temporary_constraint');
  assert.equal(request.purpose, 'plan_adjustment');
  assert.equal(request.payload.category, 'caregiving');
  assert.deepEqual(request.payload.fields.affected_days, [
    'monday',
    'wednesday',
  ]);
  assert.equal(request.payload.fields.maximum_available_minutes, 45);
  assert.equal(request.linked_subject_type, undefined);
  assert.equal(
    new Date(request.expires_at).getTime()
      - new Date(request.starts_at).getTime(),
    (7 * 24 * 60 * 60 * 1000) - 1,
  );
  assert.equal(
    new Date(request.purge_after).getTime()
      - new Date(request.expires_at).getTime(),
    30 * 24 * 60 * 60 * 1000,
  );
  assert.equal(request.narrative_purge_at, '2026-09-08T12:00:00.000Z');
});

test('execution explanation links only the selected canonical workout', () => {
  const draft = {
    ...createPersonalContextDraft('execution_explanation'),
    category: 'prefer_not_to_say',
    workoutId: 'workout-123',
    workoutDate: '2026-08-08',
    workoutStatus: 'missed',
  };

  const request = buildPersonalContextDraftRequest(
    draft,
    new Date('2026-08-09T12:00:00Z'),
  );

  assert.equal(request.kind, 'execution_explanation');
  assert.equal(request.purpose, 'execution_interpretation');
  assert.equal(request.linked_subject_type, 'workout');
  assert.equal(request.linked_subject_id, 'workout-123');
  assert.deepEqual(request.payload.fields, {
    affected_dates: ['2026-08-08'],
    workout_status: 'missed',
  });
  assert.equal(request.payload.narrative, undefined);
});

test('private context evidence IDs are strictly filtered', () => {
  assert.deepEqual(
    personalContextEvidenceIds({
      context_item_ids: ['one', null, '', 2, 'two'],
    }),
    ['one', 'two'],
  );
  assert.deepEqual(personalContextEvidenceIds({}), []);
});

test('stored context dates round-trip through the local calendar', () => {
  const startsAt = new Date(2026, 7, 10, 0, 0, 0);
  const expiresAt = new Date(2026, 7, 16, 23, 59, 59);
  const draft = draftFromContextItem({
    kind: 'temporary_constraint',
    payload: { category: 'caregiving', fields: {} },
    starts_at: startsAt.toISOString(),
    expires_at: expiresAt.toISOString(),
    linked_subject_type: null,
    linked_subject_id: null,
  });

  assert.equal(draft.startDate, '2026-08-10');
  assert.equal(draft.endDate, '2026-08-16');
});

test('AI note disclosure ends at the narrative purge deadline', () => {
  const item = {
    has_narrative: true,
    narrative_purged_at: null,
    narrative_purge_at: '2026-09-08T12:00:00.000Z',
  };
  assert.equal(
    personalContextNarrativeAvailable(
      item,
      new Date('2026-09-08T11:59:59.000Z'),
    ),
    true,
  );
  assert.equal(
    personalContextNarrativeAvailable(
      item,
      new Date('2026-09-08T12:00:00.000Z'),
    ),
    false,
  );
});

test('miniapp exposes every bounded category for either context path', () => {
  for (const categories of [TEMPORARY_CATEGORIES, EXECUTION_CATEGORIES]) {
    assert.ok(categories.includes('less_time'));
    assert.ok(categories.includes('fatigue'));
    assert.ok(categories.includes('illness'));
    assert.ok(categories.includes('prefer_not_to_say'));
  }
});

test('web and miniapp expose the same private lifecycle controls', async () => {
  const [web, mini, template, trainingTemplate] = await Promise.all([
    read('../src/components/PersonalContextPanel.tsx'),
    read('../../miniapp/components/personal-context/index.ts'),
    read('../../miniapp/components/personal-context/index.wxml'),
    read('../../miniapp/pages/training/index.wxml'),
  ]);
  const endpoints = [
    '/api/personal-context/preview',
    '/api/personal-context/confirm',
    '/api/personal-context/export',
    '/correct',
    '/ai-consent',
    '/expire',
  ];

  for (const endpoint of endpoints) {
    assert.match(web, new RegExp(endpoint.replaceAll('/', '\\/')));
    assert.match(mini, new RegExp(endpoint.replaceAll('/', '\\/')));
  }
  assert.match(web, /include_history=false&include_narrative=false/);
  assert.match(mini, /include_history=false&include_narrative=false/);
  assert.match(template, /checked="\{\{purposeConfirmed\}\}"/);
  assert.match(template, /checked="\{\{aiPermissionConfirmed\}\}"/);
  assert.match(trainingTemplate, /<personal-context \/>/);
});
