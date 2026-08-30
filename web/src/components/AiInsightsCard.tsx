import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ThumbsDown, ThumbsUp } from 'lucide-react';
import { API_BASE, getAuthHeaders, useApi } from '@/hooks/useApi';
import type {
  AiInsightResponse,
  AiInsightFinding,
  InsightFeedbackResponse,
  InsightFeedbackVote,
} from '@/types/api';
import { msg } from '@lingui/core/macro';
import { Trans, Plural, useLingui } from '@lingui/react/macro';
import { useLocale } from '@/contexts/LocaleContext';
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

const PLUGIN_URL = 'https://github.com/praxys-run/praxys-coach-plugin#install';

function timeAgo(isoDate: string, locale: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const rtf = new Intl.RelativeTimeFormat(locale === 'zh' ? 'zh-CN' : 'en-US', { style: 'short' });
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return rtf.format(-mins, 'minute');
  const hours = Math.floor(mins / 60);
  if (hours < 24) return rtf.format(-hours, 'hour');
  const days = Math.floor(hours / 24);
  return rtf.format(-days, 'day');
}

/** Render a source-aware insight receipt with AI-only feedback controls. */
export default function AiInsightsCard({
  insightType,
  attribution,
  fallback,
  onDetailsOpen,
  onFeedbackStale,
  fetchInsight = true,
}: Props) {
  const { data, refetch } = useApi<AiInsightResponse>(
    `/api/insights/${insightType}`,
    { enabled: fetchInsight },
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

  const insight = fetchInsight ? data?.insight : null;
  const aiUnavailable = fetchInsight && data?.ai_available === false;
  const rawDatasetHash = insight?.meta.dataset_hash;
  const datasetHash = insight?.feedback_allowed !== false
    && typeof rawDatasetHash === 'string'
    && /^[0-9a-f]{64}$/.test(rawDatasetHash)
    ? rawDatasetHash
    : null;
  const persistedFeedback = insight?.meta.feedback;
  const feedbackIdentityRef = useRef('');
  feedbackIdentityRef.current = `${insightType}:${datasetHash ?? ''}`;

  useEffect(() => {
    const matchesCurrent = datasetHash
      && persistedFeedback?.dataset_hash === datasetHash
      && (persistedFeedback.vote === 'up' || persistedFeedback.vote === 'down');
    setFeedbackVote(matchesCurrent ? persistedFeedback.vote : null);
    setFeedbackSent(Boolean(matchesCurrent));
    setFeedbackStale(false);
    setFeedbackSending(false);
    setFeedbackOpen(false);
    setFeedbackComment('');
    setFeedbackError('');
  }, [datasetHash, persistedFeedback?.dataset_hash, persistedFeedback?.vote]);

  // Prefer the active-locale translation when present; fall back to
  // the top-level English fields (Issue #103 contract).
  const localized = insight && ((locale === 'zh' && insight.translations?.zh) || insight);

  // Resolve the actual content to render. AI and deterministic content retain
  // distinct branding; deterministic content is never presented as AI output.
  // If neither exists the surface stays hidden.
  const content = localized
    ? {
        headline: localized.headline as ReactNode,
        summary: localized.summary,
        findings: localized.findings ?? insight!.findings ?? [],
        recommendations: localized.recommendations ?? insight!.recommendations ?? [],
        stamp: insight!.generated_at ? timeAgo(insight!.generated_at, locale) : undefined,
        isAi: true,
      }
    : fallback
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
      const response = await fetch(`${API_BASE}/api/insights/${insightType}/feedback`, {
        method: 'POST',
        headers: {
          ...(getAuthHeaders() as Record<string, string>),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vote: feedbackVote,
          dataset_hash: datasetHash,
          comment: feedbackComment.trim() || null,
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
          setFeedbackError(i18n._(msg`This insight changed. Refresh the page before sending feedback.`));
          const refreshes: Array<Promise<unknown>> = [refetch()];
          if (onFeedbackStale) {
            refreshes.push(Promise.resolve().then(onFeedbackStale));
          }
          await Promise.allSettled(refreshes);
          if (requestIsCurrent()) setFeedbackStale(false);
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

  if (!content && !aiUnavailable) return null;

  const displayedContent = content ?? {
    headline: i18n._(msg`Azure AI insights are temporarily unavailable.`),
    summary: i18n._(msg`Your synced data and deterministic training metrics remain available.`),
    findings: [],
    recommendations: [],
    stamp: undefined,
    isAi: false,
  };

  const skillName = insightType.replace(/_/g, '-');
  const hasDetails = displayedContent.findings.length > 0 || displayedContent.recommendations.length > 0;
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
          {displayedContent.isAi ? <Trans>Praxys Coach</Trans> : <Trans>Training metrics</Trans>}
        </span>
        {displayedContent.stamp && (
          <span className="coach-stamp font-data">{displayedContent.stamp}</span>
        )}
      </div>
      <div className="coach-body">
        {aiUnavailable && content && (
          <p className="coach-summary" role="status">
            <Trans>Azure AI insights are temporarily unavailable.</Trans>{' '}
            <Trans>Your synced data and deterministic training metrics remain available.</Trans>
          </p>
        )}
        <p className="coach-headline">{displayedContent.headline}</p>
        {displayedContent.summary && (
          <p className="coach-summary">{linkifyScienceTerms(displayedContent.summary)}</p>
        )}
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
                {displayedContent.findings.length > 0 && displayedContent.recommendations.length > 0 && <Trans> · </Trans>}
                {displayedContent.recommendations.length > 0 && (
                  <Plural value={displayedContent.recommendations.length} one="# recommendation" other="# recommendations" />
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
        {detailsOpen && displayedContent.recommendations.length > 0 && (
          <>
            {displayedContent.findings.length > 0 && <hr className="coach-rule" />}
            <p className="coach-label"><Trans>Recommendations</Trans></p>
            <ol className="coach-list">
              {displayedContent.recommendations.map((recommendation, index) => (
                <li key={index} className="coach-row">
                  <span className="coach-tag coach-tag-rec" aria-hidden="true">→</span>
                  <span className="coach-text">{linkifyScienceTerms(recommendation)}</span>
                </li>
              ))}
            </ol>
          </>
        )}
        {displayedContent.isAi && <p className="coach-skill-hint">
          <Trans>
            Run{' '}
            <a
              href={PLUGIN_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="coach-skill-link"
            >
              /praxys:{skillName}
            </a>{' '}
            in Claude Code for deeper analysis
          </Trans>
        </p>}
      </div>
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
      {attribution && <div className="coach-foot">{attribution}</div>}
    </aside>
  );
}
