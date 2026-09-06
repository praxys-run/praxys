import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useLocale } from "@/contexts/LocaleContext";
import { TERMS_VERSION, EFFECTIVE_DATE } from "@/lib/legal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  apiFetch,
  extractErrorMessage,
  getAuthHeaders,
} from "@/hooks/useApi";
import type { ConnectionsResponse, PlatformName } from "@/types/api";

const PLATFORM_LABELS: Record<PlatformName, string> = {
  garmin: "Garmin",
  strava: "Strava",
  stryd: "Stryd",
  oura: "Oura",
  coros: "COROS",
};

const TERMS_GATE_TITLE_ID = "terms-gate-title";
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function visibleFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((element) => (
    element.getAttribute('aria-hidden') !== 'true'
    && element.getClientRects().length > 0
  ));
}

function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform as PlatformName] ?? platform;
}

/**
 * Blocking Terms acceptance modal shown when the signed-in user's accepted
 * Terms/EULA version is stale (or null). The checkbox separately states Terms
 * acceptance and acknowledgement that the Privacy Policy was read. The app
 * stays gated until the live TERMS_VERSION is recorded via
 * POST /api/me/accept-terms.
 *
 * The modal follows the app locale (set globally from the user's saved language
 * preference / browser detection). It deliberately has no own language toggle:
 * LocaleSync owns the authed-area locale and would immediately revert a
 * local-only switch back to config.language. Readers who want the other
 * language can open the full Terms / Privacy pages, which carry their own toggle.
 */
