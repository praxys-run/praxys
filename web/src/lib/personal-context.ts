import type {
  PersonalContextCategory,
  PersonalContextDraftRequest,
  PersonalContextItem,
  PersonalContextPurpose,
} from '@/types/api';

export const PERSONAL_CONTEXT_PURPOSE_CONSENT_VERSION =
  'personal-context-purpose-v1';
export const PERSONAL_CONTEXT_AI_CONSENT_VERSION =
  'personal-context-ai-v1';

const DAY_MS = 24 * 60 * 60 * 1000;
const EXECUTION_RETENTION_DAYS = 180;
const NARRATIVE_RETENTION_DAYS = 30;
const TEMPORARY_POST_EXPIRY_RETENTION_DAYS = 30;

export const SAFETY_CONTEXT_CATEGORIES = new Set<PersonalContextCategory>([
  'illness',
  'pain_or_injury',
  'red_flag_symptoms',
]);

export type PersonalContextDraftMode =
  | 'temporary_constraint'
  | 'execution_explanation';
export type PersonalContextWorkoutStatus = '' | 'missed' | 'modified';

export interface PersonalContextDraftForm {
  mode: PersonalContextDraftMode;
  category: PersonalContextCategory | '';
  startDate: string;
  endDate: string;
  affectedDays: string[];
  maximumAvailableMinutes: string;
  availableEquipment: string[];
  availableTerrain: string[];
  workoutId: string;
  workoutDate: string;
  workoutStatus: PersonalContextWorkoutStatus;
  narrative: string;
}

function localIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function shiftDate(value: Date, days: number): Date {
  return new Date(value.getTime() + (days * DAY_MS));
}

function dateStart(value: string): Date {
  return new Date(`${value}T00:00:00.000`);
}

function dateEnd(value: string): Date {
  return new Date(`${value}T23:59:59.999`);
}

function enumerateDates(start: string, end: string): string[] {
  const first = dateStart(start);
  const last = dateStart(end);
  if (
    Number.isNaN(first.getTime())
    || Number.isNaN(last.getTime())
    || first > last
  ) {
    return [];
  }
  const dates: string[] = [];
  for (
    let current = first;
    current <= last && dates.length <= 31;
    current = shiftDate(current, 1)
  ) {
    dates.push(localIsoDate(current));
  }
  return dates.length <= 31 ? dates : [];
}

export function createPersonalContextDraft(
  mode: PersonalContextDraftMode,
  now = new Date(),
): PersonalContextDraftForm {
  return {
    mode,
    category: '',
    startDate: localIsoDate(now),
    endDate: localIsoDate(shiftDate(now, 14)),
    affectedDays: [],
    maximumAvailableMinutes: '',
    availableEquipment: [],
    availableTerrain: [],
    workoutId: '',
    workoutDate: '',
    workoutStatus: '',
    narrative: '',
  };
}

export function draftFromContextItem(
  item: PersonalContextItem,
): PersonalContextDraftForm {
  const fields = item.payload.fields;
  const affectedDates = Array.isArray(fields.affected_dates)
    ? fields.affected_dates.filter(
      (value): value is string => typeof value === 'string',
    )
    : [];
  return {
    mode: item.kind === 'execution_explanation'
      ? 'execution_explanation'
      : 'temporary_constraint',
    category: item.payload.category,
    startDate: localIsoDate(new Date(item.starts_at)),
    endDate: item.expires_at
      ? localIsoDate(new Date(item.expires_at))
      : '',
    affectedDays: Array.isArray(fields.affected_days)
      ? fields.affected_days.filter(
        (value): value is string => typeof value === 'string',
      )
      : [],
    maximumAvailableMinutes:
      typeof fields.maximum_available_minutes === 'number'
        ? String(fields.maximum_available_minutes)
        : '',
    availableEquipment: Array.isArray(fields.available_equipment)
      ? fields.available_equipment.filter(
        (value): value is string => typeof value === 'string',
      )
      : [],
    availableTerrain: Array.isArray(fields.available_terrain)
      ? fields.available_terrain.filter(
        (value): value is string => typeof value === 'string',
      )
      : [],
    workoutId: item.linked_subject_type === 'workout'
      ? item.linked_subject_id ?? ''
      : '',
    workoutDate: affectedDates[0] ?? '',
    workoutStatus:
      fields.workout_status === 'missed'
      || fields.workout_status === 'modified'
        ? fields.workout_status
        : '',
    narrative: item.payload.narrative ?? '',
  };
}

