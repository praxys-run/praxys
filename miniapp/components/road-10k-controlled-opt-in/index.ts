import { apiGet, apiPost } from '../../utils/api-client';
import { t } from '../../utils/i18n';
import type { Road10KAccessResponse } from '../../types/api';

function buildCopy() {
  return {
    invited: t('Try a Road 10K plan proposal'),
    invitedBody: t('You’re invited to a limited process pilot. Joining lets Praxys check whether it can create one deterministic 14-day outdoor road 10K proposal for you. Joining does not create or adopt a plan.'),
    review: t('Review invitation'),
    enrolled: t('Rollout status: Enrolled'),
    hold: t('Rollout status: On hold'),
    paused: t('Rollout status: Paused'),
    stopped: t('Rollout status: Ended'),
    withdrawn: t('Rollout status: Left rollout'),
    withdrawnBody: t('Your proposal will become read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.'),
    removed: t('Your rollout access ended'),
    removedBody: t('Your proposal, if any, is now a read-only receipt and cannot be adopted or regenerated. An adopted plan is unchanged and remains manageable in Training.'),
    noPlan: t('Plan status: No Road 10K plan'),
    empty: t('No Road 10K proposal has been created. Check the current status to continue.'),
    leave: t('Leave rollout'),
    screenshot: t('Screenshots are unavailable until private deletion and restore handling are verified.'),
    confirm: t('Continue to sign in'),
    join: t('Join rollout'),
    cancel: t('Cancel'),
    noticeTitle: t('Join the Road 10K rollout?'),
    noticeIntro: t('This is a limited, default-off process pilot for one deterministic 14-day outdoor road 10K proposal. Joining the rollout does not create or adopt a plan.'),
    noticeScope: t('Praxys checks your existing Goal, direct 10K baseline, recent running history, and confirmed scheduling constraints under the accepted Road 10K rules.'),
    noticeClaims: t('This does not promise faster performance, injury prevention, medical safety, diagnosis, treatment, clearance, or a personal result.'),
    noticeControl: t('No AI chooses or adopts the plan. Nothing is sent to a training provider. Nothing changes until you explicitly adopt the exact proposal.'),
    noticeData: t('The exact data used, access roles, retention, private feedback handling, export, and deletion terms appear in the current data notice below.'),
    noticeLeave: t('You can leave the rollout, export your data, or delete your account. Leaving the rollout does not pause or end an adopted plan.'),
    noticeAck: t('I understand and want to join this Road 10K rollout.'),
    joining: t('Joining the Road 10K rollout…'),
    error: t('Praxys could not complete this action. Nothing changed.'),
  };
}

Component({
  data: {
    access: null as Road10KAccessResponse | null,
    visible: false,
    loading: true,
    flow: 'idle' as 'idle' | 'notice' | 'joining',
    acknowledged: false,
    error: '',
    tr: buildCopy(),
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
    async refresh() {
      try {
        const access = await apiGet<Road10KAccessResponse>('/api/road-10k/access');
        this.setData({
          access,
          visible: true,
          loading: false,
          tr: buildCopy(),
          error: '',
        });
      } catch {
        // A hidden/off authority is the normal dormant state; do not reveal a
        // route, teaser, metadata, or error card for a 404.
        this.setData({ access: null, visible: false, loading: false });
      }
    },

    onReview() {
      this.setData({ flow: 'notice', error: '', acknowledged: false });
    },

    async onJoin() {
      const access = this.data.access as Road10KAccessResponse | null;
      if (!access || this.data.flow === 'joining' || !this.data.acknowledged) return;
      this.setData({ flow: 'joining', error: '' });
      try {
        await apiPost('/api/road-10k/opt-in', {
          password: undefined,
          notice_digest: access.notice_digest,
          client: 'miniapp',
        });
        this.setData({ flow: 'idle', acknowledged: false });
        await this.refresh();
      } catch {
        this.setData({
          flow: 'notice',
          error: this.data.tr.error,
        });
      }
    },

    async onLeave() {
      try {
        await apiPost('/api/road-10k/withdraw', {});
        await this.refresh();
      } catch {
        this.setData({ error: this.data.tr.error });
      }
    },

    onCancel() {
      if (this.data.flow !== 'joining') this.setData({ flow: 'idle', acknowledged: false });
    },

    onAck(event: WechatMiniprogram.CheckboxGroupChange) {
      this.setData({ acknowledged: (event.detail.value || []).includes('ack') });
    },
  },
});
