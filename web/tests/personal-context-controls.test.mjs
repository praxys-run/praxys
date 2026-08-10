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
import { setTabBarHidden } from '../../miniapp/utils/tabbar.ts';

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

test('miniapp context sheets hide the custom tab bar', async () => {
  const updates = [];
  const tabBar = {
    setData(data) {
      updates.push(data);
    },
  };

  setTabBarHidden({
    getTabBar(callback) {
      callback(tabBar);
    },
  }, true);
  setTabBarHidden({
    getTabBar() {
      return tabBar;
    },
  }, false);

  assert.deepEqual(updates, [{ hidden: true }, { hidden: false }]);

  const [tabBarTemplate, contextSource] = await Promise.all([
    read('../../miniapp/custom-tab-bar/index.wxml'),
    read('../../miniapp/components/personal-context/index.ts'),
  ]);
  assert.match(tabBarTemplate, /wx:if="\{\{!hidden\}\}"/);
  assert.match(contextSource, /sheetOpen\(sheetOpen: boolean\)/);
});

test('AI consent disclosure stays explicit and bilingual', async () => {
  const [web, mini, legal, miniLegal] = await Promise.all([
    read('../src/components/PersonalContextPanel.tsx'),
    read('../../miniapp/components/personal-context/index.ts'),
    read('../src/lib/legal.ts'),
    read('../../miniapp/utils/legal.ts'),
  ]);

  for (const source of [web, mini]) {
    const normalized = source.replace(/\s+/g, ' ');
    assert.match(
      normalized,
      /inputs and outputs are not available to OpenAI or used to train foundation models/,
    );
    assert.match(normalized, /Praxys does not grant that permission/);
    assert.match(normalized, /abuse monitoring under Azure terms/);
  }

  assert.match(
    legal,
    /learn\.microsoft\.com\/en-us\/azure\/foundry\/responsible-ai\/openai\/data-privacy/,
  );
  for (const source of [legal, miniLegal]) {
    assert.match(source, /计划个性化信息/);
    assert.doesNotMatch(source, /私密计划背景信息/);
  }
});

test('personal-context Chinese uses natural product language', async () => {
  const [catalog, miniExtra, miniSource] = await Promise.all([
    read('../src/locales/zh/messages.po'),
    read('../../miniapp/utils/i18n-extra.ts'),
    read('../../miniapp/components/personal-context/index.ts'),
  ]);

  assert.match(
    catalog,
    /msgid "Plan context"\r?\nmsgstr "计划个性化信息"/,
  );
  assert.match(
    catalog,
    /msgid "Add availability"\r?\nmsgstr "调整可训练时间"/,
  );
  assert.match(
    catalog,
    /msgid "Explain a workout"\r?\nmsgstr "说明训练情况"/,
  );
  assert.match(
    catalog,
    /msgid "Private note \(optional\)"\r?\nmsgstr "补充说明（选填）"/,
  );
  assert.doesNotMatch(
    catalog,
    /msgstr "(?:计划上下文|私密上下文|解释一条训练|添加可用时间)"/,
  );
  assert.match(miniExtra, /'Manage private context': '管理计划个性化信息'/);
  assert.match(miniSource, /affected_dates: \(\) => t\('Affected dates'\)/);
  assert.match(miniSource, /\.map\(disclosedFieldLabel\)/);
});

test('MCP approval uses opaque state and explicit first-party controls', async () => {
  const [page, app, login] = await Promise.all([
    read('../src/pages/McpAuthorization.tsx'),
    read('../src/App.tsx'),
    read('../src/pages/Login.tsx'),
  ]);

  assert.match(app, /path="\/mcp\/authorize"/);
  assert.match(page, /\/api\/auth\/mcp\/handoffs\//);
  assert.match(page, /decide\('approved'\)/);
  assert.match(page, /decide\('denied'\)/);
  assert.match(page, /Skeleton/);
  assert.match(page, /Alert/);
  assert.match(page, /aria-live="polite"/);
  for (const source of [app, login, page]) {
    assert.doesNotMatch(source, /cli_callback/);
    assert.doesNotMatch(source, /\?token=\$\{/);
  }
});
