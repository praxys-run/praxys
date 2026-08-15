import {
  MAX_MANAGED_PLAN_WINDOW_DAYS,
  planWindowUrl,
} from './plan.ts';

export function initialDashboardUrl(
  pathname: string,
  hasToken: boolean,
): string | null {
  if (!hasToken) return null;
  if (pathname === '/' || pathname === '/today') return '/api/today';
  if (pathname === '/training') {
    return planWindowUrl(MAX_MANAGED_PLAN_WINDOW_DAYS);
  }
  if (pathname === '/analysis') return '/api/training';
  return null;
}
