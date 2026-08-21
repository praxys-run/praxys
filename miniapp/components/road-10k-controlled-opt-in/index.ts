import { apiGet, apiPost } from '../../utils/api-client';
import { detectLocale, t } from '../../utils/i18n';
import type { IAppOption } from '../../app';
import type { Road10KAccessResponse } from '../../types/api';
import {
  ROAD_10K_PLAN_STATE_COPY,
  ROAD_10K_ROLLOUT_STATUS_COPY,
  road10kAccessStateCopy,
  road10kCopy,
} from '../../utils/road-10k-control';

type Surface = 'goal' | 'training' | 'settings';
type FlowState = 'idle' | 'reauth' | 'notice' | 'joining';

function copy(key: Parameters<typeof road10kCopy>[0]) {
  return road10kCopy(key, detectLocale() === 'zh' ? 'zh-CN' : 'en');
}

function languageClass() {
  return detectLocale() === 'en' ? 'lang-en' : 'lang-zh';
}

function wordList(value: string): string[] {
  return value.split(/\s+/).filter(Boolean);
}

function uiText() {
  const reauthBody = copy('reauth.body');
  const noticeIntro = copy('notice.intro');
  const noticeScope = copy('notice.scope');
  const noticeClaims = copy('notice.claims');
  const noticeControl = copy('notice.control');
  const noticeData = copy('notice.data');
  const noticeLeave = copy('notice.leave');

  return {
    reviewInvitation: copy('action.review_invitation'),
    notNow: copy('action.not_now'),
    viewTraining: copy('action.training'),
    leave: copy('action.leave'),
    cancel: copy('action.cancel'),
    continue: copy('action.continue'),
    join: copy('action.join'),
    check: copy('action.check'),
    addScreenshot: copy('action.add_screenshot'),
    joining: copy('progress.joining'),
    leaving: copy('progress.leaving'),
    reauthTitle: copy('reauth.title'),
    reauthBody,
    reauthBodyWords: wordList(reauthBody),
    noticeTitle: copy('notice.title'),
    noticeIntro,
    noticeIntroWords: wordList(noticeIntro),
    noticeScope,
    noticeScopeWords: wordList(noticeScope),
    noticeClaims,
    noticeClaimsWords: wordList(noticeClaims),
    noticeControl,
    noticeControlWords: wordList(noticeControl),
    noticeData,
    noticeDataWords: wordList(noticeData),
    noticeLeave,
    noticeLeaveWords: wordList(noticeLeave),
    noticeAck: copy('notice.ack'),
    withdrawTitle: copy('life.withdraw_title'),
    withdrawBody: copy('life.withdraw_body'),
    passwordPlaceholder: t('Password'),
  };
}

function canLeaveRollout(access: Road10KAccessResponse): boolean {
  return [
    'enrolled',
    'enrollment-closed',
    'hold',
    'paused',
    'revision',
  ].includes(access.rollout_status);
}

