import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { LocaleContext } from './contexts/locale-context';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { KEYS, setCompatItem } from './lib/storage-compat';
import { resolvePublicRoute, type PublicRoute } from './lib/public-route';
import type { SupportedLocale } from './i18n/init';
import Landing from './pages/Landing';
import PublicInfo from './pages/PublicInfo';
import AppLoadingShell from './components/AppLoadingShell';
import ChinaComplianceVisibility from './components/ChinaComplianceVisibility';

/** Public copy is already bilingual; it does not need the application catalog. */
function PublicLocaleProvider({ initialLocale, children }: { initialLocale: SupportedLocale; children: ReactNode }) {
  const [locale, setValue] = useState(initialLocale);
  const { pathname } = useLocation();
  useEffect(() => {
    const path = pathname.replace(/\/+$/, '') || '/';
    const explicit = path === '/en' ? 'en' : path.startsWith('/zh') ? 'zh' : null;
    if (explicit) setCompatItem(KEYS.locale.new, KEYS.locale.legacy, explicit);
  }, [pathname]);
  const setLocale = useCallback(async (next: SupportedLocale) => {
    setValue(next);
    setCompatItem(KEYS.locale.new, KEYS.locale.legacy, next);
  }, []);
  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

function PublicRoutes({ china }: { china: boolean }) {
  const location = useLocation();
  const route = resolvePublicRoute(location.pathname, china);
  const publicPage = route !== null;
  const { isAuthenticated, isDemo, isLoading } = useAuth();
  useEffect(() => {
    if (!publicPage) {
      // Cross into the application through its dedicated static loading shell.
      window.location.reload();
    } else if (location.pathname === '/' && !isLoading && isAuthenticated && !isDemo) {
      window.location.replace('/today');
    }
  }, [publicPage, location.pathname, isAuthenticated, isDemo, isLoading]);
  if (!route) return <AppLoadingShell />;
  return route.page === 'home'
    ? <Landing publicLocale={route.locale} />
    : <PublicInfo locale={route.locale} pageKey={route.page} />;
}

export function PublicSite({ initialRoute, china = false }: { initialRoute: PublicRoute; china?: boolean }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 120000, refetchOnWindowFocus: false } } }));
  return (
    <QueryClientProvider client={client}>
      <PublicLocaleProvider initialLocale={initialRoute.locale}>
        <AuthProvider>
          <PublicRoutes china={china} />
          <ChinaComplianceVisibility />
        </AuthProvider>
      </PublicLocaleProvider>
    </QueryClientProvider>
  );
}
