import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react';
import { apiFetch, getAuthHeaders, useApi } from '@/hooks/useApi';
import type {
  AiInsightResponse,
  AiInsightFinding,
  InsightFeedbackResponse,
  InsightFeedbackVote,
} from '@/types/api';
import { msg } from '@lingui/core/macro';
import { Trans, Plural, useLingui } from '@lingui/react/macro';
import { useLocale } from '@/contexts/LocaleContext';
import { Link } from 'react-router-dom';
import type { CoachTheoryRef } from '@/types/api';
import { linkifyScienceTerms } from '@/lib/science-links';

/**
 * Deterministic content rendered separately when no Azure AI insight exists.
 * It must never be presented as AI-generated output.
 */
export interface CoachFallback {
  /** Lead sentence shown in the receipt body. Accepts ReactNode so
   *  callers can embed `<strong>` highlights for numbers (Goal does
   *  this — "<strong>14</strong> days to race day…"). */
  headline: ReactNode;
  summary?: string;
  findings?: AiInsightFinding[];
  recommendations?: string[];
  /** Stamp shown in the cobalt banner where AI insights show timeAgo
   *  (e.g. "6wk" lookback for a weekly diagnosis). Optional. */
  stamp?: string;
}

interface Props {
  /** Durable insight slot, or the disabled Today slot used with deterministic content. */
  insightType: string;
  snapshot?: string | null;
  theoryRefs?: CoachTheoryRef[];
  /** Optional theory attribution rendered in the muted receipt footer. */
  attribution?: string;
  /** Separately labelled deterministic companion shown when the AI slot is empty. */
  fallback?: CoachFallback;
  /** Called the first time the user expands the receipt's reasoning details. */
  onDetailsOpen?: () => void;
  /** Refresh the page dataset when the displayed insight version is stale. */
  onFeedbackStale?: () => void | Promise<void>;
  /** Disable the insight request while retaining separately labelled deterministic content. */
  fetchInsight?: boolean;
}

function coachText(text: string): ReactNode {
  return text.split(/(\d+(?:[.,:–-]\d+)*)/g).map((part, index) =>
    /^\d/.test(part) ? <span className="font-data" key={index}>{part}</span> : part);
}

