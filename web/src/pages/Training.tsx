import { useEffect, useRef } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Trans, useLingui } from '@lingui/react/macro';

import PersonalContextPanel from '@/components/PersonalContextPanel';
import PlanStart, {
  type PlanStartNavigationState,
} from '@/components/PlanStart';
import UpcomingPlanCard from '@/components/UpcomingPlanCard';
import { useSettings } from '@/contexts/SettingsContext';
import { useApi } from '@/hooks/useApi';
import type { PlanGenerationCapabilitiesResponse } from '@/types/api';

export default function Training() {
  const { t } = useLingui();
  const location = useLocation();
  const navigationState = location.state as PlanStartNavigationState | null;
  const planStartAnchor = useRef<HTMLDivElement>(null);
  const focusedLocation = useRef<string | null>(null);
  const { config, loading: settingsLoading } = useSettings();
  const { data: capabilities, loading: capabilitiesLoading } = useApi<PlanGenerationCapabilitiesResponse>(
    '/api/plan/generation/capabilities',
    { timeoutMs: 12_000 },
  );
  const hasManagedPlan = config?.plan_management.mode === 'praxys'
    || capabilities?.active_plan_goal?.lifecycle === 'active';
  useEffect(() => {
    if (
      location.hash !== '#plan-start'
      || focusedLocation.current === location.key
      || settingsLoading
      || capabilitiesLoading
    ) return;
    const frame = requestAnimationFrame(() => {
      const target = planStartAnchor.current;
      if (!target) return;
      target.scrollIntoView({ block: 'start' });
      target.focus({ preventScroll: true });
      focusedLocation.current = location.key;
    });
    return () => cancelAnimationFrame(frame);
  }, [location.hash, location.key, settingsLoading, capabilitiesLoading]);

  const planStart = (
    <div key="plan-start" ref={planStartAnchor} tabIndex={-1} aria-label={t`Training plan`} className="scroll-mt-16 lg:scroll-mt-6">
      <PlanStart initialPurpose={navigationState?.planPurpose ?? null} />
    </div>
  );
  const upcoming = (
    <UpcomingPlanCard
      key="upcoming"
      hasCurrentPlan={hasManagedPlan}
    />
  );

  if (location.hash === '#heat-adaptation') {
    return <Navigate to="/analysis#heat-adaptation" replace />;
  }

  return (
    <div>
      <h1 className="text-[11px] font-data uppercase tracking-[0.14em] text-muted-foreground">
        <Trans>Training</Trans>
      </h1>
      <div className={hasManagedPlan ? 'mt-6 space-y-4' : 'mt-6 space-y-8'}>
        {hasManagedPlan ? [upcoming, planStart] : [planStart, upcoming]}
      </div>

      <PersonalContextPanel />
    </div>
  );
}
