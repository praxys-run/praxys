import type { PlanManagementConfig, PlannedWorkout } from '@/types/api';

export const MANAGED_PLAN_WINDOW_DAYS = 14;

function localIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function planWindowUrl(days = MANAGED_PLAN_WINDOW_DAYS): string {
  const start = new Date();
  const end = new Date(start);
  end.setDate(end.getDate() + Math.max(days - 1, 0));
  return `/api/plan?start=${localIsoDate(start)}&end=${localIsoDate(end)}`;
}

export function isPraxysOwned(workout: PlannedWorkout): boolean {
  return workout.owner === 'praxys'
    || (workout.owner === undefined && workout.source === 'ai');
}

export type ManagedPlanState = 'external' | 'active' | 'paused';

export function managedPlanState(
  config: PlanManagementConfig,
): ManagedPlanState {
  if (config.mode === 'external') return 'external';
  return config.delivery_enabled ? 'active' : 'paused';
}
