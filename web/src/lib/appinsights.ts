/**
 * Azure Application Insights + web-vitals wiring. No-op when
 * VITE_APPINSIGHTS_CONNECTION_STRING is not set at build time, so local and
 * uninstrumented previews remain no-ops. Regional builds may use the same
 * minimized first-party telemetry boundary as the international frontend.
 *
 * What gets captured when enabled:
 *   - Auto page views + SPA route changes (enableAutoRouteTracking)
 *   - Uncaught exceptions
 *   - fetch / XHR dependencies — each API call gets its own timing span
 *     correlated to the server-side OTel trace via CORS correlation
 *     headers (server wiring lives in api/main.py)
 *   - Core Web Vitals (LCP, FCP, INP, CLS, TTFB) as custom metrics
 *
 * Every telemetry item is enriched with the current navigator.connection
 * snapshot so we can segment by effectiveType (4g / 3g / slow-2g) and
 * compare mainland-China-mobile reality against everyone else.
 *
 * Why a connection string and not managed identity: browsers are not
 * Azure workloads — there is no managed identity flow available to
 * client-side code. Microsoft's intended pattern for browser telemetry
 * is a build-time-embedded connection string, which acts as a write-
 * only ingestion token (rate-limited by resource quota; unable to read
 * anything back). The backend (api/main.py) uses managed identity.
 */
import { ApplicationInsights, type ITelemetryItem } from '@microsoft/applicationinsights-web'
import { onCLS, onFCP, onINP, onLCP, onTTFB, type Metric } from 'web-vitals'

import { isAppInsightsAllowed, isChinaFrontendDeployment } from './runtime-region'
import { hasAcknowledgedChinaProcessingNotice } from './china-processing'

const CONNECTION_STRING = import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING ?? ''
const REGIONAL_URL_FIELD = /(?:url|uri|referrer|target)/i

type NetworkConnection = {
  effectiveType?: string
  downlink?: number
  rtt?: number
  saveData?: boolean
}

let appInsights: ApplicationInsights | null = null

export function initAppInsights(): ApplicationInsights | null {
  if (!isAppInsightsAllowed(Boolean(CONNECTION_STRING))) return null
  if (
    isChinaFrontendDeployment()
    && !hasAcknowledgedChinaProcessingNotice()
  ) return null
  if (appInsights) return appInsights
  const chinaDeployment = isChinaFrontendDeployment()

  appInsights = new ApplicationInsights({
    config: {
      connectionString: CONNECTION_STRING,
      enableAutoRouteTracking: true,
      enableCorsCorrelation: true,
      disableFetchTracking: false,
      disableAjaxTracking: false,
      // Exception messages and stacks can contain application values. Keep
      // the China browser stream to page, dependency, and performance data.
      disableExceptionTracking: chinaDeployment,
      autoTrackPageVisitTime: true,
    },
  })
  appInsights.loadAppInsights()
  appInsights.addTelemetryInitializer(sanitizeRegionalTelemetry)
  appInsights.addTelemetryInitializer(attachNetworkContext)
  appInsights.trackPageView()
  reportWebVitals()

  return appInsights
}

function stripQueryAndFragment(value: unknown): unknown {
  if (typeof value !== 'string') return value
  return value.replace(/[?#].*$/, '')
}

/** Remove URL parameters before a regional browser envelope leaves Praxys. */
function sanitizeRegionalTelemetry(envelope: ITelemetryItem): void {
  if (!isChinaFrontendDeployment()) return
  const baseData = envelope.baseData as Record<string, unknown> | undefined
  if (!baseData) return
  for (const key of ['uri', 'url', 'data', 'target', 'refUri', 'referrerUri']) {
    if (key in baseData) baseData[key] = stripQueryAndFragment(baseData[key])
  }
  const properties = baseData.properties
  if (!properties || typeof properties !== 'object') return
  for (const [key, value] of Object.entries(properties)) {
    if (REGIONAL_URL_FIELD.test(key)) {
      (properties as Record<string, unknown>)[key] = stripQueryAndFragment(value)
    }
  }
}

export function getAppInsights(): ApplicationInsights | null {
  return appInsights
}

/**
 * Tie all subsequent telemetry to a stable per-user pseudonym so registered-user
 * DAU/WAU is derivable via `summarize dcount(user_AuthenticatedId)`.
 *
 * The raw user id (a UUID) is NEVER sent: we hash it to 16 hex chars, matching
 * the backend's api/telemetry.py::hash_user_id, so (a) telemetry stays free of
 * PII and (b) frontend pageViews and backend custom events share the same
 * user_AuthenticatedId and correlate. No-op when App Insights is unconfigured
 * (local dev) or Web Crypto is unavailable — telemetry must never break auth.
 */
export async function setAppInsightsUser(userId: string): Promise<void> {
  const ai = getAppInsights()
  if (!ai || !userId) return
  try {
    const hashed = await hashUserId(userId)
    // authenticatedUserId must exclude spaces/commas/semicolons/pipes/equals —
    // hex satisfies that. storeInCookie=true keeps it stable across reloads.
    ai.setAuthenticatedUserContext(hashed, undefined, true)
  } catch {
    /* best-effort; never throw from a telemetry helper */
  }
}

export function clearAppInsightsUser(): void {
  try {
    getAppInsights()?.clearAuthenticatedUserContext()
  } catch {
    /* best-effort */
  }
}

async function hashUserId(userId: string): Promise<string> {
  // SHA-256, first 16 hex chars — mirrors api/telemetry.py::hash_user_id.
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(userId))
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 16)
}

function getNetworkSnapshot(): NetworkConnection | null {
  const conn = (navigator as unknown as { connection?: NetworkConnection }).connection
  return conn ?? null
}

function attachNetworkContext(envelope: ITelemetryItem): void {
  const conn = getNetworkSnapshot()
  if (!conn) return
  // Prefix with netinfo_ so we don't shadow any field the SDK populates
  // on its own envelopes (e.g. dependency spans spread into baseData.
  // properties). Same prefix on trackMetric below keeps App Insights
  // queries consistent — filter on netinfo_effectiveType everywhere.
  const baseData = (envelope.baseData ??= {})
  baseData.properties = {
    ...(baseData.properties ?? {}),
    netinfo_effectiveType: conn.effectiveType,
    netinfo_downlink: conn.downlink,
    netinfo_rtt: conn.rtt,
    netinfo_saveData: conn.saveData,
  }
}

function reportWebVitals(): void {
  if (!appInsights) return
  const send = (metric: Metric): void => {
    const conn = getNetworkSnapshot() ?? {}
    appInsights!.trackMetric(
      { name: `WebVitals.${metric.name}`, average: metric.value },
      {
        rating: metric.rating,
        navigationType: metric.navigationType,
        id: metric.id,
        netinfo_effectiveType: conn.effectiveType,
        netinfo_downlink: conn.downlink,
        netinfo_rtt: conn.rtt,
      },
    )
  }
  onCLS(send)
  onFCP(send)
  onINP(send)
  onLCP(send)
  onTTFB(send)
}
