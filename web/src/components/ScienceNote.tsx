import { useId, useState, type ReactNode } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';

/**
 * Inline progressive-disclosure reasoning surface \u2014 sits at the bottom of
 * metric cards as a default-collapsed "How this is calculated" affordance.
 *
 * Cobalt is the only signal that this is a reasoning surface (per the
 * Reasoning Color Rule in DESIGN.md). The trigger and the citation link
 * both use `text-accent-cobalt`; the expanded body stays in
 * `text-muted-foreground` because the prose is supporting context, not
 * the reasoning *signal*.
 *
 * Don't dress this up with eyebrows, banners, or a cobalt left rail \u2014
 * that pattern has been retired (it became the AI-UI clich\u00e9). For
 * standalone narrative reasoning surfaces use the `coach-receipt`
 * component instead.
 */
export interface ScienceSource {
  url: string;
  label: string;
}

interface ScienceNoteProps {
  text?: string;
  children?: ReactNode;
  label?: ReactNode;
  sourceUrl?: string;
  sourceLabel?: string;
  sources?: ScienceSource[];
  embedded?: boolean;
}

export default function ScienceNote({
  text,
  children,
  label,
  sourceUrl,
  sourceLabel,
  sources,
  embedded = false,
}: ScienceNoteProps) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  const { t } = useLingui();
  const resolvedSources = sources?.length
    ? sources
    : sourceUrl
      ? [{ url: sourceUrl, label: sourceLabel || t`Source` }]
      : [];
  const content = (
    <>
      {children ?? <p>{text}</p>}
      {resolvedSources.length > 0 && (
        <p className="mt-3 flex flex-wrap gap-x-2 gap-y-1">
          {resolvedSources.map((source, index) => (
            <span key={source.url}>
              {index > 0 && <span aria-hidden="true">· </span>}
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-cobalt underline-offset-2 hover:underline"
              >
                {source.label}
              </a>
            </span>
          ))}
        </p>
      )}
    </>
  );

  if (embedded) {
    return (
      <div className="text-[13px] leading-relaxed text-muted-foreground">
        {content}
      </div>
    );
  }

  return (
    // No own border. Page-level section hairlines do the separation
    // work in flat-page contexts; on surfaces that still need a
    // visual divider above the note (Goal's trajectory block), the
    // parent provides it. Eliminates the "double-hairline" look when
    // a flat section ends with a ScienceNote.
    <div className="mt-4">
      <button
        type="button"
        aria-controls={contentId}
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        className="text-[12px] text-accent-cobalt hover:text-accent-cobalt/80 transition-colors"
      >
        {expanded ? '\u25be' : '\u25b8'} {label ?? <Trans>How this is calculated</Trans>}
      </button>
      {expanded && (
        <div id={contentId} className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
          {content}
        </div>
      )}
    </div>
  );
}