import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web goal page switches into the baseline pilot flow', async () => {
  const [page, panel] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../src/components/GoalBaselinePanel.tsx'),
  ]);

  assert.match(page, /data\.goal_kind === 'performance_5k' \|\| data\.goal_kind === 'performance_10k'/);
  assert.match(page, /<GoalBaselinePanel/);
  assert.match(panel, /\/api\/goal\/baseline\/history\/confirm|\/api\/plan\/road-10k\/baseline\/history\/confirm/);
  assert.match(panel, /\/api\/goal\/baseline\/test/);
  assert.match(panel, /no meaningful-change threshold/i);
  assert.match(panel, /maximal-effort|optional benchmark/i);
  assert.match(panel, /Arbitrary 5K segments|Passive fastest 10K splits/i);
});

test('miniapp ships the same baseline semantics and endpoints', async () => {
  const [page, component, template, zhCatalog] = await Promise.all([
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/components/goal-baseline/index.ts'),
    read('../../miniapp/components/goal-baseline/index.wxml'),
    read('../src/locales/zh/messages.po'),
  ]);

  assert.match(page, /goalKind === 'performance_5k' \|\| goalKind === 'performance_10k'/);
  assert.match(page, /<goal-baseline/);
  assert.match(page, /id="goal-baseline-panel"/);
  assert.match(component, /\/api\/goal\/baseline\/history\/confirm/);
  assert.match(component, /\/api\/goal\/baseline\/test/);
  assert.match(component, /candidateHint: t\('Retrieval is never qualification/);
  assert.match(component, /hasCandidates: candidateRows\.length > 0/);
  assert.match(component, /maximal-effort/i);
  assert.match(zhCatalog, /检索到候选活动不代表其已合格/);
  assert.match(template, /wx:if="\{\{hasCandidates\}\}"/);
  assert.match(template, /baseline\.test\.state === 'not_offered'/);
  assert.match(template, /baseline\.test\.can_schedule && baseline\.test\.state !== 'not_offered' && baseline\.test\.state !== 'scheduled'/);
});

test('web and miniapp share the generated baseline contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const required = [
    'performance_10k',
    'interface GoalBaselineResponse',
    'interface GoalBaselineMutationResponse',
    'goal_kind?: GoalKind',
    'baseline?: PerformanceGoalBaselineResponse',
    'optional_test_is_maximal_effort: true',
    'no_meaningful_change_threshold_yet: true',
  ];

  for (const marker of required) {
    assert.match(webTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(miniTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});
