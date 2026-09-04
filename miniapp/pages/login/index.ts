import {
  clearToken,
  getToken,
  runLaunchLogin,
  saveToken,
  wechatLinkWithPassword,
} from '../../utils/auth';
import { apiDelete, apiGet, apiPost } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { exportAndShareMyData } from '../../utils/data-rights';
import {
  applyThemeChrome,
  getThemePreference,
  setThemePreference,
  themeClassName,
} from '../../utils/theme';
import type { ThemePref } from '../../utils/theme';
import { detectShareLocale, getShareMessage, setLanguagePreference } from '../../utils/share';
import { detectLocale, t } from '../../utils/i18n';
import type { Locale } from '../../utils/i18n-catalog';
import type { IAppOption } from '../../app';
import {
  acknowledgeChinaProcessingNotice,
  CHINA_PROCESSING_NOTICE_VERSION,
  hasAcknowledgedChinaProcessingNotice,
} from '../../utils/china-processing';
import {
  EFFECTIVE_DATE,
  TERMS_CONTENT_DIGEST,
  TERMS_VERSION,
} from '../../utils/legal';
import type {
  ConnectionsResponse,
  CurrentUserProfile,
  PlatformName,
} from '../../types/api';

const SIGNUP_URL = 'https://www.praxys.cn/login?register=1';
const PLATFORM_LABELS: Record<PlatformName, string> = {
  garmin: 'Garmin',
  strava: 'Strava',
  stryd: 'Stryd',
  oura: 'Oura',
  coros: 'COROS',
};

/**
 * Map auth-flow error codes to user-facing copy. Untranslated machine
 * codes ("WECHAT_NO_LOGIN_CODE") are useless to the user; we fall back
 * to the original detail when there's no mapping so backend FastAPI
 * `detail` strings still surface verbatim.
 */
function friendlyAuthError(detail: string): string {
  if (detail === 'WECHAT_NO_LOGIN_CODE') {
    return t('Sign-in code unavailable. Please try again.');
  }
  if (detail === 'WECHAT_NOT_CONFIGURED') {
    return t('WeChat sign-in is not configured on this server.');
  }
  if (detail === 'UNAUTHENTICATED') {
    return t('Your session expired. Please sign in again.');
  }
  if (detail === 'PROCESSING_NOTICE_REQUIRED') {
    return t('Read the processing notice before continuing.');
  }
  return detail;
}

async function getCurrentUserProfile(): Promise<CurrentUserProfile> {
  return apiGet<CurrentUserProfile>('/api/auth/me');
}

/**
 * Build the page's translation table once per mount. Most strings come
 * from web's lingui catalog (auto-synced via `sync-i18n.cjs`), with a
 * handful of mini-program-only keys (web-registration copy, theme-toggle aria
 * labels, tap-to-copy hints) living in `i18n-extra.ts`.
 *
 * The CTA text changes between idle and link stages on purpose:
 * - Idle: "Sign in with WeChat" (we don't yet know if the WeChat profile
 *   is bound to a Praxys account, but the action *is* a WeChat sign-in).
 * - Link: "Link to Praxys" (the user has a setup ticket; tapping the
 *   button binds their existing Praxys account).
 *
 * Tagline is split into three segments — `taglinePrefix +
 * taglineAccent + taglineSuffix` — so the green-accent span ("meets
 * you" / "知行合一") can be its own coloured `<text>` node. Skyline's
 * text composition can't put a coloured span inside a single text
 * node, so we render each segment separately and let the line wrap
 * naturally.
 */
