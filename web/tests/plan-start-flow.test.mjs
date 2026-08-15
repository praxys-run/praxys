import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('Goal links capability discovery to the Training plan-start flow', async () => {
  const [goal, miniGoal, miniGoalScript] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/pages/goal/index.ts'),
  ]);

  assert.match(goal, /PlanStartGoalEntry/);
  assert.match(goal, /invalidateQueries/);
  assert.match(miniGoalScript, /PlanGenerationCapabilitiesResponse/);
  assert.match(miniGoalScript, /\/api\/plan\/generation\/capabilities/);
  assert.match(miniGoalScript, /onOpenPlanManagement/);
  assert.match(miniGoal, /plan-generation-goal-entry/);
  assert.doesNotMatch(miniGoal, /outdoor-5k-goal-entry/);
});

test('web and miniapp use discovered deterministic actions without local scheduling', async () => {
  const [web, mini, registry] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('../../api/plan_generation_capabilities.py'),
  ]);

  for (const source of [web, mini]) {
    assert.match(source, /\/api\/plan\/generation\/capabilities/);
    assert.match(source, /actions\.readiness_href/);
    assert.match(source, /actions\.generate_href/);
    assert.match(source, /actions\.regenerate_href_template/);
    assert.match(source, /\/api\/plan\/proposals\/.*\/reject/);
    assert.match(source, /\/api\/plan\/proposals\/.*\/adopt/);
    assert.match(source, /proposal.*not.*plan/i);
    assert.match(source, /per-day.*unsupported/i);
    assert.match(source, /terrain.*equipment/i);
    assert.doesNotMatch(source, /function\s+buildSchedule|function\s+generateWorkouts/i);
  }
  assert.match(web, /SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_ID/);
  assert.match(registry, /\/api\/plan\/outdoor-5k\/readiness/);
  assert.match(registry, /\/api\/plan\/outdoor-5k\/generate/);
  assert.match(registry, /\/api\/plan\/outdoor-5k\/proposals\/\{proposal_id\}\/regenerate/);
});

test('both surfaces fence canonical adoption and defer delivery consent until after adoption', async () => {
  const [web, mini, miniScript, training] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.wxml'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('../src/pages/Training.tsx'),
  ]);

  assert.match(web, /expected_proposal_version/);
  assert.match(web, /expected_plan_version/);
  assert.match(web, /Delivery remains disabled/);
  assert.match(web, /ManagedPlanSettingsCard/);
  assert.match(mini, /proposal\.state === 'adopted'/);
  assert.match(miniScript, /Delivery remains disabled/);
  assert.match(training, /PlanStart/);
});

test('proposal lifecycle retries retain their idempotency key and reject double actions', async () => {
  const [web, mini] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
  ]);

  for (const source of [web, mini]) {
    assert.match(source, /operationKey\('generate'\)/);
    assert.match(source, /operationKey\('regenerate'\)/);
    assert.match(source, /operationKey\('reject'\)/);
    assert.match(source, /operationKey\('adopt'\)/);
  }
  assert.match(mini, /if \(this\.data\.working\) return;/);
});
