import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const read = (path) => fs.readFile(new URL(path, root), 'utf8');

test('Road 10K stays off-route while Goal, Training, and Settings/Me keep the accepted split', async () => {
  const [
    app,
    webGoal,
    webTraining,
    webSettings,
    miniGoalMarkup,
    miniTrainingMarkup,
    miniTrainingJson,
    miniSettingsMarkup,
    miniSettingsJson,
    miniComponent,
    miniMarkup,
    webComponent,
  ] = await Promise.all([
    read('web/src/App.tsx'),
    read('web/src/pages/Goal.tsx'),
    read('web/src/pages/Training.tsx'),
    read('web/src/pages/Settings.tsx'),
    read('miniapp/pages/goal/index.wxml'),
    read('miniapp/pages/training/index.wxml'),
    read('miniapp/pages/training/index.json'),
    read('miniapp/pages/settings/index.wxml'),
    read('miniapp/pages/settings/index.json'),
    read('miniapp/components/road-10k-controlled-opt-in/index.ts'),
    read('miniapp/components/road-10k-controlled-opt-in/index.wxml'),
    read('web/src/pages/Road10KControlledOptIn.tsx'),
  ]);

  assert.doesNotMatch(app, /path="\/road-10k/);
  assert.match(webGoal, /<Road10KControlledOptIn surface="goal" \/>/);
  assert.match(webTraining, /surface="training"/);
  assert.match(webSettings, /surface="settings"/);

  assert.match(miniGoalMarkup, /road-10k-controlled-opt-in[^>]*id="goal-road-10k"[^>]*surface="goal"/s);
  assert.match(miniTrainingMarkup, /road-10k-controlled-opt-in[^>]*id="training-road-10k"[^>]*surface="training"/s);
  assert.match(miniTrainingJson, /road-10k-controlled-opt-in/);
  assert.match(miniSettingsMarkup, /road-10k-controlled-opt-in[^>]*id="settings-road-10k"[^>]*surface="settings"/s);
  assert.match(miniSettingsJson, /road-10k-controlled-opt-in/);

  assert.match(miniComponent, /pendingRoad10KIntent/);
  assert.match(miniComponent, /password:/);
  assert.match(miniComponent, /client: 'miniapp'/);
  assert.match(miniComponent, /wx\.showModal/);
  assert.match(miniComponent, /confirmLeave/);
  assert.match(miniMarkup, /bindtap="onCheck"/);
  assert.match(miniMarkup, /text\.addScreenshot/);
  assert.match(webComponent, /life\.withdraw_title/);
  assert.match(webComponent, /leaveDialogOpen/);
});

test('web and miniapp ship the exact Road 10K copy catalog and state maps', async () => {
  const webControl = await import('../src/lib/road-10k-control.ts');
  const miniControl = await import('../../miniapp/utils/road-10k-control.ts');

  assert.equal(Object.keys(webControl.ROAD_10K_COPY).length, 241);
  assert.deepEqual(
    miniControl.ROAD_10K_ROLLOUT_STATES,
    webControl.ROAD_10K_ROLLOUT_STATES,
  );
  assert.deepEqual(
    miniControl.ROAD_10K_PLAN_STATES,
    webControl.ROAD_10K_PLAN_STATES,
  );
  assert.deepEqual(
    miniControl.ROAD_10K_ROLLOUT_STATUS_COPY,
    webControl.ROAD_10K_ROLLOUT_STATUS_COPY,
  );
  assert.deepEqual(
    miniControl.ROAD_10K_PLAN_STATE_COPY,
    webControl.ROAD_10K_PLAN_STATE_COPY,
  );

  assert.equal(
    webControl.ROAD_10K_COPY['notice.data']['zh-CN'],
    '下方当前数据说明列出了确切的数据使用、访问角色、保留期限、私密反馈处理、导出和删除条款。',
  );
  assert.equal(
    webControl.ROAD_10K_COPY['success.withdrawn'].en,
    'You left the Road 10K rollout. Your adopted plan, if any, is unchanged and was not paused or ended.',
  );
  assert.equal(
    webControl.ROAD_10K_COPY['success.withdrawn']['zh-CN'],
    '你已退出公路 10K 试点。如有已采纳计划，它保持不变，未被暂停或结束。',
  );

  assert.deepEqual(
    webControl.road10kAccessStateCopy('enrollment-closed', 'none'),
    ['life.close_title', 'life.close_out'],
  );
  assert.deepEqual(
    webControl.road10kAccessStateCopy('enrollment-closed', 'active'),
    ['life.close_title', 'life.close_in'],
  );
});

test('Road 10K opt-in contracts require server-verified reauthentication for every client', async () => {
  const [webTypes, miniTypes, typechecks] = await Promise.all([
    read('web/src/types/api.ts'),
    read('miniapp/types/api.ts'),
    read('web/src/types/api-request-contract.typecheck.ts'),
  ]);

  for (const source of [webTypes, miniTypes]) {
    assert.match(source, /interface Road10KOptInRequest/);
    assert.match(source, /password: string;/);
    assert.match(source, /client: 'web' \| 'miniapp';/);
    assert.doesNotMatch(source, /interface Road10KOptInRequest \{[^}]*notice_digest/s);
    assert.doesNotMatch(source, /password\?: never/);
  }

  assert.match(typechecks, /miniappRoad10KOptIn/);
  assert.match(typechecks, /invalidMiniappRoad10KOptIn/);
});

test('Road 10K synthetic state fixtures stay test-only and preserve platform parity', async () => {
  const [
    webFixtureSource,
    miniappFixtureSource,
    webApp,
    webComponent,
    miniappComponent,
    miniappProject,
    miniappPublish,
  ] = await Promise.all([
    read('web/tests/fixtures/road-10k-controlled-opt-in.fixtures.json'),
    read('miniapp/tests/fixtures/road-10k-controlled-opt-in.fixtures.json'),
    read('web/src/App.tsx'),
    read('web/src/pages/Road10KControlledOptIn.tsx'),
    read('miniapp/components/road-10k-controlled-opt-in/index.ts'),
    read('miniapp/project.config.json'),
    read('.github/workflows/miniapp-publish.yml'),
  ]);
  const webFixture = JSON.parse(webFixtureSource);
  const miniappFixture = JSON.parse(miniappFixtureSource);
  const parityKeys = [
    'schema_version',
    'synthetic_only',
    'locales',
    'access',
    'readiness',
    'baseline_inputs',
    'proposal',
    'managed_plan',
    'lifecycle',
    'network',
    'unavailable_capabilities',
  ];

  assert.equal(webFixture.synthetic_only, true);
  assert.equal(miniappFixture.synthetic_only, true);
  for (const key of parityKeys) {
    assert.deepEqual(miniappFixture[key], webFixture[key], key);
  }
  assert.deepEqual(webFixture.unavailable_capabilities, [
    'feedback-screenshot-upload',
  ]);

  const productionSources = [webApp, webComponent, miniappComponent].join('\n');
  assert.doesNotMatch(
    productionSources,
    /road-10k-controlled-opt-in\.fixtures|road-10k-synthetic-ui-fixtures-v1/,
  );
  assert.deepEqual(
    JSON.parse(miniappProject).packOptions.ignore,
    [{ type: 'folder', value: 'tests' }],
  );
  assert.match(miniappPublish, /'tests\/\*\*\/\*'/);
});

test('Road proposal UI uses accepted copy, confirmations, and bounded motion-safe sheets', async () => {
  const [
    webPlanStart,
    webOptIn,
    miniPlanStart,
    miniPlanMarkup,
    miniOptInMarkup,
    miniOptInStyles,
    miniAppStyles,
  ] = await Promise.all([
    read('web/src/components/PlanStart.tsx'),
    read('web/src/pages/Road10KControlledOptIn.tsx'),
    read('miniapp/components/outdoor-5k-plan-start/index.ts'),
    read('miniapp/components/outdoor-5k-plan-start/index.wxml'),
    read('miniapp/components/road-10k-controlled-opt-in/index.wxml'),
    read('miniapp/components/road-10k-controlled-opt-in/index.scss'),
    read('miniapp/app.scss'),
  ]);

  assert.match(webPlanStart, /ROAD_10K_OUTCOME_COPY/);
  assert.match(webPlanStart, /roadCopy\('inputs\.title'\)/);
  assert.match(webPlanStart, /roadCopy\('proposal\.badge'\)/);
  assert.match(webPlanStart, /roadCopy\('action\.review_later'\)/);
  assert.match(webPlanStart, /proposal\.reject_title/);
  assert.match(webPlanStart, /proposal\.regen_title/);
  assert.match(webPlanStart, /proposal\.adopt_title/);
  assert.match(webPlanStart, /onReviewLater/);
  assert.match(webPlanStart, /proposal\.policy_version/);
  assert.match(webPlanStart, /!road10kMode/);
  assert.match(webOptIn, /prefers-reduced-motion: reduce/);
  assert.match(
    webOptIn,
    /queryKey: \['\/api\/plan\/generation\/capabilities'\]/,
  );
  assert.doesNotMatch(webOptIn, /slate-|#fff/);

  assert.match(miniPlanStart, /roadOutcomeCopyKeys/);
  assert.match(miniPlanStart, /road10kTitle: roadCopy\('inputs\.title'\)/);
  assert.match(miniPlanStart, /roadProposalBadge: roadCopy\('proposal\.badge'\)/);
  assert.match(miniPlanStart, /wx\.showModal/);
  assert.match(miniPlanStart, /proposal\.reject_title/);
  assert.match(miniPlanStart, /proposal\.regen_title/);
  assert.match(miniPlanStart, /proposal\.adopt_title/);
  assert.match(miniPlanMarkup, /road10kMode \? tr\.road10kInputBody/);
  assert.doesNotMatch(
    miniOptInStyles,
    /--(?:text-primary|text-secondary|accent-primary|border-default|text-danger|bg-surface)|rgba\(/,
  );
  assert.match(miniAppStyles, /--overlay:/);
  assert.match(miniPlanMarkup, /bindtap="onReviewLater"/);
  assert.match(miniOptInMarkup, /wx:if="\{\{error\}\}".*road-10k-error/s);
  assert.match(miniOptInStyles, /max-height: calc\(100vh/);
  assert.match(miniOptInStyles, /env\(safe-area-inset-bottom\)/);
  assert.match(miniOptInStyles, /var\(--primary-on\)/);
  assert.doesNotMatch(miniOptInStyles, /#fff/);
});