function buildLoginTr(locale: Locale) {
  const taglinePrefix =
    locale === 'zh' ? '运动科学，' : 'Sports science that ';
  const taglineAccent = locale === 'zh' ? '知行合一' : 'meets you';
  const taglineSuffix = locale === 'zh' ? '。' : ' where you are.';

  return {
    taglinePrefix,
    taglineAccent,
    taglineSuffix,
    pillar1Strong: t("Today's signal."),
    pillar1Rest: t(' Go, modify, or rest.'),
    pillar2Strong: t('Diagnosis & forecast'),
    pillar2Rest: t(' you can verify.'),
    pillar3Strong: t('Cited science.'),
    pillar3Rest: t(' No hype.'),

    signInWeChat: t('Sign in with WeChat'),
    signingIn: t('Signing you in…'),
    signInFailed: t('Sign-in failed'),
    retry: t('Retry'),
    linkTitle: t('Sign in to Praxys'),
    linkDetail:
      locale === 'zh'
        ? '请输入在 Praxys 网页端注册时使用的邮箱和密码。'
        : 'Use the email and password you registered with on the Praxys web app.',
    emailPlaceholder: t('email'),
    passwordPlaceholder: t('password'),
    linkAction: t('Link to Praxys'),

    newHere: t('New to Praxys?'),
    registerOnPraxys: t('Create account on praxys.cn'),
    thenSignInWithWeChat: t(
      'Complete registration and account setup in your browser, then return here to link WeChat.',
    ),

    themeLight: t('Light theme'),
    themeDark: t('Dark theme'),
    themeAuto: t('System theme'),

    emailPasswordRequired: t('Email and password are required'),

    noticeTitle: t('How Praxys processes data to provide the service'),
    noticeRequired: t('Required for the service'),
    noticeIntro: t(
      'To create and manage an account and provide the requested training features, Praxys must process the information below outside mainland China. This processing is necessary to perform the service and is not based on consent.',
    ),
    noticeLocationLabel: t('Overseas processing and recipient'),
    noticeLocation: t(
      'Microsoft Corporation, its Azure affiliates, and published subprocessors process core service information outside mainland China. The current primary hosting region is Azure East Asia (Hong Kong SAR).',
    ),
    noticePurposeLabel: t('Purposes and information'),
    noticePurpose: t(
      'Account access, provider sync, training and recovery analysis, plans, security, and requested account controls use account identifiers, training data, settings, encrypted connection credentials, and necessary logs.',
    ),
    noticeSensitiveLabel: t('Sensitive personal information'),
    noticeSensitive: t(
      'Heart rate, HRV, sleep, recovery, activity routes, and related health or fitness inferences may be sensitive. Features that depend on them cannot operate without those categories.',
    ),
    noticeOptional: t(
      'Azure core hosting and Azure AI processing are distinct functions. Current Terms and server runtime state authorize the enumerated AI purposes for ordinary service; there is no separate opt-out, and inputs are minimized by account, purpose, and field.',
    ),
    noticeAcknowledge: t(
      'Continuing acknowledges that this notice has been read. If you do not accept the current Terms, ordinary service is unavailable, while the existing rights flow remains available.',
    ),
    processingNoticeName: t(
      'Privacy Policy and Mainland China processing notice',
    ),
    acknowledgeContinue: t('Acknowledge and continue'),
    notNow: t('Not now'),
    effective: t('Effective'),
    noticeReadRequired: t('Read the processing notice before continuing.'),
    updatedTermsTitle: t('Updated Terms and Privacy notice'),
    updatedTermsDetail: t(
      'The Terms of Service have been updated. The Privacy Policy distinguishes Azure core hosting from Azure AI processing and explains the enumerated ordinary AI purposes, minimization, outage behavior, and rights channels. Ordinary service has no separate AI opt-out. Review the Terms and Privacy notice before continuing.',
    ),
    acceptTermsLead: t('I accept the'),
    privacyReadLead: t('and acknowledge that I have read the'),
    updatedTermsAgreementAria: t(
      'Accept the Terms of Service and acknowledge that the Privacy Policy has been read.',
    ),
    agreementSuffix: locale === 'zh' ? '。' : '.',
    acceptTermsContinue: t('Accept Terms and continue'),
    termsSaveFailed: t('Could not save — please try again.'),
    termsRightsIntro: t(
      'You can still export your data, manage connected platforms, delete your account, or sign out without accepting.',
    ),
    demoTermsRightsIntro: t('You can still sign out without accepting.'),
    connectedPlatforms: t('Connected Platforms'),
    loadingConnections: t('Loading…'),
    disconnect: t('Disconnect'),
    connectionsLoadFailed: t(
      'Could not load connected platforms — please try again.',
    ),
    disconnectFailed: t(
      'Could not disconnect platform — please try again.',
    ),
    exportMyData: t('Export my data'),
    exportingData: t('Exporting data…'),
    exportReady: t('Your data export is ready to share.'),
    exportFailed: t('Could not export data — please try again.'),
    deleteAccount: t('Delete account'),
    deleteAccountTitle: t('Delete account permanently?'),
    deleteAccountDetail: t(
      'This permanently deletes your account, training data, and connected-platform credentials. This cannot be undone. Type DELETE to confirm.',
    ),
    deleteAccountConfirm: t('Delete account'),
    deleteAccountFailed: t('Could not delete account — please try again.'),
    deletionCleanupPending: t(
      'Your account was deleted. Private storage cleanup is still being retried in the background.',
    ),
    signOut: t('Sign out'),

    consentLead: t('By signing in, you agree to our'),
    agreeLead: t('I agree to the'),
    termsName: locale === 'zh' ? '《服务条款》' : t('Terms of Service'),
    privacyName: locale === 'zh' ? '《隐私政策》' : t('Privacy Policy'),
    agreeRequired: t('Please agree to the Terms and Privacy Policy first.'),
  };
}

