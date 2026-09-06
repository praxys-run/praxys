import type {
  TrailClientEnvelope,
  TrailGradeDistribution,
} from '../../types/trail-plan.ts';

export function unknown<T>(): TrailClientEnvelope<T> {
  return { state: 'unknown' };
}

export function known<T>(value: T): TrailClientEnvelope<T> {
  return { state: 'known', value };
}

export function applyUnknownIntent<T>(
  current: TrailClientEnvelope<T>,
  makeUnknown: boolean,
): TrailClientEnvelope<T> {
  return makeUnknown ? unknown<T>() : current;
}

export function toggleEnvelopeMember<T extends string | number>(
  current: TrailClientEnvelope<T[]>,
  value: T,
  allowKnownEmpty: boolean,
): TrailClientEnvelope<T[]> {
  const values = current.state === 'known' ? current.value : [];
  const next = values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
  return next.length > 0 || allowKnownEmpty ? known(next) : current;
}

export function parseGradeBasisPoints(raw: string): number | null {
  if (!/^\d+(?:\.\d{1,2})?$/.test(raw)) return null;
  const [whole, fraction = ''] = raw.split('.');
  const value = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return Number.isSafeInteger(value) && value >= 0 && value <= 10000
    ? value
    : null;
}

export function gradeEnvelopeFromExplicitInputs(
  raw: readonly [string, string, string, string, string],
): TrailClientEnvelope<TrailGradeDistribution> {
  const values = raw.map(parseGradeBasisPoints);
  if (values.some((value) => value === null)
    || values.reduce<number>((total, value) => total + (value ?? 0), 0) !== 10000) {
    return unknown();
  }
  const [a, b, c, d, e] = values as [number, number, number, number, number];
  return known({
    below_neg_10: a,
    neg_10_to_below_neg_3: b,
    neg_3_to_below_pos_3: c,
    pos_3_to_below_pos_10: d,
    pos_10_and_above: e,
  });
}

export function integerEnvelopeFromExplicitInput(
  raw: string,
  minimum: number,
  maximum: number,
): TrailClientEnvelope<number> {
  if (!/^-?\d+$/.test(raw)) return unknown();
  const value = Number(raw);
  return Number.isSafeInteger(value) && value >= minimum && value <= maximum
    ? known(value)
    : unknown();
}

export function decimalEnvelopeFromExplicitInput(
  raw: string,
  fractionalDigits: number,
  minimum: number,
  maximum: number,
): TrailClientEnvelope<number> {
  const expression = new RegExp(`^-?\\d+(?:\\.\\d{1,${fractionalDigits}})?$`);
  if (!expression.test(raw)) return unknown();
  const value = Number(raw);
  return Number.isFinite(value) && value >= minimum && value <= maximum
    ? known(value)
    : unknown();
}

export function metresEnvelopeFromExplicitKilometres(
  raw: string,
  minimum: number,
  maximum: number,
): TrailClientEnvelope<number> {
  if (!/^\d+(?:\.\d{1,3})?$/.test(raw)) return unknown();
  const [whole, fraction = ''] = raw.split('.');
  const value = Number(whole) * 1000 + Number(fraction.padEnd(3, '0'));
  return Number.isSafeInteger(value) && value >= minimum && value <= maximum
    ? known(value)
    : unknown();
}

export function durationEnvelopeFromExplicitInputs(
  hours: string,
  minutes: string,
  minimum: number,
  maximum: number,
): TrailClientEnvelope<number> {
  const parsedHours = integerEnvelopeFromExplicitInput(
    hours,
    0,
    Math.ceil(maximum / 60),
  );
  const parsedMinutes = integerEnvelopeFromExplicitInput(minutes, 0, 59);
  if (parsedHours.state === 'unknown' || parsedMinutes.state === 'unknown') {
    return unknown();
  }
  const value = parsedHours.value * 60 + parsedMinutes.value;
  return value >= minimum && value <= maximum ? known(value) : unknown();
}
