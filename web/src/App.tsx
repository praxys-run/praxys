import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useState,
  type ErrorInfo,
  type ReactNode,
} from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Trans } from '@lingui/react/macro';
import { RefreshCw } from 'lucide-react';
import { TooltipProvider } from './components/ui/tooltip';
import { Alert, AlertDescription, AlertTitle } from './components/ui/alert';
import { Button } from './components/ui/button';
import { PRELOAD_RELOAD_KEY } from './lib/preload-recovery';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { SettingsProvider } from './contexts/SettingsContext';
import { ScienceProvider } from './contexts/ScienceContext';
import { LocaleProvider, useLocale } from './contexts/LocaleContext';
import { StatsigProvider } from './contexts/StatsigContext';
import LocaleSync from './contexts/LocaleSync';
import Layout from './components/Layout';
import { Skeleton } from './components/ui/skeleton';
// Eagerly imported: Landing is the anonymous first-impression, Login is
// the auth entry point, Today is where every logged-in user lands. All
// three must be in the initial bundle for fastest cold-load.
import Landing from './pages/Landing';
import PublicInfo from './pages/PublicInfo';
import Login from './pages/Login';
import Today from './pages/Today';
import Setup from './pages/Setup';
import Terms from './pages/Terms';
import Privacy from './pages/Privacy';
import Verify from './pages/Verify';
import Status from './pages/Status';
import { hasSkippedSetupForSession, useSetupStatus } from './hooks/useSetupStatus';
// Lazy-loaded: secondary routes the user navigates to after landing on
// Today. Chunks load on first visit to each route; cached immutably
// thereafter (cache headers set by frontend_server/main.py).
const loadTraining = () => import('./pages/Training');
const Training = lazy(loadTraining);
const Goal = lazy(() => import('./pages/Goal'));
const History = lazy(() => import('./pages/History'));
const Science = lazy(() => import('./pages/Science'));
const Labs = lazy(() => import('./pages/Labs'));
const LabsEnvironment = lazy(() => import('./pages/LabsEnvironment'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const McpAuthorization = lazy(() => import('./pages/McpAuthorization'));
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout'));
const AdminOps = lazy(() => import('./pages/admin/AdminOps'));
const AdminUsers = lazy(() => import('./pages/admin/AdminUsers'));
const AdminFeedback = lazy(() => import('./pages/admin/AdminFeedback'));
const AdminIncidents = lazy(() => import('./pages/admin/AdminIncidents'));
const AdminCommunications = lazy(() => import('./pages/admin/AdminCommunications'));

function AdminChunkSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-6 w-36" />
      <Skeleton className="h-20 rounded-xl" />
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-56 rounded-xl" />
    </div>
  );
}

function RouteChunkSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-4 w-full max-w-2xl" />
      <Skeleton className="h-52 rounded-xl" />
    </div>
  );
}

class LabsRouteBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error('Labs route failed to load', error, info.componentStack);
  }

  private reload = (): void => {
    sessionStorage.removeItem(PRELOAD_RELOAD_KEY);
    window.location.reload();
  };

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <Alert variant="destructive">
        <AlertTitle><Trans>Labs page update required</Trans></AlertTitle>
        <AlertDescription className="mt-2">
          <p>
            <Trans>Praxys could not finish loading this page after an app update. Reload once to use the current version.</Trans>
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={this.reload}
          >
            <RefreshCw className="h-4 w-4" />
            <Trans>Reload Labs</Trans>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }
}

