import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test("web and miniapp keep Road 10K planning mechanically hidden", async () => {
  const [webPlanStart, miniPlanStart, webTypes, miniTypes] = await Promise.all([
    read("../src/components/PlanStart.tsx"),
    read("../../miniapp/components/outdoor-5k-plan-start/index.ts"),
    read("../src/types/api.ts"),
    read("../../miniapp/types/api.ts"),
  ]);

  for (const source of [webTypes, miniTypes]) {
    assert.match(source, /Road10K/);
    assert.match(source, /outdoor_road_10k_constraints_v1/);
    assert.match(source, /current_symptom_stop: boolean \| null/);
  }

  assert.match(webPlanStart, /Road 10K planning is unavailable in this revision/);
  assert.match(miniPlanStart, /road10kScopeRequired/);
  assert.doesNotMatch(webPlanStart, /adult_confirmed/);
  assert.doesNotMatch(miniPlanStart, /adult_confirmed/);
});

test('PlanStart keeps the plan-purpose Select controlled through selection', async () => {
  const planStart = await read('../src/components/PlanStart.tsx');

  assert.match(
    planStart,
    /\? purposeKey\(initialPurpose\.source, initialPurpose\.capability_id\)\s*: '',/,
  );
  assert.match(
    planStart,
    /<Select\s+value=\{selectedPurposeKey\}\s+onValueChange=\{selectPurpose\}/,
  );
  assert.match(planStart, /setSelectedPurposeKey\(value \?\? ''\);/);
  assert.doesNotMatch(planStart, /value=\{selectedPurposeKey \|\| undefined\}/);
});
