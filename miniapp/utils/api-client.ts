/**
 * Tiny HTTP client over wx.request. Adds JWT injection, JSON serialization,
 * and a 401 → relaunch-to-login redirect so dead tokens don't loop pages
 * into a fetch-401-fetch cycle.
 *
 * API_BASE points at production by default so real-device preview works
 * without LAN debug bridge gymnastics. To run against a local backend,
 * swap to `http://localhost:8000` (or your laptop's LAN IP for real-device
 * over WiFi) and uvicorn must accept that origin.
 *
 * WeChat must whitelist the host in production via mp.weixin.qq.com → 开发
 * → 开发设置 → 服务器域名 (request合法域名). The simulator + DevTools can
 * bypass this via 详情 → 本地设置 → 不校验合法域名.
 */

import {
  CHINA_PROCESSING_NOTICE_VERSION,
  hasAcknowledgedChinaProcessingNotice,
} from './china-processing';
import {
  MINIAPP_BUILD_VERSION,
  MINIAPP_SOURCE_SHA,
} from './version';
import { TERMS_CONTENT_DIGEST } from './legal';

export const API_BASE: string = 'https://api.praxys.run';

export const TOKEN_KEY = 'praxys-auth-token';
export const CN_PRIVACY_CONTRACT_VERSION = 'cn-privacy-v2';

export interface ApiError {
  status: number;
  /** FastAPI's `detail` field if present; otherwise a generic message. */
  detail: string;
  /**
   * Stable machine code for callers that want to react programmatically
   * without parsing the human-readable `detail`. The 401-with-existing-
   * token case sets this to `'UNAUTHENTICATED'` so pages can render a
   * "session expired" toast before the reLaunch unmounts them.
   */
  code?: string;
  /** wx.request errno when status is 0 (network-layer failure). */
  errno?: number;
  /** Structured FastAPI detail payload for typed recovery UI. */
  data?: unknown;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  /**
   * Skip the 401 → login redirect. Set this on the /auth/wechat/login call
   * itself (expected to be unauthenticated) so we don't loop.
   */
  skipAuthRedirect?: boolean;
  /** Bound one request when an unfinished result would block the user. */
  timeoutMs?: number;
}

const LOGIN_PAGE = 'pages/login/index';

