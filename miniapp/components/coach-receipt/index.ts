import type { AiInsightResponse, CoachTheoryRef } from '../../types/api';
import { coachToggleLabel, insightFeedbackState, localizedInsight } from '../../utils/insights';
import { detectLocale, t } from '../../utils/i18n';

interface Receipt {
  headline: string;
  summary?: string;
  stamp?: string;
  findings: { text: string; tone?: string }[];
  recommendations: { text: string }[];
}

Component({
  options: { styleIsolation: 'isolated' },
  properties: {
    response: { type: Object, value: null as AiInsightResponse | null },
    fallback: { type: Object, value: null as Receipt | null },
    insightType: { type: String, value: '' },
    snapshot: { type: String, value: '' },
    theoryRefs: { type: Array, value: [] as CoachTheoryRef[] },
    loading: { type: Boolean, value: false },
    failed: { type: Boolean, value: false },
  },
  data: {
    receipt: null as Receipt | null,
    isAi: false, detailsOpen: false, detailLabel: '', primaryAction: '',
    remaining: [] as { text: string }[], refs: [] as CoachTheoryRef[],
    statusText: '', datasetHash: '', vote: '', contentVersion: '', dataAsOf: '',
    tr: { coach: '', metrics: '', key: '', findings: '', recommendations: '', refresh: '', dataThrough: '', methods: '' },
  },
  observers: {
    'response, fallback, snapshot, theoryRefs, loading, failed'() { this.rebuild(); },
  },
  lifetimes: { attached() { this.rebuild(); } },
  methods: {
    rebuild() {
      const response = this.data.response as AiInsightResponse | null;
      const daily = this.data.insightType === 'daily_brief';
      const coherent = !daily || (Boolean(this.data.snapshot)
        && response?.snapshot === this.data.snapshot && response.content_status === 'ready'
        && response.insight?.snapshot === this.data.snapshot
        && response.insight.content_version === 'morning-coach-v1');
      const insight = coherent && !this.data.loading && !this.data.failed ? response?.insight ?? null : null;
      const view = insight ? localizedInsight(insight, detectLocale()) : null;
      const receipt: Receipt | null = view ? {
        headline: view.headline, summary: view.summary,
        stamp: insight?.as_of_date ?? insight?.generated_at?.slice(0, 10) ?? '',
        findings: view.findings.map(f => ({ text: f.text, tone: f.type })),
        recommendations: view.recommendations.map(text => ({ text })),
      } : this.data.loading ? null : this.data.fallback as Receipt | null;
      const remaining = receipt?.recommendations.slice(1) ?? [];
      const feedback = insightFeedbackState(insight);
      const statusText = this.data.failed ? t("Couldn't load Coach. Try again.")
        : this.data.loading ? t('Loading Coach…')
        : response?.ai_available === false ? t('Azure AI insights are temporarily unavailable.')
        : response?.content_status === 'unavailable' ? t('Coach analysis is unavailable. Training metrics remain available.')
        : daily && (!this.data.snapshot || response?.content_status === 'stale') ? t('Coach needs a refreshed training snapshot.')
        : !insight ? t('Coach is waiting for a current analysis.') : '';
      this.setData({
        receipt, isAi: Boolean(insight), detailsOpen: false, remaining,
        primaryAction: receipt?.recommendations[0]?.text ?? '',
        detailLabel: coachToggleLabel(receipt?.findings.length ?? 0, remaining.length, false),
        refs: response?.theory_refs ?? this.data.theoryRefs, statusText,
        datasetHash: feedback.datasetHash, vote: feedback.vote,
        contentVersion: insight?.content_version ?? '', dataAsOf: insight?.data_as_of?.slice(0, 10) ?? '',
        tr: { coach: t('Praxys Coach'), metrics: t('Training metrics'), key: t('Key recommendation'),
          findings: t('Findings'), recommendations: t('Recommendations'), refresh: t('Refresh'),
          dataThrough: t('Data through'), methods: t('Training methods') },
      });
    },
    toggle() {
      const open = !this.data.detailsOpen;
      this.setData({ detailsOpen: open, detailLabel: coachToggleLabel(
        this.data.receipt?.findings.length ?? 0, this.data.remaining.length, open) });
      if (open) this.triggerEvent('detailsopen');
    },
    refresh() { this.triggerEvent('refresh'); },
    stale() { this.triggerEvent('refresh'); },
    openTheory(event: WechatMiniprogram.TouchEvent) {
      const pillar = String(event.currentTarget.dataset.pillar ?? '');
      if (['recovery', 'load', 'prediction', 'zones'].includes(pillar)) {
        wx.navigateTo({ url: `/pages/science/index?pillar=${pillar}` });
      }
    },
  },
});