/**
 * Login page lifecycle:
 *   onLoad inspects storage:
 *     - current processing notice missing → show the bundled notice before
 *       any network request, including wx.login and stored-token checks.
 *     - notice current + token present → verify terms, then open Today.
 *     - notice current + token missing → show the sign-in stage.
 *
 *   User taps Sign in → wx.login() → /api/auth/wechat/login
 *     - status 'ok' + access_token: save JWT, require the current Terms
 *       receipt, then reLaunch to /pages/today.
 *     - status 'needs_setup' + ticket: show the link-to-existing-account
 *       form (CTA "Link to Praxys"). Account creation and initial
 *       setup live on the public Praxys web app.
 *     - failure: show error + retry button.
 *
 * Why no register stage in the mini program: the full onboarding flow
 * (platform connections, training base, threshold setup) lives on web.
 * The public registration link opens praxys.cn in the user's browser;
 * after setup they return here and bind the account to WeChat.
 */

type Stage =
  | 'notice'
  | 'idle'
  | 'loading'
  | 'choose'
  | 'link'
  | 'terms'
  | 'error';

interface PageData {
  stage: Stage;
  themeClass: string;
  themePref: ThemePref;
  ticket: string;
  errorMessage: string;
  /** Resolved locale ('en' | 'zh'); drives the active state on the
   *  top-left language toggle and selects the description copy. */
  locale: Locale;

  linkEmail: string;
  linkPassword: string;
  linkSubmitting: boolean;
  linkError: string;

  termsSubmitting: boolean;
  termsError: string;
  termsRightsAction: '' | 'export' | 'delete';
  termsRightsMessage: string;
  termsConnections: Array<{
    platform: string;
    label: string;
  }>;
  termsConnectionsLoading: boolean;
  termsDisconnectingPlatform: string;
  isDemo: boolean;

  agreedTerms: boolean;
  noticeVersion: string;
  noticeEffectiveDate: string;

  tr: ReturnType<typeof buildLoginTr>;
}

interface PageMethods extends WechatMiniprogram.IAnyObject {
  onNoticeContinue(): Promise<void>;
  onNoticeExit(): void;
  continueStoredSession(): Promise<void>;
  onTermsSubmit(): Promise<void>;
  onTermsDecline(): void;
  onTermsExport(): Promise<void>;
  onTermsDelete(): void;
  runTermsDelete(): Promise<void>;
  loadTermsConnections(): Promise<void>;
  onTermsDisconnect(e: WechatMiniprogram.TouchEvent): Promise<void>;
  onSignInTap(): void;
  runLogin(): Promise<void>;
  onRetry(): void;
  onLinkEmailInput(e: WechatMiniprogram.Input): void;
  onLinkPasswordInput(e: WechatMiniprogram.Input): void;
  onLinkSubmit(): Promise<void>;
  onCopySignupUrl(): void;
  onSwitchLang(e: WechatMiniprogram.TouchEvent): void;
  onSwitchTheme(e: WechatMiniprogram.TouchEvent): void;
  onToggleAgree(): void;
  onOpenLegal(e: WechatMiniprogram.TouchEvent): void;
}

