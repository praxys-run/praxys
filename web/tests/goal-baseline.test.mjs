import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web goal page switches into the baseline pilot flow', async () => {
  const [page, panel] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../src/components/GoalBaselinePanel.tsx'),
  ]);

  assert.match(page, /data\.goal_kind === 'performance_5k'/);
  assert.match(page, /<GoalBaselinePanel/);
  assert.match(panel, /\/api\/goal\/baseline\/history\/confirm/);
  assert.match(panel, /\/api\/goal\/baseline\/test/);
  assert.match(panel, /no meaningful-change threshold/i);
  assert.match(panel, /maximal-effort/i);
  assert.match(panel, /Arbitrary 5K segments/i);
});

test('miniapp ships the same baseline semantics and endpoints', async () => {
  const [page, component, template] = await Promise.all([
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/components/goal-baseline/index.ts'),
    read('../../miniapp/components/goal-baseline/index.wxml'),
  ]);

  assert.match(page, /goalKind === 'performance_5k'/);
  assert.match(page, /<goal-baseline/);
  assert.match(component, /\/api\/goal\/baseline\/history\/confirm/);
  assert.match(component, /\/api\/goal\/baseline\/test/);
  assert.match(component, /候选检索永远不等于资格认定/);
  assert.match(component, /最大努力|maximal effort/i);
  assert.match(template, /baseline\.test\.state === 'not_offered'/);
  assert.match(template, /baseline\.test\.can_schedule && baseline\.test\.state !== 'not_offered' && baseline\.test\.state !== 'scheduled'/);
});

test('web and miniapp share the generated baseline contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const required = [
    'type GoalKind = \'race\' | \'continuous\' | \'performance_5k\'',
    'interface GoalBaselineResponse',
    'interface GoalBaselineMutationResponse',
    'goal_kind?: GoalKind',
    'baseline?: GoalBaselineResponse',
    'optional_test_is_maximal_effort: true',
    'no_meaningful_change_threshold_yet: true',
  ];

  for (const marker of required) {
    assert.match(webTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(miniTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});
