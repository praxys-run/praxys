import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nProvider } from '@lingui/react'
import App from './App'
import { i18n, activateLocale, DEFAULT_LOCALE, isSupportedLocale, type SupportedLocale } from './i18n/init'
import { detectLocaleFromTag } from './lib/locale-detect'
import { KEYS, getCompatItem } from './lib/storage-compat'
import { isChinaFrontendDeployment } from './lib/runtime-region'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,
      gcTime: 5 * 60 * 1000,
      retry: 2,
      // Disabled because CN users on spotty mobile network were burning
      // seconds of round-trips every time they tabbed back from WeChat
      // or another app. Stale data is refetched lazily via staleTime
      // expiration + manual refetch() calls already wired where it matters
      // (sync status polling, etc.). Leaving this on made the app feel
      // like it "reloaded for no reason" after an app switch.
      refetchOnWindowFocus: false,
    },
  },
})

// Pick the locale for first paint the same way LocaleProvider will, so
// returning zh users never see an EN flash before their stored preference
// kicks in. localStorage is authoritative; then navigator.language; then
// DEFAULT_LOCALE. The server-preference case (user changed language on
// another device) still falls back to LocaleSync after settings load —
// that's an unavoidable round-trip.
function _initialLocale(): SupportedLocale {
  const stored = getCompatItem(KEYS.locale.new, KEYS.locale.legacy)
  if (isSupportedLocale(stored)) return stored
  if (isChinaFrontendDeployment()) return 'zh'
  if (typeof navigator !== 'undefined') {
    return detectLocaleFromTag(navigator.language)
  }
  return DEFAULT_LOCALE
}

export async function mountApp(root: HTMLElement) {
await activateLocale(_initialLocale())

createRoot(root).render(
  <StrictMode>
    <I18nProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </I18nProvider>
  </StrictMode>,
)

}
