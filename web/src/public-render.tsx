import { renderToString } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { PublicSite } from './public-site';
import { resolvePublicRoute } from './lib/public-route';
import AppLoadingShell from './components/AppLoadingShell';

/** Build-time only: no service, account data, API requests, or runtime SSR. */
export function renderPublicDocument(pathname: string, china: boolean) {
  const route = resolvePublicRoute(pathname, china);
  if (!route) throw new Error(`Not a public document: ${pathname}`);
  return renderToString(<MemoryRouter initialEntries={[pathname]}><PublicSite initialRoute={route} china={china} /></MemoryRouter>);
}

export function renderAppShell() {
  return renderToString(<AppLoadingShell />);
}
