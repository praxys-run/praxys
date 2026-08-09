import { ArrowRight, FlaskConical } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Trans, useLingui } from '@lingui/react/macro';
import { msg } from '@lingui/core/macro';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useApi } from '@/hooks/useApi';
import type { LabsEnvironmentResponseState } from '@/types/api';

function catalogStatus(
  state: LabsEnvironmentResponseState,
) {
  if (state.status === 'available') return msg`Result ready`;
  if (state.status === 'queued' || state.status === 'processing') return msg`Analyzing`;
  if (state.enrolled) return msg`Participating`;
  return msg`Open to check`;
}

export default function Labs() {
  const { i18n } = useLingui();
  const { data, loading, error, refetch } = useApi<LabsEnvironmentResponseState>(
    '/api/labs/environment-response',
    { refetchInterval: 5000, refetchOnMount: 'always' },
  );
  return (
    <div className="space-y-8">
      <header className="border-b border-border pb-7">
        <h1 className="text-3xl font-semibold tracking-tight"><Trans>Praxys Labs</Trans></h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          <Trans>Choose voluntary experiments that help you inspect your own training history without turning early research into advice.</Trans>
        </p>
      </header>

      <section aria-labelledby="available-experiments" className="space-y-4">
        <div>
          <h2 id="available-experiments" className="text-xl font-semibold">
            <Trans>Available experiments</Trans>
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            <Trans>Each experiment has its own consent, data requirements, limitations, and withdrawal controls.</Trans>
          </p>
        </div>

        {loading && !data ? (
          <Skeleton className="h-52 rounded-xl" />
        ) : error || !data ? (
          <Alert variant="destructive">
            <AlertTitle><Trans>Labs could not load</Trans></AlertTitle>
            <AlertDescription className="mt-2">
              <p>{error}</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                <Trans>Retry</Trans>
              </Button>
            </AlertDescription>
          </Alert>
        ) : (
          <Card>
            <CardContent className="flex flex-col gap-6 py-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-start gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <FlaskConical className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold"><Trans>Environmental response</Trans></h3>
                    <Badge variant="outline">
                      {i18n._(catalogStatus(data))}
                    </Badge>
                  </div>
                  <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                    <Trans>Explore whether modeled heart rate varied with temperature and humidity at comparable recorded Stryd power in your eligible past runs.</Trans>
                  </p>
                  <p className="mt-3 text-xs text-muted-foreground">
                    <Trans>Historical association only · personal aggregate result · continuous Stryd samples required</Trans>
                  </p>
                </div>
              </div>
              <Button
                render={<Link to="/labs/environment-response" />}
                nativeButton={false}
                className="w-full sm:w-auto"
              >
                <Trans>Open experiment</Trans>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
