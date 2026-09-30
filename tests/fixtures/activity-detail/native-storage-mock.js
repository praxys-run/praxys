function syntheticActivityDetailStorage(key) {
  const fixture = getApp().__activityDetailVerification;
  if (key === 'praxys.cn-processing-notice') return '2026.09.1';
  if (key === 'praxys-auth-token') return 'synthetic-local-only-token';
  if (key === 'praxys-theme') return fixture ? fixture.theme : 'light';
  if (key === 'praxys-language') return fixture ? fixture.locale : 'zh';
  return '';
}
