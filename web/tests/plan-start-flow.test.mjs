import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  ApiResponseError,
  apiResponseError,
  extractApiError,
} from '../src/lib/api-error.ts';
import { formatProposalDetail } from '../src/lib/proposal-display.ts';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('structured proposal details render as readable text', () => {
  assert.equal(
    formatProposalDetail({ kind: 'schedule', value: 'weekday mornings' }),
    'schedule: weekday mornings',
  );
  assert.equal(
    formatProposalDetail({ preferred_long_run_day: null }),
    'preferred long run day: —',
  );
  assert.equal(formatProposalDetail(['known', { status: 'pending' }]), 'known, status: pending');
});

test('structured plan-purpose conflicts retain their recovery code', async () => {
  const extracted = await extractApiError(
    new Response(JSON.stringify({
      detail: {
        code: 'PLAN_PURPOSE_STALE',
        message: 'The Goal changed after this plan purpose was loaded.',
      },
    }), {
      status: 409,
      headers: { 'Content-Type': 'application/json' },
    }),
    'fallback',
  );

  assert.deepEqual(extracted, {
    status: 409,
    code: 'PLAN_PURPOSE_STALE',
    message: 'The Goal changed after this plan purpose was loaded.',
  });
});

test('query failures preserve structured API status and code', async () => {
  const error = await apiResponseError(
    new Response(JSON.stringify({
      detail: {
        code: 'PLAN_PROPOSAL_NOT_FOUND',
        message: 'No active plan proposal exists.',
      },
    }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    }),
    'fallback',
  );

  assert.ok(error instanceof ApiResponseError);
  assert.equal(error.status, 404);
  assert.equal(error.code, 'PLAN_PROPOSAL_NOT_FOUND');
  assert.equal(error.message, 'No active plan proposal exists.');
});

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

test('web and miniapp default to the current Goal without binding every plan to it', async () => {
  const [web, webBaseline, mini, miniBaseline, miniGoal] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../src/components/GoalBaselinePanel.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('../../miniapp/components/goal-baseline/index.ts'),
    read('../../miniapp/pages/goal/index.ts'),
  ]);

  for (const source of [web, mini]) {
    assert.match(source, /current_goal/);
    assert.match(source, /capability/);
    assert.match(source, /expected_goal_id/);
    assert.match(source, /expected_goal_revision/);
    assert.match(source, /purpose:/);
    assert.match(source, /Plan purpose needs reassessment/);
  }
  assert.match(web, /else if \(currentCapability && capabilityDiscovery\.current_goal\)[\s\S]*?purposeKey\('current_goal', currentCapability\.id\)/);
  assert.match(web, /selectedPurposeTouched/);
  assert.match(mini, /onPurposeChange/);
  assert.match(webBaseline, /purpose/);
  assert.match(miniBaseline, /purpose/);
  assert.match(miniGoal, /plan_candidate/);
  assert.match(miniGoal, /policy_unavailable/);
  assert.match(miniGoal, /onSelectPlanIntent/);
});

test('web and miniapp expose the same intent-aware plan routing states', async () => {
  const [web, miniScript, miniMarkup, registry] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../../miniapp/pages/goal/index.ts'),
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../api/plan_generation_capabilities.py'),
  ]);

  for (const source of [web, registry]) {
    assert.match(source, /first_completion/);
    assert.match(source, /performance/);
    assert.match(source, /return_to_consistency/);
  }
  for (const source of [web, miniScript, registry]) {
    assert.match(source, /plan_candidate/);
    assert.match(source, /readiness_only/);
    assert.match(source, /clarification_required/);
    assert.match(source, /policy_unavailable/);
  }
  assert.match(miniMarkup, /data-intent="first_completion"/);
  assert.match(miniMarkup, /data-intent="performance"/);
  assert.match(miniMarkup, /data-intent="return_to_consistency"/);
  assert.match(web, /Applicability and evidence/);
  assert.match(miniMarkup, /onTogglePlanRoutingReasoning/);
  assert.match(registry, /distance in capability\.distances/);
});

