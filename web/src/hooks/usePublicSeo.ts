import { useEffect } from 'react';
import type { SupportedLocale } from '@/i18n/init';
import { getPublicPage, publicContent, type PublicPageKey } from '@/lib/public-content';

function setMeta(selector: string, attribute: string, value: string): void {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement('meta');
    const [key, rawValue] = selector
      .replace(/^meta\[/, '')
      .replace(/\]$/, '')
      .split('=');
    element.setAttribute(key, rawValue.replaceAll('"', ''));
    document.head.appendChild(element);
  }
  element.setAttribute(attribute, value);
}

function setLink(rel: string, href: string, hreflang?: string): void {
  const selector = hreflang
    ? `link[rel="${rel}"][hreflang="${hreflang}"]`
    : `link[rel="${rel}"]:not([hreflang])`;
  let element = document.head.querySelector<HTMLLinkElement>(selector);
  if (!element) {
    element = document.createElement('link');
    element.rel = rel;
    if (hreflang) element.hreflang = hreflang;
    document.head.appendChild(element);
  }
  element.href = href;
}

export function usePublicSeo(pageKey: PublicPageKey, locale: SupportedLocale): void {
  useEffect(() => {
    const localeContent = publicContent.locales[locale];
    const page = getPublicPage(locale, pageKey);
    const canonical = `${publicContent.site.baseUrl}${page.path}`;
    const alternate = `${publicContent.site.baseUrl}${page.alternatePath}`;

    document.documentElement.lang = localeContent.language;
    document.title = page.title;
    setMeta('meta[name="description"]', 'content', page.description);
    setMeta('meta[name="robots"]', 'content', 'index, follow, max-image-preview:large');
    setMeta('meta[property="og:type"]', 'content', 'website');
    setMeta('meta[property="og:title"]', 'content', page.title);
    setMeta('meta[property="og:description"]', 'content', page.description);
    setMeta('meta[property="og:url"]', 'content', canonical);
    setMeta('meta[property="og:locale"]', 'content', locale === 'zh' ? 'zh_CN' : 'en_US');
    setMeta('meta[name="twitter:title"]', 'content', page.title);
    setMeta('meta[name="twitter:description"]', 'content', page.description);
    setLink('canonical', canonical);
    setLink('alternate', canonical, localeContent.language);
    setLink('alternate', alternate, locale === 'zh' ? 'en' : 'zh-CN');
    if (pageKey === 'home') setLink('alternate', `${publicContent.site.baseUrl}/`, 'x-default');

    const schema = pageKey === 'faq'
      ? {
          '@context': 'https://schema.org',
          '@type': 'FAQPage',
          mainEntity: page.questions?.map((item) => ({
            '@type': 'Question',
            name: item.question,
            acceptedAnswer: { '@type': 'Answer', text: item.answer },
          })),
        }
      : {
          '@context': 'https://schema.org',
          '@graph': [
            {
              '@type': 'Organization',
              name: publicContent.site.name,
              url: publicContent.site.baseUrl,
              logo: `${publicContent.site.baseUrl}/favicon.svg`,
            },
            {
              '@type': 'SoftwareApplication',
              name: publicContent.site.name,
              applicationCategory: 'HealthApplication',
              operatingSystem: 'Web',
              url: canonical,
              description: page.description,
            },
          ],
        };
    let script = document.head.querySelector<HTMLScriptElement>('#praxys-structured-data');
    if (!script) {
      script = document.createElement('script');
      script.id = 'praxys-structured-data';
      script.type = 'application/ld+json';
      document.head.appendChild(script);
    }
    script.textContent = JSON.stringify(schema);

    return () => {
      setMeta('meta[name="robots"]', 'content', 'noindex, nofollow');
      document.head.querySelector('link[rel="canonical"]')?.remove();
      document.head.querySelectorAll('link[rel="alternate"]').forEach((element) => element.remove());
      document.head.querySelector('#praxys-structured-data')?.remove();
    };
  }, [locale, pageKey]);
}
