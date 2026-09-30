function setupDFAVerification(state, locale, theme) {
  const allowed = ['prepare', 'complete', 'expired', 'multiple', 'unavailable', 'no_valid', 'withdrawn'];
  if (!allowed.includes(state) || !['en', 'zh'].includes(locale) || !['light', 'dark'].includes(theme)) throw new Error('invalid_fixture_options');
  const app = getApp();
  app.__dfaVerification = {state, locale, theme, run: null, proof: null, polls: 0, generation: 1, requests: [], selected: 0};
  app.globalData.locale = locale;
  app.globalData.themeClass = 'theme-' + theme;
  return {synthetic: true, state, locale, theme};
}