function LabsRoute({ children }: { children: ReactNode }) {
  return (
    <LabsRouteBoundary>
      <Suspense fallback={<RouteChunkSkeleton />}>{children}</Suspense>
    </LabsRouteBoundary>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    // Show nothing while checking auth state to avoid flash.
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <LocaleProvider>
      <AuthProvider>
        <StatsigProvider>
          <TooltipProvider>
            <BrowserRouter>
              <Routes>
              <Route path="/" element={<LandingOrApp />} />
              <Route path="/zh" element={<Landing publicLocale="zh" />} />
              <Route path="/product" element={<PublicInfo locale="en" pageKey="product" />} />
              <Route path="/faq" element={<PublicInfo locale="en" pageKey="faq" />} />
              <Route path="/zh/product" element={<PublicInfo locale="zh" pageKey="product" />} />
              <Route path="/zh/faq" element={<PublicInfo locale="zh" pageKey="faq" />} />
              <Route path="/login" element={<LoginGuard />} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/status" element={<Status />} />
              <Route path="/verify" element={<Verify />} />
              <Route
                path="/mcp/authorize"
                element={
                  <RequireAuth>
                    <Suspense fallback={<RouteChunkSkeleton />}>
                      <McpAuthorization />
                    </Suspense>
                  </RequireAuth>
                }
              />
              <Route
                element={
                  <RequireAuth>
                    <SettingsProvider>
                      <LocaleSync />
                      <ScienceProvider>
                        <Layout />
                      </ScienceProvider>
                    </SettingsProvider>
                  </RequireAuth>
                }
              >
                <Route path="today" element={<TodayOrSetup />} />
                <Route path="setup" element={<Setup />} />
                <Route path="training" element={<Suspense fallback={null}><Training /></Suspense>} />
                <Route path="goal" element={<Suspense fallback={null}><Goal /></Suspense>} />
                <Route path="history" element={<Suspense fallback={null}><History /></Suspense>} />
                <Route path="science" element={<Suspense fallback={null}><Science /></Suspense>} />
                <Route path="labs" element={<LabsRoute><Labs /></LabsRoute>} />
                <Route path="labs/environment-response" element={<LabsRoute><LabsEnvironment /></LabsRoute>} />
                <Route path="settings" element={<Suspense fallback={null}><SettingsPage /></Suspense>} />
                <Route path="admin" element={<Suspense fallback={<AdminChunkSkeleton />}><AdminLayout /></Suspense>}>
                  <Route index element={<Navigate to="ops" replace />} />
                  <Route path="ops" element={<Suspense fallback={<AdminChunkSkeleton />}><AdminOps /></Suspense>} />
                  <Route path="users" element={<Suspense fallback={<AdminChunkSkeleton />}><AdminUsers /></Suspense>} />
                  <Route path="feedback" element={<Suspense fallback={<AdminChunkSkeleton />}><AdminFeedback /></Suspense>} />
                  <Route path="incidents" element={<Suspense fallback={<AdminChunkSkeleton />}><AdminIncidents /></Suspense>} />
                  <Route path="communications" element={<Suspense fallback={<AdminChunkSkeleton />}><AdminCommunications /></Suspense>} />
                </Route>
              </Route>
              </Routes>
            </BrowserRouter>
          </TooltipProvider>
        </StatsigProvider>
      </AuthProvider>
    </LocaleProvider>
  );
}

/** Show Setup page if onboarding incomplete, otherwise Today. */
function TodayOrSetup() {
  const { email } = useAuth();
  const setup = useSetupStatus();
  const [skippedForAccount, setSkippedForAccount] = useState<string | null>(null);
  const accountScope = email?.trim().toLowerCase() ?? '';
  const setupSkipped = skippedForAccount === accountScope || hasSkippedSetupForSession(email);

  useEffect(() => {
    if (setup.loading || (!setup.allDone && !setupSkipped)) return undefined;

    // Keep chart code off Today's critical path, then warm the most common
    // next route after the first screen has had time to settle.
    let idleCallbackId: number | undefined;
    const timer = window.setTimeout(() => {
      if ('requestIdleCallback' in window) {
        idleCallbackId = window.requestIdleCallback(
          () => { void loadTraining(); },
          { timeout: 5000 },
        );
      } else {
        void loadTraining();
      }
    }, 2500);
    return () => {
      window.clearTimeout(timer);
      if (idleCallbackId !== undefined) window.cancelIdleCallback(idleCallbackId);
    };
  }, [setup.allDone, setup.loading, setupSkipped]);

  if (setup.loading) return null;
  if (!setup.allDone && !setupSkipped) {
    return <Setup onSkip={() => setSkippedForAccount(accountScope)} />;
  }
  return <Today />;
}

/** Public landing page for unauthenticated visitors. Real authed users go
 *  straight to the app; **demo** users still see the landing (with a "Continue
 *  to demo" CTA) so they don't get silently trapped in the demo dashboard on
 *  repeat visits to `/`. */
function LandingOrApp() {
  const { isAuthenticated, isDemo, isLoading } = useAuth();
  const { locale } = useLocale();
  const location = useLocation();
  const forceEnglish = new URLSearchParams(location.search).get('lang') === 'en';

  if (isLoading) return null;
  if (isAuthenticated && !isDemo) return <Navigate to="/today" replace />;
  if (locale === 'zh' && !forceEnglish) return <Navigate to="/zh" replace />;
  return <Landing publicLocale="en" />;
}

/** If already authenticated, redirect away from login page. */
function LoginGuard() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return null;

  if (isAuthenticated) return <Navigate to="/today" replace />;

  return <Login />;
}
