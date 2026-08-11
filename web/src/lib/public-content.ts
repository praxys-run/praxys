import rawContent from '../../public/seo-content.json';
import type { SupportedLocale } from '@/i18n/init';

export type PublicPageKey = 'home' | 'product' | 'faq';

export type PublicQuestion = {
  question: string;
  answer: string;
};

export type PublicSection = {
  heading: string;
  body: string;
};

export type PublicPage = {
  path: string;
  alternatePath: string;
  title: string;
  description: string;
  heading: string;
  lead: string;
  summaryPoints?: string[];
  sections?: PublicSection[];
  dataHeading?: string;
  dataBody?: string;
  boundaryHeading?: string;
  boundaries?: string[];
  questions?: PublicQuestion[];
};

type PublicLocaleContent = {
  language: string;
  alternateLocale: string;
  nav: {
    home: string;
    product: string;
    faq: string;
    signIn: string;
    tryDemo: string;
  };
  home: PublicPage;
  product: PublicPage;
  faq: PublicPage;
};

type PublicContent = {
  site: {
    name: string;
    baseUrl: string;
    image: string;
  };
  locales: Record<SupportedLocale, PublicLocaleContent>;
};

export const publicContent = rawContent as PublicContent;

export function getPublicPage(locale: SupportedLocale, page: PublicPageKey): PublicPage {
  return publicContent.locales[locale][page];
}
