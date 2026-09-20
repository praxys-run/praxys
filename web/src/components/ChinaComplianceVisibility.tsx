import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { isChinaFilingPublicPath } from '../lib/china-compliance';

/** The regional build owns the static footer; React only syncs its visibility. */
export default function ChinaComplianceVisibility() {
  const { pathname } = useLocation();

  useLayoutEffect(() => {
    const footer = document.querySelector<HTMLElement>('[data-praxys-cn-compliance]');
    if (footer) footer.hidden = !isChinaFilingPublicPath(pathname);
  }, [pathname]);

  return null;
}