/** Render a source-aware insight receipt with AI-only feedback controls. */
export default function AiInsightsCard({
  insightType,
  snapshot,
  theoryRefs,
  attribution,
  fallback,
  onDetailsOpen,
  onFeedbackStale,
  fetchInsight = true,
}: Props) {
  const daily = insightType === 'daily_brief';
  const { data, refetch, loading, stale, error } = useApi<AiInsightResponse>(
    `/api/insights/${insightType}${daily && snapshot ? `?snapshot=${encodeURIComponent(snapshot)}` : ''}`,
    { enabled: fetchInsight && (!daily || Boolean(snapshot)), refetchOnMount: 'always', refetchOnWindowFocus: 'always' },
  );
  const { locale } = useLocale();
  const { i18n } = useLingui();

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [feedbackVote, setFeedbackVote] = useState<InsightFeedbackVote | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackStale, setFeedbackStale] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');

  const coherent = !daily || (Boolean(snapshot) && data?.snapshot === snapshot
    && data?.content_status === 'ready' && data.insight?.snapshot === snapshot
    && data.insight?.content_version === 'morning-coach-v1');
  const insight = fetchInsight && coherent && !stale && !error && !loading ? data?.insight : null;
  const aiUnavailable = fetchInsight && data?.ai_available === false;
  const refs = insight?.theory_refs ?? data?.theory_refs ?? theoryRefs ?? [];
  const statusText = error ? i18n._(msg`Couldn't load Coach. Try again.`)
    : loading ? i18n._(msg`Loading Coach…`)
    : aiUnavailable ? i18n._(msg`Azure AI insights are temporarily unavailable.`)
    : data?.content_status === 'unavailable' ? i18n._(msg`Coach analysis is unavailable. Training metrics remain available.`)
    : daily && (!snapshot || data?.content_status === 'stale') ? i18n._(msg`Coach needs a refreshed training snapshot.`)
    : !insight && fetchInsight ? i18n._(msg`Coach is waiting for a current analysis.`) : '';
  const rawDatasetHash = insight?.meta.dataset_hash;
  const datasetHash = insight?.feedback_allowed !== false
    && typeof rawDatasetHash === 'string'
    && /^[0-9a-f]{64}$/.test(rawDatasetHash)
    ? rawDatasetHash
    : null;
  const persistedFeedback = insight?.meta.feedback;
  const feedbackIdentityRef = useRef('');
  const feedbackIdentity = `${insightType}:${snapshot ?? ''}:${datasetHash ?? ''}`;
  useLayoutEffect(() => {
    feedbackIdentityRef.current = feedbackIdentity;
    return () => { feedbackIdentityRef.current = ''; };
  }, [feedbackIdentity]);

  const resetIdentity = `${feedbackIdentity}:${persistedFeedback?.vote ?? ''}`;
  const [previousIdentity, setPreviousIdentity] = useState('');
  if (previousIdentity !== resetIdentity) {
    setPreviousIdentity(resetIdentity);
    const matchesCurrent = datasetHash
      && persistedFeedback?.dataset_hash === datasetHash
      && (persistedFeedback.vote === 'up' || persistedFeedback.vote === 'down');
    setDetailsOpen(false);
    setFeedbackVote(matchesCurrent ? persistedFeedback.vote : null);
    setFeedbackSent(Boolean(matchesCurrent));
    setFeedbackStale(false);
    setFeedbackSending(false);
    setFeedbackOpen(false);
    setFeedbackComment('');
    setFeedbackError('');
  }

  // Prefer the active-locale translation when present; fall back to
  // the top-level English fields (Issue #103 contract).
  const localized = insight && (daily ? insight.translations?.[locale] : ((locale === 'zh' && insight.translations?.zh) || insight));

  // Resolve the actual content to render. AI and deterministic content retain
  // distinct branding; deterministic content is never presented as AI output.
  // If neither exists the surface stays hidden.
  const content = localized
    ? {
        headline: localized.headline as ReactNode,
        summary: localized.summary,
        findings: localized.findings ?? insight!.findings ?? [],
        recommendations: localized.recommendations ?? insight!.recommendations ?? [],
        stamp: insight!.as_of_date ?? insight!.generated_at?.slice(0, 10),
        isAi: true,
      }
    : fallback && !loading
      ? {
          headline: fallback.headline,
          summary: fallback.summary,
          findings: fallback.findings ?? [],
          recommendations: fallback.recommendations ?? [],
          stamp: fallback.stamp,
          isAi: false,
        }
      : null;

  const canCollectFeedback = Boolean(content?.isAi && datasetHash);

  const cancelFeedback = () => {
    if (feedbackSending) return;
    setFeedbackVote(null);
    setFeedbackOpen(false);
    setFeedbackComment('');
    setFeedbackError('');
  };

  const selectFeedback = (vote: InsightFeedbackVote) => {
    if (feedbackSent || feedbackSending || feedbackStale) return;
    if (feedbackVote === vote && feedbackOpen) {
      cancelFeedback();
      return;
    }
    setFeedbackVote(vote);
    setFeedbackOpen(true);
    setFeedbackError('');
  };

  const sendFeedback = async () => {
    if (!feedbackVote || !datasetHash || feedbackStale) return;
    const requestIdentity = feedbackIdentityRef.current;
    const requestIsCurrent = () => feedbackIdentityRef.current === requestIdentity;
    setFeedbackSending(true);
    setFeedbackError('');
    try {
      const response = await apiFetch(`/api/insights/${insightType}/feedback`, {
        method: 'POST',
        headers: {
          ...(getAuthHeaders() as Record<string, string>),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vote: feedbackVote,
          dataset_hash: datasetHash,
          comment: feedbackComment.trim() || null,
          ...(daily ? { snapshot, content_version: insight?.content_version } : {}),
        }),
      });
      if (!requestIsCurrent()) return;
      if (!response.ok) {
        const errorBody = await response.json().catch(() => null) as { detail?: unknown } | null;
        if (!requestIsCurrent()) return;
        if (
          response.status === 409
          && (
            errorBody?.detail === 'INSIGHT_FEEDBACK_STALE'
            || errorBody?.detail === 'INSIGHT_FEEDBACK_UNVERSIONED'
          )
        ) {
          setFeedbackStale(true);
          setFeedbackVote(null);
          setFeedbackComment('');
          setFeedbackError(i18n._(msg`This insight changed. Refresh the page before sending feedback.`));
          const refreshes: Array<Promise<unknown>> = [refetch()];
          if (onFeedbackStale) {
            refreshes.push(Promise.resolve().then(onFeedbackStale));
          }
          await Promise.allSettled(refreshes);
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json() as InsightFeedbackResponse;
      if (!requestIsCurrent()) return;
      setFeedbackVote(payload.feedback.vote);
      setFeedbackSent(true);
      setFeedbackOpen(false);
      setFeedbackComment('');
    } catch {
      if (requestIsCurrent()) {
        setFeedbackError(i18n._(msg`Couldn't send feedback. Try again.`));
      }
    } finally {
      if (requestIsCurrent()) setFeedbackSending(false);
    }
  };

  if (!content && !statusText) return null;

  const displayedContent = content ?? {
    headline: i18n._(msg`Azure AI insights are temporarily unavailable.`),
    summary: undefined,
    findings: [],
    recommendations: [],
    stamp: undefined,
    isAi: false,
  };

  const remainingRecommendations = displayedContent.recommendations.slice(1);
  const hasDetails = displayedContent.findings.length > 0 || remainingRecommendations.length > 0;
  const toggleDetails = () => {
    if (!detailsOpen) onDetailsOpen?.();
    setDetailsOpen((value) => !value);
  };

  return (
    <aside className="coach-receipt" aria-label={displayedContent.isAi
      ? i18n._(msg`Praxys Coach insight`)
      : i18n._(msg`Deterministic training summary`)}>
      <div className="coach-banner">
        <span className="coach-mark">
          {displayedContent.isAi || !content ? <Trans>Praxys Coach</Trans> : <Trans>Training metrics</Trans>}
        </span>
        {displayedContent.stamp && (
          <span className="coach-stamp font-data">{displayedContent.stamp}</span>
        )}
      </div>
      <div className="coach-body">
        {statusText && <div role={error ? 'alert' : 'status'} className="coach-status">
          <p><strong><Trans>Praxys Coach</Trans></strong> — {statusText}</p>
          {loading && <div className="coach-loading" aria-hidden="true"><span /><span /><span /></div>}
          {!loading && !aiUnavailable && <button type="button" className="coach-toggle" onClick={() => {
            if (onFeedbackStale) void onFeedbackStale();
            void refetch();
          }}><Trans>Refresh</Trans></button>}
        </div>}
        <h2 className="coach-headline">{content ? displayedContent.headline : <Trans>Praxys Coach</Trans>}</h2>
        {displayedContent.summary && (
          <p className="coach-summary">{coachText(displayedContent.summary)}</p>
        )}
        {displayedContent.recommendations[0] && <div className="coach-key-recommendation">
          <h3 className="coach-label"><Trans>Key recommendation</Trans></h3>
          <p className="coach-text">{coachText(displayedContent.recommendations[0])}</p>
        </div>}
        {insight?.data_as_of && <p className="coach-summary"><Trans>Data through</Trans>{' '}<span className="font-data">{insight.data_as_of.slice(0, 10)}</span></p>}
        {hasDetails && (
          <button
            type="button"
            className="coach-toggle font-data"
            onClick={toggleDetails}
            aria-expanded={detailsOpen}
          >
            <span className="coach-toggle-caret" aria-hidden="true">{detailsOpen ? '▾' : '▸'}</span>
            {detailsOpen ? (
              <Trans>Hide details</Trans>
            ) : (
              <span>
                {displayedContent.findings.length > 0 && (
                  <Plural value={displayedContent.findings.length} one="# finding" other="# findings" />
                )}
                {displayedContent.findings.length > 0 && remainingRecommendations.length > 0 && <Trans> · </Trans>}
                {remainingRecommendations.length > 0 && (
                  <Plural value={remainingRecommendations.length} one="# recommendation" other="# recommendations" />
                )}
              </span>
            )}
          </button>
        )}
        {detailsOpen && displayedContent.findings.length > 0 && (
          <>
            <p className="coach-label"><Trans>Findings</Trans></p>
            <ul className="coach-list">
              {displayedContent.findings.map((finding, index) => (
                <li key={index} className={`coach-row coach-row-${finding.type}`}>
                  <span className="coach-tag" aria-hidden="true">[{finding.type === 'positive' ? '+' : finding.type === 'warning' ? '!' : '·'}]</span>
                  <span className="coach-text">{linkifyScienceTerms(finding.text)}</span>
                </li>
              ))}
            </ul>
          </>
        )}
        {detailsOpen && remainingRecommendations.length > 0 && (
          <>
            {displayedContent.findings.length > 0 && <hr className="coach-rule" />}
            <p className="coach-label"><Trans>Recommendations</Trans></p>
            <ol className="coach-list">
              {remainingRecommendations.map((recommendation, index) => (
                <li key={index} className="coach-row">
                  <span className="coach-tag coach-tag-rec" aria-hidden="true">→</span>
                  <span className="coach-text">{linkifyScienceTerms(recommendation)}</span>
                </li>
              ))}
            </ol>
          </>
        )}

      </div>
      {refs.length > 0 && <nav className="coach-foot coach-theory-links" aria-label={i18n._(msg`Training methods`)}>
        {refs.map(ref => <Link key={ref.pillar} to={`/science#${ref.pillar}`}>{ref.label}</Link>)}
      </nav>}
      {canCollectFeedback && (
        <div className={`coach-feedback-panel ${feedbackOpen ? 'is-open' : ''}`.trim()}>
          <div className="coach-feedback-toolbar">
            {feedbackSent ? (
              <span className="coach-feedback-sent font-data" role="status">
                <Check size={13} aria-hidden="true" /> <Trans>Sent</Trans>
              </span>
            ) : (
              <>
                <span className="coach-feedback-question"><Trans>Was this insight useful?</Trans></span>
                <div
                  className="coach-feedback-actions"
                  role="group"
                  aria-label={i18n._(msg`Was this insight useful?`)}
                >
                  <button
                    type="button"
                    className={`coach-feedback-icon ${feedbackVote === 'up' ? 'is-selected' : ''}`.trim()}
                    aria-label={i18n._(msg`Helpful`)}
                    aria-pressed={feedbackVote === 'up'}
                    disabled={feedbackSending || feedbackStale}
                    onClick={() => selectFeedback('up')}
                  >
                    <ThumbsUp size={14} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className={`coach-feedback-icon ${feedbackVote === 'down' ? 'is-selected' : ''}`.trim()}
                    aria-label={i18n._(msg`Not helpful`)}
                    aria-pressed={feedbackVote === 'down'}
                    disabled={feedbackSending || feedbackStale}
                    onClick={() => selectFeedback('down')}
                  >
                    <ThumbsDown size={14} aria-hidden="true" />
                  </button>
                </div>
              </>
            )}
          </div>
          {feedbackOpen && !feedbackSent && (
            <div className="coach-feedback-form">
              <label className="sr-only" htmlFor={`coach-feedback-${insightType}`}>
                <Trans>Optional comment</Trans>
              </label>
              <textarea
                id={`coach-feedback-${insightType}`}
                value={feedbackComment}
                maxLength={200}
                rows={2}
                placeholder={i18n._(msg`What was useful or missing?`)}
                disabled={feedbackSending || feedbackStale}
                onChange={(event) => setFeedbackComment(event.target.value)}
              />
              <div className="coach-feedback-form-footer">
                <span className="coach-feedback-count font-data">{feedbackComment.length}/200</span>
                <button
                  type="button"
                  className="coach-feedback-cancel"
                  disabled={feedbackSending}
                  onClick={cancelFeedback}
                >
                  <Trans>Cancel</Trans>
                </button>
                <button
                  type="button"
                  className="coach-feedback-send"
                  disabled={feedbackSending || feedbackStale || !feedbackVote}
                  onClick={() => void sendFeedback()}
                >
                  {feedbackSending ? <Trans>Sending...</Trans> : <Trans>Send</Trans>}
                </button>
              </div>
              {feedbackError && (
                <p className="coach-feedback-error" role="alert">{feedbackError}</p>
              )}
            </div>
          )}
        </div>
      )}
      {attribution && refs.length === 0 && <div className="coach-foot">{attribution}</div>}
    </aside>
  );
}
