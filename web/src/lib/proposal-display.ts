function displayKey(value: string): string {
  return value.replace(/_/g, ' ');
}

export function formatProposalDetail(value: unknown): string {
  if (value == null) return '—';
  if (typeof value !== 'object') return String(value);
  if (Array.isArray(value)) {
    return value.map(formatProposalDetail).join(', ');
  }

  const record = value as Record<string, unknown>;
  const entries = Object.entries(record);
  if (entries.length === 0) return '—';

  const kind = record.kind;
  if (typeof kind === 'string' && Object.hasOwn(record, 'value')) {
    return `${displayKey(kind)}: ${formatProposalDetail(record.value)}`;
  }

  return entries
    .map(([key, nestedValue]) => `${displayKey(key)}: ${formatProposalDetail(nestedValue)}`)
    .join(', ');
}
