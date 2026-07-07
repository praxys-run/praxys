import type { IAppOption } from '../../app';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import { detectLocale, t } from '../../utils/i18n';
import {
  TERMS_VERSION,
  EFFECTIVE_DATE,
  SUPPORT_EMAIL,
  TERMS_SECTIONS,
  PRIVACY_SECTIONS,
} from '../../utils/legal';

/**
 * Legal document viewer — renders either the Terms of Service / EULA or the
 * Privacy Policy from `utils/legal.ts` (synced from web's canonical
 * `web/src/lib/legal.ts`). Which document shows is chosen by the `?kind=`
 * query param the login page passes when the user taps a doc link.
 *
 * The section content is bilingual inline (en/zh) in the synced data, so we
 * pick the active locale here exactly the way web's LegalPage does — this
 * copy never rides the `t()` catalog. Only the page chrome (nav title,
 * "Effective" label, cross-link, copied toast) goes through `t()`.
 */

type Kind = 'terms' | 'privacy';

interface RenderedSection {
  id: string;
  title: string;
  body: string[];
}

function buildLegalTr(kind: Kind) {
  const termsTitle = t('Terms of Service & EULA');
  const privacyTitle = t('Privacy Policy');
  return {
    navTitle: kind === 'terms' ? termsTitle : privacyTitle,
    effective: t('Effective'),
    crossLabel: kind === 'terms' ? privacyTitle : termsTitle,
    copied: t('Copied'),
  };
}

function renderSections(kind: Kind): RenderedSection[] {
  const zh = detectLocale() === 'zh';
  const source = kind === 'terms' ? TERMS_SECTIONS : PRIVACY_SECTIONS;
  return source.map((section) => ({
    id: section.id,
    title: zh ? section.title.zh : section.title.en,
    body: section.body.map((para) => (zh ? para.zh : para.en)),
  }));
}

interface PageData {
  themeClass: string;
  kind: Kind;
  crossKind: Kind;
  version: string;
  effectiveDate: string;
  supportEmail: string;
  sections: RenderedSection[];
  tr: ReturnType<typeof buildLegalTr>;
}

interface PageMethods extends WechatMiniprogram.IAnyObject {
  onCrossLink(): void;
  onCopyEmail(): void;
}

Page<PageData, PageMethods>({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass,
    kind: 'terms',
    crossKind: 'privacy',
    version: TERMS_VERSION,
    effectiveDate: EFFECTIVE_DATE,
    supportEmail: SUPPORT_EMAIL,
    sections: [],
    tr: buildLegalTr('terms'),
  },

  onLoad(options: Record<string, string | undefined>) {
    const kind: Kind = options.kind === 'privacy' ? 'privacy' : 'terms';
    this.setData({
      kind,
      crossKind: kind === 'terms' ? 'privacy' : 'terms',
      themeClass: themeClassName(),
      sections: renderSections(kind),
      tr: buildLegalTr(kind),
    });
  },

  onShow() {
    const tc = themeClassName();
    if (tc !== this.data.themeClass) this.setData({ themeClass: tc });
    applyThemeChrome();
  },

  /**
   * Jump between the Terms and Privacy documents without growing the page
   * stack — redirectTo swaps the current page so Back still returns to login.
   */
  onCrossLink() {
    wx.redirectTo({ url: `/pages/legal/index?kind=${this.data.crossKind}` });
  },

  /**
   * Mini programs can't open a mailto: link, so tapping the support address
   * copies it to the clipboard (same affordance the login page uses for the
   * praxys.run URL).
   */
  onCopyEmail() {
    wx.setClipboardData({
      data: this.data.supportEmail,
      success: () => {
        wx.showToast({ title: this.data.tr.copied, icon: 'success', duration: 1500 });
      },
    });
  },
});