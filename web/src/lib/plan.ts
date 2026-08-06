import type { PlanManagementConfig, PlannedWorkout } from '@/types/api';

export const MANAGED_PLAN_WINDOW_DAYS = 14;

function utcIsoDate(value: Date): string {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, '0');
  const day = String(value.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function localIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function shiftAthletePlanDate(
  isoDate: string,
  days: number,
): string {
  const shifted = new Date(`${isoDate}T12:00:00`);
  shifted.setDate(shifted.getDate() + days);
  return localIsoDate(shifted);
}

export function athletePlanDateDistance(
  start: string,
  end: string,
): number {
  const [startYear, startMonth, startDay] = start.split('-').map(Number);
  const [endYear, endMonth, endDay] = end.split('-').map(Number);
  return Math.round((
    Date.UTC(endYear, endMonth - 1, endDay)
    - Date.UTC(startYear, startMonth - 1, startDay)
  ) / 86_400_000);
}

export function managedPlanWindow(
  days = MANAGED_PLAN_WINDOW_DAYS,
  now = new Date(),
): { start: string; end: string } {
  const end = new Date(now);
  end.setUTCDate(end.getUTCDate() + Math.max(days - 1, 0));
  return {
    start: utcIsoDate(now),
    end: utcIsoDate(end),
  };
}

export function athletePlanWindow(
  days = MANAGED_PLAN_WINDOW_DAYS,
  now = new Date(),
): { start: string; end: string } {
  const end = new Date(now);
  end.setDate(end.getDate() + Math.max(days - 1, 0));
  return {
    start: localIsoDate(now),
    end: localIsoDate(end),
  };
}

export function planWindowUrl(
  days = MANAGED_PLAN_WINDOW_DAYS,
  now = new Date(),
): string {
  const { start, end } = athletePlanWindow(days, now);
  return `/api/plan?start=${start}&end=${end}`;
}

export function managedPlanPreviewUrl(
  days = MANAGED_PLAN_WINDOW_DAYS,
  now = new Date(),
): string {
  const { start, end } = managedPlanWindow(days, now);
  return `/api/plan?start=${start}&end=${end}`;
}

export function isPraxysOwned(workout: PlannedWorkout): boolean {
  return workout.owner === 'praxys'
    || (workout.owner === undefined && workout.source === 'ai');
}

export function isRestWorkoutType(value: string): boolean {
  return ['rest', 'off'].includes(value.trim().toLowerCase());
}

export type ManagedPlanState = 'external' | 'active' | 'paused';

export function managedPlanState(
  config: PlanManagementConfig,
): ManagedPlanState {
  if (config.mode === 'external') return 'external';
  return config.delivery_enabled ? 'active' : 'paused';
}
