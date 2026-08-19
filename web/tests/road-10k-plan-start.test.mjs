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
    miniPlanStartMarkup,
    miniTypes,
  ] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../src/components/GoalEditor.tsx'),
    read('../src/components/PlanStart.tsx'),
    read('../src/types/api.ts'),
    read('../../miniapp/pages/goal/index.ts'),
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.wxml'),
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
  assert.match(webPlanStart, /plan_returned/);
  assert.match(webPlanStart, /route_state/);
  assert.match(webPlanStart, /focusFirstInvalidConstraint/);
  assert.match(webPlanStart, /role="alert"/);
  assert.match(webPlanStart, /showRoad10KScheduleGuardrails/);
  assert.match(webPlanStart, /eligible_rolling_proposal/);
  assert.match(webPlanStart, /eligible_taper_proposal/);
  assert.match(webPlanStart, /Road 10K schedule guardrails/);
  assert.match(webPlanStart, /road10KGuardrails\.committed_proposal_days/);
  assert.match(webPlanStart, /road10KGuardrails\.advisory_reassessment_after_completed_days/);
  assert.match(webPlanStart, /road10KGuardrails\.minimum_planned_low_intensity_running_minutes_fraction/);
  assert.doesNotMatch(webPlanStart, />14<\/span>-day proposal/);
  assert.doesNotMatch(webPlanStart, />75%<\/span> planned low-intensity/);
  assert.match(
    webPlanStart,
    /data\/science\/decisions\/sdr-road-10k-plan-generation-policy-v2\.yaml/,
  );

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
  assert.match(miniPlanStart, /plan_returned/);
  assert.match(miniPlanStart, /route_state/);
  assert.match(miniPlanStart, /road10kReadinessContext/);
  assert.match(miniPlanStart, /readinessBadge/);
  assert.match(miniPlanStartMarkup, /\{\{readinessBadge\}\}/);
  assert.match(miniPlanStartMarkup, /readinessContextRows/);
  assert.match(miniPlanStartMarkup, /\{\{proposalStateLabel\}\}/);
  assert.doesNotMatch(miniPlanStartMarkup, /readiness\.result\.code/);
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
