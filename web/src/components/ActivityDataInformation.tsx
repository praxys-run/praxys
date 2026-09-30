import { Trans, useLingui } from '@lingui/react/macro';
import { ChevronDown } from 'lucide-react';
import { knownRecordSource } from '@/lib/activity-record';
import { useRecordSourceName } from '@/hooks/useRecordSourceName';
import type { ActivityDetailResponse } from '@/types/api';

export default function ActivityDataInformation({ detail }: { detail: ActivityDetailResponse }) {
  const { t } = useLingui();
  const sourceName = useRecordSourceName();
  const scopedName = (source: string | null | undefined) => knownRecordSource(source)
    && knownRecordSource(source) === knownRecordSource(detail.activity.source)
    ? t`Same as activity record` : sourceName(source);
  return <details className="activity-report__data-info">
    <summary><Trans>Data information</Trans><ChevronDown size={16} aria-hidden="true" /></summary>
    <div className="activity-report__data-notes">
      {detail.sample_count > 0 && <>
        <p><Trans>Recorded sample rows</Trans>: <span className="font-data">{detail.sample_count}</span></p>
        {detail.sample_count > detail.samples.length && <p><Trans>Extrema shown; omitted points are not interpolated.</Trans></p>}
        <p><Trans>Missing metric readings and time gaps are shown as breaks, never filled in.</Trans></p>
      </>}
      {detail.time_origin === 'sample_start' && <p><Trans>Time is measured from the first stored sample; activity start time is unverified.</Trans></p>}
      {detail.time_origin === 'activity_start' && <p><Trans>Time is measured from the recorded activity start.</Trans></p>}
      <dl className="activity-report__provenance">
        <div><dt><Trans>Sample records</Trans></dt><dd>{detail.sample_sources.length
          ? [...new Set(detail.sample_sources.map(scopedName))].join(', ') : sourceName(null)}</dd></div>
        <div><dt><Trans>Environment records</Trans></dt><dd>{scopedName(detail.activity.environment_source)}</dd></div>
      </dl>
      <p><Trans>Record sources do not verify every field's source.</Trans></p>
      {detail.activity.splits.length > 0 && <p><Trans>Recorded split boundaries and recording method are unverified.</Trans></p>}
      {detail.kilometer_splits.length > 0 && <p><Trans>Kilometer boundaries use the first recorded distance sample to reach each kilometer.</Trans></p>}
      {(detail.activity.rss != null || detail.activity.cp_estimate != null) && <p><Trans>RSS and the source CP estimate are activity-level references, not sampled curves or a Praxys training verdict.</Trans></p>}
    </div>
  </details>;
}
