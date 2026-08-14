export function initialDashboardUrl(
  pathname: string,
  hasToken: boolean,
): '/api/today' | '/api/training' | null {
  if (!hasToken) return null;
  if (pathname === '/' || pathname === '/today') return '/api/today';
  if (pathname === '/analysis') return '/api/training';
  return null;
}
