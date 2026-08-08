/**
 * S2 — Cold first load of Training page (via login).
 *
 * Same login flow as S1, but the measured navigation lands on /training
 * instead of /today. Training is the page with the worst pre-Phase-2-#4
 * waterfall (multiple parallel /api/* calls) so this scenario is where
 * Phase 1 #3 (FastAPI GZip) and Phase 2 #4 (Training collapse) become
 * measurable.
 */

module.exports = async function (context, commands) {
  const baseUrl = process.env.PRAXYS_PERF_BASE_URL || 'https://www.praxys.run';
  const user = process.env.PRAXYS_PERF_USER || 'demo@trainsight.dev';
  const password = process.env.PRAXYS_PERF_PASSWORD || 'demo';

  // Step 1 — log in (not measured).
  await commands.navigate(`${baseUrl}/login`);
  await commands.wait.bySelector('input[type="email"]', 10000);

  await commands.click.bySelector('input[type="email"]');
  await commands.addText.bySelector(user, 'input[type="email"]');

  await commands.click.bySelector('input[type="password"]');
  await commands.addText.bySelector(password, 'input[type="password"]');

  await commands.click.bySelector('button[type="submit"]');
  await commands.wait.byCondition(
    'document.location.pathname === "/today"',
    30000,
  );
  await commands.wait.byPageToComplete(15000);

  // Step 2 — now navigate to /training and measure that.
  await commands.measure.start('s2-training');
  await commands.navigate(`${baseUrl}/training`);
  await commands.wait.byPageToComplete(20000);
  await commands.measure.stop();
};
