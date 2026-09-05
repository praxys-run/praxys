import { useMemo, useState } from 'react';
import { Bot, Check, ExternalLink, LockKeyhole, MessageSquarePlus, RefreshCw, RotateCcw } from 'lucide-react';
import AdminFeedbackImages from '@/components/AdminFeedbackImages';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiFetch, extractErrorMessage, useApi } from '@/hooks/useApi';
import { Trans, useLingui } from '@lingui/react/macro';
import type {
  AdminAgentReadyAdjudicationRequest,
  AdminAgentReadyAdjudicationResponse,
  AdminFeedbackItem,
  AdminFeedbackSyncResult,
  AgentReadyAdjudicationReason,
  AgentReadyDecisionReason,
  FeedbackPriority,
  FeedbackPublicationStatus,
  FeedbackStatus,
} from '@/types/api';
import { AdminEmptyState, AdminRouteError, AdminRouteSkeleton } from './AdminRouteState';

type AdminFeedbackFilter = 'active' | 'all' | FeedbackStatus;

const FEEDBACK_STATUS_ORDER: Record<FeedbackStatus, number> = {
  needs_review: 0,
  failed: 1,
  new: 2,
  triaged: 3,
  issue_created: 4,
  resolved: 5,
  rejected: 6,
};

const FEEDBACK_PRIORITY_ORDER: Record<FeedbackPriority, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const FEEDBACK_PRIORITY_CLASS: Record<FeedbackPriority, string> = {
  critical: 'border-destructive/40 text-destructive',
  high: 'border-amber-500/40 text-amber-600',
  medium: 'text-muted-foreground',
  low: 'text-muted-foreground',
};

function feedbackStatusVariant(status: FeedbackStatus): 'default' | 'destructive' | 'outline' | 'secondary' {
  if (status === 'issue_created') return 'default';
  if (status === 'failed') return 'destructive';
  if (status === 'resolved') return 'outline';
  return 'secondary';
}