export default function TermsGate() {
  const { acceptTerms, isDemo, logout, termsAcceptanceStatus } = useAuth();
  const { locale } = useLocale();
  const navigate = useNavigate();
  const zh = locale === "zh";
  const [agreed, setAgreed] = useState(false);
  const [rightsBusy, setRightsBusy] = useState<"export" | "delete" | null>(null);
  const [rightsMessage, setRightsMessage] = useState<string | null>(null);
  const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>([]);
  const [connectionsLoading, setConnectionsLoading] = useState(!isDemo);
  const [disconnectingPlatform, setDisconnectingPlatform] = useState<string | null>(null);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const fallbackAlertRef = useRef<HTMLParagraphElement>(null);
  const fallbackFocusedRef = useRef(false);

  const staleBundle = termsAcceptanceStatus === "updating"
    || termsAcceptanceStatus === "reloading"
    || termsAcceptanceStatus === "fallback";
  const acceptanceBusy = termsAcceptanceStatus === "submitting"
    || termsAcceptanceStatus === "accepted"
    || termsAcceptanceStatus === "updating"
    || termsAcceptanceStatus === "reloading";
  const progressMessage = termsAcceptanceStatus === "submitting"
    ? (zh ? "正在保存条款选择…" : "Saving your Terms choice…")
    : termsAcceptanceStatus === "updating"
      ? (zh ? "检测到新版条款，正在安全更新页面…" : "A newer Terms bundle is available. Updating this page safely…")
      : termsAcceptanceStatus === "reloading"
        ? (zh ? "更新已就绪，正在载入当前条款…" : "Update ready. Reloading the current Terms…")
        : null;
  const acceptanceError = termsAcceptanceStatus === "fallback"
    ? (zh ? "此页面版本已过期，且无法自动更新。请刷新页面，然后阅读并接受当前条款。" : "This page is out of date and could not update automatically. Refresh this page, then review and accept the current Terms.")
    : termsAcceptanceStatus === "submit_error"
      ? (zh ? "无法保存，请重试。" : "Could not save — please try again.")
      : null;

  useEffect(() => {
    if (
      termsAcceptanceStatus !== "fallback"
      || fallbackFocusedRef.current
      || !fallbackAlertRef.current
    ) {
      return;
    }
    fallbackAlertRef.current.focus({ preventScroll: true });
    fallbackFocusedRef.current = true;
  }, [termsAcceptanceStatus]);

  useEffect(() => {
    if (isDemo) {
      setConnectionsLoading(false);
      return;
    }

    let active = true;
    void apiFetch('/api/settings/connections', {
      headers: getAuthHeaders(),
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            await extractErrorMessage(
              response,
              zh ? "无法读取已连接平台。" : "Could not load connected platforms.",
            ),
          );
        }
        return response.json() as Promise<ConnectionsResponse>;
      })
      .then((data) => {
        if (!active) return;
        const platforms = Object.entries(data.connections)
          .filter(([, connection]) => (
            connection.has_credentials
            || (
              connection.status !== null
              && connection.status !== "disconnected"
            )
          ))
          .map(([platform]) => platform);
        setConnectedPlatforms(platforms);
      })
      .catch((connectionError: unknown) => {
        if (!active) return;
        setRightsMessage(
          connectionError instanceof Error
            ? connectionError.message
            : (zh ? "无法读取已连接平台。" : "Could not load connected platforms."),
        );
      })
      .finally(() => {
        if (active) setConnectionsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isDemo, zh]);

  const handleAccept = async () => {
    if (!agreed) return;
    await acceptTerms(() => setAgreed(false));
    // On success the gate unmounts as termsCurrent flips true.
  };

  const handleExport = async () => {
    setRightsBusy("export");
    setRightsMessage(null);
    try {
      const response = await apiFetch('/api/me/export', {
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            zh ? "无法导出数据。" : "Could not export data.",
          ),
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "praxys-data-export.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setRightsMessage(zh ? "数据导出已开始下载。" : "Your data export is downloading.");
    } catch (exportError) {
      setRightsMessage(
        exportError instanceof Error
          ? exportError.message
          : (zh ? "无法导出数据。" : "Could not export data."),
      );
    } finally {
      setRightsBusy(null);
    }
  };

  const handleDelete = async () => {
    if (deleteConfirm !== "DELETE") return;
    setRightsBusy("delete");
    setRightsMessage(null);
    try {
      const response = await apiFetch('/api/me', {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            zh ? "无法删除账号。" : "Could not delete account.",
          ),
        );
      }
      logout();
      navigate("/login", { replace: true });
    } catch (deleteError) {
      setRightsMessage(
        deleteError instanceof Error
          ? deleteError.message
          : (zh ? "无法删除账号。" : "Could not delete account."),
      );
      setRightsBusy(null);
    }
  };

  const handleDisconnect = async (platform: string) => {
    setDisconnectingPlatform(platform);
    setRightsMessage(null);
    try {
      const response = await apiFetch(
        `/api/settings/connections/${encodeURIComponent(platform)}`,
        {
        method: "DELETE",
        headers: getAuthHeaders(),
        },
      );
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            zh ? "无法断开该平台。" : "Could not disconnect this platform.",
          ),
        );
      }
      setConnectedPlatforms((current) => current.filter((item) => item !== platform));
    } catch (disconnectError) {
      setRightsMessage(
        disconnectError instanceof Error
          ? disconnectError.message
          : (zh ? "无法断开该平台。" : "Could not disconnect this platform."),
      );
    } finally {
      setDisconnectingPlatform(null);
    }
  };

  const handleSignOut = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const handleDialogKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab" || event.altKey || event.ctrlKey || event.metaKey) {
      return;
    }
    const focusable = visibleFocusableElements(event.currentTarget);
    if (focusable.length === 0) {
      event.preventDefault();
      document.getElementById(TERMS_GATE_TITLE_ID)?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    const title = document.getElementById(TERMS_GATE_TITLE_ID);
    if (event.shiftKey && (active === first || active === title)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || active === title)) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <Dialog open modal>
      <DialogContent
        showCloseButton={false}
        initialFocus={() => document.getElementById(TERMS_GATE_TITLE_ID)}
        onKeyDownCapture={handleDialogKeyDown}
        className="max-h-[calc(100vh-2rem)] max-w-lg gap-0 overflow-y-auto rounded-lg border border-border bg-card p-6 shadow-lg sm:max-w-lg"
      >
        <DialogTitle
          id={TERMS_GATE_TITLE_ID}
          tabIndex={-1}
          className="text-lg leading-normal font-semibold outline-none"
        >
          {zh ? "条款与隐私告知已更新" : "Updated Terms and Privacy notice"}
        </DialogTitle>
        <p className="mt-1 text-sm text-muted-foreground font-data">
          v{TERMS_VERSION} · {zh ? "生效日期 " : "Effective "}{EFFECTIVE_DATE}
        </p>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          {zh
            ? "服务条款已经更新。隐私政策区分 Azure 核心托管与 Azure AI 处理，并说明已列明的普通 AI 用途、数据最小化、中断状态及权利渠道。普通服务不另设 AI 退出选项。继续前，请阅读服务条款和隐私告知。"
            : "The Terms of Service have been updated. The Privacy Policy distinguishes Azure core hosting from Azure AI processing and explains the enumerated ordinary AI purposes, minimization, outage behavior, and rights channels. Ordinary service has no separate AI opt-out. Review the Terms and Privacy notice before continuing."}
        </p>

        <label className="mt-5 flex min-h-11 items-start gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={!staleBundle && agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            disabled={acceptanceBusy || termsAcceptanceStatus === "fallback"}
            className="mt-3 size-5 flex-none accent-primary"
          />
          <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1 leading-relaxed">
            <span>{zh ? "我接受" : "I accept the"}</span>
            <Link
              to="/terms"
              target="_blank"
              className="inline-flex min-h-11 min-w-11 items-center rounded-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {zh ? "服务条款" : "Terms of Service"}
            </Link>
            <span>{zh ? "，并确认已阅读" : "and acknowledge that I have read the"}</span>
            <Link
              to="/privacy"
              target="_blank"
              className="inline-flex min-h-11 min-w-11 items-center rounded-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {zh ? "隐私政策" : "Privacy Policy"}
            </Link>
            <span>{zh ? "。" : "."}</span>
          </span>
        </label>

        {progressMessage && (
          <p
            className="mt-3 text-sm text-muted-foreground"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            {progressMessage}
          </p>
        )}

        {acceptanceError && (
          <p
            ref={termsAcceptanceStatus === "fallback" ? fallbackAlertRef : undefined}
            tabIndex={termsAcceptanceStatus === "fallback" ? -1 : undefined}
            className="mt-3 text-sm text-destructive outline-none"
            role="alert"
            aria-atomic="true"
          >
            {acceptanceError}
          </p>
        )}

        <Button
          onClick={termsAcceptanceStatus === "fallback"
            ? () => window.location.reload()
            : handleAccept}
          disabled={termsAcceptanceStatus === "fallback"
            ? false
            : !agreed || acceptanceBusy}
          className="mt-6 min-h-11 w-full"
        >
          {termsAcceptanceStatus === "fallback"
            ? (zh ? "刷新此页面" : "Refresh this page")
            : acceptanceBusy
              ? (termsAcceptanceStatus === "updating"
                ? (zh ? "正在更新…" : "Updating…")
                : termsAcceptanceStatus === "reloading"
                  ? (zh ? "正在重新载入…" : "Reloading…")
                  : (zh ? "保存中…" : "Saving…"))
              : (zh ? "接受条款并继续" : "Accept Terms and continue")}
        </Button>

        <div className="mt-6 border-t border-border pt-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {isDemo
              ? (zh
                ? "即使暂不接受，也可以退出登录。"
                : "You can still sign out without accepting.")
              : (zh
                ? "即使暂不接受，也可以导出数据、管理已连接平台、删除账号或退出登录。"
                : "You can still export your data, manage connected platforms, delete your account, or sign out without accepting.")}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            {!isDemo && (
              <>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-11 min-w-11 px-1 text-muted-foreground"
                  disabled={rightsBusy !== null || disconnectingPlatform !== null}
                  onClick={handleExport}
                >
                  {rightsBusy === "export"
                    ? (zh ? "正在导出…" : "Exporting…")
                    : (zh ? "导出我的数据" : "Export my data")}
                </Button>
                <span aria-hidden="true" className="text-border">·</span>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-11 min-w-11 px-1 text-destructive"
                  disabled={rightsBusy !== null || disconnectingPlatform !== null}
                  onClick={() => setShowDelete(true)}
                >
                  {zh ? "删除账号" : "Delete account"}
                </Button>
                <span aria-hidden="true" className="text-border">·</span>
              </>
            )}
            <Button
              type="button"
              variant="link"
              size="sm"
              className="h-11 min-w-11 px-1 text-muted-foreground"
              disabled={rightsBusy !== null || disconnectingPlatform !== null}
              onClick={handleSignOut}
            >
              {zh ? "退出登录" : "Sign out"}
            </Button>
          </div>

          {!isDemo && (connectionsLoading || connectedPlatforms.length > 0) && (
            <div className="mt-3 border-t border-border pt-3">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                {zh ? "已连接平台" : "Connected platforms"}
              </p>
              {connectionsLoading ? (
                <p className="mt-2 text-sm text-muted-foreground" role="status">
                  {zh ? "正在读取…" : "Loading…"}
                </p>
              ) : (
                <div className="mt-1 divide-y divide-border">
                  {connectedPlatforms.map((platform) => (
                    <div key={platform} className="flex min-h-11 items-center justify-between gap-3">
                      <span className="text-sm text-foreground">
                        {platformLabel(platform)}
                      </span>
                      <Button
                        type="button"
                        variant="link"
                        size="sm"
                        className="h-11 min-w-11 px-1 text-muted-foreground"
                        disabled={rightsBusy !== null || disconnectingPlatform !== null}
                        onClick={() => void handleDisconnect(platform)}
                      >
                        {disconnectingPlatform === platform
                          ? (zh ? "正在断开…" : "Disconnecting…")
                          : (zh ? "断开" : "Disconnect")}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!isDemo && showDelete && (
            <div className="mt-3 border-t border-border pt-3">
              <p className="text-sm text-muted-foreground">
                {zh
                  ? "此操作会永久删除账号和训练数据。输入 DELETE 以确认。"
                  : "This permanently deletes your account and training data. Type DELETE to confirm."}
              </p>
              <Input
                value={deleteConfirm}
                onChange={(event) => setDeleteConfirm(event.target.value)}
                placeholder="DELETE"
                aria-label={zh ? "输入 DELETE 以确认删除账号" : "Type DELETE to confirm account deletion"}
                disabled={rightsBusy !== null}
                className="mt-3 min-h-11"
              />
              <div className="mt-3 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="min-h-11 min-w-11"
                  disabled={rightsBusy !== null}
                  onClick={() => {
                    setShowDelete(false);
                    setDeleteConfirm("");
                  }}
                >
                  {zh ? "取消" : "Cancel"}
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  className="min-h-11 min-w-11"
                  disabled={deleteConfirm !== "DELETE" || rightsBusy !== null}
                  onClick={handleDelete}
                >
                  {rightsBusy === "delete"
                    ? (zh ? "正在删除…" : "Deleting…")
                    : (zh ? "永久删除账号" : "Delete permanently")}
                </Button>
              </div>
            </div>
          )}

          {rightsMessage && (
            <p
              className="mt-3 text-sm text-muted-foreground"
              role="status"
              aria-live="polite"
            >
              {rightsMessage}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
