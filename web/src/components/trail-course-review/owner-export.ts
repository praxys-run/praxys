export type TrailOwnerExportStatus = 'idle' | 'preparing' | 'success' | 'error';

interface TrailOwnerExportOptions {
  getAuthHeaders: () => HeadersInit;
  closeMenuAndFocus: () => void;
  onStatusChange: (status: TrailOwnerExportStatus) => void;
}

function accountExportFilename(disposition: string | null): string {
  const match = disposition?.match(
    /(?:^|;)\s*filename\s*=\s*(?:"([^"]*)"|([^;\s]+))\s*(?=;|$)/i,
  );
  const candidate = match?.[1] ?? match?.[2];
  const allowed = candidate?.match(/^praxys-data-export-[0-9]{4}-[0-9]{2}-[0-9]{2}\.json$/)?.[0];
  return candidate && allowed === candidate ? candidate : 'praxys-data-export.json';
}

/** Account export only: no draft input, mutation, cache, or error details. */
export function createTrailOwnerExportAction({
  getAuthHeaders,
  closeMenuAndFocus,
  onStatusChange,
}: TrailOwnerExportOptions) {
  // This synchronous latch survives React renders and guards reentrant calls,
  // including calls made before a busy-state render can disable the menu item.
  let inFlight: AbortController | null = null;

  return {
    async run(): Promise<void> {
      if (inFlight) return;
      const controller = new AbortController();
      inFlight = controller;
      try {
        onStatusChange('preparing');
        closeMenuAndFocus();
        const response = await fetch('/api/me/export', {
          method: 'GET',
          headers: getAuthHeaders(),
          mode: 'same-origin',
          redirect: 'error',
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!response.ok) {
          onStatusChange('error');
          return;
        }
        const filename = accountExportFilename(response.headers.get('content-disposition'));
        const blob = await response.blob();
        if (controller.signal.aborted) return;

        // Reuse Settings' blob/anchor download, with cleanup even if DOM work
        // fails or the page unmounts during activation.
        const url = URL.createObjectURL(blob);
        try {
          const link = document.createElement('a');
          try {
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
          } finally {
            link.remove();
          }
        } finally {
          URL.revokeObjectURL(url);
        }
        if (!controller.signal.aborted) onStatusChange('success');
      } catch {
        if (!controller.signal.aborted) onStatusChange('error');
      } finally {
        inFlight = null;
      }
    },
    cancel(): void {
      inFlight?.abort();
    },
  };
}
