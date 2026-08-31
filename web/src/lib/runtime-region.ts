export const CHINA_DEPLOYMENT_META_NAME = 'praxys-deployment-region';

export function isChinaDeploymentRegion(
  region: string | null | undefined,
): boolean {
  return region?.trim().toLowerCase() === 'cn';
}

export function isChinaFrontendDeployment(): boolean {
  if (typeof document === 'undefined') return false;
  const marker = document.querySelector<HTMLMetaElement>(
    `meta[name="${CHINA_DEPLOYMENT_META_NAME}"]`,
  );
  return isChinaDeploymentRegion(marker?.content);
}

export function isAppInsightsAllowed(configured: boolean): boolean {
  return configured;
}

export function isStatsigBrowserAllowed(configured: boolean): boolean {
  return configured && !isChinaFrontendDeployment();
}
