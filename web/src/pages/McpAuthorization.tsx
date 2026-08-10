import { useCallback, useEffect, useState } from 'react';
import { Trans } from '@lingui/react/macro';
import { LockKeyhole, ShieldCheck } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useLocale } from '@/contexts/LocaleContext';
import { apiFetch, extractErrorMessage } from '@/hooks/useApi';
import type {
  McpAccessHandoff,
  PersonalContextKind,
  PersonalContextPurpose,
} from '@/types/api';

type PageState = 'loading' | 'ready' | 'approved' | 'denied' | 'error';

function purposeLabel(purpose: PersonalContextPurpose | null) {
  if (purpose === 'plan_adjustment') {
    return <Trans>Suggest adjustments to the current plan</Trans>;
  }
  if (purpose === 'execution_interpretation') {
    return <Trans>Interpret one workout without guessing a cause</Trans>;
  }
  if (purpose === 'plan_generation') {
    return <Trans>Use confirmed context for plan generation</Trans>;
  }
  if (purpose === 'goal_review') {
    return <Trans>Review the current goal</Trans>;
  }
  if (purpose === 'outcome_review') {
    return <Trans>Review plan outcomes</Trans>;
  }
  return <Trans>Not requested</Trans>;
}

function kindLabel(kind: PersonalContextKind | null) {
  if (kind === 'temporary_constraint') {
    return <Trans>Temporary availability</Trans>;
  }
  if (kind === 'execution_explanation') {
    return <Trans>Workout explanation</Trans>;
  }
  if (kind === 'durable_preference') {
    return <Trans>Durable preference</Trans>;
  }
  return <Trans>Not requested</Trans>;
}

