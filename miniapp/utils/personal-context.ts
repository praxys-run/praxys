import type {
  PersonalContextCategory,
  PersonalContextDraftRequest,
  PersonalContextFieldValue,
  PersonalContextItem,
  PersonalContextKind,
} from '../types/api';

export const PURPOSE_CONSENT_VERSION = 'personal-context-purpose-v1';
const ALL_CONTEXT_CATEGORIES: PersonalContextCategory[] = [
  'less_time',
  'unavailable_day',
  'schedule_conflict',
  'caregiving',
  'travel',
  'fatigue',
  'motivation',
  'illness',
  'pain_or_injury',
  'red_flag_symptoms',
  'weather',
  'equipment_access',
  'other',
  'prefer_not_to_say',
];

export const TEMPORARY_CATEGORIES = [...ALL_CONTEXT_CATEGORIES];
export const EXECUTION_CATEGORIES = [...ALL_CONTEXT_CATEGORIES];

export interface MiniContextDraft {
  kind: Extract<
    PersonalContextKind,
    'temporary_constraint' | 'execution_explanation'
  >;
  category: PersonalContextCategory;
  startDate: string;
  endDate: string;
  availableDays: string[];
  maximumMinutes: string;
  equipment: string[];
  terrain: string[];
  workoutId: string;
  workoutDate: string;
  workoutStatus: '' | 'missed' | 'modified';
  narrative: string;
}

const DAY_MS = 24 * 60 * 60 * 1000;

export function localIsoDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function addLocalDays(date: string, days: number): string {
  const parsed = new Date(`${date}T12:00:00`);
  parsed.setDate(parsed.getDate() + days);
  return localIsoDate(parsed);
}

export function defaultContextDraft(
  kind: MiniContextDraft['kind'] = 'temporary_constraint',
): MiniContextDraft {
  const today = localIsoDate();
  return {
    kind,
    category: kind === 'execution_explanation'
      ? 'schedule_conflict'
      : 'less_time',
    startDate: today,
    endDate: addLocalDays(today, 14),
    availableDays: [],
    maximumMinutes: '',
    equipment: [],
    terrain: [],
    workoutId: '',
    workoutDate: '',
    workoutStatus: '',
    narrative: '',
  };
}

function localStartIso(date: string): string {
  return new Date(`${date}T00:00:00.000`).toISOString();
}

function localEndIso(date: string): string {
  return new Date(`${date}T23:59:59.999`).toISOString();
}

function boundedDates(start: string, end: string): string[] {
  const values: string[] = [];
  let cursor = start;
  while (cursor <= end && values.length <= 31) {
    values.push(cursor);
    cursor = addLocalDays(cursor, 1);
  }
  return values.length <= 31 ? values : [];
}

function draftFields(
  draft: MiniContextDraft,
): Record<string, PersonalContextFieldValue> {
  if (draft.kind === 'execution_explanation') {
    return {
      affected_dates: draft.workoutDate ? [draft.workoutDate] : [],
      workout_status: draft.workoutStatus || 'missed',
    };
  }

  const fields: Record<string, PersonalContextFieldValue> = {};
  const dates = boundedDates(draft.startDate, draft.endDate);
  if (dates.length > 0) fields.affected_dates = dates;
  if (draft.availableDays.length > 0) {
    fields.affected_days = draft.availableDays;
  }
  const maximumMinutes = Number(draft.maximumMinutes);
  if (
    draft.maximumMinutes.trim()
    && Number.isInteger(maximumMinutes)
    && maximumMinutes >= 1
    && maximumMinutes <= 1440
  ) {
    fields.maximum_available_minutes = maximumMinutes;
  }
  if (draft.equipment.length > 0) {
    fields.available_equipment = draft.equipment;
  }
  if (draft.terrain.length > 0) {
    fields.available_terrain = draft.terrain;
  }
  return fields;
}

export function buildContextDraftRequest(
  draft: MiniContextDraft,
  now = new Date(),
): PersonalContextDraftRequest {
  const narrative = draft.narrative.trim();
  const payload = {
    category: draft.category,
    fields: draftFields(draft),
    ...(narrative ? { narrative } : {}),
  };
  const narrativePurge = narrative
    ? new Date(now.getTime() + (30 * DAY_MS)).toISOString()
    : null;

  if (draft.kind === 'execution_explanation') {
    const purge = new Date(now.getTime() + (180 * DAY_MS)).toISOString();
    return {
      kind: draft.kind,
      purpose: 'execution_interpretation',
      payload,
      linked_subject_type: 'workout',
      linked_subject_id: draft.workoutId,
      starts_at: now.toISOString(),
      expires_at: purge,
      purge_after: purge,
      narrative_purge_at: narrativePurge,
    };
  }

  const expires = localEndIso(draft.endDate);
  return {
    kind: draft.kind,
    purpose: 'plan_adjustment',
    payload,
    starts_at: localStartIso(draft.startDate),
    expires_at: expires,
    purge_after: new Date(
      new Date(expires).getTime() + (30 * DAY_MS),
    ).toISOString(),
    narrative_purge_at: narrativePurge,
  };
}

export function hydrateContextDraft(item: PersonalContextItem): MiniContextDraft {
  const fields = item.payload.fields;
  const stringList = (value: PersonalContextFieldValue | undefined): string[] => (
    Array.isArray(value)
      ? value.filter((entry): entry is string => typeof entry === 'string')
      : []
  );
  return {
    kind: item.kind === 'execution_explanation'
      ? 'execution_explanation'
      : 'temporary_constraint',
    category: item.payload.category,
    startDate: localIsoDate(new Date(item.starts_at)),
    endDate: item.expires_at
      ? localIsoDate(new Date(item.expires_at))
      : localIsoDate(new Date(item.starts_at)),
    availableDays: stringList(fields.affected_days),
    maximumMinutes:
      typeof fields.maximum_available_minutes === 'number'
        ? String(fields.maximum_available_minutes)
        : '',
    equipment: stringList(fields.available_equipment),
    terrain: stringList(fields.available_terrain),
    workoutId: item.linked_subject_type === 'workout'
      ? item.linked_subject_id ?? ''
      : '',
    workoutDate: stringList(fields.affected_dates)[0] ?? '',
    workoutStatus:
      fields.workout_status === 'missed'
      || fields.workout_status === 'modified'
        ? fields.workout_status
        : '',
    narrative: item.payload.narrative ?? '',
  };
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

export function contextIdempotencyKey(action: string): string {
  return `${action}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
}
