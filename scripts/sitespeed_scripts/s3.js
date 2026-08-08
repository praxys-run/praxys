/**
 * S3 — Warm repeat visit to Today (after login).
 *
 * Drives Chrome through:
 *   1. Login flow (not measured)
 *   2. Settle on /today (warm-up — populates SW cache, react-query cache)
 *   3. Navigate AWAY (about:blank) to clear current page state
 *   4. Re-navigate to /today and MEASURE that
 *
 * Step 3 is the trick: simply re-navigating to the same URL would no-op or
 * use bfcache. Bouncing through about:blank forces a real navigation, but
 * the SW + HTTP cache from step 2 still apply, so we measure "what does
 * /today feel like for a returning user whose service worker already has
 * the shell cached?"
 *
 * Phase 2 #7 (PWA precaching) is exactly the change that makes this
 * scenario fast — without the SW, S3 is a normal cold load minus the
 * login.
 */

module.exports = async function (context, commands) {
  const baseUrl = process.env.PRAXYS_PERF_BASE_URL || 'https://www.praxys.run';
  const user = process.env.PRAXYS_PERF_USER || 'demo@trainsight.dev';
  const password = process.env.PRAXYS_PERF_PASSWORD || 'demo';

  // Step 1 — log in.
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

  // Step 2 — bounce off about:blank to force a real next navigation.
  await commands.navigate('about:blank');
  await commands.wait.byTime(500);

  // Step 3 — measured warm revisit to /today.
  await commands.measure.start('s3-today-warm');
  await commands.navigate(`${baseUrl}/today`);
  await commands.wait.byPageToComplete(15000);
  await commands.measure.stop();
};
