function setupActivityDetailVerification(state, locale, theme) {
  const allowed = ['normal', 'sparse', 'single_metric', 'distance_only', 'no_samples', 'not_found', 'server_error', 'network_error'];
  if (!allowed.includes(state) || !['en', 'zh'].includes(locale) || !['light', 'dark'].includes(theme)) {
    throw new Error('invalid_fixture_options');
  }
  const app = getApp();
  app.__activityDetailVerification = { state, locale, theme, requests: [] };
  app.globalData.locale = locale;
  app.globalData.themeClass = 'theme-' + theme;
  return { synthetic: true, state, locale, theme };
}
