import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  CloudOff,
  Database,
  ExternalLink,
  GitPullRequest,
  Loader2,
  MessageSquareWarning,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldAlert,
  X,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { apiFetch, useApi } from '@/hooks/useApi';
import { cn } from '@/lib/utils';
import { Trans, useLingui } from '@lingui/react/macro';
import type {
  AdminOpsAgentEvalConfusion,
  AdminOpsFreshness,
  AdminOpsReason,
  AdminOpsSectionMeta,
  AdminOpsSectionWindow,
  AdminOpsSummary,
  AdminOpsWindow,
  AdminManagedPlanAttentionItem,
  AdminManagedPlanAttentionResponse,
  AdminManagedPlanRecoveryErrorCode,
  AdminManagedPlanRecoveryResponse,
  ComponentStatus,
  OverallStatus,
} from '@/types/api';
import { AdminRouteError } from './AdminRouteState';

const WINDOWS: AdminOpsWindow[] = ['24h', '7d', '28d'];
const EMPTY_AGENT_EVAL: AdminOpsAgentEvalConfusion = {
  evaluated: 0,
  true_positives: 0,
  true_negatives: 0,
  false_positives: 0,
  false_negatives: 0,
  accuracy: null,
};

const COMPONENT_DOT: Record<ComponentStatus, string> = {
  operational: 'bg-primary',
  degraded_performance: 'bg-accent-amber',
  partial_outage: 'bg-accent-amber',
  major_outage: 'bg-accent-red',
};

const OVERALL_ICON: Record<OverallStatus, typeof CheckCircle2> = {
  operational: CheckCircle2,
  degraded: AlertTriangle,
  partial_outage: AlertTriangle,
  major_outage: AlertOctagon,
};

const OVERALL_TONE: Record<OverallStatus, string> = {
  operational: 'text-primary',
  degraded: 'text-accent-amber',
  partial_outage: 'text-accent-amber',
  major_outage: 'text-accent-red',
};

type AttentionTone = 'clear' | 'warning' | 'critical' | 'unavailable';

const ATTENTION_TONE: Record<AttentionTone, { icon: string; title: string }> = {
  clear: { icon: 'bg-primary/10 text-primary', title: 'text-foreground' },
  warning: { icon: 'bg-accent-amber/10 text-accent-amber', title: 'text-foreground' },
  critical: { icon: 'bg-accent-red/10 text-accent-red', title: 'text-accent-red' },
  unavailable: { icon: 'bg-muted text-muted-foreground', title: 'text-foreground' },
};

function formatTimestamp(value: string | null, locale: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatPercent(value: number | null, digits = 0): string {
  if (value === null || !Number.isFinite(value)) return '-';
  return `${(value * 100).toFixed(digits)}%`;
}

function formatDuration(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return '-';
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

function unavailableAzureMeta(window: AdminOpsSectionWindow): AdminOpsSectionMeta {
  return {
    source: 'azure_monitor',
    window,
    freshness: 'unavailable',
    as_of: null,
    reason: 'azure_telemetry_not_configured',
  };
}

function isManagedRecoveryErrorCode(
  value: unknown,
): value is AdminManagedPlanRecoveryErrorCode {
  return (
    value === 'MANAGED_PLAN_RECOVERY_NOT_FOUND'
    || value === 'MANAGED_PLAN_RECOVERY_BUSY'
    || value === 'MANAGED_PLAN_RECOVERY_STALE'
    || value === 'MANAGED_PLAN_RECOVERY_UNSUPPORTED'
  );
}

async function managedRecoveryErrorCode(
  response: Response,
): Promise<AdminManagedPlanRecoveryErrorCode | null> {
  try {
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== 'object') return null;
    const detail = Reflect.get(payload, 'detail');
    if (!detail || typeof detail !== 'object') return null;
    const code = Reflect.get(detail, 'code');
    return isManagedRecoveryErrorCode(code) ? code : null;
  } catch {
    return null;
  }
}

function AdminOpsSkeleton() {
  return (
    <div className="space-y-8" aria-busy="true">
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-8 w-52" />
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="flex items-center gap-4 border-b border-border px-4 py-4 last:border-b-0">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-3 w-72" />
            </div>
            <Skeleton className="h-7 w-24" />
          </div>
        ))}
      </div>
      <div className="grid gap-8 xl:grid-cols-2">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  );
}

function SectionMeta({ meta, stale = false, className }: { meta: AdminOpsSectionMeta; stale?: boolean; className?: string }) {
  const { t, i18n } = useLingui();
  const effectiveFreshness = stale && meta.freshness === 'fresh' ? 'stale' : meta.freshness;
  const freshnessClass =
    effectiveFreshness === 'fresh'
      ? 'border-primary/30 text-primary'
      : effectiveFreshness === 'stale'
        ? 'border-accent-amber/40 text-accent-amber'
        : 'border-border text-muted-foreground';

  const freshnessLabel = (freshness: AdminOpsFreshness): string => {
    switch (freshness) {
      case 'fresh':
        return t`Up to date`;
      case 'stale':
        return t`Stale`;
      case 'unavailable':
        return t`Unavailable`;
    }
  };

  const sourceLabel = (): string => {
    switch (meta.source) {
      case 'praxys_database':
        return t`Praxys database`;
      case 'live_probe':
        return t`Live probe`;
      case 'azure_monitor':
        return t`Azure Monitor`;
    }
  };

  const windowLabel = (window: AdminOpsSectionWindow): string => {
    switch (window) {
      case 'live':
        return t`Live`;
      case 'rolling_1d_7d_30d':
        return t`Rolling 1 / 7 / 30 days`;
      case '24h':
        return t`24 hours`;
      case '7d':
        return t`7 days`;
      case '28d':
        return t`28 days`;
    }
  };

  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground', className)}>
      <Badge variant="outline" className={cn('h-5 font-data', freshnessClass)}>
        {freshnessLabel(effectiveFreshness)}
      </Badge>
      <span>{sourceLabel()}</span>
      <span className="font-data">{windowLabel(meta.window)}</span>
      {meta.as_of ? (
        <span className="font-data">
          <Trans>Updated {formatTimestamp(meta.as_of, i18n.locale)}</Trans>
        </span>
      ) : null}
    </div>
  );
}

