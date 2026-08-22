import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const read = (path) => fs.readFile(new URL(path, root), 'utf8');

test('Road 10K stays mechanically absent from web and miniapp surfaces', async () => {
  const sources = await Promise.all([
    read('web/src/App.tsx'),
    read('web/src/pages/Goal.tsx'),
    read('web/src/pages/Training.tsx'),
    read('web/src/pages/Settings.tsx'),
    read('miniapp/pages/goal/index.wxml'),
    read('miniapp/pages/goal/index.json'),
    read('miniapp/pages/training/index.wxml'),
    read('miniapp/pages/training/index.json'),
    read('miniapp/pages/settings/index.wxml'),
    read('miniapp/pages/settings/index.json'),
  ]);

  for (const source of sources) {
    assert.doesNotMatch(source, /Road10KControlledOptIn|road-10k-controlled-opt-in|\/api\/road-10k/);
  }
});

test('Plan-start allowlists reject dormant Road capability discovery', async () => {
  const [webPlanStart, miniPlanStart] = await Promise.all([
    read('web/src/components/PlanStart.tsx'),
    read('miniapp/components/outdoor-5k-plan-start/index.ts'),
  ]);

  for (const source of [webPlanStart, miniPlanStart]) {
    const declaration = source.match(/const SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_IDS = new Set\(\[([\s\S]*?)\]\);/);
    assert.ok(declaration);
    assert.match(declaration[1], /outdoor_road_5k_constraints_v1/);
    assert.doesNotMatch(declaration[1], /outdoor_road_10k_constraints_v1/);
  }
});

test('clients declare only the reachable Road rights response', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('web/src/types/api.ts'),
    read('miniapp/types/api.ts'),
  ]);

  for (const source of [webTypes, miniTypes]) {
    assert.doesNotMatch(source, /Road10KAccessResponse|Road10KOptInRequest|Road10KRolloutStatus|Road10KPlanStatus/);
    assert.match(source, /interface Road10KActionResponse/);
    assert.match(source, /outcome: 'withdrawn'/);
    assert.doesNotMatch(source, /outcome: 'enrolled'/);
  }
});
