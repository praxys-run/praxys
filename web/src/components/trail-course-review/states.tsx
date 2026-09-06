import { useEffect, useRef, useState } from 'react';
import { useLingui } from '@lingui/react/macro';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { apiFetch, extractErrorMessage } from '@/hooks/useApi';
import {
  TRAIL_API_ENDPOINTS,
  type TrailUnknownSchemaDraft,
} from '@/types/trail-plan';
import {
  parseTrailDeleteResponse,
  parseTrailDraftResponse,
} from './validation';
import { requestTrailMutation } from './mutation-error';

export function TrailCourseReviewSkeleton() {
  const { i18n, t } = useLingui();
  const isZh = i18n.locale.toLowerCase().startsWith('zh');
  const loadingLabel = isZh
    ? t`正在加载越野赛道核对`
    : t`Loading Trail course review`;
  return (
    <div
      aria-label={loadingLabel}
      aria-busy="true"
      className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8"
    >
      <div className="space-y-3">
        <Skeleton className="h-8 w-64 max-w-full" />
        <Skeleton className="h-4 w-[34rem] max-w-full" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]">
        <div className="space-y-5">
          {[1, 2, 3, 4, 5].map((item) => (
            <div key={item} className="space-y-3 border-b border-border pb-5">
              <Skeleton className="h-6 w-56 max-w-full" />
              <Skeleton className="h-11 w-full" />
              <Skeleton className="h-11 w-4/5" />
            </div>
          ))}
        </div>
        <div className="space-y-3 lg:sticky lg:top-6 lg:self-start">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      </div>
    </div>
  );
}
export function TrailCourseReviewLoadError({
  status,
  onRetry,
}: {
  status: number | null;
  onRetry: () => Promise<void>;
}) {
  const { i18n, t } = useLingui();
  const isZh = i18n.locale.toLowerCase().startsWith('zh');
  const title = status === 404
    ? isZh
      ? t`未找到此私密越野赛道核对`
      : t`This private Trail course review was not found`
    : isZh
      ? t`暂时无法加载越野赛道核对`
      : t`Trail course review could not be loaded`;
  const description = status === 404
    ? isZh
      ? t`请确认已登录赛事目标的所有者账号。Praxys 不会透露其他账号是否有此数据。`
      : t`Sign in as the owner of the event goal. Praxys does not reveal whether another account has this data.`
    : isZh
      ? t`请重试。未加载的数据不会被猜测或替换。`
      : t`Retry the request. Unavailable data will not be guessed or replaced.`;
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <Alert variant="destructive">
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{description}</p>
          {status === 404 ? null : (
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              onClick={() => { void onRetry().catch(() => undefined); }}
            >
              {isZh ? t`重试` : t`Retry`}
            </Button>
          )}
        </AlertDescription>
      </Alert>
    </main>
  );
}

