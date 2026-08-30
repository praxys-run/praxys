import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('Today deterministic guidance uses source-aware branding', async () => {
  const [webToday, insightsCard, miniToday, miniTemplate, miniAnalysis] = await Promise.all([
    read('../src/pages/Today.tsx'),
    read('../src/components/AiInsightsCard.tsx'),
    read('../../miniapp/pages/today/index.ts'),
    read('../../miniapp/pages/today/index.wxml'),
    read('../../miniapp/pages/analysis/index.ts'),
  ]);

  assert.match(webToday, /summary:\s*localizedRecoverySummary\(ra,\s*i18n\)/);
  assert.match(webToday, /recommendations:\s*localizedAlternatives/);
  assert.match(webToday, /fetchInsight=\{false\}/);

  assert.match(
    miniToday,
    /summary:\s*localizedRecoverySummary\(response\.recovery_analysis\)/,
  );
  assert.match(miniToday, /recommendations,\s*\n\s*attribution,/);
  assert.match(miniTemplate, /class="coach-summary">\{\{coach\.summary\}\}/);

  assert.match(miniToday, /mark: t\('Training metrics'\)/);
  assert.match(miniToday, /aria: t\('Deterministic training summary'\)/);
  assert.doesNotMatch(miniToday, /t\('Praxys Coach(?: guidance)?'\)/);
  assert.match(miniAnalysis, /mark: coachIsAi \? tr\.coachMark : tr\.metricsMark/);
  assert.match(miniAnalysis, /aria: coachIsAi \? tr\.coachAria : tr\.metricsAria/);

  assert.match(
    insightsCard,
    /displayedContent\.isAi \? <Trans>Praxys Coach<\/Trans> : <Trans>Training metrics<\/Trans>/,
  );
  assert.match(
    insightsCard,
    /displayedContent\.isAi[\s\S]*Praxys Coach insight[\s\S]*Deterministic training summary/,
  );
});
