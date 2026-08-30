import { TERMS_VERSION } from "./legal.ts";
import { isChinaFrontendDeployment } from "./runtime-region.ts";

export const CHINA_PROCESSING_NOTICE_VERSION = TERMS_VERSION;
export const CHINA_PROCESSING_NOTICE_STORAGE_KEY =
  "praxys.cn-processing-notice";

const PUBLIC_PATHS = new Set([
  "/",
  "/zh",
  "/product",
  "/faq",
  "/zh/product",
  "/zh/faq",
  "/terms",
  "/privacy",
  "/status",
]);

let acknowledgedForThisPage = false;

interface NoticeStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function browserStorage(): NoticeStorage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function normalizePathname(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "");
}

/** Return whether a route can render without starting personal-data traffic. */
export function isChinaProcessingPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.has(normalizePathname(pathname));
}

/** Return whether the current notice version has been acknowledged locally. */
export function hasAcknowledgedChinaProcessingNotice(
  storage: NoticeStorage | null = browserStorage(),
): boolean {
  if (acknowledgedForThisPage) return true;
  try {
    return (
      storage?.getItem(CHINA_PROCESSING_NOTICE_STORAGE_KEY) ===
      CHINA_PROCESSING_NOTICE_VERSION
    );
  } catch {
    return false;
  }
}

/** Record a pre-transfer read acknowledgement for the current browser. */
export function acknowledgeChinaProcessingNotice(
  storage: NoticeStorage | null = browserStorage(),
): void {
  acknowledgedForThisPage = true;
  try {
    storage?.setItem(
      CHINA_PROCESSING_NOTICE_STORAGE_KEY,
      CHINA_PROCESSING_NOTICE_VERSION,
    );
  } catch {
    // The in-memory receipt still permits this page session. A future visit
    // will show the notice again when persistent storage is unavailable.
  }
}

/** Gate authenticated requests before the current China notice is presented. */
export function canStartPersonalDataRequests(): boolean {
  return (
    !isChinaFrontendDeployment() ||
    hasAcknowledgedChinaProcessingNotice()
  );
}
