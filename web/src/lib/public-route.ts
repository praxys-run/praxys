import type { SupportedLocale } from '../i18n/init';

export interface PublicRoute {
  page: 'home' | 'product' | 'faq';
  locale: SupportedLocale;
}

/** Public document language is decided by its URL, before React starts. */
export function resolvePublicRoute(pathname: string, china = false): PublicRoute | null {
  const path = pathname.replace(/\/+$/, '') || '/';
  if (path === '/') return { page: 'home', locale: china ? 'zh' : 'en' };
  if (path === '/en') return { page: 'home', locale: 'en' };
  if (path === '/zh') return { page: 'home', locale: 'zh' };
  if (path === '/product' || path === '/faq') return { page: path.slice(1) as 'product' | 'faq', locale: 'en' };
  if (path === '/zh/product' || path === '/zh/faq') return { page: path.slice(4) as 'product' | 'faq', locale: 'zh' };
  return null;
}