export function buildPersonalContextDraftRequest(
  form: PersonalContextDraftForm,
  now = new Date(),
): PersonalContextDraftRequest {
  if (!form.category) {
    throw new Error('A context category is required');
  }
  const narrative = form.narrative.trim();
  const fields: Record<string, string | number | string[]> = {};

  if (form.mode === 'execution_explanation') {
    if (!form.workoutId || !form.workoutDate || !form.workoutStatus) {
      throw new Error('A workout and outcome are required');
    }
    fields.affected_dates = [form.workoutDate];
    fields.workout_status = form.workoutStatus;
    const expiresAt = shiftDate(now, EXECUTION_RETENTION_DAYS);
    return {
      kind: 'execution_explanation',
      purpose: 'execution_interpretation',
      payload: {
        category: form.category,
        fields,
        ...(narrative ? { narrative } : {}),
      },
      linked_subject_type: 'workout',
      linked_subject_id: form.workoutId,
      starts_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
      purge_after: expiresAt.toISOString(),
      ...(narrative
        ? {
          narrative_purge_at: shiftDate(
            now,
            NARRATIVE_RETENTION_DAYS,
          ).toISOString(),
        }
        : {}),
    };
  }

  const startsAt = dateStart(form.startDate);
  const expiresAt = dateEnd(form.endDate);
  const affectedDates = enumerateDates(form.startDate, form.endDate);
  if (affectedDates.length > 0) fields.affected_dates = affectedDates;
  if (form.affectedDays.length > 0) {
    fields.affected_days = form.affectedDays;
  }
  const maximumMinutes = Number(form.maximumAvailableMinutes);
  if (
    form.maximumAvailableMinutes.trim()
    && Number.isInteger(maximumMinutes)
    && maximumMinutes >= 1
    && maximumMinutes <= 1440
  ) {
    fields.maximum_available_minutes = maximumMinutes;
  }
  if (form.availableEquipment.length > 0) {
    fields.available_equipment = form.availableEquipment;
  }
  if (form.availableTerrain.length > 0) {
    fields.available_terrain = form.availableTerrain;
  }
  return {
    kind: 'temporary_constraint',
    purpose: 'plan_adjustment',
    payload: {
      category: form.category,
      fields,
      ...(narrative ? { narrative } : {}),
    },
    starts_at: startsAt.toISOString(),
    expires_at: expiresAt.toISOString(),
    purge_after: new Date(
      expiresAt.getTime()
      + (TEMPORARY_POST_EXPIRY_RETENTION_DAYS * DAY_MS),
    ).toISOString(),
    ...(narrative
      ? {
        narrative_purge_at: shiftDate(
          now,
          NARRATIVE_RETENTION_DAYS,
        ).toISOString(),
      }
      : {}),
  };
}

export function personalContextDisclosedFields(
  item: PersonalContextItem,
): string[] {
  return [
    'category',
    ...Object.keys(item.payload.fields)
      .sort()
      .map((field) => `fields.${field}`),
  ];
}

export function personalContextNarrativeAvailable(
  item: PersonalContextItem,
  now = new Date(),
): boolean {
  return (
    item.has_narrative
    && item.narrative_purged_at == null
    && item.narrative_purge_at != null
    && new Date(item.narrative_purge_at).getTime() > now.getTime()
  );
}

export function personalContextPurpose(
  mode: PersonalContextDraftMode,
): PersonalContextPurpose {
  return mode === 'execution_explanation'
    ? 'execution_interpretation'
    : 'plan_adjustment';
}

export function personalContextEvidenceIds(
  evidence: Record<string, unknown>,
): string[] {
  const values = evidence.context_item_ids;
  if (!Array.isArray(values)) return [];
  return values.filter(
    (value): value is string => typeof value === 'string' && value.length > 0,
  );
}

export function personalContextIdempotencyKey(): string {
  const suffix = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `personal-context:${suffix}`;
}
