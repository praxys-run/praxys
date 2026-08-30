import { useEffect, useRef, useState, type SyntheticEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { useLocale } from '@/contexts/LocaleContext';
import { useAuth } from '@/hooks/useAuth';
import ChinaProcessingNoticeGate from '@/components/ChinaProcessingNoticeGate';
import { PraxysFlag } from '@/components/PraxysFlag';
import StatusIndicator from '@/components/StatusIndicator';
import type { SupportedLocale } from '@/i18n/init';
import { usePublicSeo } from '@/hooks/usePublicSeo';
import {
  acknowledgeChinaProcessingNotice,
  canStartPersonalDataRequests,
} from '@/lib/china-processing';
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
  vizDecisionLabel: string;
  vizDecisionState: string;
  vizDecisionAction: string;
  vizDecisionReasons: [string, string];
  vizPlanLabel: string;
  vizPlanSync: string;
  vizPlanDays: [PlanDayCopy, PlanDayCopy, PlanDayCopy];
  vizGoalLabel: string;
  vizGoalCurrentLabel: string;
  vizGoalCurrent: string;
  vizGoalTargetLabel: string;
  vizGoalTarget: string;
  vizGoalGap: string;
};

type FeatureCopy = { idx: string; title: string; body: string };
type PlanDayCopy = { day: string; session: string };
type DemoTrigger = 'hero' | 'close';

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
    featuresTitle: {
      before: 'One system. ',
      accent: 'Every training horizon',
      after: '.',
    },
    features: [
      {
        idx: 'Today',
        title: 'A decision, not another score.',
        body:
          'Training load and recovery signals become a clear recommendation, with the reasons visible.',
      },
      {
        idx: 'Next 14 days',
        title: 'A plan that follows your current state.',
        body:
          'Managed workouts adjust as training and recovery change, then synchronize with an available delivery platform.',
      },
      {
        idx: 'Race day',
        title: 'A goal grounded in current evidence.',
        body:
          'Forecasts show the gap between current ability and the target, so ambition becomes a concrete training problem.',
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
    discoverBody: 'Praxys connects daily guidance, weekly review, adaptive planning, and race goals so each decision builds on the same training history.',
    vizDecisionLabel: "Today's recommendation",
    vizDecisionState: 'Modify',
    vizDecisionAction: 'Reduce intensity',
    vizDecisionReasons: ['Recovery below recent baseline', 'Training load remains elevated'],
    vizPlanLabel: 'Managed plan',
    vizPlanSync: 'Delivery · selected platform',
    vizPlanDays: [
      { day: 'Tue', session: 'Easy · 45 min' },
      { day: 'Thu', session: 'Threshold · 4 × 8 min' },
      { day: 'Sun', session: 'Long run · 1 h 50 min' },
    ],
    vizGoalLabel: 'Marathon forecast',
    vizGoalCurrentLabel: 'Current',
    vizGoalCurrent: '3:18',
    vizGoalTargetLabel: 'Goal',
    vizGoalTarget: '3:10',
    vizGoalGap: '8 min gap',
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
    featuresTitle: {
      before: '一套系统，',
      accent: '贯穿每个训练阶段',
      after: '。',
    },
    features: [
      {
        idx: '今天',
        title: '给出判断，而不只是一个分数。',
        body:
          '把训练负荷与恢复状态放在一起，给出明确建议，并说明背后的原因。',
      },
      {
        idx: '未来 14 天',
        title: '跟随一份会根据状态调整的计划。',
        body:
          '托管训练会随训练与恢复状态调整，并同步到账号可用的训练平台。',
      },
      {
        idx: '比赛日',
        title: '让目标建立在当前能力之上。',
        body:
          '比赛预测会显示当前能力与目标之间的差距，把愿望变成具体的训练问题。',
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
    discoverBody: 'Praxys 把每日建议、每周复盘、动态计划和比赛目标串联起来，让每次判断都建立在同一份训练历史之上。',
    vizDecisionLabel: '今日建议',
    vizDecisionState: '适当调整',
    vizDecisionAction: '降低训练强度',
    vizDecisionReasons: ['恢复状态低于近期水平', '训练负荷仍然偏高'],
    vizPlanLabel: '托管训练计划',
    vizPlanSync: '同步 · 已选平台',
    vizPlanDays: [
      { day: '周二', session: '轻松跑 · 45 分钟' },
      { day: '周四', session: '阈值训练 · 4 × 8 分钟' },
      { day: '周日', session: '长距离 · 1 小时 50 分' },
    ],
    vizGoalLabel: '马拉松预测',
    vizGoalCurrentLabel: '当前',
    vizGoalCurrent: '3:18',
    vizGoalTargetLabel: '目标',
    vizGoalTarget: '3:10',
    vizGoalGap: '相差 8 分钟',
  },
};

export default function Landing({ publicLocale }: { publicLocale?: SupportedLocale }) {
  const { locale, setLocale } = useLocale();
  const { login, logout, isDemo } = useAuth();
  const navigate = useNavigate();
  const [demoState, setDemoState] = useState<'idle' | 'loading' | 'error'>('idle');
  const [showChinaNotice, setShowChinaNotice] = useState(false);
  const [restoreDemoFocus, setRestoreDemoFocus] = useState(false);
  const heroDemoButtonRef = useRef<HTMLButtonElement>(null);
  const closeDemoButtonRef = useRef<HTMLButtonElement>(null);
  const noticeTriggerRef = useRef<DemoTrigger>('hero');
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

  useEffect(() => {
    if (showChinaNotice || !restoreDemoFocus) return;
    const button = noticeTriggerRef.current === 'hero'
      ? heroDemoButtonRef.current
      : closeDemoButtonRef.current;
    button?.focus();
    setRestoreDemoFocus(false);
  }, [restoreDemoFocus, showChinaNotice]);

  const startDemo = async () => {
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

  const handleDemo = async (trigger: DemoTrigger) => {
    if (!canStartPersonalDataRequests()) {
      noticeTriggerRef.current = trigger;
      setShowChinaNotice(true);
      return;
    }
    await startDemo();
  };

  const ctaPrimaryLabel = isDemo ? t.ctaContinueDemo : t.ctaPrimary;
  const closeCtaPrimaryLabel = isDemo ? t.ctaContinueDemo : t.closeCtaPrimary;

  const Vizzes = [VizDecision, VizPlan, VizGoal] as const;

  if (showChinaNotice) {
    return (
      <ChinaProcessingNoticeGate
        onContinue={() => {
          acknowledgeChinaProcessingNotice();
          setShowChinaNotice(false);
          void startDemo();
        }}
        onCancel={() => {
          setRestoreDemoFocus(true);
          setShowChinaNotice(false);
        }}
      />
    );
  }

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
            <LanguageToggle locale={activeLocale} />
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
              ref={heroDemoButtonRef}
              type="button"
              className="landing-btn-primary"
              onClick={() => void handleDemo('hero')}
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
          <img src="/logos/oura.svg" alt="Oura" className="plogo plogo-oura" onError={handleLogoError} />
        </section>

        {/* ─── CLOSE ─── */}
        <section className="landing-close">
          <h2>{t.closeTitle}</h2>
          <div className="landing-close-actions">
            <button
              ref={closeDemoButtonRef}
              type="button"
              className="landing-btn-primary"
              onClick={() => void handleDemo('close')}
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

function VizDecision({ t }: { t: Copy }) {
  return (
    <div className="miniviz-decision">
      <div className="decision-head">
        <span>{t.vizDecisionLabel}</span>
        <strong>{t.vizDecisionState}</strong>
      </div>
      <div className="decision-action">{t.vizDecisionAction}</div>
      <ul>
        {t.vizDecisionReasons.map((reason) => <li key={reason}>{reason}</li>)}
      </ul>
    </div>
  );
}

function VizPlan({ t }: { t: Copy }) {
  return (
    <div className="miniviz-plan">
      <div className="plan-head">
        <span>{t.vizPlanLabel}</span>
        <strong>{t.vizPlanSync}</strong>
      </div>
      {t.vizPlanDays.map((item) => (
        <div className="plan-day" key={item.day}>
          <span>{item.day}</span>
          <strong>{item.session}</strong>
        </div>
      ))}
    </div>
  );
}

function VizGoal({ t }: { t: Copy }) {
  return (
    <div className="miniviz-goal">
      <div className="goal-label">{t.vizGoalLabel}</div>
      <div className="goal-times">
        <div>
          <span>{t.vizGoalCurrentLabel}</span>
          <strong>{t.vizGoalCurrent}</strong>
        </div>
        <div>
          <span>{t.vizGoalTargetLabel}</span>
          <strong>{t.vizGoalTarget}</strong>
        </div>
      </div>
      <div className="goal-gap">{t.vizGoalGap}</div>
    </div>
  );
}

function LanguageToggle({ locale }: { locale: SupportedLocale }) {
  return (
    <div className="landing-lang-toggle" role="group" aria-label="Language">
      <button
        type="button"
        className={locale === 'en' ? 'active' : ''}
        onClick={() => {
          window.location.assign('/?lang=en');
        }}
        aria-pressed={locale === 'en'}
      >
        EN
      </button>
      <button
        type="button"
        className={locale === 'zh' ? 'active' : ''}
        onClick={() => {
          window.location.assign('/zh');
        }}
        aria-pressed={locale === 'zh'}
      >
        中
      </button>
    </div>
  );
}
