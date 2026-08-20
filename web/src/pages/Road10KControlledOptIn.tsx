import { useState } from 'react';
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { useLocale } from '@/contexts/LocaleContext';
import { useApi, apiFetch } from '@/hooks/useApi';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { Road10KAccessResponse } from '@/types/api';
import {
  ROAD_10K_PLAN_STATE_COPY,
  road10kCopy,
  type Road10KCopyKey,
} from '@/lib/road-10k-control';

type FlowState = 'idle' | 'reauth' | 'notice' | 'joining' | 'withdrawn';

const ROLLOUT_TITLE_COPY: Record<Road10KAccessResponse['rollout_status'], Road10KCopyKey> = {
  invited: 'invitation.title',
  'reauth-required': 'reauth.title',
  'notice-unavailable': 'notice.blocked_title',
  enrolled: 'status.rollout_enrolled',
  'enrollment-closed': 'life.close_title',
  hold: 'life.hold_title',
  withdrawn: 'status.rollout_withdrawn',
  removed: 'life.removed_title',
  paused: 'life.pause_title',
  killed: 'life.kill_title',
  rollback: 'life.rollback_title',
  stopped: 'life.stop_title',
  revision: 'life.revision_title',
};

const ROLLOUT_BODY_COPY: Record<Road10KAccessResponse['rollout_status'], Road10KCopyKey> = {
  invited: 'invitation.body',
  'reauth-required': 'reauth.body',
  'notice-unavailable': 'notice.blocked_body',
  enrolled: 'empty.no_proposal',
  'enrollment-closed': 'life.close_out',
  hold: 'life.hold_body',
  withdrawn: 'success.withdrawn',
  removed: 'life.removed_body',
  paused: 'life.pause_body',
  killed: 'life.kill_body',
  rollback: 'life.rollback_body',
  stopped: 'life.stop_body',
  revision: 'life.revision_body',
};

function localized(
  key: Parameters<typeof road10kCopy>[0],
  locale: 'en' | 'zh',
): string {
  return road10kCopy(key, locale === 'zh' ? 'zh-CN' : 'en');
}

/**
 * Dormant owner-scoped experience. It is rendered from incumbent Goal rather
 * than registered as a public route; a 404/unknown authority returns null.
 */
export default function Road10KControlledOptIn() {
  const { locale } = useLocale();
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
  const planKeys = ROAD_10K_PLAN_STATE_COPY[data?.plan_status ?? 'none'];
  const planTitle = localized(planKeys[0], locale);
  const planBody = localized(
    planKeys[planKeys.length - 1] ?? planKeys[0],
    locale,
  );

  if (loading || !data) return null;

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
          notice_digest: data.notice_digest,
          client: 'web',
        }),
      });
      if (!response.ok) throw new Error(copy('error.generic'));
      setFlow('idle');
      setPassword('');
      setAcknowledged(false);
      await refetch();
    } catch {
      setFlow('notice');
      setError(copy('error.generic'));
    }
  };

  const leave = async () => {
    setError(null);
    try {
      const response = await apiFetch('/api/road-10k/withdraw', { method: 'POST' });
      if (!response.ok) throw new Error(copy('error.generic'));
      setFlow('withdrawn');
      await refetch();
    } catch {
      setError(copy('error.generic'));
    }
  };

  return (
    <>
      {data.rollout_status === 'invited' && !invitationDismissed && (
        <Card className="mt-6 border-slate-200 dark:border-slate-800">
          <CardHeader>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
              <ShieldCheck className="h-4 w-4 text-accent-cobalt" aria-hidden="true" />
              {copy('status.rollout_invited')}
            </div>
            <CardTitle>{copy('invitation.title')}</CardTitle>
            <CardDescription>{copy('invitation.body')}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button onClick={() => setFlow('reauth')}>
              {copy('action.review_invitation')} <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setFlow('idle');
                setInvitationDismissed(true);
              }}
            >
              {copy('action.not_now')}
            </Button>
          </CardContent>
        </Card>
      )}

      {data.rollout_status === 'enrolled' && (
        <Card className="mt-6 border-slate-200 dark:border-slate-800">
          <CardHeader>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
              <ShieldCheck className="h-4 w-4 text-accent-cobalt" aria-hidden="true" />
              {copy('status.rollout_enrolled')}
            </div>
            <CardTitle>{planTitle}</CardTitle>
            <CardDescription>{planBody}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" onClick={leave}>{copy('action.leave')}</Button>
            <Button variant="outline" disabled title={copy('feedback.screenshot_blocked')}>
              {copy('action.add_screenshot')}
            </Button>
            <p className="text-sm text-slate-600 dark:text-slate-300" role="status">
              {copy('feedback.screenshot_blocked')}
            </p>
          </CardContent>
        </Card>
      )}

      {data.rollout_status !== 'invited' && data.rollout_status !== 'enrolled' && (
        <Card className="mt-6 border-slate-200 dark:border-slate-800">
          <CardHeader>
            <CardTitle>{copy(ROLLOUT_TITLE_COPY[data.rollout_status])}</CardTitle>
            <CardDescription>{copy(ROLLOUT_BODY_COPY[data.rollout_status])}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" disabled title={copy('disabled.authority')}>
              {copy('action.latest')}
            </Button>
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300" role="status">
              {planTitle}: {planBody}
            </p>
          </CardContent>
        </Card>
      )}

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
                <Label htmlFor="road-10k-password"><LockKeyhole className="mr-2 inline h-4 w-4" aria-hidden="true" />Password</Label>
                <Input
                  id="road-10k-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setFlow('idle')}>{copy('action.cancel')}</Button>
                <Button onClick={() => setFlow('notice')} disabled={!password}>{copy('action.continue')}</Button>
              </DialogFooter>
            </>
          )}
          {(flow === 'notice' || flow === 'joining') && (
            <>
              <DialogHeader>
                <DialogTitle>{copy('notice.title')}</DialogTitle>
                <DialogDescription>{copy('notice.intro')}</DialogDescription>
              </DialogHeader>
              <div className="max-h-[50vh] space-y-3 overflow-y-auto text-sm text-slate-700 dark:text-slate-200">
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
              <DialogFooter>
                <Button variant="outline" onClick={() => setFlow('idle')} disabled={flow === 'joining'}>{copy('action.cancel')}</Button>
                <Button onClick={submitOptIn} disabled={!acknowledged || flow === 'joining'}>
                  {flow === 'joining' ? copy('progress.joining') : copy('action.join')}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
