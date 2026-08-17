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
  assert.match(web, /The current Goal is the default/);
  assert.match(mini, /onPurposeChange/);
  assert.match(webBaseline, /purpose/);
  assert.match(miniBaseline, /purpose/);
  assert.match(miniGoal, /alternate_available/);
  assert.match(miniGoal, /accepted separate 5K plan purpose/);
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
    /const refreshPlanContext = async \(\) => \{[\s\S]*?setReadiness\(null\)[\s\S]*?setProposal\(null\)[\s\S]*?refetchCapabilities\(\)[\s\S]*?refetchProposal\(\)[\s\S]*?refetchGoal\(\)/,
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
  assert.match(web, /\{displayedProposal && \(/);
  assert.match(web, /proposalPurposeConflict/);
  assert.match(web, /currentCapability\?\.id !== capability\.id/);
  assert.match(web, /function ProposalRecoveryCard/);
  assert.match(
    web,
    /selectedCurrentProposal = noCurrentProposal\s*\?\s*null\s*:\s*currentProposal/,
  );
  assert.match(web, /'\/api\/plan\/proposals\/current',\s*\{ timeoutMs: 12_000 \}/);
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
