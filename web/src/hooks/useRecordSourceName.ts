import { useLingui } from '@lingui/react/macro';
import { knownRecordSource } from '@/lib/activity-record';

export function useRecordSourceName() {
  const { t } = useLingui();
  return (source: string | null | undefined) => {
    if (!source?.trim()) return t`Source unavailable`;
    const known = knownRecordSource(source);
    if (known === 'Garmin activity weather') return t`Garmin activity weather`;
    if (known === 'Stryd activity weather') return t`Stryd activity weather`;
    return known ?? t`Unrecognized source name`;
  };
}