Component({
  properties: {
    surface: {
      type: String,
      value: 'goal',
    },
  },

  data: {
    access: null as Road10KAccessResponse | null,
    visible: false,
    invitationDismissed: false,
    loading: true,
    flow: 'idle' as FlowState,
    acknowledged: false,
    password: '',
    error: '',
    languageClass: languageClass(),
    text: uiText(),
    rolloutTitle: '',
    rolloutBody: '',
    rolloutBodyWords: [] as string[],
    rolloutStatusLabel: '',
    planStatusLabel: '',
    planStatusLabelWords: [] as string[],
    planBody: '',
    leaveHint: '',
    leaveHintWords: [] as string[],
    screenshotHint: '',
    leaveAvailable: false,
    leaving: false,
  },

  lifetimes: {
    attached() {
      void this.refresh();
    },
  },

  pageLifetimes: {
    show() {
      void this.refresh();
    },
  },

  methods: {
    summarize(access: Road10KAccessResponse) {
      const rolloutKeys = road10kAccessStateCopy(
        access.rollout_status,
        access.plan_status,
      );
      const planKeys = ROAD_10K_PLAN_STATE_COPY[access.plan_status];
      const rolloutTitleKey = access.rollout_status === 'enrolled'
        ? 'status.rollout_enrolled'
        : rolloutKeys[0];
      const rolloutBodyKey = access.rollout_status === 'enrolled'
        ? 'success.joined'
        : (rolloutKeys[rolloutKeys.length - 1] ?? rolloutTitleKey);
      const rolloutBody = copy(rolloutBodyKey);
      const planStatusLabel = copy(planKeys[0]);
      const leaveHint = copy('notice.leave');

      return {
        rolloutTitle: copy(rolloutTitleKey),
        rolloutBody,
        rolloutBodyWords: wordList(rolloutBody),
        rolloutStatusLabel: copy(ROAD_10K_ROLLOUT_STATUS_COPY[access.rollout_status]),
        planStatusLabel,
        planStatusLabelWords: wordList(planStatusLabel),
        planBody: copy(planKeys[planKeys.length - 1] ?? planKeys[0]),
        leaveHint,
        leaveHintWords: wordList(leaveHint),
        screenshotHint: copy('feedback.screenshot_blocked'),
        leaveAvailable: canLeaveRollout(access),
      };
    },

    consumeTrainingIntent(access: Road10KAccessResponse) {
      if (this.properties.surface !== 'training') return;
      const app = getApp<IAppOption>();
      if (app.globalData.pendingRoad10KIntent === 'review_status') {
        app.globalData.pendingRoad10KIntent = null;
        return;
      }
      if (
        app.globalData.pendingRoad10KIntent === 'review_invitation'
        && access.rollout_status === 'invited'
      ) {
        app.globalData.pendingRoad10KIntent = null;
        this.setData({
          invitationDismissed: false,
          flow: 'reauth',
          error: '',
        });
        return;
      }
      app.globalData.pendingRoad10KIntent = null;
    },

    async refresh() {
      try {
        const access = await apiGet<Road10KAccessResponse>('/api/road-10k/access');
        this.setData({
          access,
          visible: !(this.data.invitationDismissed && access.rollout_status === 'invited'),
          loading: false,
          error: '',
          languageClass: languageClass(),
          text: uiText(),
          ...this.summarize(access),
        });
        this.consumeTrainingIntent(access);
      } catch {
        // Hidden/off remains the normal dormant state.
        this.setData({ access: null, visible: false, loading: false });
      }
    },

    openTraining(intent: 'review_invitation' | 'review_status') {
      const app = getApp<IAppOption>();
      app.globalData.pendingRoad10KIntent = intent;
      wx.switchTab({ url: '/pages/training/index' });
    },

    onReview() {
      if (this.properties.surface === 'goal') {
        this.openTraining('review_invitation');
        return;
      }
      this.setData({ flow: 'reauth', error: '', acknowledged: false });
    },

    onOpenTraining() {
      this.openTraining('review_status');
    },

    onNotNow() {
      this.setData({
        invitationDismissed: true,
        visible: false,
        flow: 'idle',
        error: '',
      });
    },

    onPasswordInput(event: WechatMiniprogram.Input) {
      this.setData({ password: event.detail.value || '' });
    },

    onContinue() {
      if (!this.data.password) return;
      this.setData({ flow: 'notice', error: '' });
    },

    async onJoin() {
      const access = this.data.access as Road10KAccessResponse | null;
      if (
        !access
        || this.data.flow === 'joining'
        || !this.data.acknowledged
        || !this.data.password
      ) return;
      this.setData({ flow: 'joining', error: '' });
      try {
        await apiPost('/api/road-10k/opt-in', {
          password: this.data.password,
          client: 'miniapp',
        });
        this.setData({
          flow: 'idle',
          acknowledged: false,
          password: '',
        });
        await this.refresh();
      } catch {
        this.setData({
          flow: 'reauth',
          error: copy('error.generic'),
        });
      }
    },

    async onLeave() {
      if (this.data.leaving) return;
      wx.showModal({
        title: copy('life.withdraw_title'),
        content: copy('life.withdraw_body'),
        confirmText: copy('action.leave'),
        cancelText: copy('action.cancel'),
        success: (result) => {
          if (result.confirm) void this.confirmLeave();
        },
      });
    },

    async confirmLeave() {
      this.setData({ leaving: true, error: '' });
      try {
        await apiPost('/api/road-10k/withdraw', {});
        await this.refresh();
      } catch {
        this.setData({ error: copy('error.generic') });
      } finally {
        this.setData({ leaving: false });
      }
    },

    onCheck() {
      this.triggerEvent('check');
    },

    onCancel() {
      if (this.data.flow !== 'joining') {
        this.setData({
          flow: 'idle',
          acknowledged: false,
          password: '',
        });
      }
    },

    onAck(event: WechatMiniprogram.CheckboxGroupChange) {
      this.setData({ acknowledged: (event.detail.value || []).includes('ack') });
    },

    noop() {},
  },
});
