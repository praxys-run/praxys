export const PRELOAD_RELOAD_KEY = 'praxys-preload-reload';
export const PRELOAD_RELOAD_WINDOW_MS = 30_000;

export interface PreloadReloadMarker {
  pathname: string;
  attemptedAt: number;
}

export function parsePreloadReloadMarker(
  raw: string | null,
): PreloadReloadMarker | null {
  if (!raw) return null;
  try {
    const marker = JSON.parse(raw) as Partial<PreloadReloadMarker>;
    if (
      typeof marker.pathname === 'string'
      && typeof marker.attemptedAt === 'number'
    ) {
      return marker as PreloadReloadMarker;
    }
  } catch {
    return null;
  }
  return null;
}

export function isActivePreloadReload(
  marker: PreloadReloadMarker | null,
  pathname: string,
  now: number,
): boolean {
  return (
    marker?.pathname === pathname
    && now - marker.attemptedAt < PRELOAD_RELOAD_WINDOW_MS
  );
}
