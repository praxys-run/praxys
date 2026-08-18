import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web and miniapp add gated 10K performance plan support', async () => {
  const [
    webGoal,
    webEditor,
    webPlanStart,
    webTypes,
    miniGoalScript,
    miniGoalMarkup,
    miniPlanStart,
    miniTypes,
  ] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../src/components/GoalEditor.tsx'),
    read('../src/components/PlanStart.tsx'),
    read('../src/types/api.ts'),
    read('../../miniapp/pages/goal/index.ts'),
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('../../miniapp/types/api.ts'),
  ]);

  for (const source of [webTypes, miniTypes]) {
    assert.match(source, /performance_10k/);
    assert.match(source, /outdoor_road_10k_constraints_v1/);
    assert.match(source, /Road10K/);
    assert.match(source, /interface Road10KHistoryConfirmationRequest/);
  }

  assert.match(webGoal, /performance_10k/);
  assert.match(webGoal, /GoalBaselinePanel/);
  assert.match(webGoal, /enablePerformance10k && data\.goal_kind === 'performance_10k'/);
  assert.match(webEditor, /enablePerformance10k && \(/);
  assert.match(webPlanStart, /outdoor_road_10k_constraints_v1/);
  assert.match(webPlanStart, /10K performance/);
  assert.match(webPlanStart, /baseline source/i);
  assert.match(webPlanStart, /history cutoff/i);
  assert.match(webPlanStart, /benchmark/i);
  assert.match(webPlanStart, /adult_confirmed/);
  assert.match(webPlanStart, /weekly_time_limit_min/);
  assert.match(webPlanStart, /maximum_session_duration_min/);
  assert.match(webPlanStart, /preferred_longest_easy_weekday/);
  assert.match(webPlanStart, /eligible_/);

  assert.match(miniGoalScript, /performance_10k/);
  assert.match(miniGoalMarkup, /performance10kEnabled && goalKind === 'performance_10k'/);
  assert.match(miniGoalMarkup, /wx:if="\{\{performance10kEnabled\}\}"/);
  assert.match(miniPlanStart, /outdoor_road_10k_constraints_v1/);
  assert.match(miniPlanStart, /10 公里表现|10K performance/);
  assert.match(miniPlanStart, /benchmark/i);
  assert.match(miniPlanStart, /adult_confirmed/);
  assert.match(miniPlanStart, /weekly_time_limit_min/);
  assert.match(miniPlanStart, /maximum_session_duration_min/);
  assert.match(miniPlanStart, /preferred_longest_easy_weekday/);
  assert.match(miniPlanStart, /eligible_/);
});
