export type RestoredSessionDisposition =
  | "authenticated"
  | "invalid"
  | "transient-failure";

export interface RestoredSessionDecision {
  disposition: RestoredSessionDisposition;
  token: string | null;
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