test('intent routing lives in Training and resets after Goal edits', async () => {
  const [
    web,
    training,
    reconciliation,
    miniApp,
    miniGoal,
    miniPlanStart,
  ] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../src/pages/Training.tsx'),
    read('../src/components/GoalPlanReconciliationDialog.tsx'),
    read('../../miniapp/app.ts'),
    read('../../miniapp/pages/goal/index.ts'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
  ]);

  assert.match(web, /goalRevision: currentGoalRevision/);
  assert.match(web, /onSelect\(routedPurpose\)/);
  assert.match(web, /<PlanIntentChooser\s+onSelect=\{confirmPurpose\}/);
  assert.match(training, /initialPurpose=\{navigationState\?\.planPurpose/);
  assert.match(reconciliation, /\/training#plan-start/);
  assert.match(miniApp, /pendingPlanStartPurpose/);
  assert.match(miniGoal, /_planIntentGoalRevision/);
  assert.match(miniGoal, /pendingPlanStartPurpose/);
  assert.match(miniPlanStart, /pendingPlanStartPurpose/);
});

test('Goal keeps progress before a lightweight Training entry', async () => {
  const [goal, web] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../src/components/PlanStart.tsx'),
  ]);
  const entry = web.slice(
    web.indexOf('export function PlanStartGoalEntry'),
    web.indexOf('function PlanIntentChooser'),
  );
  assert.ok(goal.indexOf('<TrajectoryGoal') < goal.indexOf('<PlanStartGoalEntry'));
  assert.match(entry, /to="\/training#plan-start"/);
  assert.doesNotMatch(entry, /useApi|ToggleGroup|PlanIntent|<Card/);
});

