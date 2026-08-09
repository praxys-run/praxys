import type {
  PlanManagementConfig,
  PlannedWorkout,
} from '../types/api';

export const MANAGED_PLAN_WINDOW_DAYS = 14;

const requestGenerations = new WeakMap<object, number>();

export function beginManagedPlanRequest(owner: object): number {
  const generation = (requestGenerations.get(owner) ?? 0) + 1;
  requestGenerations.set(owner, generation);
  return generation;
}

export function isLatestManagedPlanRequest(
  owner: object,
  generation: number,
): boolean {
  return requestGenerations.get(owner) === generation;
}

export function invalidateManagedPlanRequests(owner: object): void {
  beginManagedPlanRequest(owner);
}

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

export type ManagedPlanState = 'external' | 'active' | 'paused';

interface PlanTargetChoice<T extends string> {
  key: T;
  selectable: boolean;
}

/**
 * Keep active delivery read-only while allowing paused mode to stage another
 * eligible target without enabling delivery.
 */
export function planTargetSelection<T extends string>(
  state: ManagedPlanState,
  options: readonly PlanTargetChoice<T>[],
  explicitChoice: T | null,
  primaryActivitySource: T | null,
  configuredTarget: T | null,
): T | null {
  if (state === 'active') return configuredTarget;
  const selectable = options
    .filter((option) => option.selectable)
    .map((option) => option.key);
  if (state === 'paused') {
    if (explicitChoice && selectable.includes(explicitChoice)) {
      return explicitChoice;
    }
    if (configuredTarget) return configuredTarget;
  }
  if (explicitChoice && selectable.includes(explicitChoice)) {
    return explicitChoice;
  }
  if (
    primaryActivitySource
    && selectable.includes(primaryActivitySource)
  ) {
    return primaryActivitySource;
  }
  if (configuredTarget && selectable.includes(configuredTarget)) {
    return configuredTarget;
  }
  return selectable.length === 1 ? selectable[0] : null;
}

export function managedPlanState(
  config: PlanManagementConfig,
): ManagedPlanState {
  if (config.mode === 'external') return 'external';
  return config.delivery_enabled ? 'active' : 'paused';
}

export function workoutKey(workout: PlannedWorkout): string {
  return workout.canonical_id
    ?? workout.reconciliation?.id
    ?? `${workout.source}-${workout.date}-${workout.workout_type}`;
}

export function formatWorkoutType(value: string): string {
  return value
    .split(/[\s_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