export default function AdminFeedback() {
  const { t } = useLingui();
  const [feedbackFilter, setFeedbackFilter] = useState<AdminFeedbackFilter>('active');
  const [feedbackBusy, setFeedbackBusy] = useState<number | null>(null);
  const [feedbackSyncing, setFeedbackSyncing] = useState(false);
  const [feedbackSyncMsg, setFeedbackSyncMsg] = useState<string | null>(null);
  const [feedbackActionMsg, setFeedbackActionMsg] = useState<string | null>(null);
  const [feedbackActionError, setFeedbackActionError] = useState(false);
  const [agentReadyChoices, setAgentReadyChoices] = useState<
    Record<number, AgentReadyAdjudicationReason | undefined>
  >({});

  const feedbackUrl = feedbackFilter === 'all' ? '/api/admin/feedback' : `/api/admin/feedback?status=${feedbackFilter}`;
  const { data, loading, error, refetch } = useApi<AdminFeedbackItem[]>(feedbackUrl, { refetchOnMount: 'always' });
  const feedback = useMemo(() => data ?? [], [data]);

  const feedbackStatusLabel = (status: FeedbackStatus): string => {
    switch (status) {
      case 'new':
        return t`New`;
      case 'triaged':
        return t`Triaged`;
      case 'needs_review':
        return t`Needs review`;
      case 'issue_created':
        return t`Issue created`;
      case 'resolved':
        return t`Resolved`;
      case 'failed':
        return t`Failed`;
      case 'rejected':
        return t`Rejected`;
    }
  };

  const feedbackPriorityLabel = (priority: FeedbackPriority): string => {
    switch (priority) {
      case 'critical':
        return t`Critical`;
      case 'high':
        return t`High`;
      case 'medium':
        return t`Medium`;
      case 'low':
        return t`Low`;
    }
  };

  const feedbackPublicationLabel = (status: FeedbackPublicationStatus): string => {
    switch (status) {
      case 'private':
        return t`Private`;
      case 'queued':
        return t`Publication queued`;
      case 'published':
        return t`Published`;
      case 'manual_required':
        return t`Manual publication review`;
      case 'unknown':
        return t`Publication unknown`;
      case 'unavailable':
        return t`Publication unavailable`;
    }
  };

  const feedbackKindLabel = (kind: AdminFeedbackItem['kind']): string => {
    switch (kind) {
      case 'bug':
        return t`Bug`;
      case 'feature':
        return t`Feature`;
      case 'other':
        return t`Other`;
    }
  };

  const agentReadyReasonLabel = (reason: AgentReadyDecisionReason | null): string => {
    switch (reason) {
      case 'eligible':
        return t`Eligible`;
      case 'not_bug':
        return t`Not a bug`;
      case 'sensitivity_gate':
        return t`Sensitivity gate`;
      case 'not_actionable':
        return t`Not actionable`;
      case 'insufficient_detail':
        return t`Insufficient detail`;
      default:
        return t`No decision`;
    }
  };

  const adjudicationReasonLabel = (reason: AgentReadyAdjudicationReason): string => {
    switch (reason) {
      case 'bounded_actionable_defect':
        return t`Should be agent-ready — bounded actionable defect`;
      case 'not_a_defect':
        return t`Should not be agent-ready — not a defect`;
      case 'insufficient_detail':
        return t`Should not be agent-ready — insufficient detail`;
      case 'needs_product_judgment':
        return t`Should not be agent-ready — needs product judgment`;
      case 'sensitivity_or_privacy':
        return t`Should not be agent-ready — sensitivity or privacy gate`;
      case 'other':
        return t`Should not be agent-ready — other`;
    }
  };

  const sortedFeedback = useMemo(
    () =>
      [...feedback].sort((left, right) => {
        const byStatus = FEEDBACK_STATUS_ORDER[left.status] - FEEDBACK_STATUS_ORDER[right.status];
        if (byStatus !== 0) return byStatus;
        if (left.priority && right.priority) {
          return FEEDBACK_PRIORITY_ORDER[left.priority] - FEEDBACK_PRIORITY_ORDER[right.priority];
        }
        if (left.priority) return -1;
        if (right.priority) return 1;
        return 0;
      }),
    [feedback],
  );

  const handleFeedbackAction = async (item: AdminFeedbackItem, action: 'retry' | 'reject' | 'approve') => {
    setFeedbackBusy(item.id);
    setFeedbackActionMsg(null);
    setFeedbackActionError(false);
    try {
      const res = await apiFetch(`/api/admin/feedback/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          review_token: action === 'approve' ? item.publication_review_token : null,
        }),
      });
      if (!res.ok) {
        setFeedbackActionMsg(await extractErrorMessage(res, t`Couldn't update feedback.`));
        setFeedbackActionError(true);
      } else if (action === 'retry') {
        setFeedbackActionMsg(
          t`Analysis and routing refreshed. Publication permission and GitHub issue state were unchanged.`,
        );
      }
      await refetch();
    } catch {
      setFeedbackActionMsg(t`Network error. Is the server running?`);
    } finally {
      setFeedbackBusy(null);
    }
  };

  const handleAgentReadyAdjudication = async (item: AdminFeedbackItem) => {
    const reason = agentReadyChoices[item.id];
    const readiness = item.agent_readiness;
    if (!reason || !readiness) return;
    const expected = reason === 'bounded_actionable_defect';
    const payload: AdminAgentReadyAdjudicationRequest = {
      decision_id: readiness.decision_id,
      expected,
      reason,
    };
    setFeedbackBusy(item.id);
    setFeedbackActionMsg(null);
    setFeedbackActionError(false);
    try {
      const res = await apiFetch(`/api/admin/feedback/${item.id}/agent-ready-adjudication`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        if (res.status === 409) {
          setFeedbackActionMsg(
            t`The readiness decision changed. Review the refreshed decision before recording a judgment.`,
          );
          setFeedbackActionError(true);
          await refetch();
          return;
        }
        setFeedbackActionMsg(await extractErrorMessage(res, t`Couldn't record the readiness judgment.`));
        setFeedbackActionError(true);
        return;
      }
      const result: AdminAgentReadyAdjudicationResponse = await res.json();
      if (result.label_sync === 'failed' || result.label_sync === 'github_unavailable') {
        setFeedbackActionMsg(
          t`Judgment recorded, but the GitHub agent-ready label could not be synchronized.`,
        );
        setFeedbackActionError(true);
      } else if (result.label_sync === 'issue_not_open') {
        setFeedbackActionMsg(
          t`Judgment recorded. The linked issue is not open, so no label was added.`,
        );
      } else if (result.label_sync === 'not_linked') {
        setFeedbackActionMsg(
          t`Judgment recorded. This feedback has no linked GitHub issue.`,
        );
      } else if (result.label_sync === 'repository_mismatch') {
        setFeedbackActionMsg(
          t`Judgment recorded, but the linked issue belongs to a different repository configuration.`,
        );
        setFeedbackActionError(true);
      } else {
        setFeedbackActionMsg(
          expected
            ? t`Judgment recorded and agent-ready synchronized.`
            : t`Judgment recorded and agent-ready removed.`,
        );
      }
      setAgentReadyChoices((current) => ({ ...current, [item.id]: undefined }));
      await refetch();
    } catch {
      setFeedbackActionMsg(t`Network error. Is the server running?`);
      setFeedbackActionError(true);
    } finally {
      setFeedbackBusy(null);
    }
  };

  const handleFeedbackSync = async () => {
    setFeedbackSyncing(true);
    setFeedbackSyncMsg(null);
    setFeedbackActionError(false);
    try {
      const res = await apiFetch(`/api/admin/feedback/sync`, {
        method: 'POST',
      });
      if (!res.ok) {
        setFeedbackSyncMsg(await extractErrorMessage(res, t`Sync failed.`));
        return;
      }
      const result: AdminFeedbackSyncResult = await res.json();
      const repositoryMismatches = result.repository_mismatches ?? 0;
      setFeedbackSyncMsg(
        !result.configured
          ? t`GitHub isn't configured. Nothing to sync.`
          : repositoryMismatches > 0
            ? t`Updated ${result.updated} linked ticket(s). Skipped ${repositoryMismatches} because their stored repository no longer matches the configured feedback repository.`
          : result.updated > 0
            ? t`Updated ${result.updated} of ${result.checked} linked ticket(s).`
            : t`All ${result.checked} linked ticket(s) already up to date.`,
      );
      await refetch();
    } catch {
      setFeedbackSyncMsg(t`Network error. Is the server running?`);
    } finally {
      setFeedbackSyncing(false);
    }
  };

  if (loading) {
    return <AdminRouteSkeleton />;
  }

  if (error) {
    return (
      <AdminRouteError
        title={t`Couldn't load feedback queue`}
        description={t`Retry to load submitted reports and GitHub sync state.`}
        error={error}
        onRetry={refetch}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-foreground">
          <Trans>Feedback triage</Trans>
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          <Trans>Review reports, manage screenshots, and sync linked GitHub issues.</Trans>
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4" />
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Trans>User feedback</Trans>
                  {feedback.some((item) => item.status === 'needs_review') ? (
                    <Badge variant="secondary" className="font-data">
                      {feedback.filter((item) => item.status === 'needs_review').length}
                    </Badge>
                  ) : null}
                </CardTitle>
                <CardDescription>
                  <Trans>
                    Bug reports and feature requests submitted from the app. Priority orders work; it never determines agent readiness.
                  </Trans>
                </CardDescription>
                <CardDescription className="mt-1">
                  <Trans>
                    Re-run triage refreshes analysis and routing only. It does not grant publication permission or create a GitHub issue.
                  </Trans>
                </CardDescription>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Select value={feedbackFilter} onValueChange={(value) => setFeedbackFilter(value as AdminFeedbackFilter)}>
                <SelectTrigger size="sm" className="w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">{t`Active`}</SelectItem>
                  <SelectItem value="all">{t`All`}</SelectItem>
                  <SelectItem value="new">{t`New`}</SelectItem>
                  <SelectItem value="needs_review">{t`Needs review`}</SelectItem>
                  <SelectItem value="failed">{t`Failed`}</SelectItem>
                  <SelectItem value="issue_created">{t`Issue created`}</SelectItem>
                  <SelectItem value="resolved">{t`Resolved`}</SelectItem>
                  <SelectItem value="rejected">{t`Rejected`}</SelectItem>
                  <SelectItem value="triaged">{t`Triaged`}</SelectItem>
                </SelectContent>
              </Select>
              <Button type="button" size="sm" variant="outline" disabled={feedbackSyncing} onClick={() => void handleFeedbackSync()}>
                <RefreshCw className={`h-3.5 w-3.5 ${feedbackSyncing ? 'animate-spin' : ''}`} />
                <Trans>Sync from GitHub</Trans>
              </Button>
            </div>
          </div>
          {feedbackSyncMsg ? <p className="mt-2 text-xs text-muted-foreground">{feedbackSyncMsg}</p> : null}
          <p
            className={`mt-2 min-h-4 text-xs ${feedbackActionError ? 'text-destructive' : 'text-muted-foreground'}`}
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            {feedbackActionMsg ?? ''}
          </p>
        </CardHeader>
        <CardContent>
          {sortedFeedback.length === 0 ? (
            <AdminEmptyState
              title={feedbackFilter === 'active' ? t`No active tickets` : t`No tickets to show`}
              description={
                feedbackFilter === 'active'
                  ? t`Newly triaged work will appear here when admin action is needed.`
                  : t`Try another filter or sync again after new reports arrive.`
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead><Trans>Type</Trans></TableHead>
                  <TableHead><Trans>Status</Trans></TableHead>
                  <TableHead><Trans>Report</Trans></TableHead>
                  <TableHead><Trans>Issue</Trans></TableHead>
                  <TableHead><Trans>Agent readiness</Trans></TableHead>
                  <TableHead className="text-right"><Trans>Actions</Trans></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedFeedback.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="align-top">
                      <Badge variant="outline">{feedbackKindLabel(item.kind)}</Badge>
                    </TableCell>
                    <TableCell className="align-top">
                      <div className="flex flex-col items-start gap-1">
                        <Badge
                          variant={feedbackStatusVariant(item.status)}
                          className={item.status === 'resolved' ? 'border-primary/40 text-primary' : undefined}
                        >
                          {feedbackStatusLabel(item.status)}
                        </Badge>
                        <Badge variant="outline">
                          {feedbackPublicationLabel(item.publication_status)}
                        </Badge>
                        {item.priority ? (
                          <Badge variant="outline" className={FEEDBACK_PRIORITY_CLASS[item.priority]}>
                            {feedbackPriorityLabel(item.priority)}
                          </Badge>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-sm align-top">
                      <p className="truncate text-sm" title={item.message}>{item.ai_title || item.message}</p>
                      {item.ai_body ? (
                        <details className="mt-2 text-xs">
                          <summary className="min-h-11 cursor-pointer py-3 text-muted-foreground hover:text-foreground">
                            <Trans>Review exact public issue text</Trans>
                          </summary>
                          <p className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted/30 p-3 leading-relaxed text-foreground">
                            {item.ai_body}
                          </p>
                        </details>
                      ) : null}
                      {item.error ? <p className="text-xs text-destructive">{item.error}</p> : null}
                      {item.image_count > 0 ? (
                        <>
                          {item.image_sensitive ? (
                            <Badge variant="secondary" className="mt-1">
                              <Trans>Screenshot flagged sensitive</Trans>
                            </Badge>
                          ) : null}
                          {item.image_description ? (
                            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground" title={item.image_description}>
                              {item.image_description}
                            </p>
                          ) : null}
                          <AdminFeedbackImages feedbackId={item.id} count={item.image_count} />
                        </>
                      ) : null}
                    </TableCell>
                    <TableCell className="align-top">
                      {item.github_issue_url ? (
                        <a
                          href={item.github_issue_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                        >
                          <span className="font-data">#{item.github_issue_number}</span>
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="min-w-[290px] align-top whitespace-normal">
                      {item.agent_readiness ? (
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                            <Badge
                              variant="outline"
                              className={
                                item.agent_readiness.candidate
                                  ? 'border-primary/40 text-primary'
                                  : 'text-muted-foreground'
                              }
                            >
                              {item.agent_readiness.candidate === null
                                ? t`Unavailable`
                                : item.agent_readiness.candidate
                                  ? t`Candidate`
                                  : t`Review required`}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {agentReadyReasonLabel(item.agent_readiness.reason)}
                            </span>
                          </div>
                          <p
                            className="font-data text-xs text-muted-foreground"
                            title={`${item.agent_readiness.policy_name} ${item.agent_readiness.policy_version} ${item.agent_readiness.prompt_hash ?? ''}`}
                          >
                            {item.agent_readiness.model ?? t`Rule based`} · {item.agent_readiness.policy_version} ·{' '}
                            {item.agent_readiness.prompt_hash && item.agent_readiness.prompt_version
                              ? item.agent_readiness.prompt_version
                              : t`No prompt`}
                          </p>
                          {item.agent_readiness.challenger ? (
                            <p className="text-xs text-muted-foreground">
                              <Trans>Challenger</Trans>{' '}
                              <span className="font-data">{item.agent_readiness.challenger.prompt_version}</span>
                              {' · '}
                              {item.agent_readiness.challenger.available
                                ? item.agent_readiness.challenger.candidate
                                  ? t`Candidate`
                                  : t`Review required`
                                : t`Unavailable`}
                              {item.agent_readiness.challenger.available ? (
                                <>
                                  {' · '}
                                  {agentReadyReasonLabel(item.agent_readiness.challenger.reason)}
                                </>
                              ) : null}
                            </p>
                          ) : null}
                          {item.agent_readiness.adjudication ? (
                            <p className="text-xs font-medium text-foreground">
                              <Trans>Maintainer verdict:</Trans>{' '}
                              {adjudicationReasonLabel(item.agent_readiness.adjudication.reason)}
                            </p>
                          ) : null}
                          <div className="flex flex-col gap-2">
                            <Select
                              value={agentReadyChoices[item.id]}
                              onValueChange={(value) =>
                                setAgentReadyChoices((current) => ({
                                  ...current,
                                  [item.id]: value as AgentReadyAdjudicationReason,
                                }))
                              }
                            >
                              <SelectTrigger size="sm" className="w-full">
                                <SelectValue placeholder={t`Record maintainer judgment`} />
                              </SelectTrigger>
                              <SelectContent>
                                {([
                                  'bounded_actionable_defect',
                                  'not_a_defect',
                                  'insufficient_detail',
                                  'needs_product_judgment',
                                  'sensitivity_or_privacy',
                                  'other',
                                ] as const).map((reason) => (
                                  <SelectItem key={reason} value={reason}>
                                    {adjudicationReasonLabel(reason)}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <Button
                              type="button"
                              size="xs"
                              variant="outline"
                              disabled={feedbackBusy === item.id || !agentReadyChoices[item.id]}
                              onClick={() => void handleAgentReadyAdjudication(item)}
                            >
                              <Check className="h-3 w-3" />
                              <Trans>Record judgment</Trans>
                            </Button>
                          </div>
                          <p className="text-[11px] leading-relaxed text-muted-foreground">
                            <Trans>
                              Agent-ready applies only to feedback already linked to a public GitHub issue. A positive judgment synchronizes the label; when it newly labels an open, non-backlogged linked issue, the assignment workflow hands it to Copilot. A negative judgment removes the label, but an existing assignment or PR may remain.
                            </Trans>
                          </p>
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">
                          <Trans>Awaiting triage decision</Trans>
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="align-top text-right">
                      <div className="flex flex-wrap items-center justify-end gap-1">
                        {item.status === 'needs_review' ? (
                          item.external_publication_consent ? (
                            <Button
                              type="button"
                              size="xs"
                              variant="outline"
                              disabled={feedbackBusy === item.id || !item.publication_review_token}
                              onClick={() => void handleFeedbackAction(item, 'approve')}
                            >
                              <Check className="h-3 w-3" />
                              <Trans>Approve & queue</Trans>
                            </Button>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs leading-tight text-muted-foreground">
                              <LockKeyhole aria-hidden="true" className="h-3 w-3 shrink-0" />
                              <Trans>Private submission</Trans>
                            </span>
                          )
                        ) : null}
                        {item.status !== 'issue_created' && item.status !== 'needs_review' && item.status !== 'resolved' ? (
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            disabled={feedbackBusy === item.id}
                            onClick={() => void handleFeedbackAction(item, 'retry')}
                          >
                            <RotateCcw className="h-3 w-3" />
                            {feedbackBusy === item.id
                              ? <Trans>Re-running…</Trans>
                              : <Trans>Re-run triage</Trans>}
                          </Button>
                        ) : null}
                        {item.status !== 'rejected' ? (
                          <Button
                            type="button"
                            size="xs"
                            variant="ghost"
                            disabled={feedbackBusy === item.id}
                            onClick={() => void handleFeedbackAction(item, 'reject')}
                          >
                            <Trans>Reject</Trans>
                          </Button>
                        ) : null}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