test('plan setup is opt-in and constraints require a confirmed, current purpose', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  assert.match(web, /\[setupOpen, setSetupOpen\] = useState\(Boolean\(initialPurpose\)\)/);
  assert.match(web, /id="plan-start-setup" hidden=\{!setupOpen\}/);
  assert.match(web, /\{purposeConfirmed && \(\s*<fieldset/);
  assert.doesNotMatch(web, /disabled=\{!purposeSelection\}/);
  assert.match(web, /purposeSelection\.expected_goal_id === confirmedPurpose\.expected_goal_id/);
  assert.match(web, /purposeSelection\.expected_goal_revision === confirmedPurpose\.expected_goal_revision/);
  assert.match(web, /const constraints = [\s\S]*?if \(!purposeConfirmed\)/);
  assert.match(web, /const closeSetup = \(\) => \{\s*setSetupOpen\(false\);\s*focusSection\('plan-start-configure'\);/);
});

test('draft review is collapsed without hiding blockers or assuming a failed fetch is empty', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  assert.match(web, /\[expandedProposalId, setExpandedProposalId\] = useState<string \| null>\(null\)/);
  assert.match(web, /open=\{expandedProposalId === displayedProposal\.id\}/);
  assert.match(web, /<CollapsibleContent keepMounted>/);
  assert.match(web, /currentProposalLoading && !displayedProposal/);
  assert.match(web, /if \(proposalLoadError && !displayedProposal\)/);
  const proposalView = web.slice(web.indexOf('{displayedProposal && !isAdopted && ('));
  assert.ok(proposalView.indexOf('proposalNeedsReassessment') < proposalView.indexOf('<CollapsibleContent'));
  assert.ok(proposalView.indexOf('displayedProposal.warnings') < proposalView.indexOf('<CollapsibleContent'));
  assert.match(proposalView, /proposalNeedsReassessment \|\| Boolean\(proposalLoadError\)/);
});

test('active plan workouts stay first without remounting the setup or hiding management behind a draft', async () => {
  const [training, web] = await Promise.all([
    read('../src/pages/Training.tsx'),
    read('../src/components/PlanStart.tsx'),
  ]);
  assert.match(training, /key="plan-start"/);
  assert.match(training, /key="upcoming"/);
  assert.match(training, /hasManagedPlan \? \[upcoming, planStart\] : \[planStart, upcoming\]/);
  assert.match(web, /const hasManagedPlan = isAdopted\s*\|\| config\.plan_management\.mode === 'praxys'\s*\|\| capabilityDiscovery\?\.active_plan_goal\?\.lifecycle === 'active'/);
  assert.match(web, /<ManagedPlanSettingsCard\s+compact\s+showSummary=\{hasManagedPlan\}/);
});

test('one explicit scope checkbox controls the same four required facts', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  assert.match(web, /scopeComplete = adult && selfCoached && canComplete && outdoorRoad;/);
  const confirmation = web.slice(web.indexOf('const confirmScope ='), web.indexOf('const weeklyTimeLimitNumber ='));
  for (const state of ['Adult', 'SelfCoached', 'CanComplete', 'OutdoorRoad']) {
    assert.match(web, new RegExp(`set${state}\\] = useState\\(false\\)`));
    assert.match(confirmation, new RegExp(`set${state}\\(checked\\)`));
  }
  assert.match(confirmation, /invalidateReadiness\(\)/);
  assert.match(web, /aria-describedby=\{!scopeComplete \? 'plan-start-scope-facts plan-start-validation'/);
  assert.match(web, /aria-invalid=\{!scopeComplete && error\?\.message === formError\}/);
  assert.match(web, /checked=\{scopeComplete\}\s+disabled=\{working != null\}\s+onCheckedChange=\{confirmScope\}/);
  assert.match(web, /targetId === 'plan-start-scope-confirmation'\s*\? scopeCheckbox\.current/);
  const scopeView = web.slice(web.indexOf('id="plan-start-scope-facts"'), web.indexOf('onCheckedChange={confirmScope}'));
  assert.equal((scopeView.match(/<li>/g) ?? []).length, 4);
  assert.doesNotMatch(scopeView, /continuously|without stopping|terms|adopt|delivery/i);
  assert.doesNotMatch(web, /plan-start-scope-adult|plan-start-scope-self-coached|plan-start-scope-can-complete|plan-start-scope-outdoor-road/);
  for (const mapping of ['age_18_or_older: adult', 'self_coached_recreational_road_runner: selfCoached', 'can_complete_5k: canComplete', 'outdoor_road_goal_confirmed: outdoorRoad']) {
    const [field, state] = mapping.split(': ');
    assert.match(web, new RegExp(`${field}: ${state}`));
  }
});

test('training names preserve source identities and distinguish same-distance alternatives', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  for (const source of ['current_goal', 'capability', 'unlinked']) {
    assert.match(web, new RegExp(`purposeKey\\('${source}', (currentCapability|item)\\.id\\)`));
    assert.match(web, new RegExp(`planOptionLabel\\((currentCapability|item), '${source}'\\)`));
  }
  assert.match(web, /tDisplay\(names\[distance\] \?\? distance\.toUpperCase\(\), i18n\)/);
  assert.match(web, /hasLinkedAlternative = currentCapability\?\.id === item\.id/);
  assert.match(web, /hasLinkedAlternative && source === 'current_goal'/);
  assert.match(web, /hasLinkedAlternative && source === 'capability'/);
  assert.match(web, /purposeSelection && !usesCurrentGoal && capabilityDiscovery\?\.current_goal/);
  assert.doesNotMatch(web, /Separate \$\{.*plan purpose/);
});

test('the adopted snapshot is subordinate but a successor stays visible', async () => {
  const [web, training, calendar, details] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../src/pages/Training.tsx'),
    read('../src/components/UpcomingPlanCard.tsx'),
    read('../src/components/AdoptedPlanDetails.tsx'),
  ]);
  assert.match(training, /hasCurrentPlan=\{hasManagedPlan\}/);
  assert.match(calendar, /hasCurrentPlan \? <Trans>Current training plan/);
  assert.match(calendar, /!hasCurrentPlan \|\| \(managementState === 'active' && !targetConnected\)/);
  assert.match(calendar, /\{firstExternalOverlap && \(/);
  assert.match(web, /<ManagedPlanSettingsCard\s+compact/);
  assert.match(web, /\{displayedProposal && !isAdopted && \(/);
  assert.match(web, /\{isAdopted && \(\s*<AdoptedPlanDetails/);
  assert.match(web, /hasManagedPlan && isDraft\s*\? <Trans>New proposal to review/);
  assert.match(details, /<DialogTrigger id="plan-start-configure"/);
  assert.match(details, /The calendar shows your current workouts, including later changes/);
  assert.match(details, /onOpenChangeComplete/);
  assert.doesNotMatch(details, /proposal\.(policy_version|model_version|science_version)/);
  assert.match(web, /setProposal\(value\.proposal\);\s*setSetupOpen\(false\);\s*setExpandedProposalId\(null\)/);
});

test('Goal-to-Training anchor navigation restores position and focus only once per visit', async () => {
  const training = await read('../src/pages/Training.tsx');
  assert.match(training, /location\.hash !== '#plan-start'/);
  assert.match(training, /focusedLocation\.current === location\.key/);
  assert.match(training, /settingsLoading\s*\|\| capabilitiesLoading/);
  assert.match(training, /target\.scrollIntoView\(\{ block: 'start' \}\)/);
  assert.match(training, /target\.focus\(\{ preventScroll: true \}\)/);
  assert.match(training, /focusedLocation\.current = location\.key/);
  assert.match(training, /ref=\{planStartAnchor\} tabIndex=\{-1\}/);
});

test('collapsed setup keeps safety stops and blocked readiness outside the hidden intake', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  const summary = web.indexOf('{!setupOpen && (safetyEdited || (result && !isPlanReadyResult(result)))');
  assert.ok(summary > 0);
  assert.ok(summary < web.indexOf('id="plan-start-setup" hidden={!setupOpen}'));
  assert.match(web.slice(summary, web.indexOf('id="plan-start-setup"')), /outcomeCopy\(result/);
  assert.match(web, /proposalDistance = displayedProposal\?\.goal\?\.target\?\.distance/);
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
    assert.match(source, /terrain.*equipment/i);
    assert.doesNotMatch(source, /function\s+buildSchedule|function\s+generateWorkouts/i);
  }
  assert.match(web, /maximum_session_duration_min: sharedDuration/);
  assert.match(mini, /per-day.*unsupported/i);
  assert.match(web, /SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_IDS/);
  assert.match(registry, /\/api\/plan\/outdoor-5k\/readiness/);
  assert.match(registry, /\/api\/plan\/outdoor-5k\/generate/);
  assert.match(registry, /\/api\/plan\/outdoor-5k\/proposals\/\{proposal_id\}\/regenerate/);
});

test('the neutral start entry names its destination without inventing plan absence', async () => {
  const [web, training] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../src/pages/Training.tsx'),
  ]);
  assert.doesNotMatch(training, /Start, review, and adjust/);
  assert.match(web, /!setupOpen && !displayedProposal/);
  assert.match(web, /openSetup\(setupStarted \? setupStep : 'purpose'\)/);
  assert.match(web, /View available training plans/);
  assert.doesNotMatch(web, /Choose another training plan|<Trans>No plans yet/);
  assert.match(web, /Automatic plans are not yet available for this training direction and distance/);
  assert.match(web, /This selects a training direction, not a plan/);
});

test('5K availability uses one explicit shared duration and keeps 10K fields distinct', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  assert.match(web, /\[maximumSessionDuration, setMaximumSessionDuration\] = useState\(''\)/);
  assert.equal((web.match(/id="outdoor-5k-session-limit"/g) ?? []).length, 1);
  assert.match(web, /sharedDuration = Number\(maximumSessionDuration\)/);
  assert.match(web, /Number\.isInteger\(sharedDuration\) && sharedDuration > 0/);
  assert.match(web, /maximum_session_duration_min: sharedDuration/);
  assert.match(web, /targetId = 'outdoor-5k-session-limit'/);
  assert.doesNotMatch(web, /dayLimits|setDayLimit|perDayLimitsUnsupported|outdoor-5k-day-/);
  assert.match(web, /weekly_time_limit_min: weeklyTimeLimitNumber/);
  assert.match(web, /maximum_session_duration_min: singleSessionLimitNumber/);
  assert.match(web, /availableDays\.map\(\(day\) => \(\s*<SelectItem/);
});

test('safety feedback separates local edits, actual results and stored-draft adoption', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  const change = web.slice(web.indexOf('const changeSafetyStop ='), web.indexOf('const constraints ='));
  assert.match(change, /setSafetyStop\(checked\)/);
  assert.match(change, /setSafetyEdited\(true\)/);
  assert.match(change, /invalidateReadiness\('none'\)/);
  assert.doesNotMatch(change, /apiFetch|updateSettings|adopt\(/);
  for (const [operation, next] of [
    ['requestReadiness', 'generate'],
    ['generate', 'regenerate'],
    ['regenerate', 'adopt'],
  ]) {
    const start = web.indexOf(`const ${operation} =`);
    const end = web.indexOf(`const ${next} =`, start + 1);
    assert.ok(start >= 0 && end > start);
    const request = web.slice(start, end);
    assert.match(request, /setReadiness\(value\)/);
    assert.match(
      request,
      /catch \(requestError\) \{\s*setReadiness\(null\);\s*setSafetyRequestState\('failed'\)/,
    );
  }
  assert.equal((web.match(/setSafetyRequestState\('submitted'\)/g) ?? []).length, 3);
  assert.equal((web.match(/setSafetyRequestState\('failed'\)/g) ?? []).length, 3);
  const invalidation = web.slice(web.indexOf('const invalidateReadiness ='), web.indexOf('const focusSection ='));
  assert.match(invalidation, /setReadiness\(null\)/);
  assert.match(invalidation, /setSafetyRequestState\(\(current\) => current === 'none' \? 'none' : nextState\)/);
  assert.match(invalidation, /setError\(null\)/);
  assert.match(web, /setMaximumSessionDuration\(event\.target\.value\);\s*invalidateReadiness\(\)/);
  assert.match(web, /safetyRequestState === 'changed'/);
  assert.doesNotMatch(web, /see the error below/);
  assert.equal((web.match(/setReadiness\(null\)/g) ?? []).length, 4);
  assert.match(web, /result\?\.code === 'safety_stop'/);
  assert.match(web, /isDraft && safetyEdited/);
  assert.match(web, /does not update those inputs or independently block adoption/);
  const adoption = web.slice(web.indexOf('const adopt ='), web.indexOf('const refreshPlanContext ='));
  assert.doesNotMatch(adoption, /safetyStop|safetyEdited|safety_stop|current_symptom_stop/);
  assert.match(adoption, /expected_proposal_version/);
});

test('population explanation is readable in product with claim-linked sources', async () => {
  const web = await read('../src/components/PlanStart.tsx');
  const chooser = web.slice(web.indexOf('function PlanIntentChooser'), web.indexOf('function PlanStartSkeleton'));
  assert.match(chooser, /<ScienceNote label=\{<Trans>Applicability and evidence/);
  assert.match(chooser, /Sparse records do not establish/);
  assert.match(chooser, /nonclinical training for adults/);
  assert.match(chooser, /Limits of a universal beginner schedule/);
  assert.match(chooser, /10\.1007\/s40279-015-0333-8/);
  assert.match(chooser, /10\.4085\/1062-6050-0195\.21/);
  assert.match(chooser, /10\.1155\/2022\/2130993/);
  assert.match(chooser, /10\.3389\/fphys\.2023\.1334766/);
  assert.doesNotMatch(chooser, /github\.com.*\.yaml/);
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

test('miniapp binds generation responses to the request purpose', async () => {
  const [miniScript, miniMarkup] = await Promise.all([
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.wxml'),
  ]);

  assert.match(miniScript, /function samePurposeSelection/);
  assert.equal(
    (miniScript.match(/const requestPurpose = constraints\.purpose;/g) ?? []).length,
    2,
  );
  assert.equal(
    (miniScript.match(/samePurposeSelection\(\s*response\.purpose,\s*requestPurpose,\s*\)/g) ?? []).length,
    2,
  );
  assert.equal(
    (miniScript.match(/samePurposeSelection\(\s*requestPurpose,\s*this\.data\.selectedPurpose,\s*\)/g) ?? []).length,
    2,
  );
  assert.match(
    miniScript,
    /onPurposeChange\(e:[\s\S]*?if \(this\.data\.working\) return;/,
  );
  assert.match(miniMarkup, /<picker[^>]*disabled="\{\{working !== ''\}\}"[^>]*bindchange="onPurposeChange"/);
  assert.doesNotMatch(
    miniScript,
    /proposalPurposeLabel: this\.data\.selectedPurpose\?\.source/,
  );
});

test('reject clears proposal gates without losing the safety notice', async () => {
  const [web, mini] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
  ]);

  assert.match(
    web,
    /await planStartResponse<AdaptivePlanProposal>[\s\S]*?Proposal rejected\. Your canonical plan was not changed\.[\s\S]*?await Promise\.all\(\[[\s\S]*?refetchProposal\(\)[\s\S]*?setProposal\(null\)/,
  );
  assert.match(
    web,
    /selectedCurrentProposal = noCurrentProposal\s*\?\s*null\s*:\s*currentProposal/,
  );
  assert.match(
    mini,
    /proposal: null,\s*proposalMatchesPurpose: true,\s*proposalPurposeLabel: '',\s*notice: this\.data\.tr\.rejected/,
  );
});

test('web recovers plan-purpose conflicts with fresh plan context', async () => {
  const web = await read('../src/components/PlanStart.tsx');

  assert.match(web, /PLAN_PURPOSE_STALE/);
  assert.match(web, /PLAN_PURPOSE_REASSESSMENT_REQUIRED/);
  assert.match(web, /extractApiError/);
  assert.match(
    web,
    /const refreshPlanContext = async \(\) => \{[\s\S]*?invalidateReadiness\(\)[\s\S]*?setProposal\(null\)[\s\S]*?refetchCapabilities\(\)[\s\S]*?refetchProposal\(\)[\s\S]*?refetchGoal\(\)/,
  );
  assert.match(web, /needsPlanContextRecovery\(error\)/);
  assert.doesNotMatch(web, /error\.includes\('STALE'\)|error\.includes\('CONFLICT'\)|error\.includes\('409'\)/);
});

test('drafts stay visible and rejectable when policy or Goal context is unavailable', async () => {
  const [web, miniMarkup, miniScript] = await Promise.all([
    read('../src/components/PlanStart.tsx'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.wxml'),
    read('../../miniapp/components/outdoor-5k-plan-start/index.ts'),
  ]);

  assert.match(web, /displayedProposal = activeProposal \?\? conflictingProposal/);
  assert.match(web, /if \(!displayedProposal\) return/);
  assert.match(web, /\{displayedProposal && !isAdopted && \(/);
  assert.match(web, /proposalPurposeConflict/);
  assert.match(web, /currentCapability\?\.id !== capability\.id/);
  assert.match(web, /function ProposalRecoveryCard/);
  assert.match(
    web,
    /selectedCurrentProposal = noCurrentProposal\s*\?\s*null\s*:\s*currentProposal/,
  );
  assert.match(web, /'\/api\/plan\/proposals\/current',\s*\{ timeoutMs: 12_000, retry: shouldRetryCurrentPlanProposal \}/);
  assert.match(web, /recognizedLegacyCurrentGoalProposal/);
  assert.match(web, /policyProposal\.policy_version === 'outdoor-5k-plan-generation-policy-v1'/);
  assert.match(web, /currentProposalErrorCode === 'PLAN_PROPOSAL_NOT_FOUND'/);
  assert.match(web, /if \(!hasSelectablePurpose\) \{/);
  assert.match(web, /\{!proposalPurposeConflict && \(/);
  assert.match(web, /\{proposalRecoveryCard\}/);
  assert.doesNotMatch(web, /!hasSelectablePurpose && !displayedProposal/);
  assert.doesNotMatch(web, /usesCurrentGoal\s+&& !displayedProposal/);
  assert.match(miniMarkup, /<\/block>\s*<view wx:if="\{\{proposal\}\}" class="ts-card plan-start-card"/);
  assert.match(miniMarkup, /wx:if="\{\{proposalMatchesPurpose\}\}".*bindtap="onAdopt"/);
  assert.match(miniMarkup, /bindtap="onReject"/);
  assert.match(miniScript, /proposal = await apiGet<AdaptivePlanProposal>\(\s*'\/api\/plan\/proposals\/current'/);
  assert.doesNotMatch(miniScript, /if \(capabilityAvailable\) \{\s*try \{\s*proposal = await apiGet/);
  assert.ok(
    miniScript.indexOf('/api/plan/proposals/current')
      < miniScript.indexOf('/api/plan/generation/capabilities'),
  );
  assert.match(miniScript, /proposalMatchesPurpose = !proposal \|\| Boolean\(\s*proposalCapability/);
  assert.match(miniScript, /\n\s*proposal,\n\s*proposalMatchesPurpose,/);
  assert.match(miniScript, /if \(!this\.data\.proposalMatchesPurpose\)/);
});