function authHeader(): Record<string, string> {
  const token = wx.getStorageSync<string>(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function isOnLoginPage(): boolean {
  // getCurrentPages() returns the in-memory page stack; the top of the
  // stack is the active page. Route strings are stored without a leading
  // slash. The wrapping try/catch covers the "no pages yet" edge case
  // when this runs during the very first onLaunch tick.
  try {
    const pages = getCurrentPages();
    const top = pages[pages.length - 1];
    return top?.route === LOGIN_PAGE;
  } catch {
    return false;
  }
}

function redirectToLogin(): void {
  // Caller is responsible for clearing TOKEN_KEY before calling this so
  // the order matches "session is dead → tell user → navigate". A short
  // toast surfaces *why* the redirect is happening; without it the user
  // just sees the login page reappear with no explanation.
  try {
    wx.showToast({ title: 'Session expired', icon: 'none', duration: 1500 });
  } catch {
    /* showToast is unavailable during onLaunch — silent fallback is fine */
  }
  wx.reLaunch({
    url: `/${LOGIN_PAGE}`,
    fail: () => {
      // wx.reLaunch rejects with "redundant" if we're already on the
      // login page — caller already guards via isOnLoginPage().
    },
  });
}

function redirectToProcessingNotice(): void {
  if (isOnLoginPage()) return;
  wx.reLaunch({
    url: `/${LOGIN_PAGE}`,
    fail: () => {},
  });
}

function clientBoundaryHeaders(): Record<string, string> {
  return {
    'X-Praxys-Client': 'wechat-miniapp',
    'X-Praxys-Client-Version': MINIAPP_BUILD_VERSION || 'develop',
    'X-Praxys-Source-Sha': MINIAPP_SOURCE_SHA || 'develop',
    'X-Praxys-Notice-Version': CHINA_PROCESSING_NOTICE_VERSION,
    'X-Praxys-Policy-Digest': TERMS_CONTENT_DIGEST,
    'X-Praxys-Api-Contract': CN_PRIVACY_CONTRACT_VERSION,
  };
}

// Override wx.request's 60s default — failures should surface quickly
// during dev so you don't wait a full minute when prod is unreachable
// or a host isn't whitelisted.
const REQUEST_TIMEOUT_MS = 30000;

function wxRequest(opts: WechatMiniprogram.RequestOption): Promise<WechatMiniprogram.RequestSuccessCallbackResult> {
  return new Promise((resolve, reject) => {
    wx.request({
      timeout: REQUEST_TIMEOUT_MS,
      ...opts,
      success: (res) => resolve(res),
      fail: (err) => reject(err),
    });
  });
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!hasAcknowledgedChinaProcessingNotice()) {
    redirectToProcessingNotice();
    throw {
      status: 0,
      detail: 'PROCESSING_NOTICE_REQUIRED',
      code: 'PROCESSING_NOTICE_REQUIRED',
    } as ApiError;
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;
  let response: WechatMiniprogram.RequestSuccessCallbackResult;
  try {
    response = await wxRequest({
      url,
      timeout: options.timeoutMs ?? REQUEST_TIMEOUT_MS,
      method: (options.method ?? 'GET') as WechatMiniprogram.RequestOption['method'],
      data: options.body as WechatMiniprogram.RequestOption['data'],
      header: {
        'Content-Type': 'application/json',
        ...clientBoundaryHeaders(),
        ...authHeader(),
        ...options.headers,
      },
    });
  } catch (e) {
    // wx.request fail callbacks deliver `{ errMsg: "request:fail ...", errno }`
    // — translate to our ApiError shape so the page error UI shows
    // something meaningful instead of "[object Object]". errno is
    // surfaced separately so callers can distinguish offline (~600003) from
    // timeout (-202) without parsing the message string.
    const errMsg =
      (e as { errMsg?: string })?.errMsg ?? (e instanceof Error ? e.message : String(e));
    const errno = (e as { errno?: number })?.errno;
    const code: ApiError['code'] = /timeout/i.test(errMsg)
      ? 'TIMEOUT'
      : /fail|abort|offline/i.test(errMsg)
        ? 'OFFLINE'
        : 'NETWORK';
    throw { status: 0, detail: errMsg, code, errno } as ApiError;
  }

  const status = response.statusCode;
  const rawDetail = (
    response.data as { detail?: unknown } | null | undefined
  )?.detail;
  const code = (
    rawDetail != null
    && typeof rawDetail === 'object'
    && typeof (rawDetail as { code?: unknown }).code === 'string'
  )
    ? (rawDetail as { code: ApiError['code'] }).code
    : undefined;

  if (status === 401 && !options.skipAuthRedirect) {
    // Always clear the dead token and surface a typed `UNAUTHENTICATED`
    // ApiError so callers' `finally`/`catch` branches actually run.
    // Pages catching `code === 'UNAUTHENTICATED'` can show a session-
    // expired toast before the reLaunch unmounts them.
    wx.removeStorageSync(TOKEN_KEY);
    if (!isOnLoginPage()) redirectToLogin();
    throw { status: 401, detail: 'UNAUTHENTICATED', code: 'UNAUTHENTICATED' } as ApiError;
  }
  if (status === 428 && code === 'TERMS_ACCEPTANCE_REQUIRED') {
    redirectToProcessingNotice();
    throw {
      status,
      detail: 'TERMS_ACCEPTANCE_REQUIRED',
      code,
      data: rawDetail,
    } as ApiError;
  }

  if (status >= 200 && status < 300) {
    return response.data as T;
  }

  const detail =
    typeof rawDetail === 'string'
      ? rawDetail
      : (
          rawDetail != null
          && typeof rawDetail === 'object'
          && typeof (rawDetail as { message?: unknown }).message === 'string'
        )
        ? (rawDetail as { message: string }).message
      : rawDetail != null
        ? JSON.stringify(rawDetail)
        : `HTTP ${status}`;
  throw { status, detail, code, data: rawDetail } as ApiError;
}

export const apiGet = <T>(
  path: string,
  opts?: Pick<RequestOptions, 'timeoutMs'>,
) => request<T>(path, { ...opts, method: 'GET' });
export const apiPost = <T>(path: string, body?: unknown, opts?: RequestOptions) =>
  request<T>(path, { ...opts, method: 'POST', body });
export const apiPut = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body });
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' });
