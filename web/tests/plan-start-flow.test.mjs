import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('Goal links the supported 5K purpose to the Training plan-start flow', async () => {
  const [goal, miniGoal, miniGoalScript] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/pages/goal/index.ts'),
  ]);

  assert.match(goal, /Outdoor5KGoalEntry/);
  assert.match(goal, /performance_5k/);
  assert.match(miniGoalScript, /onStartOutdoor5kPlan/);
  assert.match(miniGoal, /outdoor-5k-goal-entry/);
});

test('web and miniapp use the deterministic proposal lifecycle without local scheduling', async () => {
  const [web, mini] = await Promise.all([
    read('../src/components/Outdoor5KPlanStart.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
  ]);

  for (const source of [web, mini]) {
    assert.match(source, /\/api\/plan\/outdoor-5k\/readiness/);
    assert.match(source, /\/api\/plan\/outdoor-5k\/generate/);
    assert.match(source, /\/api\/plan\/outdoor-5k\/proposals\/.*\/regenerate/);
    assert.match(source, /\/api\/plan\/proposals\/.*\/reject/);
    assert.match(source, /\/api\/plan\/proposals\/.*\/adopt/);
    assert.match(source, /proposal.*not.*plan/i);
    assert.match(source, /per-day.*unsupported/i);
    assert.match(source, /terrain.*equipment/i);
    assert.doesNotMatch(source, /function\s+buildSchedule|function\s+generateWorkouts/i);
  }
});

test('both surfaces fence canonical adoption and defer delivery consent until after adoption', async () => {
  const [web, mini, miniScript, training] = await Promise.all([
    read('../src/components/Outdoor5KPlanStart.tsx'),
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
  assert.match(training, /Outdoor5KPlanStart/);
});

test('proposal lifecycle retries retain their idempotency key and reject double actions', async () => {
  const [web, mini] = await Promise.all([
    read('../src/components/Outdoor5KPlanStart.tsx'),
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
