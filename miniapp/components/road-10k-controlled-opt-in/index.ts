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

function uiText() {
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
    reauthBody: copy('reauth.body'),
    noticeTitle: copy('notice.title'),
    noticeIntro: copy('notice.intro'),
    noticeScope: copy('notice.scope'),
    noticeClaims: copy('notice.claims'),
    noticeControl: copy('notice.control'),
    noticeData: copy('notice.data'),
    noticeLeave: copy('notice.leave'),
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
    text: uiText(),
    rolloutTitle: '',
    rolloutBody: '',
    rolloutStatusLabel: '',
    planStatusLabel: '',
    planBody: '',
    leaveHint: '',
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

      return {
        rolloutTitle: copy(rolloutTitleKey),
        rolloutBody: copy(rolloutBodyKey),
        rolloutStatusLabel: copy(ROAD_10K_ROLLOUT_STATUS_COPY[access.rollout_status]),
        planStatusLabel: copy(planKeys[0]),
        planBody: copy(planKeys[planKeys.length - 1] ?? planKeys[0]),
        leaveHint: copy('notice.leave'),
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
