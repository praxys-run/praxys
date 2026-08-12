import { useEffect, useState, type SyntheticEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { useLocale } from '@/contexts/LocaleContext';
import { useAuth } from '@/hooks/useAuth';
import { PraxysFlag } from '@/components/PraxysFlag';
import StatusIndicator from '@/components/StatusIndicator';
import type { SupportedLocale } from '@/i18n/init';
import { usePublicSeo } from '@/hooks/usePublicSeo';
import { publicContent } from '@/lib/public-content';
import './Landing.css';

/** Demo account credentials. Hardcoded by design — demo is read-only and
 *  intentionally public (VITE_ vars are embedded in the bundle at build time,
 *  so they aren't a secret anyway). Override in web/.env.local for a
 *  self-hosted fork.
 */
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || 'demo@trainsight.dev';
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || 'demo';

/** If a platform logo asset is missing (renamed, 404 from CDN), hide the broken-
 *  image icon so the trust band stays visually clean, and log enough detail to
 *  debug the deploy. Without this the band gets a default broken-image glyph
 *  with zero telemetry. */
function handleLogoError(e: SyntheticEvent<HTMLImageElement>) {
  console.warn('[landing] logo missing:', e.currentTarget.src);
  e.currentTarget.style.display = 'none';
}

type Copy = {
  signIn: string;
  exitDemo: string;
  heroEyebrow: string;
  ctaPrimary: string;
  ctaContinueDemo: string;
  ctaSecondary: string;
  demoLoading: string;
  demoError: string;
  demoActiveNote: string;
  featuresEyebrow: string;
  featuresTitle: { before: string; accent: string; after: string };
  features: [FeatureCopy, FeatureCopy, FeatureCopy];
  platformsLabel: string;
  closeTitle: string;
  closeCtaPrimary: string;
  closeCtaSecondary: string;
  closeMicro: string;
  footerLeft: string;
  footerRight: string;
  termsLink: string;
  privacyLink: string;
  productLink: string;
  faqLink: string;
  discoverTitle: string;
  discoverBody: string;
  vizCpLabel: string;
  vizCpDelta: string;
  vizCpUnit: string;
  vizFormulaEyebrow: string;
  vizFormulaCite: string;
  vizClaudePrompt: string;
  vizClaudeAnswer: string;
  vizClaudeCite: string;
};

type FeatureCopy = { idx: string; title: string; body: string };

const COPY: Record<SupportedLocale, Copy> = {
  en: {
    signIn: 'Sign in',
    exitDemo: 'Exit demo',
    heroEyebrow: 'Endurance training · Decisions · Evidence',
    ctaPrimary: 'Try the demo',
    ctaContinueDemo: 'Continue to demo',
    ctaSecondary: 'Create account',
    demoLoading: 'Loading demo…',
    demoError: 'Demo temporarily unavailable. Try signing in instead.',
    demoActiveNote: 'Demo session active — data is read-only.',
    featuresEyebrow: 'Why Praxys',
    featuresTitle: {
      before: 'Interpretation first. ',
      accent: 'Evidence always',
      after: '.',
    },
    features: [
      {
        idx: '01 · Science',
        title: 'Grounded in published research.',
        body:
          'Every zone, formula, and prediction traces back to peer-reviewed sport science — Coggan, Riegel, Monod & Scherrer, Stryd RPP. Click any number to see its source.',
      },
      {
        idx: '02 · Personalized',
        title: 'Your data becomes your next action.',
        body:
          'Praxys turns training and recovery data into a daily signal, personalized zones, threshold trends, race forecasts, and plans that adjust as your fitness and fatigue change.',
      },
      {
        idx: '03 · AI-native',
        title: 'AI is a layer, not the foundation.',
        body:
          'Cited metrics and deterministic rules work without an AI service. When enabled, AI adds explanation, planning, and natural-language analysis without replacing the evidence underneath.',
      },
    ],
    platformsLabel: 'Connects with',
    closeTitle: 'Ready to see what your training really says?',
    closeCtaPrimary: 'Try the demo',
    closeCtaSecondary: 'Create account',
    closeMicro: 'No signup for the demo · your data stays yours',
    footerLeft: 'Praxys Endurance',
    footerRight: 'praxys.run',
    termsLink: 'Terms',
    privacyLink: 'Privacy',
    productLink: 'Product',
    faqLink: 'FAQ',
    discoverTitle: 'From today’s decision to the season ahead.',
    discoverBody: 'Praxys connects daily readiness, weekly diagnosis, adaptive planning, race forecasts, and opt-in research in one evidence-led training system.',
    vizCpLabel: 'Your CP',
    vizCpDelta: '+6 W · 14 d',
    vizCpUnit: 'W',
    vizFormulaEyebrow: 'Critical Power',
    vizFormulaCite: 'Monod & Scherrer · 1965',
    vizClaudePrompt: 'Why is my fitness dropping?',
    vizClaudeAnswer: 'TSB −22 W · overload. Back off 2–3 days, then rebuild.',
    vizClaudeCite: 'via Praxys · Claude Code plugin',
  },
  zh: {
    signIn: '登录',
    exitDemo: '退出演示',
    heroEyebrow: '耐力训练 · 明确建议 · 科学依据',
    ctaPrimary: '试用演示',
    ctaContinueDemo: '继续演示',
    ctaSecondary: '创建账号',
    demoLoading: '正在加载演示……',
    demoError: '演示暂时不可用，请尝试登录。',
    demoActiveNote: '演示会话进行中 — 数据为只读。',
    featuresEyebrow: '为什么选择 Praxys',
    featuresTitle: {
      before: '先说结论，',
      accent: '依据随时可查',
      after: '。',
    },
    features: [
      {
        idx: '01 · 科学依据',
        title: '每个结论，都有研究依据。',
        body:
          '训练区间、公式和预测都能追溯到同行评审的运动科学文献——Coggan、Riegel、Monod & Scherrer、Stryd RPP。点击数值，就能查看出处。',
      },
      {
        idx: '02 · 因人而异',
        title: '从你的数据出发，告诉你下一步怎么练。',
        body:
          'Praxys 把训练与恢复数据转化为每日建议、个性化区间、阈值变化、比赛预测和训练计划，并随体能与疲劳状态持续调整。',
      },
      {
        idx: '03 · AI 增强',
        title: 'AI 增强理解，不替代科学基础。',
        body:
          '即使没有 AI 服务，带文献来源的指标和确定性规则仍能运行。启用 AI 后，它会帮助解释变化、调整计划和深入分析，但不会取代底层证据。',
      },
    ],
    platformsLabel: '可连接',
    closeTitle: '看看你的训练数据，到底在告诉你什么。',
    closeCtaPrimary: '试用演示',
    closeCtaSecondary: '创建账号',
    closeMicro: '演示无需注册 · 你的数据始终属于你',
    footerLeft: 'Praxys Endurance',
    footerRight: 'praxys.run',
    termsLink: '服务条款',
    privacyLink: '隐私政策',
    productLink: '产品',
    faqLink: '常见问题',
    discoverTitle: '从今天怎么练，到整个赛季怎么安排。',
    discoverBody: 'Praxys 把每日状态、每周复盘、动态计划、比赛预测和自愿研究串联起来，形成一套以证据为基础的训练系统。',
    vizCpLabel: '你的 CP',
    vizCpDelta: '+6 W · 14 天',
    vizCpUnit: '瓦',
    vizFormulaEyebrow: 'Critical Power',
    vizFormulaCite: 'Monod & Scherrer · 1965',
    vizClaudePrompt: '最近体能为什么下滑？',
    vizClaudeAnswer: 'TSB −22 W · 负荷偏高。先减量 2–3 天，再逐步恢复。',
    vizClaudeCite: '来自 Praxys · Claude Code 插件',
  },
};

export default function Landing({ publicLocale }: { publicLocale?: SupportedLocale }) {
  const { locale, setLocale } = useLocale();
  const { login, logout, isDemo } = useAuth();
  const navigate = useNavigate();
  const [demoState, setDemoState] = useState<'idle' | 'loading' | 'error'>('idle');
  const activeLocale = publicLocale ?? locale;
  const t = COPY[activeLocale];
  const publicNav = publicContent.locales[activeLocale];
  const homePage = publicNav.home;
  const heroAccent = homePage.headingAccent;
  const heroHeading = heroAccent && homePage.heading.endsWith(heroAccent)
    ? homePage.heading.slice(0, -heroAccent.length)
    : homePage.heading;
  usePublicSeo('home', activeLocale);

  useEffect(() => {
    if (publicLocale && publicLocale !== locale) void setLocale(publicLocale);
  }, [locale, publicLocale, setLocale]);

  const handleDemo = async () => {
    // If a demo session already exists (user tried demo earlier and came
    // back to `/`), skip the login round-trip and jump straight in.
    if (isDemo) {
      navigate('/today', { replace: true });
      return;
    }
    setDemoState('loading');
    try {
      const result = await login(DEMO_EMAIL, DEMO_PASSWORD);
      if (result.ok) {
        navigate('/today', { replace: true });
      } else {
        // Surface the backend error detail in the console so ops can diagnose
        // a rotated demo password or a deleted demo account (the UI can only
        // afford a generic error string).
        console.error('[landing] demo login failed:', result.error);
        setDemoState('error');
      }
    } catch (err) {
      console.error('[landing] demo login threw:', err);
      setDemoState('error');
    }
  };

  const ctaPrimaryLabel = isDemo ? t.ctaContinueDemo : t.ctaPrimary;
  const closeCtaPrimaryLabel = isDemo ? t.ctaContinueDemo : t.closeCtaPrimary;

  const Vizzes = [VizScience, VizPersonal, VizClaude] as const;

  return (
    <div className="landing-root">
      <header className="landing-header">
        <div className="landing-header-inner">
          <div className="landing-brand">
            <PraxysFlag className="h-6 w-6 shrink-0" strokeWidth={3} />
            <span className="name">Praxys</span>
          </div>
          <div className="landing-header-nav">
            <nav className="landing-primary-nav" aria-label={activeLocale === 'zh' ? '公共页面' : 'Public pages'}>
              <Link to={publicNav.product.path}>{t.productLink}</Link>
              <Link to={publicNav.faq.path}>{t.faqLink}</Link>
            </nav>
            <LanguageToggle locale={activeLocale} setLocale={setLocale} />
            {isDemo ? (
              <button type="button" className="landing-btn-signin" onClick={logout}>
                {t.exitDemo}
              </button>
            ) : (
              <Link to="/login" className="landing-btn-signin">
                {t.signIn}
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="landing-container">
        {/* ─── HERO ─── */}
        <section className="landing-hero">
          <div className="landing-hero-eyebrow landing-rise landing-rise-1">{t.heroEyebrow}</div>
          <h1 className="landing-rise landing-rise-2">
            {heroHeading}
            {heroAccent && <span className="accent">{heroAccent}</span>}
          </h1>
          <p className="landing-hero-sub landing-rise landing-rise-3">{homePage.lead}</p>
          <div className="landing-hero-actions landing-rise landing-rise-4">
            <button
              type="button"
              className="landing-btn-primary"
              onClick={handleDemo}
              disabled={demoState === 'loading'}
            >
              {demoState === 'loading' ? t.demoLoading : ctaPrimaryLabel}
              {demoState !== 'loading' && <ArrowUpRight className="h-[15px] w-[15px]" strokeWidth={2.2} />}
            </button>
            <Link to="/login" className="landing-btn-ghost">
              {t.ctaSecondary}
            </Link>
          </div>
          {isDemo && demoState !== 'error' && (
            <div className="landing-demo-note landing-rise">{t.demoActiveNote}</div>
          )}
          {demoState === 'error' && (
            <div className="landing-demo-error landing-rise">{t.demoError}</div>
          )}
        </section>

        <section className="landing-discover">
          <div>
            <h2>{t.discoverTitle}</h2>
            <p>{t.discoverBody}</p>
            <div className="landing-discover-actions">
              <Link to={publicNav.product.path} className="landing-btn-primary">{t.productLink}</Link>
              <Link to={publicNav.faq.path} className="landing-btn-ghost">{t.faqLink}</Link>
            </div>
          </div>
          <ul>
            {homePage.summaryPoints?.map((point) => <li key={point}>{point}</li>)}
          </ul>
        </section>

        {/* ─── FEATURES ─── */}
        <section id="why" className="landing-features">
          <div className="landing-features-head">
            <span className="eyebrow">{t.featuresEyebrow}</span>
            <h2>
              {t.featuresTitle.before}
              <em>{t.featuresTitle.accent}</em>
              {t.featuresTitle.after}
            </h2>
          </div>

          <div className="landing-features-grid">
            {t.features.map((f, i) => {
              const Viz = Vizzes[i];
              return (
                <article key={f.idx} className="landing-fcard">
                  <span className="fidx">{f.idx}</span>
                  <div className="fviz"><Viz t={t} /></div>
                  <div className="fcap">
                    <h3>{f.title}</h3>
                    <p>{f.body}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        {/* ─── PLATFORMS (quieter) ─── */}
        <section className="landing-platforms-band">
          <span className="label">{t.platformsLabel}</span>
          <img src="/logos/garmin.png" alt="Garmin" className="plogo plogo-garmin" onError={handleLogoError} />
          <img src="/logos/strava.svg" alt="Strava" className="plogo plogo-strava" onError={handleLogoError} />
          <img src="/logos/coros.png" alt="COROS" className="plogo plogo-coros" onError={handleLogoError} />
          <img src="/logos/stryd.svg" alt="Stryd" className="plogo plogo-stryd" onError={handleLogoError} />
          <img src="/logos/oura.svg" alt="Oura" className="plogo plogo-oura" onError={handleLogoError} />
        </section>

        {/* ─── CLOSE ─── */}
        <section className="landing-close">
          <h2>{t.closeTitle}</h2>
          <div className="landing-close-actions">
            <button
              type="button"
              className="landing-btn-primary"
              onClick={handleDemo}
              disabled={demoState === 'loading'}
            >
              {demoState === 'loading' ? t.demoLoading : closeCtaPrimaryLabel}
              {demoState !== 'loading' && <ArrowUpRight className="h-[15px] w-[15px]" strokeWidth={2.2} />}
            </button>
            <Link to="/login" className="landing-btn-ghost">
              {t.closeCtaSecondary}
            </Link>
          </div>
          <div className="microcopy">{t.closeMicro}</div>
        </section>

        <footer className="landing-footer">
          <div className="fbrand">
            <PraxysFlag className="h-4 w-4" strokeWidth={3} />
            <span>{t.footerLeft}</span>
          </div>
          <span className="fnote"><Link to={publicNav.product.path}>{t.productLink}</Link> · <Link to={publicNav.faq.path}>{t.faqLink}</Link></span>
          <StatusIndicator className="landing-status" />
          <span><a href="/terms">{t.termsLink}</a> · <a href="/privacy">{t.privacyLink}</a></span>
          <span>{t.footerRight}</span>
        </footer>
      </main>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Mini product vizzes
   ────────────────────────────────────────────────────────── */

function VizScience({ t }: { t: Copy }) {
  return (
    <div className="miniviz-formula">
      <div className="eyebrow">◆ {t.vizFormulaEyebrow}</div>
      <div className="expr">
        CP = <span className="v">W′</span> / t + <span className="v">P</span>
      </div>
      <div className="sub">
        = <span className="res">281 W</span>
      </div>
      <div className="cite">— {t.vizFormulaCite}</div>
    </div>
  );
}

function VizPersonal({ t }: { t: Copy }) {
  return (
    <div className="miniviz-cp">
      <div className="stat">
        <span className="stat-label">{t.vizCpLabel}</span>
      </div>
      <div className="stat" style={{ marginTop: -6 }}>
        <span className="stat-value">281</span>
        <span className="stat-unit">{t.vizCpUnit}</span>
        <span className="stat-delta">▲ {t.vizCpDelta}</span>
      </div>
      <div className="zone-bar" aria-hidden="true">
        <span className="zone z1" style={{ width: '12%' }} />
        <span className="zone z2" style={{ width: '38%' }} />
        <span className="zone z3" style={{ width: '28%' }} />
        <span className="zone z4" style={{ width: '16%' }} />
        <span className="zone z5" style={{ width: '6%' }} />
      </div>
      <div className="zone-legend">
        <span>Z1</span>
        <span>Z2</span>
        <span>Z3</span>
        <span>Z4</span>
        <span>Z5</span>
      </div>
    </div>
  );
}

function VizClaude({ t }: { t: Copy }) {
  return (
    <div className="miniviz-claude">
      <div className="line prompt">
        <span className="chev">▸</span>
        {t.vizClaudePrompt}
      </div>
      <div className="line answer">{t.vizClaudeAnswer}</div>
      <div className="cite">{t.vizClaudeCite}</div>
    </div>
  );
}

function LanguageToggle({
  locale,
  setLocale,
}: {
  locale: SupportedLocale;
  setLocale: (l: SupportedLocale) => Promise<void>;
}) {
  return (
    <div className="landing-lang-toggle" role="group" aria-label="Language">
      <button
        type="button"
        className={locale === 'en' ? 'active' : ''}
        onClick={() => {
          void setLocale('en');
          window.location.assign('/');
        }}
        aria-pressed={locale === 'en'}
      >
        EN
      </button>
      <button
        type="button"
        className={locale === 'zh' ? 'active' : ''}
        onClick={() => {
          void setLocale('zh');
          window.location.assign('/zh');
        }}
        aria-pressed={locale === 'zh'}
      >
        中
      </button>
    </div>
  );
}