function AttentionRow({
  Icon,
  tone,
  title,
  description,
  detail,
  to,
  href,
  anchor,
  action,
}: {
  Icon: typeof CheckCircle2;
  tone: AttentionTone;
  title: string;
  description: string;
  detail?: string;
  to?: string;
  href?: string;
  anchor?: string;
  action: string;
}) {
  const styles = ATTENTION_TONE[tone];
  const actionContent = (
    <>
      <span>{action}</span>
      {href ? <ExternalLink className="h-3.5 w-3.5" /> : <ArrowUpRight className="h-3.5 w-3.5" />}
    </>
  );

  return (
    <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center">
      <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', styles.icon)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className={cn('text-sm font-semibold', styles.title)}>{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        {detail ? <p className="mt-1 truncate text-xs text-foreground">{detail}</p> : null}
      </div>
      {to ? (
        <Link
          to={to}
          className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-primary hover:underline"
        >
          {actionContent}
        </Link>
      ) : anchor ? (
        <a
          href={anchor}
          className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-primary hover:underline"
        >
          {actionContent}
        </a>
      ) : href ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-accent-cobalt hover:underline"
        >
          {actionContent}
        </a>
      ) : null}
    </div>
  );
}

export default function AdminOps() {
  const { t, i18n } = useLingui();
  const [window, setWindow] = useState<AdminOpsWindow>('24h');
  const [confirmingRecoveryId, setConfirmingRecoveryId] = useState<string | null>(null);
  const [runningRecoveryId, setRunningRecoveryId] = useState<string | null>(null);
  const [recoveryNotice, setRecoveryNotice] = useState<{
    tone: 'success' | 'error';
    message: string;
  } | null>(null);
  const { data, loading, stale, error, refetch } = useApi<AdminOpsSummary>(
    `/api/admin/ops/summary?window=${window}`,
    {
      refetchInterval: 60000,
      refetchOnMount: 'always',
      refetchOnWindowFocus: 'always',
    },
  );
  const {
    data: managedAttention,
    loading: managedAttentionLoading,
    error: managedAttentionError,
    refetch: refetchManagedAttention,
  } = useApi<AdminManagedPlanAttentionResponse>(
    '/api/admin/managed-plans/attention',
    {
      refetchInterval: 60000,
      refetchOnMount: 'always',
      refetchOnWindowFocus: 'always',
    },
  );

  if (loading) {
    return <AdminOpsSkeleton />;
  }

  if (!data) {
    return (
      <AdminRouteError
        title={t`Couldn't load operations summary`}
        description={t`Management routes remain available. Retry the aggregate health snapshot.`}
        error={error}
        onRetry={refetch}
      />
    );
  }

  const localizedReason = (reason: AdminOpsReason | null, fallback: string): string => {
    switch (reason) {
      case 'azure_telemetry_not_configured':
      case 'azure_telemetry_not_connected':
        return t`Trusted Azure telemetry is not configured for this deployment.`;
      case 'azure_sdk_unavailable':
        return t`The Azure Monitor query client is unavailable in this deployment.`;
      case 'azure_query_timed_out':
        return t`Azure Monitor did not respond before the operations deadline.`;
      case 'azure_query_partial':
        return t`Azure Monitor returned an incomplete result, so this section was not refreshed.`;
      case 'azure_query_failed':
        return t`Azure Monitor could not refresh this section.`;
      default:
        return fallback;
    }
  };

  const surfaceLabel = (surface: string): string => {
    switch (surface) {
      case 'web':
        return t`Web`;
      case 'miniapp':
        return t`Mini program`;
      default:
        return surface;
    }
  };

  const insightTypeLabel = (insightType: string): string => {
    switch (insightType) {
      case 'daily_brief':
        return t`Daily brief`;
      case 'training_review':
        return t`Training review`;
      case 'race_forecast':
        return t`Race forecast`;
      default:
        return insightType.replaceAll('_', ' ');
    }
  };

  const failureClassLabel = (failureClass: string): string => {
    switch (failureClass) {
      case 'rate_limited':
        return t`Rate limited`;
      case 'captcha_required':
        return t`CAPTCHA required`;
      case 'access_blocked':
        return t`Access blocked`;
      case 'token_rejected':
        return t`Token rejected`;
      case 'mfa_unattended':
        return t`MFA required`;
      case 'platform_error':
        return t`Platform error`;
      case 'network_error':
        return t`Network error`;
      default:
        return t`Unknown failure`;
    }
  };

  const connectionFlowLabel = (flow: string): string => {
    switch (flow) {
      case 'mfa':
        return t`MFA`;
      case 'non_mfa':
        return t`No MFA`;
      default:
        return t`Standard`;
    }
  };

  const connectionOutcomeLabel = (outcome: string): string => {
    switch (outcome) {
      case 'connected':
        return t`Connected`;
      case 'mfa_required':
        return t`MFA required`;
      case 'error':
        return t`Error`;
      default:
        return outcome.replaceAll('_', ' ');
    }
  };

  const managedIssueLabel = (item: AdminManagedPlanAttentionItem): string => {
    switch (item.issue) {
      case 'stale_pending':
        return t`Delivery never started`;
      case 'stuck_inflight':
        return t`Delivery is stuck in progress`;
      case 'delivery_failed':
        return t`Delivery failed`;
      case 'retry_exhausted':
        return t`Automatic retries exhausted`;
      case 'delivery_conflict':
        return t`Workout conflict requires athlete input`;
      case 'provider_outcome_unknown':
        return t`Provider outcome is uncertain`;
    }
  };

  const managedIssueDescription = (item: AdminManagedPlanAttentionItem): string => {
    if (!item.recovery_supported) {
      switch (item.recovery_blocked_reason) {
        case 'user_resolution_required':
          return t`Do not replay this item. The athlete must resolve it from the plan reconciliation flow.`;
        case 'failure_not_retryable':
          return t`Do not replay this item. Its failure is marked non-retryable by the delivery safety policy.`;
        case 'attempt_not_managed':
        case 'failure_not_managed':
          return t`Automated recovery is unavailable because this attempt was not recorded by the managed-delivery worker.`;
        default:
          return t`Automated recovery is unavailable for this item.`;
      }
    }
    if (item.issue === 'stuck_inflight') {
      return t`Refresh the provider calendar first, then replay only if the prior write is confirmed absent.`;
    }
    return t`Refresh the provider calendar, re-check ownership, and allow one fenced retry for this item.`;
  };

  const managedBlockedLabel = (item: AdminManagedPlanAttentionItem): string => {
    switch (item.recovery_blocked_reason) {
      case 'user_resolution_required':
        return t`Athlete action required`;
      case 'failure_not_retryable':
        return t`Replay blocked by safety policy`;
      default:
        return t`Automated recovery unavailable`;
    }
  };

  const failureDomainLabel = (domain: string): string => {
    switch (domain) {
      case 'provider_auth':
        return t`Provider authentication`;
      case 'provider':
        return t`Provider failure`;
      case 'praxys':
        return t`Praxys defect`;
      case 'conflict':
        return t`Ownership conflict`;
      case 'policy':
        return t`Safety policy`;
      case 'none':
        return t`No failure`;
      default:
        return t`Unclassified`;
    }
  };

  const attention = data.attention.data;
  const incidents = attention?.incident_counts;
  const feedback = attention?.feedback;
  const incidentTone: AttentionTone = !incidents
    ? 'unavailable'
    : incidents.critical > 0
      ? 'critical'
      : incidents.total > 0
        ? 'warning'
        : 'clear';
  const feedbackTone: AttentionTone = !feedback
    ? 'unavailable'
    : feedback.critical > 0
      ? 'critical'
      : feedback.actionable > 0
        ? 'warning'
        : 'clear';
  const incidentDetail = attention?.active_incidents.slice(0, 2).map((incident) => incident.title).join(' · ');
  const service = data.service_health.data;
  const product = data.product_value.data;
  const agentLearningSection = data.agent_learning;
  const agentLearning = agentLearningSection?.data ?? null;
  const activeAgentEval = agentLearning?.active_eval ?? EMPTY_AGENT_EVAL;
  const challengerAgentEval = agentLearning?.challenger_eval ?? EMPTY_AGENT_EVAL;
  const activeSemanticEval = agentLearning?.active_semantic_eval ?? EMPTY_AGENT_EVAL;
  const challengerSemanticEval =
    agentLearning?.challenger_semantic_eval ?? EMPTY_AGENT_EVAL;
  const postgresActiveConnections = service?.postgres_active_connections ?? null;
  const postgresMaxConnections = service?.postgres_max_connections ?? null;
  const postgresConnectionUtilization =
    service?.postgres_connection_utilization ?? null;
  const serviceTelemetryMeta = data.service_telemetry ?? unavailableAzureMeta(window);
  const productTelemetryMeta = data.product_telemetry ?? unavailableAzureMeta('28d');
  const serviceTelemetry = data.service_telemetry?.data ?? null;
  const productTelemetry = data.product_telemetry?.data ?? null;
  const alertsSection = data.azure_alerts ?? {
    ...unavailableAzureMeta(window),
    data: null,
  };
  const platformSection = data.platform_health ?? {
    ...unavailableAzureMeta(window),
    data: null,
  };
  const managedTelemetrySection = data.managed_plan_telemetry ?? {
    ...unavailableAzureMeta(window),
    data: null,
  };
  const managedHealthSection = data.managed_plans ?? {
    source: 'praxys_database' as const,
    window: 'live' as const,
    freshness: 'unavailable' as const,
    as_of: null,
    reason: 'section_refresh_failed' as const,
    data: null,
  };
  const alerts = alertsSection.data;
  const platform = platformSection.data;
  const managedTelemetry = managedTelemetrySection.data;
  const managedHealth = managedHealthSection.data;
  const snapshotStale = Boolean(error) || stale;
  const alertsLastKnown = snapshotStale || alertsSection.freshness === 'stale';
  const platformLastKnown = snapshotStale || platformSection.freshness === 'stale';
  const alertTone: AttentionTone = !alerts
    ? 'unavailable'
    : alerts.firing > 0
      ? 'critical'
      : alertsLastKnown
        ? 'warning'
        : 'clear';
  const systemicAffectedUsers = platform?.systemic_affected_users ?? 0;
  const systemicTone: AttentionTone = !platform
    ? 'unavailable'
    : systemicAffectedUsers > 0
      ? 'warning'
      : platformLastKnown
        ? 'warning'
        : 'clear';
  const managedAttentionCount = Math.max(
    managedHealth?.attention_required ?? 0,
    managedAttention?.items.length ?? 0,
  );
  const managedTone: AttentionTone =
    !managedHealth && !managedAttention
      ? 'unavailable'
      : managedAttentionCount > 0
        ? 'warning'
        : 'clear';
  const alertDetail = alerts?.rules
    .filter((rule) => rule.firing > 0)
    .slice(0, 2)
    .map((rule) => rule.rule)
    .join(' · ');
  const systemicDetail = platform?.systemic_failures
    .slice(0, 2)
    .map((failure) => `${failure.platform}: ${failureClassLabel(failure.failure_class)}`)
    .join(' · ');
  const alertTitle = alerts
    ? alerts.firing > 0
      ? t`Azure alerts firing: ${alerts.firing}`
      : t`No Azure alerts firing`
    : '';
  const systemicTitle = platform
    ? systemicAffectedUsers > 0
      ? t`Systemic sync failures affected ${systemicAffectedUsers} users in this window`
      : t`No systemic sync failures`
    : '';
  const managedTitle =
    managedHealth || managedAttention
      ? managedAttentionCount > 0
        ? t`Managed-plan deliveries needing attention: ${managedAttentionCount}`
        : t`Managed-plan delivery queue is clear`
      : '';
  const azureAlertsUrl = data.links.azure_alerts ?? data.links.monitoring_docs;
  const azureLogsUrl = data.links.azure_logs ?? data.links.monitoring_docs;
  const OverallIcon = service ? (snapshotStale ? AlertTriangle : OVERALL_ICON[service.overall]) : CloudOff;

  const handleRecovery = async (
    item: AdminManagedPlanAttentionItem,
  ): Promise<void> => {
    if (runningRecoveryId !== null) return;
    setRunningRecoveryId(item.recovery_id);
    setConfirmingRecoveryId(null);
    setRecoveryNotice(null);
    try {
      let response: Response;
      try {
        response = await apiFetch(
          `/api/admin/managed-plans/recover/${item.recovery_id}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              expected_version: item.expected_version,
            }),
          },
        );
      } catch {
        throw new Error(t`Network error. Refresh the queue and try again.`);
      }
      if (!response.ok) {
        const errorCode = await managedRecoveryErrorCode(response);
        switch (errorCode) {
          case 'MANAGED_PLAN_RECOVERY_NOT_FOUND':
            throw new Error(t`This queue item no longer exists. Refresh the queue.`);
          case 'MANAGED_PLAN_RECOVERY_BUSY':
            throw new Error(t`Another recovery is already running for this delivery. The queue has been refreshed.`);
          case 'MANAGED_PLAN_RECOVERY_STALE':
            throw new Error(t`This delivery changed before recovery started. Review the refreshed queue.`);
          case 'MANAGED_PLAN_RECOVERY_UNSUPPORTED':
            throw new Error(t`This delivery cannot be replayed automatically. Review the refreshed queue for the required action.`);
          default:
            if (response.status === 404) {
              throw new Error(t`This queue item no longer exists. Refresh the queue.`);
            }
            if (response.status === 409) {
              throw new Error(t`Recovery could not start because the delivery state changed. Review the refreshed queue.`);
            }
            throw new Error(t`Recovery could not be completed. Refresh the queue and try again.`);
        }
      }
      const result = (await response.json()) as AdminManagedPlanRecoveryResponse;
      if (result.status !== 'complete') {
        switch (result.status) {
          case 'partial':
            throw new Error(t`Recovery completed only partially. Review the refreshed queue before taking another action.`);
          case 'blocked':
            throw new Error(t`Recovery was blocked after provider reconciliation. Review the refreshed queue.`);
          case 'skipped':
            throw new Error(t`Recovery was skipped because delivery eligibility changed. Review the refreshed queue.`);
        }
      }
      setRecoveryNotice({
        tone: 'success',
        message:
          result.successful_items > 0
            ? t`Recovery completed after a fresh provider reconciliation.`
            : t`Reconciliation completed without replaying a workout.`,
      });
    } catch (recoveryError) {
      setRecoveryNotice({
        tone: 'error',
        message:
          recoveryError instanceof Error
            ? recoveryError.message
            : t`Network error. Refresh the queue and try again.`,
      });
    } finally {
      try {
        await Promise.all([refetchManagedAttention(), refetch()]);
      } finally {
        setRunningRecoveryId(null);
      }
    }
  };

  const overallLabel = (status: OverallStatus): string => {
    switch (status) {
      case 'operational':
        return t`All components operational`;
      case 'degraded':
        return t`Service performance degraded`;
      case 'partial_outage':
        return t`Partial service outage`;
      case 'major_outage':
        return t`Major service outage`;
    }
  };

  const componentStatusLabel = (status: ComponentStatus): string => {
    switch (status) {
      case 'operational':
        return t`Operational`;
      case 'degraded_performance':
        return t`Degraded`;
      case 'partial_outage':
        return t`Partial outage`;
      case 'major_outage':
        return t`Outage`;
    }
  };

  const componentLabel = (key: string, fallback: string): string => {
    switch (key) {
      case 'api':
        return t`API`;
      case 'database':
        return t`Database`;
      case 'sync':
        return t`Background sync`;
      default:
        return fallback;
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-foreground">
            <Trans>Operations</Trans>
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            <Trans>Start with operator action, then use health and usage context to choose the next workflow.</Trans>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-border bg-background p-0.5" aria-label={t`Summary window`}>
            {WINDOWS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setWindow(option)}
                aria-pressed={window === option}
                className={cn(
                  'h-7 rounded-md px-2.5 font-data text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  window === option
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {option}
              </button>
            ))}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void Promise.all([refetch(), refetchManagedAttention()])}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <Trans>Refresh</Trans>
          </Button>
        </div>
      </div>

      {error ? (
        <div
          role="status"
          className="flex items-center gap-2 rounded-lg border border-accent-amber/40 bg-accent-amber/5 px-3 py-2 text-xs text-foreground"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-accent-amber" />
          <Trans>Refresh failed. Showing the last successful snapshot.</Trans>
        </div>
      ) : null}

      <section aria-labelledby="needs-attention-heading">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <h3 id="needs-attention-heading" className="text-base font-semibold text-foreground">
            <Trans>Needs attention</Trans>
          </h3>
          <p className="font-data text-[11px] text-muted-foreground">
            <Trans>Snapshot {formatTimestamp(data.generated_at, i18n.locale)}</Trans>
          </p>
        </div>

        <div className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
          <AttentionRow
            Icon={incidents ? (incidents.total ? ShieldAlert : CheckCircle2) : CloudOff}
            tone={incidentTone}
            title={
              incidents
                ? incidents.total > 0
                  ? t`Active incidents: ${incidents.total}`
                  : t`No active service incidents`
                : t`Incident state unavailable`
            }
            description={
              incidents
                ? incidents.total > 0
                  ? t`Critical: ${incidents.critical}. Major: ${incidents.major}. Minor: ${incidents.minor}.`
                  : t`The public status feed has no unresolved incidents.`
                : localizedReason(data.attention.reason, t`The incident aggregate could not be refreshed.`)
            }
            detail={incidentDetail || undefined}
            to={data.links.incidents}
            action={t`Manage incidents`}
          />
          <AttentionRow
            Icon={feedback ? (feedback.actionable ? MessageSquareWarning : CheckCircle2) : CloudOff}
            tone={feedbackTone}
            title={
              feedback
                ? feedback.actionable > 0
                  ? t`Feedback requiring action: ${feedback.actionable}`
                  : t`Feedback queue is clear`
                : t`Feedback state unavailable`
            }
            description={
              feedback
                ? feedback.actionable > 0
                  ? t`Needs review: ${feedback.needs_review}. Failed: ${feedback.failed}. Critical: ${feedback.critical}. High: ${feedback.high}.`
                  : t`No feedback rows are waiting for review or retry.`
                : localizedReason(data.attention.reason, t`The feedback aggregate could not be refreshed.`)
            }
            to={data.links.feedback}
            action={t`Open feedback`}
          />
          <AttentionRow
            Icon={alerts ? (alerts.firing > 0 ? AlertOctagon : CheckCircle2) : CloudOff}
            tone={alertTone}
            title={
              alerts
                ? alertsLastKnown
                  ? t`Last known: ${alertTitle}`
                  : alertTitle
                : t`Azure alert state unavailable`
            }
            description={
              alerts
              ? t`Alert instances in view: ${alerts.total}. Resolved in the selected window: ${alerts.resolved}.`
                : localizedReason(alertsSection.reason, t`The alert summary could not be refreshed.`)
            }
            detail={alertDetail || undefined}
            href={azureAlertsUrl}
            action={t`Open Azure alerts`}
          />
          <AttentionRow
            Icon={platform ? (systemicAffectedUsers > 0 ? ShieldAlert : CheckCircle2) : CloudOff}
            tone={systemicTone}
            title={
              platform
                ? platformLastKnown
                  ? t`Last known: ${systemicTitle}`
                  : systemicTitle
                : t`Systemic sync failures unavailable`
            }
            description={
              platform
                ? t`Failure classes observed: ${platform.systemic_failures.length}.`
                : localizedReason(platformSection.reason, t`Platform aggregates could not be refreshed.`)
            }
            detail={systemicDetail || undefined}
            href={azureLogsUrl}
            action={t`Open Azure logs`}
          />
          <AttentionRow
            Icon={
              managedHealth || managedAttention
                ? managedAttentionCount > 0
                  ? CalendarClock
                  : CheckCircle2
                : CloudOff
            }
            tone={managedTone}
            title={
              managedHealth || managedAttention
                ? managedTitle
                : t`Managed-plan delivery state unavailable`
            }
            description={
              managedHealth
                ? t`Recoverable: ${managedHealth.recoverable}. Retry exhausted: ${managedHealth.retry_exhausted}. Stuck in progress: ${managedHealth.stuck_inflight}.`
                : managedAttention
                  ? t`The bounded operator queue is available, but aggregate delivery health could not be refreshed.`
                  : t`Managed-plan diagnostics could not be refreshed.`
            }
            anchor="#managed-plan-delivery"
            action={t`Review delivery queue`}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
          <SectionMeta meta={data.attention} stale={snapshotStale} />
          <SectionMeta meta={alertsSection} stale={snapshotStale} />
          <SectionMeta meta={platformSection} stale={snapshotStale} />
          <SectionMeta meta={managedHealthSection} stale={snapshotStale} />
        </div>
      </section>

      <section
        id="managed-plan-delivery"
        aria-labelledby="managed-plan-delivery-heading"
        className="scroll-mt-6 border-t border-border pt-7"
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <div
              className={cn(
                'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                managedAttentionCount > 0
                  ? 'bg-accent-amber/10 text-accent-amber'
                  : managedHealth || managedAttention
                    ? 'bg-primary/10 text-primary'
                    : 'bg-muted text-muted-foreground',
              )}
            >
              <CalendarClock className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h3
                id="managed-plan-delivery-heading"
                className="text-base font-semibold text-foreground"
              >
                <Trans>Managed plan delivery</Trans>
              </h3>
              <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                <Trans>
                  Diagnose Praxys-owned workout delivery without exposing athlete identity or provider workout data.
                </Trans>
              </p>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                <SectionMeta meta={managedHealthSection} stale={snapshotStale} />
                <SectionMeta meta={managedTelemetrySection} stale={snapshotStale} />
              </div>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void Promise.all([refetchManagedAttention(), refetch()])}
            disabled={runningRecoveryId !== null}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <Trans>Refresh delivery state</Trans>
          </Button>
        </div>

        {managedHealth ? (
          <>
            <dl className="mt-5 grid grid-cols-2 border-y border-border sm:grid-cols-4">
              {[
                { label: t`Managed athletes`, value: managedHealth.adopted_users },
                { label: t`Delivery enabled`, value: managedHealth.delivery_enabled_users },
                { label: t`Paused`, value: managedHealth.paused_users },
                { label: t`Needs attention`, value: managedHealth.attention_required },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="border-b border-border px-3 py-4 sm:border-b-0 sm:border-r sm:last:border-r-0"
                >
                  <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
                  <dd className="mt-1 font-data text-lg font-semibold text-foreground">
                    {metric.value}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
              <span>
                <Trans>
                  Synced <strong className="font-data font-semibold text-foreground">{managedHealth.states.synced}</strong>
                </Trans>
              </span>
              <span>
                <Trans>
                  Pending <strong className="font-data font-semibold text-foreground">{managedHealth.states.pending}</strong>
                </Trans>
              </span>
              <span>
                <Trans>
                  In progress <strong className="font-data font-semibold text-foreground">{managedHealth.states.delivering}</strong>
                </Trans>
              </span>
              <span>
                <Trans>
                  Failed <strong className="font-data font-semibold text-foreground">{managedHealth.states.failed}</strong>
                </Trans>
              </span>
              <span>
                <Trans>
                  Conflict <strong className="font-data font-semibold text-foreground">{managedHealth.states.conflict}</strong>
                </Trans>
              </span>
            </div>
          </>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">
            <Trans>Managed-plan database health is unavailable.</Trans>
          </p>
        )}

        {managedTelemetry ? (
          <div className="mt-6">
            <h4 className="text-sm font-semibold text-foreground">
              <Trans>Delivery outcomes</Trans>
            </h4>
            <dl className="mt-2 grid grid-cols-2 border-y border-border sm:grid-cols-5">
              {[
                { label: t`Runs`, value: String(managedTelemetry.delivery_runs) },
                {
                  label: t`Completed`,
                  value: formatPercent(
                    managedTelemetry.delivery_runs > 0
                      ? managedTelemetry.complete_runs / managedTelemetry.delivery_runs
                      : null,
                  ),
                },
                {
                  label: t`Provider / auth failures`,
                  value: String(
                    managedTelemetry.provider_failures + managedTelemetry.auth_failures,
                  ),
                },
                { label: t`Praxys defects`, value: String(managedTelemetry.praxys_failures) },
                { label: t`Run p95`, value: formatDuration(managedTelemetry.p95_delivery_ms) },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="border-b border-border px-3 py-3 sm:border-b-0 sm:border-r sm:last:border-r-0"
                >
                  <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
                  <dd className="mt-1 font-data text-sm font-semibold text-foreground">
                    {metric.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        <div className="mt-7 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h4 className="text-sm font-semibold text-foreground">
              <Trans>Operator queue</Trans>
            </h4>
            <p className="mt-1 text-xs text-muted-foreground">
              <Trans>
                Recovery always reconciles the provider calendar first. Conflicts and uncertain provider outcomes stay athlete-resolved.
              </Trans>
            </p>
          </div>
          {managedAttention?.generated_at ? (
            <p className="font-data text-[11px] text-muted-foreground">
              <Trans>Updated {formatTimestamp(managedAttention.generated_at, i18n.locale)}</Trans>
            </p>
          ) : null}
        </div>

        <div aria-live="polite" className="mt-3">
          {recoveryNotice ? (
            <div
              role={recoveryNotice.tone === 'error' ? 'alert' : 'status'}
              className={cn(
                'flex items-start gap-2 rounded-lg border px-3 py-2 text-xs',
                recoveryNotice.tone === 'error'
                  ? 'border-accent-red/30 bg-accent-red/5 text-accent-red'
                  : 'border-primary/30 bg-primary/5 text-foreground',
              )}
            >
              {recoveryNotice.tone === 'error' ? (
                <AlertOctagon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              ) : (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              )}
              <span>{recoveryNotice.message}</span>
            </div>
          ) : null}
        </div>

        {managedAttentionLoading ? (
          <div className="mt-3 divide-y divide-border overflow-hidden rounded-xl border border-border">
            {[0, 1].map((item) => (
              <div key={item} className="space-y-2 px-4 py-4">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-full max-w-xl" />
              </div>
            ))}
          </div>
        ) : managedAttentionError ? (
          <div className="mt-3 flex flex-col gap-3 rounded-xl border border-accent-amber/40 bg-accent-amber/5 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" />
              <p className="text-sm text-foreground">
                <Trans>The managed-plan operator queue could not be loaded.</Trans>
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void refetchManagedAttention()}
            >
              <Trans>Retry queue</Trans>
            </Button>
          </div>
        ) : managedAttention && managedAttention.items.length > 0 ? (
          <div className="mt-3 divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            {managedAttention.items.map((item) => {
              const isConfirming = confirmingRecoveryId === item.recovery_id;
              const isRunning = runningRecoveryId === item.recovery_id;
              return (
                <div key={item.recovery_id} className="px-4 py-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-data text-xs font-semibold text-foreground">
                          <Trans>Athlete {item.user_id_hash}</Trans>
                        </p>
                        <Badge variant="outline" className="h-5 capitalize">
                          {item.target}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={cn(
                            'h-5',
                            item.recovery_supported
                              ? 'border-accent-amber/40 text-accent-amber'
                              : 'border-border text-muted-foreground',
                          )}
                        >
                          {failureDomainLabel(item.failure_domain)}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm font-semibold text-foreground">
                        {managedIssueLabel(item)}
                      </p>
                      <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
                        {managedIssueDescription(item)}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-data text-[11px] text-muted-foreground">
                        <span>
                          <Trans>Attempts {item.attempt_count}</Trans>
                        </span>
                        <span>
                          <Trans>
                            Updated {formatTimestamp(item.updated_at, i18n.locale)}
                          </Trans>
                        </span>
                        {item.operation ? (
                          <span className="capitalize">
                            <Trans>Operation {item.operation}</Trans>
                          </span>
                        ) : null}
                      </div>
                    </div>
                    {item.recovery_supported ? (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => {
                          setRecoveryNotice(null);
                          setConfirmingRecoveryId(item.recovery_id);
                        }}
                        disabled={runningRecoveryId !== null}
                        aria-expanded={isConfirming}
                        aria-controls={`confirm-recovery-${item.recovery_id}`}
                      >
                        {isRunning ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
                        ) : (
                          <RotateCcw className="h-3.5 w-3.5" />
                        )}
                        <Trans>Reconcile and replay</Trans>
                      </Button>
                    ) : (
                      <span className="text-xs font-medium text-muted-foreground">
                        {managedBlockedLabel(item)}
                      </span>
                    )}
                  </div>

                  {isConfirming ? (
                    <div
                      id={`confirm-recovery-${item.recovery_id}`}
                      className="mt-4 flex flex-col gap-3 rounded-lg border border-accent-amber/40 bg-accent-amber/5 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <p className="max-w-3xl text-xs text-foreground">
                        <Trans>
                          Confirm one fenced replay. Praxys will refresh the provider calendar and stop if ownership or delivery state changed.
                        </Trans>
                      </p>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => setConfirmingRecoveryId(null)}
                          disabled={isRunning}
                        >
                          <X className="h-3.5 w-3.5" />
                          <Trans>Cancel</Trans>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void handleRecovery(item)}
                          disabled={isRunning}
                        >
                          {isRunning ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
                          ) : (
                            <RotateCcw className="h-3.5 w-3.5" />
                          )}
                          <Trans>Confirm replay</Trans>
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-3 rounded-xl border border-dashed border-border px-4 py-8 text-center">
            <CheckCircle2 className="mx-auto h-5 w-5 text-primary" />
            <p className="mt-2 text-sm font-medium text-foreground">
              <Trans>No managed deliveries need operator action.</Trans>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              <Trans>Automatic delivery is within policy, or athlete-owned conflicts remain in the athlete workflow.</Trans>
            </p>
          </div>
        )}
      </section>

      <div className="grid gap-8 xl:grid-cols-2">
        <section aria-labelledby="service-health-heading">
          <div className="flex items-start justify-between gap-4">
            <h3 id="service-health-heading" className="text-base font-semibold text-foreground">
              <Trans>Service health</Trans>
            </h3>
            {service ? (
              <div
                className={cn(
                  'inline-flex items-center gap-1.5 text-xs font-medium',
                  snapshotStale ? 'text-accent-amber' : OVERALL_TONE[service.overall],
                )}
              >
                <OverallIcon className="h-4 w-4" />
                {snapshotStale ? t`Last known: ${overallLabel(service.overall)}` : overallLabel(service.overall)}
              </div>
            ) : null}
          </div>

          {service ? (
            <div className="mt-4 divide-y divide-border border-y border-border">
              {service.components.map((component) => (
                <div key={component.key} className="flex items-center justify-between gap-4 py-3">
                  <div className="flex items-center gap-2.5">
                    {component.key === 'database' ? (
                      <Database className="h-4 w-4 text-muted-foreground" />
                    ) : component.key === 'api' ? (
                      <Server className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Activity className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span className="text-sm font-medium text-foreground">{componentLabel(component.key, component.name)}</span>
                  </div>
                  <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                    <span
                      className={cn(
                        'h-2.5 w-2.5 rounded-full',
                        snapshotStale && component.status === 'operational'
                          ? 'bg-accent-amber'
                          : COMPONENT_DOT[component.status],
                      )}
                    />
                    {snapshotStale
                      ? t`Last known: ${componentStatusLabel(component.status)}`
                      : componentStatusLabel(component.status)}
                  </span>
                </div>
              ))}
              {postgresActiveConnections !== null ? (
                <div className="flex items-center justify-between gap-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <Database className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">
                      <Trans>PostgreSQL connections</Trans>
                    </span>
                  </div>
                  <span className="font-data text-xs text-muted-foreground">
                    {postgresActiveConnections}
                    {postgresMaxConnections !== null ? ` / ${postgresMaxConnections}` : ''}
                    {postgresConnectionUtilization !== null
                      ? ` (${formatPercent(postgresConnectionUtilization)})`
                      : ''}
                  </span>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              <Trans>Live component health is unavailable.</Trans>
            </div>
          )}
          {serviceTelemetry ? (
            <dl className="mt-4 grid grid-cols-2 border-y border-border">
              {[
                {
                  label: t`Availability rate`,
                  value: formatPercent(serviceTelemetry.availability_rate, 1),
                },
                {
                  label: t`Server error rate`,
                  value: formatPercent(serviceTelemetry.server_error_rate, 1),
                },
                {
                  label: t`Request p95`,
                  value: formatDuration(serviceTelemetry.p95_request_ms),
                },
                {
                  label: t`Database health failures`,
                  value: String(serviceTelemetry.database_health_failures),
                },
              ].map((metric) => (
                <div key={metric.label} className="border-b border-border px-3 py-3 odd:border-r last:border-b-0">
                  <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
                  <dd className="mt-1 font-data text-sm font-semibold text-foreground">{metric.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-4 text-xs text-muted-foreground">
              {localizedReason(serviceTelemetryMeta.reason, t`Request and availability telemetry is unavailable.`)}
            </p>
          )}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              <SectionMeta meta={data.service_health} stale={snapshotStale} />
              <SectionMeta meta={serviceTelemetryMeta} stale={snapshotStale} />
            </div>
            <a
              href={data.links.public_status}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
            >
              <Trans>Public status</Trans>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          </div>
        </section>

        <section aria-labelledby="product-value-heading">
          <div className="flex items-start justify-between gap-4">
            <h3 id="product-value-heading" className="text-base font-semibold text-foreground">
              <Trans>Product value</Trans>
            </h3>
            {product?.directional ? (
              <Badge variant="outline" className="border-accent-cobalt/40 text-accent-cobalt">
                <Trans>Directional</Trans>
              </Badge>
            ) : null}
          </div>

          {product ? (
            <dl className="mt-4 grid grid-cols-2 border-y border-border sm:grid-cols-4">
              {[
                { label: t`DAU`, value: product.dau },
                { label: t`WAU`, value: product.wau },
                { label: t`MAU`, value: product.mau },
                { label: t`Registered`, value: product.registered_users },
              ].map((metric) => (
                <div key={metric.label} className="border-b border-border px-3 py-4 sm:border-b-0 sm:border-r sm:last:border-r-0">
                  <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
                  <dd className="mt-1 font-data text-lg font-semibold text-foreground">{metric.value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              <Trans>Usage aggregates are unavailable.</Trans>
            </div>
          )}
          {productTelemetry ? (
            <div className="mt-5 space-y-5">
              <div>
                <p className="text-xs font-semibold text-foreground">
                  <Trans>Today engagement</Trans>
                </p>
                {productTelemetry.surfaces.length > 0 ? (
                  <div className="mt-2 divide-y divide-border border-y border-border">
                    {productTelemetry.surfaces.map((surface) => (
                      <div key={surface.surface} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-3">
                        <span className="min-w-24 text-sm font-medium text-foreground">
                          {surfaceLabel(surface.surface)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          <Trans>Today reach rate</Trans>{' '}
                          <strong className="font-data font-semibold text-foreground">
                            {formatPercent(surface.today_reach_rate)}
                          </strong>
                        </span>
                        <span className="text-xs text-muted-foreground">
                          <Trans>Decision response rate</Trans>{' '}
                          <strong className="font-data font-semibold text-foreground">
                            {formatPercent(surface.decision_response_rate)}
                          </strong>
                        </span>
                        <span className="text-xs text-muted-foreground">
                          <Trans>Reported value rate</Trans>{' '}
                          <strong className="font-data font-semibold text-foreground">
                            {formatPercent(surface.reported_value_rate)}
                          </strong>
                        </span>
                        <span className="text-xs text-muted-foreground">
                          <Trans>Repeated weekly use</Trans>{' '}
                          <strong className="font-data font-semibold text-foreground">
                            {formatPercent(surface.repeated_rate)}
                          </strong>
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    <Trans>No Today events were recorded in this window.</Trans>
                  </p>
                )}
              </div>
              <div>
                <p className="text-xs font-semibold text-foreground">
                  <Trans>Coach useful-vote rate</Trans>
                </p>
                {productTelemetry.coach.length > 0 ? (
                  <div className="mt-2 divide-y divide-border border-y border-border">
                    {productTelemetry.coach.map((insight) => (
                      <div key={insight.insight_type} className="flex items-center justify-between gap-4 py-3">
                        <span className="text-sm text-foreground">{insightTypeLabel(insight.insight_type)}</span>
                        <span className="font-data text-sm font-semibold text-foreground">
                          {formatPercent(insight.useful_rate)}
                          <span className="ml-2 text-[11px] font-normal text-muted-foreground">
                            {insight.useful_votes}/{insight.total_votes}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    <Trans>No Coach votes were recorded in this window.</Trans>
                  </p>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-xs text-muted-foreground">
              {localizedReason(productTelemetryMeta.reason, t`Today and Coach telemetry is unavailable.`)}
            </p>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            <Trans>DAU, WAU, and MAU use authenticated request activity for context. Today and Coach metrics use trusted backend telemetry.</Trans>
          </p>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            <SectionMeta meta={data.product_value} stale={snapshotStale} />
            <SectionMeta meta={productTelemetryMeta} stale={snapshotStale} />
          </div>
        </section>
      </div>

      {agentLearningSection ? (
        <section aria-labelledby="agent-learning-heading" className="border-t border-border pt-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                  agentLearning
                    ? agentLearning.autonomy_level === 'policy_gated_auto_merge'
                      ? 'bg-primary/10 text-primary'
                      : 'bg-accent-amber/10 text-accent-amber'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 id="agent-learning-heading" className="text-base font-semibold text-foreground">
                    <Trans>Agent learning</Trans>
                  </h3>
                  {agentLearning ? (
                    <Badge
                      variant="outline"
                      className={cn(
                        agentLearning.autonomy_level === 'policy_gated_auto_merge'
                          ? 'border-primary/30 text-primary'
                          : 'border-accent-amber/40 text-accent-amber',
                      )}
                    >
                      {agentLearning.autonomy_level === 'policy_gated_auto_merge'
                        ? t`Policy-gated auto-merge`
                        : t`Review required`}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                  {agentLearning
                    ? agentLearning.autonomy_level === 'policy_gated_auto_merge'
                      ? t`${agentLearning.promoted_classes.length} narrow change class(es) may merge through the independent policy gate.`
                      : t`No change class is promoted. Decisions and outcomes are being recorded while merge remains review-gated.`
                    : t`The agent decision and outcome aggregate could not be refreshed.`}
                </p>
                <SectionMeta meta={agentLearningSection} stale={snapshotStale} className="mt-3" />
              </div>
            </div>
            {agentLearning ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <GitPullRequest className="h-4 w-4" />
                <span>
                  <Trans>
                    Policy {agentLearning.review_policy_version} · decision {agentLearning.decision_policy_version}
                  </Trans>
                </span>
              </div>
            ) : null}
          </div>
          {agentLearning ? (
            <>
              <dl className="mt-5 grid grid-cols-2 border-y border-border sm:grid-cols-4">
                {[
                  { label: t`Decisions`, value: agentLearning.decisions_total },
                  { label: t`Adjudicated`, value: activeAgentEval.evaluated },
                  {
                    label: t`Active accuracy`,
                    value: formatPercent(activeAgentEval.accuracy),
                  },
                  {
                    label: t`Challenger accuracy`,
                    value: formatPercent(challengerAgentEval.accuracy),
                  },
                ].map((metric) => (
                  <div key={metric.label} className="border-b border-border px-3 py-4 sm:border-b-0 sm:border-r sm:last:border-r-0">
                    <dt className="text-[11px] text-muted-foreground">{metric.label}</dt>
                    <dd className="mt-1 font-data text-lg font-semibold text-foreground">{metric.value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs text-muted-foreground">
                <Trans>
                  {agentLearning.shadow_decisions} shadow decisions · {agentLearning.agent_ready_applied} labels applied · {agentLearning.outcomes_total} durable outcomes
                </Trans>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                <Trans>Active errors:</Trans>{' '}
                <span className="font-data">
                  {activeAgentEval.false_positives} FP · {activeAgentEval.false_negatives} FN
                </span>
                {' · '}
                <Trans>Challenger errors:</Trans>{' '}
                <span className="font-data">
                  {challengerAgentEval.false_positives} FP · {challengerAgentEval.false_negatives} FN
                  {' · '}
                  {challengerAgentEval.evaluated} <Trans>cases</Trans>
                </span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                <Trans>Prompt-semantic slice:</Trans>{' '}
                <Trans>Active</Trans>{' '}
                <span className="font-data">
                  {formatPercent(activeSemanticEval.accuracy)} · {activeSemanticEval.evaluated}{' '}
                  <Trans>cases</Trans> · {activeSemanticEval.false_positives} FP ·{' '}
                  {activeSemanticEval.false_negatives} FN
                </span>
                {' · '}
                <Trans>Challenger</Trans>{' '}
                <span className="font-data">
                  {formatPercent(challengerSemanticEval.accuracy)} ·{' '}
                  {challengerSemanticEval.evaluated} <Trans>cases</Trans> ·{' '}
                  {challengerSemanticEval.false_positives} FP ·{' '}
                  {challengerSemanticEval.false_negatives} FN
                </span>
                {' · '}
                <Trans>Priority is excluded from readiness evaluation.</Trans>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="font-data">{agentLearning.agent_ready_candidates}</span>{' '}
                <Trans>agent-ready candidates</Trans>
                {' · '}
                <span className="font-data">{agentLearning.merged_pull_requests}</span>{' '}
                <Trans>merged PR outcomes</Trans>
                {' · '}
                <span className="font-data">{agentLearning.human_overrides}</span>{' '}
                <Trans>publication overrides</Trans>
              </p>
            </>
          ) : null}
        </section>
      ) : null}

      <section aria-labelledby="platform-health-heading" className="border-t border-border pt-7">
        <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-start">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                platform
                  ? platformLastKnown
                    ? 'bg-accent-amber/10 text-accent-amber'
                    : 'bg-primary/10 text-primary'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              {platform ? <Activity className="h-4 w-4" /> : <CloudOff className="h-4 w-4" />}
            </div>
            <div>
              <h3 id="platform-health-heading" className="text-base font-semibold text-foreground">
                <Trans>Platform health</Trans>
              </h3>
              <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                {platform
                  ? t`Trusted sync and connection outcomes from the backend telemetry boundary.`
                  : localizedReason(platformSection.reason, t`Platform telemetry is unavailable.`)}
              </p>
              <SectionMeta meta={platformSection} stale={snapshotStale} className="mt-3" />
            </div>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <a
              href={azureLogsUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-cobalt hover:underline"
            >
              <Trans>Azure logs</Trans>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
            <a
              href={data.links.monitoring_docs}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-cobalt hover:underline"
            >
              <Trans>Monitoring runbook</Trans>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
        {platform ? (
          <div className="mt-6 space-y-7">
            <div className="grid gap-7 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold text-foreground">
                  <Trans>Sync reliability</Trans>
                </h4>
                {platform.sync.length > 0 ? (
                  <div className="mt-2 divide-y divide-border border-y border-border">
                    {platform.sync.map((sync) => (
                      <div key={sync.platform} className="flex items-center justify-between gap-4 py-3">
                        <span className="text-sm font-medium capitalize text-foreground">{sync.platform}</span>
                        <span className="text-right text-xs text-muted-foreground">
                          <strong className="font-data font-semibold text-foreground">
                            {formatPercent(
                              sync.attempts > 0 ? sync.successes / sync.attempts : null,
                              1,
                            )}
                          </strong>{' '}
                          <Trans>successful</Trans>
                          <span className="ml-2 font-data">
                            {sync.successes}/{sync.attempts}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    <Trans>No sync attempts were recorded in this window.</Trans>
                  </p>
                )}
              </div>
              <div>
                <h4 className="text-sm font-semibold text-foreground">
                  <Trans>Systemic failure classes</Trans>
                </h4>
                {platform.systemic_failures.length > 0 ? (
                  <div className="mt-2 divide-y divide-border border-y border-border">
                    {platform.systemic_failures.map((failure) => (
                      <div
                        key={`${failure.platform}-${failure.failure_class}`}
                        className="flex items-center justify-between gap-4 py-3"
                      >
                        <span className="min-w-0 text-sm text-foreground">
                          <span className="font-medium capitalize">{failure.platform}</span>
                          <span className="ml-2 text-xs text-muted-foreground">
                            {failureClassLabel(failure.failure_class)}
                          </span>
                        </span>
                        <span className="shrink-0 text-right text-xs text-muted-foreground">
                          <strong className="font-data font-semibold text-foreground">
                            {failure.affected_users}
                          </strong>{' '}
                          <Trans>users</Trans>
                          <span className="ml-2 font-data">
                            {failure.failures} <Trans>failures</Trans>
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">
                    <Trans>No systemic failure classes were recorded in this window.</Trans>
                  </p>
                )}
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground">
                <Trans>Connection funnel</Trans>
              </h4>
              {platform.connections.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-x-6 gap-y-3 border-y border-border py-3">
                  {platform.connections.map((connection) => (
                    <div
                      key={`${connection.platform}-${connection.flow}-${connection.stage}-${connection.outcome}`}
                      className="min-w-48"
                    >
                      <p className="text-xs text-muted-foreground">
                        <span className="font-medium capitalize text-foreground">{connection.platform}</span>
                        {' · '}
                        {connectionFlowLabel(connection.flow)}
                        {' · '}
                        {connectionOutcomeLabel(connection.outcome)}
                      </p>
                      <p className="mt-1 font-data text-sm font-semibold text-foreground">
                        {connection.attempts} <Trans>attempts</Trans>
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-xs text-muted-foreground">
                  <Trans>No connection attempts were recorded in this window.</Trans>
                </p>
              )}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
