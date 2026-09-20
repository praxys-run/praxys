import './index.css'
import './pages/Landing.css'
import { resolvePublicRoute } from './lib/public-route'
import { isChinaFrontendDeployment } from './lib/runtime-region'
import {
  CHINA_PROCESSING_NOTICE_ACKNOWLEDGED_EVENT,
} from './lib/china-processing'
import { registerSW } from 'virtual:pwa-register'
import {
  PRELOAD_RELOAD_KEY,
  PRELOAD_RELOAD_WINDOW_MS,
  isActivePreloadReload,
  parsePreloadReloadMarker,
  type PreloadReloadMarker,
} from './lib/preload-recovery'

function initAppInsights() {
  void import('./lib/appinsights').then((telemetry) => telemetry.initAppInsights())
}

// Start telemetry independently of rendering. The SDK retains its regional
// consent checks and is a no-op when the public connection string is unset.
initAppInsights()
window.addEventListener(
  CHINA_PROCESSING_NOTICE_ACKNOWLEDGED_EVENT,
  initAppInsights,
)

// Register the service worker that vite-plugin-pwa generated. `immediate:
// true` activates the new SW as soon as it's installed, so a freshly-
// deployed version takes effect on the next navigation instead of after
// every open tab closes. onNeedRefresh / onOfflineReady are left as the
// default no-ops — we auto-update silently and don't prompt the user
// (matches registerType: 'autoUpdate' in vite.config.ts).
const publicRoute = resolvePublicRoute(window.location.pathname, isChinaFrontendDeployment())
// New marketing visitors do not need the offline application precache. Existing
// installations still check for updates; app entry keeps the complete offline cache.
if (!publicRoute || navigator.serviceWorker?.controller) registerSW({ immediate: true })

function preloadReloadMarker(): PreloadReloadMarker | null {
  const raw = sessionStorage.getItem(PRELOAD_RELOAD_KEY)
  const marker = parsePreloadReloadMarker(raw)
  if (raw && !marker) sessionStorage.removeItem(PRELOAD_RELOAD_KEY)
  return marker
}

// A deploy can replace a lazily loaded route chunk while an older app shell is
// still open. Reload once so Vite resolves the new manifest. If the same chunk
// still fails during the recovery window, let the Labs route error boundary
// render an explicit retry state instead of reloading Safari indefinitely.
window.addEventListener('vite:preloadError', (event) => {
  const now = Date.now()
  const marker = preloadReloadMarker()
  if (isActivePreloadReload(marker, window.location.pathname, now)) {
    return
  }

  event.preventDefault()
  sessionStorage.setItem(PRELOAD_RELOAD_KEY, JSON.stringify({
    pathname: window.location.pathname,
    attemptedAt: now,
  } satisfies PreloadReloadMarker))
  window.location.reload()
})

window.addEventListener('load', () => {
  const marker = preloadReloadMarker()
  if (!marker || marker.pathname !== window.location.pathname) return
  const remaining = Math.max(
    0,
    PRELOAD_RELOAD_WINDOW_MS - (Date.now() - marker.attemptedAt),
  )
  window.setTimeout(() => {
    const current = preloadReloadMarker()
    if (
      current?.pathname === marker.pathname
      && current.attemptedAt === marker.attemptedAt
    ) {
      sessionStorage.removeItem(PRELOAD_RELOAD_KEY)
    }
  }, remaining)
}, { once: true })

const root = document.getElementById('root')!
function showBootFailure() {
  const zh = document.documentElement.lang.startsWith('zh')
  const notice = document.createElement('div')
  notice.className = 'boot-error'
  notice.setAttribute('role', 'alert')
  const message = document.createElement('p')
  message.textContent = zh ? '页面未能加载完成，请刷新重试。' : 'The page could not finish loading. Please refresh to try again.'
  const retry = document.createElement('button')
  retry.type = 'button'
  retry.className = 'landing-btn-primary'
  retry.textContent = zh ? '重新加载' : 'Reload page'
  retry.addEventListener('click', () => window.location.reload())
  notice.append(message, retry)
  root.prepend(notice)
  root.querySelector('[aria-busy]')?.setAttribute('aria-busy', 'false')
}
if (publicRoute) {
  void import('./public-main').then(({ mountPublic }) => mountPublic(root, publicRoute)).catch(showBootFailure)
} else {
  void import('./app-main').then(({ mountApp }) => mountApp(root)).catch(showBootFailure)
}
