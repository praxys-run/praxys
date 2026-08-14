import { detectLocale, t } from '../../utils/i18n';

type ObservedTrainingSection = 'analysis' | 'activities';

function translations() {
  return {
    label: t('Observed training'),
    analysis: t('Analysis'),
    activities: t('Activities'),
  };
}

Component({
  properties: {
    active: {
      type: String as StringConstructor,
      value: 'analysis',
    },
    disabled: {
      type: Boolean as BooleanConstructor,
      value: false,
    },
  },

  data: {
    locale: detectLocale(),
    tr: translations(),
  },

  lifetimes: {
    attached() {
      this.setData({
        locale: detectLocale(),
        tr: translations(),
      });
    },
  },

  pageLifetimes: {
    show() {
      const locale = detectLocale();
      if (locale !== this.data.locale) {
        this.setData({ locale, tr: translations() });
      }
    },
  },

  methods: {
    onPick(event: WechatMiniprogram.TouchEvent) {
      if (this.data.disabled) return;
      const value = String(event.currentTarget.dataset.value ?? '');
      if (
        (value !== 'analysis' && value !== 'activities')
        || value === this.data.active
      ) {
        return;
      }
      this.triggerEvent('change', {
        value: value as ObservedTrainingSection,
      });
    },
  },
});
