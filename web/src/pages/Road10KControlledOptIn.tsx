import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { Trans } from '@lingui/react/macro';
import { useQueryClient } from '@tanstack/react-query';

import { useLocale } from '@/contexts/LocaleContext';
import { apiFetch, useApi } from '@/hooks/useApi';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { Road10KAccessResponse } from '@/types/api';
import {
  ROAD_10K_PLAN_STATE_COPY,
  road10kAccessStateCopy,
  road10kCopy,
  type Road10KCopyKey,
  type Road10KExperienceRolloutState,
} from '@/lib/road-10k-control';

type FlowState = 'idle' | 'reauth' | 'notice' | 'joining';
type Surface = 'goal' | 'training' | 'settings';

export type Road10KNavigationIntent = 'review_invitation' | 'review_status';

interface Road10KControlledOptInProps {
  surface?: Surface;
  intent?: Road10KNavigationIntent | null;
}

const ROLLOUT_STATUS_COPY: Record<
  Road10KExperienceRolloutState,
  Road10KCopyKey
> = {
  invited: 'status.rollout_invited',
  'reauth-required': 'status.rollout_reauth',
  'notice-unavailable': 'status.rollout_notice',
  enrolled: 'status.rollout_enrolled',
  'enrollment-closed': 'status.rollout_closed',
  hold: 'status.rollout_hold',
  withdrawn: 'status.rollout_withdrawn',
  removed: 'status.rollout_removed',
  paused: 'status.rollout_paused',
  killed: 'status.rollout_killed',
  rollback: 'status.rollout_rollback',
  stopped: 'status.rollout_stopped',
  revision: 'status.rollout_revision',
};

function localized(
  key: Parameters<typeof road10kCopy>[0],
  locale: 'en' | 'zh',
): string {
  return road10kCopy(key, locale === 'zh' ? 'zh-CN' : 'en');
}

function scrollToPlanStart() {
  const reduceMotion = window.matchMedia(
    '(prefers-reduced-motion: reduce)',
  ).matches;
  document.getElementById('plan-start')?.scrollIntoView({
    behavior: reduceMotion ? 'auto' : 'smooth',
    block: 'start',
  });
}

