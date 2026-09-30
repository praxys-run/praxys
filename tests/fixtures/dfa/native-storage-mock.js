function syntheticDFAStorage(key) {
  const fixture = getApp().__dfaVerification;
  // Entire API is mocked: never read existing credentials or write user storage.
  if (key === 'praxys.cn-processing-notice') return '2026.09.1';
  if (key === 'praxys-theme') return fixture ? fixture.theme : 'light';
  if (key === 'praxys-language') return fixture ? fixture.locale : 'zh';
  return '';
}
