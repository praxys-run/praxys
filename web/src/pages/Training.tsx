import { Navigate, useLocation } from 'react-router-dom';
import { Trans } from '@lingui/react/macro';

import Outdoor5KPlanStart from '@/components/Outdoor5KPlanStart';
import PersonalContextPanel from '@/components/PersonalContextPanel';
import UpcomingPlanCard from '@/components/UpcomingPlanCard';

export default function Training() {
  const location = useLocation();

  if (location.hash === '#heat-adaptation') {
    return <Navigate to="/analysis#heat-adaptation" replace />;
  }

  return (
    <div>
      <h1 className="text-[11px] font-data uppercase tracking-[0.14em] text-muted-foreground">
        <Trans>Training</Trans>
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        <Trans>Start, review, and adjust the plan Praxys manages for you.</Trans>
      </p>

      <div className="mt-8 space-y-12">
        <Outdoor5KPlanStart />
        <UpcomingPlanCard />
      </div>

      <PersonalContextPanel />
    </div>
  );
}
