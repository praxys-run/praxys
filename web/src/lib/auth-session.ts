import { removeRecentFeedbackId } from './feedback.ts';
import { KEYS, removeCompatItem } from './storage-compat.ts';

export type RestoredSessionDisposition =
  | "authenticated"
  | "invalid"
  | "transient-failure";

export interface RestoredSessionDecision {
  disposition: RestoredSessionDisposition;
  token: string | null;
}

type UnauthorizedRedirect = () => void;

function hardRedirectToLogin(): void {
  window.location.href = '/login';
}

/** Clear client-owned session locators before following the caller's redirect. */
export function handleUnauthorizedSession(
  redirect: UnauthorizedRedirect = hardRedirectToLogin,
): void {
  removeRecentFeedbackId();
  removeCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
  redirect();
}

/** Classify auth restoration without deleting credentials on retryable failures. */
export function classifyRestoredSession(
  status: number,
  hasProfile: boolean,
): RestoredSessionDisposition {
  if (status === 401) return "invalid";
  if (status === 200 && hasProfile) return "authenticated";
  return "transient-failure";
}

/** Keep a stored credential unless the server authoritatively rejects it. */
export function resolveRestoredSession(
  storedToken: string,
  status: number,
  hasProfile: boolean,
): RestoredSessionDecision {
  const disposition = classifyRestoredSession(status, hasProfile);
  return {
    disposition,
    token: disposition === "invalid" ? null : storedToken,
  };
}
