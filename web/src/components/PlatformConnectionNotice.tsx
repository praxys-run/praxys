import { ExternalLink } from "lucide-react";
import { useLingui } from "@lingui/react/macro";

const PROVIDER_PRIVACY: Record<string, { label: string; url: string }> = {
  garmin: {
    label: "Garmin",
    url: "https://www.garmin.com/en-US/privacy/connect/",
  },
  strava: {
    label: "Strava",
    url: "https://www.strava.com/legal/privacy",
  },
  stryd: {
    label: "Stryd",
    url: "https://www.stryd.com/privacy",
  },
  oura: {
    label: "Oura",
    url: "https://ouraring.com/privacy-policy",
  },
  coros: {
    label: "COROS",
    url: "https://coros.com/privacy",
  },
};

interface PlatformConnectionNoticeProps {
  platform: string;
}

export default function PlatformConnectionNotice({
  platform,
}: PlatformConnectionNoticeProps) {
  const { t } = useLingui();
  const provider = PROVIDER_PRIVACY[platform];

  if (!provider) return null;

  return (
    <div className="border-t border-border/70 pt-3" role="note">
      <p className="text-xs leading-5 text-muted-foreground">
        {t`When you continue, Praxys sends the authentication details needed for this connection to ${provider.label} and retrieves the activity, route, fitness, recovery, or plan data that this connection supports. ${provider.label} may process this exchange outside mainland China under its own policy. Disconnecting stops future retrieval.`}
      </p>
      <a
        href={provider.url}
        target="_blank"
        rel="noreferrer"
        className="mt-1.5 inline-flex min-h-7 items-center gap-1 text-xs text-muted-foreground underline decoration-border underline-offset-4 transition-colors hover:text-foreground focus-visible:text-foreground"
      >
        {t`${provider.label} privacy and contact information`}
        <ExternalLink className="h-3 w-3" aria-hidden="true" />
      </a>
    </div>
  );
}