const initialLocale: Locale = 'zh';

const initialData: PageData = {
  stage: 'notice',
  themeClass: getApp<IAppOption>().globalData.themeClass,
  themePref: 'auto',
  ticket: '',
  errorMessage: '',
  locale: initialLocale,
  linkEmail: '',
  linkPassword: '',
  linkSubmitting: false,
  linkError: '',
  termsSubmitting: false,
  termsError: '',
  termsRightsAction: '',
  termsRightsMessage: '',
  termsConnections: [],
  termsConnectionsLoading: false,
  termsDisconnectingPlatform: '',
  isDemo: false,
  agreedTerms: false,
  noticeVersion: CHINA_PROCESSING_NOTICE_VERSION,
  noticeEffectiveDate: EFFECTIVE_DATE,
  tr: buildLoginTr(initialLocale),
};

Page<PageData, PageMethods>({
  data: { ...initialData },

  onLoad(options: { accountDeletionStatus?: string }) {
    const locale = detectLocale();
    const noticeAcknowledged = hasAcknowledgedChinaProcessingNotice();
    const hasToken = Boolean(getToken());
    this.setData({
      themeClass: themeClassName(),
      themePref: getThemePreference(),
      locale,
      tr: buildLoginTr(locale),
      errorMessage: options.accountDeletionStatus === 'deleted_cleanup_pending'
        ? buildLoginTr(locale).deletionCleanupPending
        : '',
      stage: noticeAcknowledged ? (hasToken ? 'loading' : 'idle') : 'notice',
    });
    if (noticeAcknowledged && hasToken) {
      void this.continueStoredSession();
    }
  },

  async onNoticeContinue() {
    acknowledgeChinaProcessingNotice();
    if (getToken()) {
      this.setData({ stage: 'loading', errorMessage: '' });
      await this.continueStoredSession();
      return;
    }
    this.setData({ stage: 'idle', errorMessage: '' }, () => {
      wx.pageScrollTo({ scrollTop: 0, duration: 0 });
    });
  },

  onNoticeExit() {
    wx.exitMiniProgram({});
  },

  async continueStoredSession() {
    try {
      const profile = await getCurrentUserProfile();
      if (!profile.terms_current) {
        this.setData(
          {
            stage: 'terms',
            isDemo: profile.is_demo,
            agreedTerms: false,
            termsSubmitting: false,
            termsError: '',
            termsRightsAction: '',
            termsRightsMessage: '',
            termsConnections: [],
            termsConnectionsLoading: !profile.is_demo,
            termsDisconnectingPlatform: '',
          },
          () => {
            wx.pageScrollTo({ scrollTop: 0, duration: 0 });
            if (!profile.is_demo) void this.loadTermsConnections();
          },
        );
        return;
      }
      wx.reLaunch({ url: '/pages/today/index' });
    } catch (e) {
      const detail = (e as Partial<ApiError>)?.detail ?? String(e);
      this.setData({
        stage: 'error',
        errorMessage: friendlyAuthError(detail),
      });
    }
  },

  async loadTermsConnections() {
    this.setData({
      termsConnectionsLoading: true,
      termsRightsMessage: '',
    });
    try {
      const data = await apiGet<ConnectionsResponse>(
        '/api/settings/connections',
      );
      const termsConnections = Object.entries(data.connections)
        .filter(([, connection]) => Boolean(
          connection
          && (
            connection.has_credentials
            || (
              connection.status !== null
              && connection.status !== 'disconnected'
            )
          ),
        ))
        .map(([platform]) => ({
          platform,
          label: PLATFORM_LABELS[platform as PlatformName] ?? platform,
        }));
      this.setData({ termsConnections });
    } catch (error) {
      const detail = (error as Partial<ApiError>)?.detail
        ?? this.data.tr.connectionsLoadFailed;
      this.setData({ termsRightsMessage: detail });
    } finally {
      this.setData({ termsConnectionsLoading: false });
    }
  },

  async onTermsSubmit() {
    const { agreedTerms, tr } = this.data;
    if (!agreedTerms) {
      this.setData({ termsError: tr.agreeRequired });
      return;
    }
    this.setData({ termsSubmitting: true, termsError: '' });
    try {
      await apiPost('/api/me/accept-terms', {
        terms_version: TERMS_VERSION,
        terms_digest: TERMS_CONTENT_DIGEST,
        locale: this.data.locale,
      });
      wx.reLaunch({ url: '/pages/today/index' });
    } catch {
      this.setData({
        termsSubmitting: false,
        termsError: tr.termsSaveFailed,
      });
    }
  },

  onTermsDecline() {
    clearToken();
    this.setData(
      {
        stage: 'idle',
        agreedTerms: false,
        termsSubmitting: false,
        termsError: '',
        termsRightsAction: '',
        termsRightsMessage: '',
        termsConnections: [],
        termsConnectionsLoading: false,
        termsDisconnectingPlatform: '',
        isDemo: false,
      },
      () => {
        wx.pageScrollTo({ scrollTop: 0, duration: 0 });
      },
    );
  },

  async onTermsExport() {
    if (this.data.isDemo) return;
    if (this.data.termsRightsAction) return;
    this.setData({
      termsRightsAction: 'export',
      termsRightsMessage: '',
    });
    try {
      await exportAndShareMyData();
      this.setData({ termsRightsMessage: this.data.tr.exportReady });
    } catch {
      this.setData({ termsRightsMessage: this.data.tr.exportFailed });
    } finally {
      this.setData({ termsRightsAction: '' });
    }
  },

  onTermsDelete() {
    if (this.data.isDemo) return;
    if (this.data.termsRightsAction) return;
    const { tr } = this.data;
    wx.showModal({
      title: tr.deleteAccountTitle,
      content: tr.deleteAccountDetail,
      editable: true,
      placeholderText: 'DELETE',
      confirmText: tr.deleteAccountConfirm,
      confirmColor: '#d93a2c',
      success: (result) => {
        if (result.confirm && result.content === 'DELETE') {
          void this.runTermsDelete();
        }
      },
    });
  },

  async runTermsDelete() {
    if (this.data.isDemo) return;
    this.setData({
      termsRightsAction: 'delete',
      termsRightsMessage: '',
    });
    try {
      await apiDelete('/api/me');
      clearToken();
      wx.reLaunch({ url: '/pages/login/index' });
    } catch {
      this.setData({
        termsRightsAction: '',
        termsRightsMessage: this.data.tr.deleteAccountFailed,
      });
    }
  },

  async onTermsDisconnect(event: WechatMiniprogram.TouchEvent) {
    if (this.data.isDemo || this.data.termsDisconnectingPlatform) return;
    const platform = event.currentTarget.dataset.platform as
      | string
      | undefined;
    if (!platform) return;

    this.setData({
      termsDisconnectingPlatform: platform,
      termsRightsMessage: '',
    });
    try {
      await apiDelete(
        `/api/settings/connections/${encodeURIComponent(platform)}`,
      );
      this.setData({
        termsConnections: this.data.termsConnections.filter(
          (connection) => connection.platform !== platform,
        ),
      });
    } catch (error) {
      const detail = (error as Partial<ApiError>)?.detail
        ?? this.data.tr.disconnectFailed;
      this.setData({ termsRightsMessage: detail });
    } finally {
      this.setData({ termsDisconnectingPlatform: '' });
    }
  },

  onSignInTap() {
    this.setData({ stage: 'loading', errorMessage: '' });
    void this.runLogin();
  },

  onShow() {
    applyThemeChrome();
  },

  onShareAppMessage() {
    return getShareMessage(detectShareLocale(), '/pages/login/index');
  },

  async runLogin() {
    try {
      const result = await runLaunchLogin();
      if (result.status === 'ok' && result.access_token) {
        saveToken(result.access_token);
        await this.continueStoredSession();
        return;
      }
      if (result.status === 'needs_setup' && result.wechat_login_ticket) {
        // Skip the choose-link-or-register split — register lives on web.
        this.setData({ stage: 'link', agreedTerms: false, ticket: result.wechat_login_ticket });
        return;
      }
      this.setData({ stage: 'error', errorMessage: 'Unexpected login response' });
    } catch (e) {
      const detail = (e as Partial<ApiError>)?.detail ?? String(e);
      this.setData({ stage: 'error', errorMessage: friendlyAuthError(detail) });
    }
  },

  onRetry() {
    this.setData({ stage: 'loading', errorMessage: '' });
    if (getToken()) {
      void this.continueStoredSession();
    } else {
      void this.runLogin();
    }
  },

  onLinkEmailInput(e) {
    this.setData({ linkEmail: e.detail.value });
  },
  onLinkPasswordInput(e) {
    this.setData({ linkPassword: e.detail.value });
  },

  async onLinkSubmit() {
    const { linkEmail, linkPassword, ticket, tr } = this.data;
    if (!linkEmail || !linkPassword) {
      this.setData({ linkError: tr.emailPasswordRequired });
      return;
    }
    if (!this.data.agreedTerms) {
      this.setData({ linkError: tr.agreeRequired });
      return;
    }
    this.setData({ linkSubmitting: true, linkError: '' });
    try {
      const r = await wechatLinkWithPassword(ticket, linkEmail, linkPassword);
      saveToken(r.access_token);
      this.setData({ linkSubmitting: false });
      await this.continueStoredSession();
    } catch (e) {
      this.setData({
        linkSubmitting: false,
        linkError: friendlyAuthError((e as Partial<ApiError>)?.detail ?? String(e)),
      });
    }
  },

  /**
   * Agreement checkbox toggle, shown on the Terms stage and the
   * account-link stage. Submission is blocked until the applicable
   * acknowledgement is explicit.
   */
  onToggleAgree() {
    this.setData({ agreedTerms: !this.data.agreedTerms });
  },

  /**
   * Open the Terms or Privacy document. `data-kind` on the tapped link picks
   * which; both render in pages/legal from the web-canonical legal content
   * synced into utils/legal.ts.
   */
  onOpenLegal(e: WechatMiniprogram.TouchEvent) {
    const kind = e.currentTarget.dataset.kind === 'privacy' ? 'privacy' : 'terms';
    wx.navigateTo({ url: `/pages/legal/index?kind=${kind}` });
  },

  /**
   * Copy the public Web registration deep link. WeChat does not let mini
   * programs open an arbitrary external browser URL, so the user pastes it
   * into their browser, completes setup, then returns to bind WeChat.
   */
  onCopySignupUrl() {
    wx.setClipboardData({
      data: SIGNUP_URL,
      success: () => {
        wx.showToast({ title: t('URL copied'), icon: 'success', duration: 1500 });
      },
    });
  },

  /**
   * Top-left language toggle. Mirror of web's LanguageToggle: writes
   * the new preference to wx storage and reLaunches the page so every
   * `t()` call resolves against the new catalog.
   */
  onSwitchLang(e) {
    const next = e.currentTarget.dataset.lang as Locale | undefined;
    if (!next || next === this.data.locale) return;
    setLanguagePreference(next);
    getApp<IAppOption>().globalData.locale = next;
    wx.reLaunch({ url: '/pages/login/index' });
  },

  /**
   * Top-left theme toggle. Three-state pill (light / dark / auto) —
   * tap on a segment to make it active. Persists the preference to
   * wx storage and reLaunches the page so the new theme class
   * applies everywhere consistently.
   */
  onSwitchTheme(e) {
    const next = e.currentTarget.dataset.theme as ThemePref | undefined;
    if (!next || next === this.data.themePref) return;
    setThemePreference(next);
    wx.reLaunch({ url: '/pages/login/index' });
  },
});
