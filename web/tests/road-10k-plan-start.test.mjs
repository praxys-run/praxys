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


test("taper UI renders the returned horizon and digest-bound science projection", async () => {
  const [
    webTypes,
    miniTypes,
    webPlanStart,
    miniPlanStart,
    miniTemplate,
    webCopy,
    miniCopy,
    contractProjection,
    apiModels,
  ] = await Promise.all([
    read("../src/types/api.ts"),
    read("../../miniapp/types/api.ts"),
    read("../src/components/PlanStart.tsx"),
    read("../../miniapp/components/outdoor-5k-plan-start/index.ts"),
    read("../../miniapp/components/outdoor-5k-plan-start/index.wxml"),
    read("../src/lib/road-10k-control.ts"),
    read("../../miniapp/utils/road-10k-control.ts"),
    read("../../analysis/road_10k_contract.py"),
    read("../../api/routes/road_10k_plan_generation.py"),
  ]);

  for (const source of [webTypes, miniTypes]) {
    assert.match(source, /interface Road10KTaperGuardrailProjection/);
    assert.match(source, /planned_volume_reduction_fraction: number/);
    assert.match(source, /maintain_intensity_exposure_without_adding_quality: true/);
    assert.match(source, /evidence_population: \x27mixed_endurance_athletes\x27/);
    assert.match(source, /direct_recreational_road_10k_validation: false/);
    assert.match(source, /single_target_taper_result: \x27taper_proposal_truncated_to_event_eve\x27/);
    assert.match(source, /personal_performance_gain_claim: false/);
    assert.match(source, /causal_plan_benefit_claim: \x27disabled\x27/);
    assert.match(source, /personal_injury_probability: \x27disabled\x27/);
    assert.match(source, /taper: Road10KTaperGuardrailProjection/);
  }

  assert.match(contractProjection, /ROAD_10K_EVENTS\["taper"\]/);
  assert.match(contractProjection, /ROAD_10K_DEMOGRAPHICS/);
  assert.match(apiModels, /class Road10KTaperGuardrailProjectionResponse/);
  assert.match(apiModels, /taper: Road10KTaperGuardrailProjectionResponse/);

  assert.match(webPlanStart, /displayedProposal\.goal\?\.horizon_start/);
  assert.match(webPlanStart, /displayedProposal\.goal\?\.horizon_end/);
  assert.match(webPlanStart, /road10kTaperScienceCopy/);
  assert.match(webPlanStart, /proposal\.event_eve/);
  assert.match(webPlanStart, /sdr-road-10k-plan-generation-policy-v2\.yaml/);

  assert.match(miniPlanStart, /road10kTaperScienceCopy/);
  assert.match(miniPlanStart, /proposal\?\.goal\?\.horizon_start/);
  assert.match(miniPlanStart, /proposal\?\.goal\?\.horizon_end/);
  assert.match(miniTemplate, /proposal\.goal\.horizon_start/);
  assert.match(miniTemplate, /proposal\.goal\.horizon_end/);
  assert.match(miniTemplate, /roadTaperScience/);

  for (const source of [webCopy, miniCopy]) {
    assert.match(source, /road10kTaperScienceCopy/);
    assert.doesNotMatch(source, /This exact 14-day proposal/);
    assert.doesNotMatch(source, /The 14-day plan window is complete/);
  }
});
