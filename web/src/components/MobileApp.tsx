import { Smartphone } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Card, CardHeader, CardContent, CardTitle, CardDescription } from '@/components/ui/card';
import { Trans, useLingui } from '@lingui/react/macro';

/**
 * Praxys mobile-client discovery.
 *
 * Surfaces the ways to use Praxys away from the desktop web app. Today that is
 * the WeChat Mini Program (scan the 小程序码); the layout is structured so native
 * iOS / Android app entries can slot in below the WeChat block later without a
 * redesign.
 *
 * Three exports share one inner `MobileClients` body:
 *  - `MobileClients` — the client list (theme-aware QR + scan instruction).
 *  - `MobileAppDialog` — dialog wrapper, opened from the sidebar footer.
 *  - `MobileAppCard` — Settings card wrapper (the canonical home).
 */

// The WeChat mini program 小程序码, exported from the WeChat MP console into
// `web/public/`. Two variants so the code sits on the right field in each theme
// (the light asset carries a warm-paper background, the dark asset a dark one).
// We render both and let the `.dark` class on <html> swap them via CSS, so the
// QR reacts to a theme change instantly with no JS state to fall stale.
const QR_LIGHT = '/qr-praxys-prod.png';
const QR_DARK = '/qr-praxys-prod-dark.png';

function WeChatQr() {
  const { t } = useLingui();
  const alt = t`WeChat Mini Program QR code`;
  return (
    <div className="shrink-0">
      <img
        src={QR_LIGHT}
        alt={alt}
        width={176}
        height={176}
        className="h-44 w-44 rounded-lg border border-border dark:hidden"
      />
      <img
        src={QR_DARK}
        alt={alt}
        width={176}
        height={176}
        className="hidden h-44 w-44 rounded-lg border border-border dark:block"
      />
    </div>
  );
}

/**
 * The shared client list. One entry today (WeChat Mini Program); when native
 * apps ship, add store-badge rows beneath the WeChat block here.
 */
export function MobileClients() {
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:gap-6">
      <WeChatQr />
      <div className="space-y-1.5 text-center sm:text-left">
        <p className="text-sm font-semibold text-foreground">
          <Trans>WeChat Mini Program</Trans>
        </p>
        <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">
          <Trans>
            Open WeChat, tap the Scan button, and point your camera at this code to use Praxys on your phone.
          </Trans>
        </p>
      </div>
    </div>
  );
}

/** Dialog wrapper opened from the sidebar footer entry. */
export function MobileAppDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <Trans>Praxys on your phone</Trans>
          </DialogTitle>
          <DialogDescription>
            <Trans>Carry your training signal outdoors. Scan to open Praxys in WeChat.</Trans>
          </DialogDescription>
        </DialogHeader>
        <div className="pt-2">
          <MobileClients />
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Settings card — the canonical home for mobile-client discovery. */
export function MobileAppCard() {
  return (
    <Card className="mb-8">
      <CardHeader>
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            <Smartphone className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-sm font-semibold text-foreground">
              <Trans>Praxys on your phone</Trans>
            </CardTitle>
            <CardDescription className="text-xs">
              <Trans>Use Praxys on the go with the WeChat Mini Program</Trans>
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <MobileClients />
      </CardContent>
    </Card>
  );
}