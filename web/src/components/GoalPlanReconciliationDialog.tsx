import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Trans, useLingui } from '@lingui/react/macro';
import { useNavigate } from 'react-router-dom';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useSettings } from '@/contexts/SettingsContext';
import { apiFetch, extractErrorMessage } from '@/hooks/useApi';
import type { GoalPlanKeepResponse } from '@/types/api';

export default function GoalPlanReconciliationDialog() {
  const { t } = useLingui();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { goalPlanImpact, dismissGoalPlanImpact } = useSettings();
  const [action, setAction] = useState<'keep' | 'review' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (action) return;
    setError(null);
    dismissGoalPlanImpact();
  };

  const reviewPlan = async () => {
    if (action) return;
    setAction('review');
    setError(null);
    try {
      await Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: ['/api/goal'] }),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/generation/capabilities'],
        }),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/proposals/current'],
        }),
      ]);
    } finally {
      dismissGoalPlanImpact();
      setAction(null);
      navigate('/training');
    }
  };

  const keepCurrentPlan = async () => {
    if (!goalPlanImpact || action) return;
    setAction('keep');
    setError(null);
    try {
      const response = await apiFetch(
        `/api/plan/${goalPlanImpact.adaptive_plan_id}/goal-reconciliation/keep-current`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expected_goal_revision: goalPlanImpact.current_goal_revision,
            expected_goal_snapshot_id:
              goalPlanImpact.plan_goal_snapshot_id,
            idempotency_key:
              `goal-plan-keep:${goalPlanImpact.plan_goal_snapshot_id}`,
          }),
        },
      );
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            t`Could not keep the current plan. Reload and try again.`,
          ),
        );
      }
      const result = await response.json() as GoalPlanKeepResponse;
      if (result.link_status !== 'independent') {
        throw new Error(
          t`The plan decision returned an unexpected state. Reload and try again.`,
        );
      }
      dismissGoalPlanImpact();
      await Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: ['/api/goal'] }),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/generation/capabilities'],
        }),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/proposals/current'],
        }),
      ]);
    } catch (keepError) {
      setError(
        keepError instanceof Error
          ? keepError.message
          : t`Could not keep the current plan. Reload and try again.`,
      );
    } finally {
      setAction(null);
    }
  };

  return (
    <Dialog
      open={goalPlanImpact !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            <Trans>Your Goal changed. Should your plan change too?</Trans>
          </DialogTitle>
          <DialogDescription className="text-sm leading-relaxed">
            {goalPlanImpact?.lifecycle === 'draft' ? (
              <Trans>
                The open proposal was built for your previous Goal and can no
                longer be adopted. Review a fresh proposal now or decide later.
              </Trans>
            ) : goalPlanImpact?.can_generate_successor ? (
              <Trans>
                Your current plan was built for your previous Goal. Review a
                successor proposal, keep this plan as an independent plan, or
                decide later.
              </Trans>
            ) : (
              <Trans>
                There is no approved automatic plan policy for this Goal yet.
                Praxys will not repurpose another policy. Keep the current plan
                independent, manage workouts manually, or decide later.
              </Trans>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
          <Trans>
            Until you adopt a replacement, your current workouts and delivery
            continue unchanged.
          </Trans>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertTitle><Trans>Plan decision not saved</Trans></AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="ghost" disabled={action !== null} onClick={close}>
            <Trans>Decide later</Trans>
          </Button>
          {goalPlanImpact?.can_keep_current_plan && (
            <Button
              variant="outline"
              disabled={action !== null}
              onClick={keepCurrentPlan}
            >
              {action === 'keep'
                ? <Trans>Keeping plan…</Trans>
                : <Trans>Keep current plan</Trans>}
            </Button>
          )}
          <Button
            disabled={action !== null}
            onClick={() => { void reviewPlan(); }}
          >
            {goalPlanImpact?.can_generate_successor
              ? <Trans>Review and update plan</Trans>
              : <Trans>Manage plan</Trans>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