export function TrailUnknownVersion({
  draft,
  onReload,
  onClearData,
  onRejectData,
}: {
  draft: TrailUnknownSchemaDraft;
  onReload: () => Promise<void>;
  onClearData: () => void;
  onRejectData: (message: string) => void;
}) {
  const { i18n, t } = useLingui();
  const isZh = i18n.locale.toLowerCase().startsWith('zh');
  const [dialog, setDialog] = useState<'reset' | 'delete' | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestRef.current?.abort();
      requestRef.current = null;
    };
  }, []);

  const mutate = async (kind: 'reset' | 'delete') => {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setMessage(null);
    try {
      const response = await requestTrailMutation(
        apiFetch,
        kind === 'reset' ? TRAIL_API_ENDPOINTS.reset : TRAIL_API_ENDPOINTS.draft,
        {
          method: kind === 'reset' ? 'POST' : 'DELETE',
          headers: { 'If-Match': draft.composite_revision },
        },
        controller.signal,
      );
      if (!mountedRef.current || requestRef.current !== controller) return;
      if (!response.ok) {
        throw new Error(await extractErrorMessage(response, 'Request failed.'));
      }
      const payload = await response.json() as unknown;
      if (!mountedRef.current || requestRef.current !== controller) return;
      if (kind === 'delete') {
        if (!parseTrailDeleteResponse(payload)) {
          throw new Error('The Trail deletion response was not recognized.');
        }
      } else {
        const reset = parseTrailDraftResponse(payload);
        if (!reset || reset.state !== 'current' || reset.reset_is_erasure !== false) {
          throw new Error('The Trail reset response was not recognized.');
        }
      }
      setDialog(null);
      onClearData();
      await onReload();
    } catch (error) {
      if (!mountedRef.current || requestRef.current !== controller) return;
      const failure = error instanceof Error
        ? error.message
        : isZh
          ? t`操作未完成。`
          : t`The action did not complete.`;
      setMessage(failure);
      onRejectData(failure);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        if (mountedRef.current) setBusy(false);
      }
    }
  };

  return (
    <main className="mx-auto w-full max-w-3xl space-y-5 px-4 py-8 sm:px-6 lg:px-8">
      <Alert variant="destructive">
        <AlertTitle>
          {isZh
            ? t`此赛道核对使用了不受支持的版本`
            : t`This course review uses an unsupported version`}
        </AlertTitle>
        <AlertDescription>
          {isZh
            ? t`Praxys 不会猜测旧版或未来字段如何映射到 v2。你可以重新加载、重置赛道核对，或删除这份越野草稿。`
            : t`Praxys will not guess how old or future fields map to v2. Reload, reset the course review, or delete this Trail draft.`}
        </AlertDescription>
      </Alert>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          onClick={() => { void onReload().catch(() => undefined); }}
        >
          {isZh ? t`重新加载受支持版本` : t`Reload the supported version`}
        </Button>
        <Button type="button" variant="outline" className="min-h-11" onClick={() => setDialog('reset')}>
          {isZh ? t`重置赛道核对` : t`Reset course review`}
        </Button>
        <Button type="button" variant="destructive" className="min-h-11" onClick={() => setDialog('delete')}>
          {isZh ? t`删除越野目标` : t`Delete Trail goal`}
        </Button>
      </div>
      <p aria-live="polite" className="break-words text-sm text-muted-foreground">
        {message}
      </p>
      <Dialog open={dialog !== null} onOpenChange={(open) => { if (!open) setDialog(null); }}>
        <DialogContent
          closeLabel={isZh ? t`关闭` : t`Close`}
          className="motion-reduce:animate-none sm:max-w-lg"
        >
          <DialogHeader>
            <DialogTitle>
              {dialog === 'reset'
                ? isZh ? t`重置赛道核对？` : t`Reset course review?`
                : isZh ? t`删除越野目标？` : t`Delete Trail goal?`}
            </DialogTitle>
            <DialogDescription className="break-words leading-6">
              {dialog === 'reset'
                ? isZh
                  ? t`重置会把当前可编辑回答改为未知；不会删除来源活动或已保留的提案记录。`
                  : t`Reset replaces the current editable answers with unknowns. It does not erase source activities or retained proposal records.`
                : isZh
                  ? t`删除越野目标不同于删除账号。系统会请求移除该目标拥有的草稿、快照、提案、审计、索引和缓存；只有服务端确认的结果才会显示为完成。`
                  : t`Deleting the Trail goal is different from deleting your account. This requests removal of its owned draft, snapshots, proposals, audits, indexes, and caches; only the server-confirmed result will be reported as complete.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" className="min-h-11" onClick={() => setDialog(null)}>
              {isZh ? t`取消` : t`Cancel`}
            </Button>
            <Button
              type="button"
              variant={dialog === 'delete' ? 'destructive' : 'outline'}
              className="min-h-11"
              disabled={busy || dialog === null}
              onClick={() => { if (dialog) void mutate(dialog); }}
            >
              {busy
                ? isZh ? t`正在处理…` : t`Working…`
                : dialog === 'reset'
                  ? isZh ? t`确认重置` : t`Confirm reset`
                  : isZh ? t`确认删除` : t`Confirm deletion`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
