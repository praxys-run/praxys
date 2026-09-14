import { useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { tDisplay } from '@/lib/display-labels';
import { formatProposalDetail } from '@/lib/proposal-display';
import type { AdaptivePlanProposal } from '@/types/api';

interface AdoptedPlanDetailsProps {
  proposal: AdaptivePlanProposal;
  distanceLabel?: string;
  onReviewInputs?: () => void;
}

export default function AdoptedPlanDetails({
  proposal,
  distanceLabel,
  onReviewInputs,
}: AdoptedPlanDetailsProps) {
  const { t, i18n } = useLingui();
  const [open, setOpen] = useState(false);
  const [reviewAfterClose, setReviewAfterClose] = useState(false);

  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      onOpenChangeComplete={(nextOpen) => {
        if (!nextOpen && reviewAfterClose) {
          setReviewAfterClose(false);
          onReviewInputs?.();
        }
      }}
    >
      <DialogTrigger id="plan-start-configure" render={<Button variant="ghost" className="min-h-11" />}>
        <Trans>Plan details</Trans>
      </DialogTrigger>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl" closeLabel={t`Close`}>
        <DialogHeader className="pr-10">
          <DialogTitle><Trans>Plan details</Trans></DialogTitle>
          <DialogDescription>
            <Trans>This is the proposal saved when you adopted it. The calendar shows your current workouts, including later changes.</Trans>
          </DialogDescription>
        </DialogHeader>
        <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
          {distanceLabel && (
            <div>
              <dt className="text-muted-foreground"><Trans>Distance</Trans></dt>
              <dd className="mt-1 font-data">{distanceLabel}</dd>
            </div>
          )}
          <div>
            <dt className="text-muted-foreground"><Trans>Version</Trans></dt>
            <dd className="mt-1 font-data">{proposal.version}</dd>
          </div>
          {proposal.workouts.length > 0 && (
            <div>
              <dt className="text-muted-foreground"><Trans>Original plan dates</Trans></dt>
              <dd className="mt-1 font-data">
                {proposal.workouts[0].date} – {proposal.workouts[proposal.workouts.length - 1].date}
              </dd>
            </div>
          )}
        </dl>
        <div>
          <h3 className="text-sm font-semibold"><Trans>Original workouts</Trans></h3>
          <div className="mt-2 divide-y divide-border border-y border-border">
            {proposal.workouts.map((workout) => (
              <div key={`${workout.date}-${workout.workout_type}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3 text-sm">
                <span>
                  <span className="font-data">{workout.date}</span>
                  {' · '}
                  {tDisplay(
                    workout.workout_type.split(/[\s_]+/).map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' '),
                    i18n,
                  )}
                </span>
                <span className="font-data text-muted-foreground">
                  {workout.planned_duration_min ?? '—'} <Trans>min</Trans>
                </span>
              </div>
            ))}
          </div>
        </div>
        {[proposal.assumptions, proposal.unknowns, proposal.warnings, proposal.alternatives]
          .filter((items) => items.length > 0)
          .map((items, index) => (
            <p key={index} className="text-sm leading-relaxed text-muted-foreground">
              {items.map(formatProposalDetail).join(' · ')}
            </p>
          ))}
        {onReviewInputs && (
          <DialogFooter>
            <Button variant="outline" className="min-h-11" onClick={() => {
              setReviewAfterClose(true);
              setOpen(false);
            }}>
              <Trans>Review plan inputs</Trans>
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
