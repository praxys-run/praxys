import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Road routing requires the exact present allowlisted capability", async () => {
  const { matchingPlanStartCapability } = await import(
    "../src/lib/plan-start-routing.ts"
  );
  const route = { capability_id: "outdoor_road_10k_performance_v1" };
  const road = {
    id: "outdoor_road_10k_performance_v1",
    constraint_schema_id: "outdoor_road_10k_constraints_v1",
  };
  const allowlisted = new Map([[
    "outdoor_road_10k_performance_v1",
    "outdoor_road_10k_constraints_v1",
  ]]);

  assert.equal(matchingPlanStartCapability([], route, allowlisted), null);
  assert.equal(
    matchingPlanStartCapability(
      [{ ...road, id: "outdoor_road_5k_v1" }],
      route,
      allowlisted,
    ),
    null,
  );
  assert.equal(
    matchingPlanStartCapability(
      [{ ...road, constraint_schema_id: "outdoor_road_5k_constraints_v1" }],
      route,
      new Map([[
        "outdoor_road_5k_v1",
        "outdoor_road_5k_constraints_v1",
      ]]),
    ),
    null,
  );
  assert.equal(
    matchingPlanStartCapability(
      [{ ...road, constraint_schema_id: "unexpected_schema" }],
      route,
      allowlisted,
    ),
    null,
  );
  assert.equal(matchingPlanStartCapability([road], route, allowlisted), road);

  const source = await read("../src/components/PlanStart.tsx");
  assert.match(source, /matchingPlanStartCapability/);
  assert.match(source, /if \(!routedCapability \|\| !selectedRoute\?\.purpose_source\)/);
});

test("taper disclosure is derived from the persisted proposal only", async () => {
  const { road10kTaperGuardrailForProposal } = await import(
    "../src/lib/road-10k-control.ts"
  );
  const taper = {
    planned_volume_reduction_fraction: 0.5,
    maintain_intensity_exposure_without_adding_quality: true,
    evidence_population: "mixed_endurance_athletes",
    direct_recreational_road_10k_validation: false,
    single_target_taper_result: "taper_proposal_truncated_to_event_eve",
    personal_performance_gain_claim: false,
    causal_plan_benefit_claim: "disabled",
    personal_injury_probability: "disabled",
  };
  const proposal = {
    policy_version: "road-10k-plan-generation-policy-v2",
    science_version: "sdr-road-10k-plan-generation-policy-v2",
    goal: {
      goal_kind: "performance_10k",
      horizon_start: "2026-08-19",
      horizon_end: "2026-09-01",
      target: {
        event_state: "single_target",
        target_event_date: "2026-09-02",
        benchmark_date: null,
        guardrail_projection: {
          contract_digest: "sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496",
          source_decision_digest: "sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad",
          taper,
        },
      },
    },
  };

  assert.equal(road10kTaperGuardrailForProposal(proposal), taper);
  assert.equal(
    road10kTaperGuardrailForProposal({
      ...proposal,
      goal: { ...proposal.goal, horizon_end: "2026-08-31" },
    }),
    null,
  );
  assert.equal(
    road10kTaperGuardrailForProposal({
      ...proposal,
      policy_version: "outdoor-5k-plan-generation-policy-v1",
    }),
    null,
  );
  assert.equal(
    road10kTaperGuardrailForProposal({
      ...proposal,
      goal: {
        ...proposal.goal,
        target: {
          ...proposal.goal.target,
          guardrail_projection: {
            ...proposal.goal.target.guardrail_projection,
            contract_digest: "sha256:stale",
          },
        },
      },
    }),
    null,
  );

  const [web, mini] = await Promise.all([
    read("../src/components/PlanStart.tsx"),
    read("../../miniapp/components/outdoor-5k-plan-start/index.ts"),
  ]);
  assert.doesNotMatch(web, /isRoad10KTaperProposal/);
  assert.doesNotMatch(mini, /roadTaperScience\(readiness\)/);
  for (const source of [web, mini]) {
    assert.match(source, /road10kTaperGuardrailForProposal/);
  }
});

test("Road taper-reachable copy has no fixed fourteen-day proposal claim", async () => {
  const sources = await Promise.all([
    read("../../analysis/road_10k_plan_generation.py"),
    read("../src/components/PlanStart.tsx"),
    read("../../miniapp/components/outdoor-5k-plan-start/index.ts"),
    read("../../miniapp/utils/i18n-extra.ts"),
  ]);
  for (const source of sources) {
    assert.doesNotMatch(source, /14-day/i);
  }
});

test("Road-specific web targets declare at least 44 CSS pixels", async () => {
  const source = await read("../src/components/PlanStart.tsx");
  for (const id of [
    "plan-start-road-10k-adult",
    "road-10k-symptom-stop",
    "road-10k-weekly-limit",
    "road-10k-session-limit",
    "road-10k-long-day",
    "road-10k-benchmark-date",
  ]) {
    const start = source.indexOf(`id="${id}"`);
    assert.notEqual(start, -1, id);
    assert.match(source.slice(start, start + 700), /min-h-11/);
  }
  assert.match(source, /id=\{`plan-start-day-\$\{day\}`\}[\s\S]{0,400}min-h-11 min-w-12/);
});

test("account deletion clients model committed cleanup pending", async () => {
  const [settings, login, adminUsers, webTypes, miniSettings, miniTypes] = await Promise.all([
    read("../src/pages/Settings.tsx"),
    read("../src/pages/Login.tsx"),
    read("../src/pages/admin/AdminUsers.tsx"),
    read("../src/types/api.ts"),
    read("../../miniapp/pages/settings/index.ts"),
    read("../../miniapp/types/api.ts"),
  ]);
  for (const source of [webTypes, miniTypes]) {
    assert.match(source, /AccountDeletionResponse/);
    assert.match(source, /deleted_cleanup_pending/);
  }
  assert.match(settings, /AccountDeletionResponse/);
  assert.match(settings, /accountDeletionStatus: result\.status/);
  assert.match(login, /deleted_cleanup_pending/);
  assert.match(login, /role="status"/);
  assert.match(adminUsers, /deleted_cleanup_pending/);
  assert.match(adminUsers, /Your account was deleted/);
  assert.match(adminUsers, /still being retried in the background/);
  assert.match(miniSettings, /apiDelete<AccountDeletionResponse>/);
  assert.match(miniSettings, /clearToken\(\)/);
  assert.match(miniSettings, /accountDeletionStatus=\$\{result\.status\}/);
});