export default function McpAuthorization() {
  const { locale } = useLocale();
  const [params] = useSearchParams();
  const state = params.get('state') ?? '';
  const [pageState, setPageState] = useState<PageState>('loading');
  const [handoff, setHandoff] = useState<McpAccessHandoff | null>(null);
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  const load = useCallback(async () => {
    if (!state) {
      setError('MCP_HANDOFF_NOT_FOUND');
      setPageState('error');
      return;
    }
    setPageState('loading');
    setError('');
    try {
      const response = await apiFetch(
        `/api/auth/mcp/handoffs/${encodeURIComponent(state)}`,
      );
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            'MCP_HANDOFF_UNAVAILABLE',
          ),
        );
      }
      const result = await response.json() as McpAccessHandoff;
      setHandoff(result);
      if (result.status === 'approved' || result.status === 'exchanged') {
        setPageState('approved');
      } else if (result.status === 'denied') {
        setPageState('denied');
      } else {
        setPageState('ready');
      }
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : 'MCP_HANDOFF_UNAVAILABLE',
      );
      setPageState('error');
    }
  }, [state]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      void load();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [load]);

  const decide = async (decision: 'approved' | 'denied') => {
    setWorking(true);
    setError('');
    try {
      const response = await apiFetch(
        `/api/auth/mcp/handoffs/${encodeURIComponent(state)}/decision`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decision }),
        },
      );
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            'MCP_HANDOFF_UNAVAILABLE',
          ),
        );
      }
      setPageState(decision);
    } catch (decisionError) {
      setError(
        decisionError instanceof Error
          ? decisionError.message
          : 'MCP_HANDOFF_UNAVAILABLE',
      );
      setPageState('error');
    } finally {
      setWorking(false);
    }
  };

  const isContext = handoff?.request_type === 'context';

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10 sm:px-6">
      <Card className="w-full max-w-xl">
        <CardHeader className="border-b border-border pb-5">
          <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-accent-cobalt/10 text-accent-cobalt">
            {isContext
              ? <LockKeyhole className="size-5" aria-hidden="true" />
              : <ShieldCheck className="size-5" aria-hidden="true" />}
          </div>
          <CardTitle className="text-xl font-semibold">
            {isContext
              ? <Trans>Allow structured plan context?</Trans>
              : <Trans>Connect Praxys Coach?</Trans>}
          </CardTitle>
          <CardDescription className="max-w-[65ch] leading-relaxed">
            {isContext
              ? (
                <Trans>
                  Review the exact purpose and access below. The plugin cannot
                  approve this request, read private notes, grant AI consent,
                  or save context on its own.
                </Trans>
              )
              : (
                <Trans>
                  This connects the official Praxys Coach plugin to your
                  account. Personal plan context stays unavailable until you
                  approve a separate, short-lived request.
                </Trans>
              )}
          </CardDescription>
        </CardHeader>

        <CardContent className="min-h-52 py-2" aria-live="polite">
          {pageState === 'loading' && (
            <div className="space-y-4 py-4" aria-label="Loading authorization request">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}

          {pageState === 'error' && (
            <Alert variant="destructive" className="my-4">
              <AlertTitle><Trans>Authorization link unavailable</Trans></AlertTitle>
              <AlertDescription className="space-y-3">
                <p>
                  <Trans>
                    This link is invalid, expired, or belongs to another
                    account. Start a new request from the plugin.
                  </Trans>
                </p>
                <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
                  <Trans>Retry</Trans>
                </Button>
                <span className="sr-only">{error}</span>
              </AlertDescription>
            </Alert>
          )}

          {pageState === 'ready' && handoff && (
            <div className="divide-y divide-border">
              <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-4 py-4 text-sm">
                <span className="text-muted-foreground"><Trans>Client</Trans></span>
                <span className="font-medium text-foreground">
                  <Trans>Praxys Coach plugin</Trans>
                </span>
              </div>
              {isContext && (
                <>
                  <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-4 py-4 text-sm">
                    <span className="text-muted-foreground"><Trans>Purpose</Trans></span>
                    <span className="font-medium text-foreground">
                      {purposeLabel(handoff.purpose)}
                    </span>
                  </div>
                  <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-4 py-4 text-sm">
                    <span className="text-muted-foreground"><Trans>Context type</Trans></span>
                    <span className="font-medium text-foreground">
                      {kindLabel(handoff.kind)}
                    </span>
                  </div>
                  <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-4 py-4 text-sm">
                    <span className="text-muted-foreground"><Trans>Access</Trans></span>
                    <span className="font-medium text-foreground">
                      {handoff.access.includes('read') && handoff.access.includes('write')
                        ? <Trans>Read structured fields and draft one change</Trans>
                        : handoff.access.includes('write')
                          ? <Trans>Draft one change for your review</Trans>
                          : <Trans>Read structured fields</Trans>}
                    </span>
                  </div>
                </>
              )}
              <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-4 py-4 text-sm">
                <span className="text-muted-foreground"><Trans>Request expires</Trans></span>
                <time
                  dateTime={handoff.expires_at}
                  className="font-data text-foreground"
                >
                  {new Date(handoff.expires_at).toLocaleString(
                    locale === 'zh' ? 'zh-CN' : 'en-US',
                  )}
                </time>
              </div>
              {isContext && (
                <p className="py-4 text-xs leading-relaxed text-muted-foreground">
                  <Trans>
                    Read access returns only the minimum structured projection.
                    Write access creates one request-scoped preview; saving
                    still requires confirmation in Praxys. Optional notes and
                    AI permission are never included.
                  </Trans>
                </p>
              )}
            </div>
          )}

          {(pageState === 'approved' || pageState === 'denied') && (
            <div className="py-8 text-center">
              <ShieldCheck className="mx-auto size-8 text-primary" aria-hidden="true" />
              <h2 className="mt-4 text-lg font-semibold text-foreground">
                {pageState === 'approved'
                  ? <Trans>Access approved</Trans>
                  : <Trans>Access denied</Trans>}
              </h2>
              <p className="mx-auto mt-2 max-w-[48ch] text-sm leading-relaxed text-muted-foreground">
                {pageState === 'approved'
                  ? (
                    <Trans>
                      Return to the plugin to finish the one-time exchange.
                      You can close this tab.
                    </Trans>
                  )
                  : (
                    <Trans>
                      No access was granted. You can close this tab and return
                      to the plugin.
                    </Trans>
                  )}
              </p>
            </div>
          )}
        </CardContent>

        {pageState === 'ready' && (
          <CardFooter className="flex flex-col-reverse gap-2 bg-muted/35 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={working}
              onClick={() => void decide('denied')}
              className="w-full sm:w-auto"
            >
              <Trans>Deny</Trans>
            </Button>
            <Button
              type="button"
              disabled={working}
              onClick={() => void decide('approved')}
              className="w-full sm:w-auto"
            >
              {working ? <Trans>Saving decision…</Trans> : <Trans>Approve access</Trans>}
            </Button>
          </CardFooter>
        )}
      </Card>
    </main>
  );
}
