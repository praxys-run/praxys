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
  ]);

  assert.doesNotMatch(app, /path="\/road-10k/);
  assert.match(webGoal, /<Road10KControlledOptIn surface="goal" \/>/);
  assert.match(webTraining, /surface="training"/);
  assert.match(webSettings, /surface="settings"/);

  assert.match(miniGoalMarkup, /road-10k-controlled-opt-in surface="goal"/);
  assert.match(miniTrainingMarkup, /road-10k-controlled-opt-in id="training-road-10k" surface="training"/);
  assert.match(miniTrainingJson, /road-10k-controlled-opt-in/);
  assert.match(miniSettingsMarkup, /road-10k-controlled-opt-in surface="settings"/);
  assert.match(miniSettingsJson, /road-10k-controlled-opt-in/);

  assert.match(miniComponent, /pendingRoad10KIntent/);
  assert.match(miniComponent, /password:/);
  assert.match(miniComponent, /client: 'miniapp'/);
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
    assert.doesNotMatch(source, /password\?: never/);
  }

  assert.match(typechecks, /miniappRoad10KOptIn/);
  assert.match(typechecks, /invalidMiniappRoad10KOptIn/);
});