export default function Road10KControlledOptIn({
  surface = 'training',
  intent = null,
}: Road10KControlledOptInProps) {
  const { locale } = useLocale();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const copy = <K extends Parameters<typeof road10kCopy>[0]>(key: K) =>
    localized(key, locale);
  const { data, loading, refetch } = useApi<Road10KAccessResponse>(
    '/api/road-10k/access',
    { timeoutMs: 12_000 },
  );
  const [flow, setFlow] = useState<FlowState>('idle');
  const [password, setPassword] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [invitationDismissed, setInvitationDismissed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const consumedIntentRef = useRef<Road10KNavigationIntent | null>(null);

  useEffect(() => {
    if (
      surface !== 'training'
      || !intent
      || !data
      || consumedIntentRef.current === intent
    ) {
      return;
    }
    consumedIntentRef.current = intent;
    if (intent === 'review_invitation' && data.rollout_status === 'invited') {
      let active = true;
      queueMicrotask(() => {
        if (!active) return;
        setInvitationDismissed(false);
        setFlow('reauth');
        setError(null);
      });
      return () => {
        active = false;
      };
    }
  }, [data, intent, surface]);

  if (loading || !data) return null;

  const rolloutKeys = road10kAccessStateCopy(
    data.rollout_status,
    data.plan_status,
  );
  const planKeys = ROAD_10K_PLAN_STATE_COPY[data.plan_status];
  const rolloutTitleKey: Road10KCopyKey = data.rollout_status === 'enrolled'
    ? 'status.rollout_enrolled'
    : rolloutKeys[0];
  const rolloutBodyKey: Road10KCopyKey = data.rollout_status === 'enrolled'
    ? 'success.joined'
    : (rolloutKeys[rolloutKeys.length - 1] ?? rolloutTitleKey);
  const rolloutTitle = copy(rolloutTitleKey);
  const rolloutBody = copy(rolloutBodyKey);
  const rolloutStatus = copy(ROLLOUT_STATUS_COPY[data.rollout_status]);
  const planStatus = copy(planKeys[0]);
  const planBody = copy(planKeys[planKeys.length - 1] ?? planKeys[0]);
  const showLeaveControl = surface === 'settings' && [
    'enrolled',
    'enrollment-closed',
    'hold',
    'paused',
    'revision',
  ].includes(data.rollout_status);
  if (data.rollout_status === 'invited' && invitationDismissed) return null;

  const openTraining = (nextIntent: Road10KNavigationIntent) => {
    navigate('/training#plan-start', {
      state: { road10kIntent: nextIntent },
    });
  };

  const submitOptIn = async () => {
    if (!acknowledged) return;
    setFlow('joining');
    setError(null);
    try {
      const response = await apiFetch('/api/road-10k/opt-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password,
          client: 'web',
        }),
      });
      if (!response.ok) throw new Error(copy('error.generic'));
      setFlow('idle');
      setPassword('');
      setAcknowledged(false);
      await Promise.all([
        refetch(),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/generation/capabilities'],
        }),
      ]);
    } catch {
      setFlow('reauth');
      setError(copy('error.generic'));
    }
  };

  const leave = async () => {
    if (leaving) return;
    setLeaving(true);
    setError(null);
    try {
      const response = await apiFetch('/api/road-10k/withdraw', { method: 'POST' });
      if (!response.ok) throw new Error(copy('error.generic'));
      setLeaveDialogOpen(false);
      await refetch();
    } catch {
      setError(copy('error.generic'));
    } finally {
      setLeaving(false);
    }
  };

  const leaveConfirmation = (
    <Dialog
      open={leaveDialogOpen}
      onOpenChange={(open) => {
        if (!leaving) setLeaveDialogOpen(open);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{copy('life.withdraw_title')}</DialogTitle>
          <DialogDescription>{copy('life.withdraw_body')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setLeaveDialogOpen(false)}
            disabled={leaving}
          >
            {copy('action.cancel')}
          </Button>
          <Button onClick={leave} disabled={leaving}>
            {leaving ? copy('progress.leaving') : copy('action.leave')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  if (surface === 'goal') {
    if (data.rollout_status === 'invited') {
      return (
        <Card className="mt-6 border-border">
          <CardHeader>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-accent-cobalt" aria-hidden="true" />
              {rolloutStatus}
            </div>
            <CardTitle>{copy('invitation.title')}</CardTitle>
            <CardDescription>{copy('invitation.body')}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button onClick={() => openTraining('review_invitation')}>
              {copy('action.review_invitation')} <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setInvitationDismissed(true);
                setError(null);
              }}
            >
              {copy('action.not_now')}
            </Button>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card className="mt-6 border-border">
        <CardHeader>
          <CardTitle>{rolloutStatus}</CardTitle>
          <CardDescription>{planStatus}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {rolloutBody}
          </p>
          <Button variant="outline" onClick={() => openTraining('review_status')}>
            {copy('action.training')}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (surface === 'settings') {
    return (
      <>
        <Card id="road-10k-settings" className="mb-8 border-border">
          <CardHeader>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-accent-cobalt" aria-hidden="true" />
              {copy('action.training')}
            </div>
            <CardTitle>{rolloutTitle}</CardTitle>
            <CardDescription>{rolloutBody}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <p className="text-sm text-foreground">{rolloutStatus}</p>
              <p className="text-sm text-foreground">{planStatus}</p>
            </div>
            <p className="text-sm text-muted-foreground">
              {copy('notice.leave')}
            </p>
            {showLeaveControl && (
              <Button variant="outline" onClick={() => setLeaveDialogOpen(true)}>
                {copy('action.leave')}
              </Button>
            )}
          </CardContent>
        </Card>
        {error && flow === 'idle' && (
          <Alert variant="destructive" className="mb-8" role="alert">
            <AlertTitle>{copy('error.generic')}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {leaveConfirmation}
      </>
    );
  }

  return (
    <>
      <Card className="mt-8 border-border">
        <CardHeader>
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-accent-cobalt" aria-hidden="true" />
            {rolloutStatus}
          </div>
          <CardTitle>{rolloutTitle}</CardTitle>
          <CardDescription>{rolloutBody}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <p className="text-sm text-foreground">{rolloutStatus}</p>
            <p className="text-sm text-foreground">{planStatus}</p>
          </div>

          {data.rollout_status === 'invited' && (
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => {
                  setError(null);
                  setFlow('reauth');
                }}
              >
                {copy('action.review_invitation')}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setInvitationDismissed(true);
                  setError(null);
                }}
              >
                {copy('action.not_now')}
              </Button>
            </div>
          )}

          {data.rollout_status === 'enrolled' && (
            <>
              <Button onClick={scrollToPlanStart}>
                {copy('action.check')}
              </Button>
              <Button
                variant="outline"
                disabled
                title={copy('feedback.screenshot_blocked')}
              >
                {copy('action.add_screenshot')}
              </Button>
              <p className="text-sm text-muted-foreground" role="status">
                {copy('feedback.screenshot_blocked')}
              </p>
            </>
          )}

          {data.rollout_status !== 'invited' && data.rollout_status !== 'enrolled' && (
            <p className="text-sm text-muted-foreground" role="status">
              {planBody}
            </p>
          )}
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="mt-4" role="alert">
          <AlertTitle>{copy('error.generic')}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Dialog
        open={flow === 'reauth' || flow === 'notice' || flow === 'joining'}
        onOpenChange={(open) => {
          if (!open && flow !== 'joining') {
            setFlow('idle');
            setPassword('');
            setAcknowledged(false);
          }
        }}
      >
        <DialogContent>
          {flow === 'reauth' && (
            <>
              <DialogHeader>
                <DialogTitle>{copy('reauth.title')}</DialogTitle>
                <DialogDescription>{copy('reauth.body')}</DialogDescription>
              </DialogHeader>
              <div className="space-y-2">
                <Label htmlFor="road-10k-password">
                  <LockKeyhole className="mr-2 inline h-4 w-4" aria-hidden="true" />
                  <Trans>Password</Trans>
                </Label>
                <Input
                  id="road-10k-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />
              </div>
              {error && (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setFlow('idle')}>
                  {copy('action.cancel')}
                </Button>
                <Button onClick={() => setFlow('notice')} disabled={!password}>
                  {copy('action.continue')}
                </Button>
              </DialogFooter>
            </>
          )}
          {(flow === 'notice' || flow === 'joining') && (
            <>
              <DialogHeader>
                <DialogTitle>{copy('notice.title')}</DialogTitle>
                <DialogDescription>{copy('notice.intro')}</DialogDescription>
              </DialogHeader>
              <div className="max-h-[50vh] space-y-3 overflow-y-auto text-sm text-foreground">
                <p>{copy('notice.scope')}</p>
                <p>{copy('notice.claims')}</p>
                <p>{copy('notice.control')}</p>
                <p>{copy('notice.data')}</p>
                <p>{copy('notice.leave')}</p>
                <label className="flex min-h-11 items-start gap-3 rounded-lg border p-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-5 w-5 shrink-0"
                    checked={acknowledged}
                    onChange={(event) => setAcknowledged(event.target.checked)}
                  />
                  <span>{copy('notice.ack')}</span>
                </label>
              </div>
              {error && (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              )}
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setFlow('idle')}
                  disabled={flow === 'joining'}
                >
                  {copy('action.cancel')}
                </Button>
                <Button onClick={submitOptIn} disabled={!acknowledged || flow === 'joining'}>
                  {flow === 'joining' ? copy('progress.joining') : copy('action.join')}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {leaveConfirmation}
    </>
  );
}
