import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const read = (path) => fs.readFile(new URL(path, root), 'utf8');

test('Road 10K remains hidden from public routing while exposing typed dormant states', async () => {
  const [app, control, page, miniControl, miniPage] = await Promise.all([
    read('web/src/App.tsx'),
    read('web/src/lib/road-10k-control.ts'),
    read('web/src/pages/Road10KControlledOptIn.tsx'),
    read('miniapp/utils/road-10k-control.ts'),
    read('miniapp/components/road-10k-controlled-opt-in/index.ts'),
  ]);
  assert.doesNotMatch(app, /path="\/road-10k/);
  assert.match(app, /path="goal"/);
  assert.match(page, /\/api\/road-10k\/access/);
  assert.match(page, /action\.not_now[\s\S]*setFlow\('idle'\)/);
  assert.match(page, /feedback\.screenshot_blocked/);
  assert.match(control, /ROAD_10K_ACCESS_STATE_COPY/);
  assert.match(control, /ROAD_10K_PLAN_STATE_COPY/);
  assert.match(control, /ROAD_10K_NETWORK_STATE_COPY/);
  assert.match(miniControl, /ROAD_10K_SCREENSHOT_AVAILABLE = false/);
  assert.match(miniPage, /import type \{ Road10KAccessResponse \}/);
  assert.match(miniPage, /withdrawnBody/);
});

test('Road 10K copy key catalog includes the complete accepted key families', async () => {
  const source = await read('web/src/lib/road-10k-control.ts');
  for (const key of [
    'invitation.title',
    'notice.ack',
    'proposal.adopt_title',
    'life.withdraw_body',
    'status.rollout_withdrawn',
    'status.plan_successor',
    'network.unavailable_title',
    'feedback.screenshot_blocked',
    'success.deleted',
  ]) {
    assert.match(source, new RegExp(`'${key.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}'`));
  }
});
