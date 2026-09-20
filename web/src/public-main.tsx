import { StrictMode } from 'react';
import { createRoot, hydrateRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { PublicSite } from './public-site';
import type { PublicRoute } from './lib/public-route';
import { isChinaFrontendDeployment } from './lib/runtime-region';

export function mountPublic(root: HTMLElement, route: PublicRoute) {
  const content = (
    <StrictMode>
      <BrowserRouter>
        <PublicSite initialRoute={route} china={isChinaFrontendDeployment()} />
      </BrowserRouter>
    </StrictMode>
  );
  if (root.dataset.praxysPublicPage === route.page && root.dataset.praxysPublicLocale === route.locale) {
    hydrateRoot(root, content);
  } else {
    // Development's unrendered shell and old service-worker documents.
    createRoot(root).render(content);
  }
}
