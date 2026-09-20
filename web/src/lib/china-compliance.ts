// Display policy only; this does not grant access or change processing consent.
const PUBLIC_FILING_PATHS = new Set([
  '/', '/zh', '/product', '/faq', '/zh/product', '/zh/faq',
  '/login', '/terms', '/privacy', '/status', '/verify',
]);

export function isChinaFilingPublicPath(pathname: string): boolean {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  return PUBLIC_FILING_PATHS.has(normalized);
}
