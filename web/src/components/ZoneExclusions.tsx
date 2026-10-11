import { Trans } from '@lingui/react/macro';
import { Info } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { formatTime } from '@/lib/format';
import type { ExcludedPowerActivity } from '@/types/api';

/** A touch and keyboard accessible explanation with owned activity links. */
export default function ZoneExclusions({ excluded = [] }: { excluded?: ExcludedPowerActivity[] }) {
  if (!excluded.length) return null;
  const count = excluded.length;
  return (
    <div className="mb-4">
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="ghost" size="sm" className="min-h-11" />}>
          <Info data-icon="inline-start" />
          <Trans>Excluded runs: {count}</Trans>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-80 max-w-[calc(100vw-2rem)]">
          <p className="px-3 py-2 text-sm text-muted-foreground">
            <Trans>These runs have no usable recorded power and are excluded. The comparison covers only included runs.</Trans>
          </p>
          <DropdownMenuGroup>
            {excluded.map((activity) => (
              <DropdownMenuItem
                key={activity.activity_id}
                className="min-h-11"
                render={<Link to={`/history/${encodeURIComponent(activity.activity_id)}`} />}
              >
                <span className="font-data">{activity.date}</span>
                {activity.duration_sec != null && (
                  <span className="ml-auto font-data">{formatTime(activity.duration_sec)}</span>
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
