import { useEffect } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PraxysFlag } from '@/components/PraxysFlag';
import { useLocale } from '@/contexts/LocaleContext';
import { usePublicSeo } from '@/hooks/usePublicSeo';
import type { SupportedLocale } from '@/i18n/init';
import { getPublicPage, publicContent, type PublicPageKey } from '@/lib/public-content';
import './Landing.css';

export default function PublicInfo({
  locale,
  pageKey,
}: {
  locale: SupportedLocale;
  pageKey: Exclude<PublicPageKey, 'home'>;
}) {
  const { setLocale } = useLocale();
  const localeContent = publicContent.locales[locale];
  const page = getPublicPage(locale, pageKey);
  const alternateLocale: SupportedLocale = locale === 'en' ? 'zh' : 'en';
  usePublicSeo(pageKey, locale);

  useEffect(() => {
    void setLocale(locale);
  }, [locale, setLocale]);

  return (
    <div className="landing-root public-info-root">
      <header className="landing-header">
        <div className="landing-header-inner">
          <Link to={localeContent.home.path} className="landing-brand">
            <PraxysFlag className="h-6 w-6 shrink-0" strokeWidth={3} />
            <span className="name">Praxys</span>
          </Link>
          <nav className="landing-header-nav" aria-label={locale === 'zh' ? '公共页面' : 'Public pages'}>
            <Link className="landing-nav-link" to={localeContent.product.path}>{localeContent.nav.product}</Link>
            <Link className="landing-nav-link" to={localeContent.faq.path}>{localeContent.nav.faq}</Link>
            <Link className="landing-lang-link" to={getPublicPage(alternateLocale, pageKey).path}>
              {locale === 'zh' ? 'EN' : '中'}
            </Link>
            <Link to="/login" className="landing-btn-signin">{localeContent.nav.signIn}</Link>
          </nav>
        </div>
      </header>

      <main className="landing-container public-info">
        <header className="public-info-hero">
          <h1>{page.heading}</h1>
          <p>{page.lead}</p>
        </header>

        {pageKey === 'product' ? (
          <>
            <div className="public-capability-list">
              {page.sections?.map((section) => (
                <section key={section.heading}>
                  <h2>{section.heading}</h2>
                  <p>{section.body}</p>
                </section>
              ))}
            </div>
            <section className="public-evidence-block">
              <h2>{page.dataHeading}</h2>
              <p>{page.dataBody}</p>
            </section>
            <section className="public-boundaries">
              <h2>{page.boundaryHeading}</h2>
              <ul>
                {page.boundaries?.map((boundary) => <li key={boundary}>{boundary}</li>)}
              </ul>
            </section>
          </>
        ) : (
          <div className="public-faq-list">
            {page.questions?.map((item) => (
              <details key={item.question}>
                <summary>{item.question}</summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        )}

        <section className="landing-close">
          <h2>{locale === 'zh' ? '看看 Praxys 如何解释真实训练数据。' : 'See how Praxys interprets real training data.'}</h2>
          <Link className="landing-btn-primary" to="/">
            {localeContent.nav.tryDemo}
            <ArrowUpRight className="h-[15px] w-[15px]" strokeWidth={2.2} />
          </Link>
        </section>

        <footer className="landing-footer">
          <div className="fbrand">
            <PraxysFlag className="h-4 w-4" strokeWidth={3} />
            <span>Praxys Endurance</span>
          </div>
          <span><Link to="/terms">{locale === 'zh' ? '服务条款' : 'Terms'}</Link> · <Link to="/privacy">{locale === 'zh' ? '隐私政策' : 'Privacy'}</Link></span>
          <span>praxys.run</span>
        </footer>
      </main>
    </div>
  );
}
