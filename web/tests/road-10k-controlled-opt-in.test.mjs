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
    read('miniapp/utils/plan-start-routing.ts'),
  ]);

  for (const source of [webPlanStart, miniPlanStart]) {
    const declaration = source.match(/const SUPPORTED_PLAN_START_CAPABILITY_CONTRACTS[\s\S]*?= (?:new Map\(\[|\{)([\s\S]*?)(?:\]\);|\};)/);
    assert.ok(declaration);
    assert.match(declaration[1], /outdoor_road_5k_v1/);
    assert.match(declaration[1], /outdoor_road_5k_constraints_v1/);
    assert.doesNotMatch(declaration[1], /outdoor_road_10k_performance_v1/);
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


test("Goal editors ignore stale Road 10K discovery while preserving 5K", async () => {
  const [webGoal, miniGoal, miniTemplate] = await Promise.all([
    read("web/src/pages/Goal.tsx"),
    read("miniapp/pages/goal/index.ts"),
    read("miniapp/pages/goal/index.wxml"),
  ]);

  assert.match(webGoal, /enablePerformance10k=\{false\}/);
  assert.doesNotMatch(webGoal, /capabilityDiscovery\?\.capabilities\.some/);
  assert.doesNotMatch(webGoal, /enablePerformance10k && data\.goal_kind/);
  assert.match(webGoal, /data\.goal_kind === \x27performance_5k\x27/);

  const miniRouting = await read('miniapp/utils/plan-start-routing.ts');
  const discoveryAllowlist = miniRouting.match(/const SUPPORTED_PLAN_START_CAPABILITY_CONTRACTS[\s\S]*?= \{([\s\S]*?)\};/);
  assert.ok(discoveryAllowlist);
  assert.match(discoveryAllowlist[1], /outdoor_road_5k_v1/);
  assert.match(discoveryAllowlist[1], /outdoor_road_5k_constraints_v1/);
  assert.doesNotMatch(discoveryAllowlist[1], /outdoor_road_10k_performance_v1/);
  assert.doesNotMatch(discoveryAllowlist[1], /outdoor_road_10k_constraints_v1/);
  assert.match(miniGoal, /performance10kEnabled: false/);
  assert.doesNotMatch(miniGoal, /performance10kEnabled: supportedCapabilityIds\.includes/);
  assert.match(miniTemplate, /wx:if="\{\{performance10kEnabled\}\}"/);
});
