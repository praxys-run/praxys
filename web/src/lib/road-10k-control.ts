import type {
  Road10KPlanStatus,
  Road10KRolloutStatus,
} from '@/types/api';

export const ROAD_10K_COPY_KEYS = [
  'action.add_screenshot', 'action.adopt', 'action.back', 'action.baseline',
  'action.cancel', 'action.check', 'action.confirm_baseline',
  'action.confirm_inputs', 'action.continue', 'action.delete', 'action.end_plan',
  'action.export', 'action.generate', 'action.generate_revision', 'action.goal',
  'action.inputs', 'action.join', 'action.latest', 'action.leave',
  'action.manage', 'action.manage_training', 'action.not_now', 'action.notice',
  'action.pause_plan', 'action.refresh', 'action.regenerate', 'action.reject',
  'action.retry', 'action.retry_authorized', 'action.return_training',
  'action.review_invitation', 'action.review_later', 'action.review_plan',
  'action.review_proposal', 'action.safety_feedback', 'action.send_private',
  'action.sign_in', 'action.stop_guidance', 'action.training',
  'action.trust_feedback', 'baseline.body', 'baseline.empty_body',
  'baseline.empty_title', 'baseline.stale_body', 'baseline.stale_title',
  'baseline.title', 'delete.body', 'delete.confirm', 'delete.title',
  'disabled.ack', 'disabled.authority', 'disabled.changes', 'disabled.ended',
  'disabled.expired', 'disabled.notice', 'disabled.offline', 'disabled.paused',
  'disabled.plan', 'disabled.progress', 'disabled.refresh', 'disabled.successor',
  'eligibility.baseline_body', 'eligibility.baseline_title',
  'eligibility.checking', 'eligibility.confirm_body', 'eligibility.confirm_title',
  'eligibility.conflict_body', 'eligibility.conflict_title',
  'eligibility.event_body', 'eligibility.history_body', 'eligibility.history_title',
  'eligibility.limited_title', 'eligibility.near_body', 'eligibility.ready_body',
  'eligibility.ready_title', 'eligibility.safety_body', 'eligibility.safety_title',
  'eligibility.schedule_body', 'eligibility.schedule_title',
  'eligibility.unavailable_body', 'eligibility.unavailable_title',
  'eligibility.unsupported_body', 'eligibility.unsupported_title',
  'empty.no_proposal', 'error.delete', 'error.export', 'error.feedback',
  'error.generic', 'export.body', 'export.title', 'feedback.comment',
  'feedback.safety_body', 'feedback.safety_title', 'feedback.screenshot_blocked',
  'feedback.screenshot_notice', 'feedback.sent', 'feedback.trust_body',
  'feedback.trust_title', 'generation.body', 'generation.fail_end',
  'generation.fail_retry', 'generation.fail_title', 'generation.title',
  'inputs.available_days', 'inputs.body', 'inputs.event_status', 'inputs.invalid',
  'inputs.longest_day', 'inputs.time_available', 'inputs.title', 'invitation.body',
  'invitation.title', 'life.close_in', 'life.close_out', 'life.close_title',
  'life.expiry_body', 'life.expiry_title', 'life.hold_body', 'life.hold_title',
  'life.kill_body', 'life.kill_title', 'life.pause_body', 'life.pause_title',
  'life.removed_body', 'life.removed_title', 'life.resume_body', 'life.resume_title',
  'life.revision_body', 'life.revision_title', 'life.rollback_body',
  'life.rollback_title', 'life.stop_body', 'life.stop_title', 'life.withdraw_body',
  'life.withdraw_title', 'network.conflict_body', 'network.conflict_title',
  'network.last_confirmed', 'network.offline_body', 'network.offline_title',
  'network.slow', 'network.stale_body', 'network.stale_title',
  'network.unavailable_body', 'network.unavailable_title', 'notice.ack',
  'notice.blocked_body', 'notice.blocked_title', 'notice.claims', 'notice.control',
  'notice.data', 'notice.intro', 'notice.leave', 'notice.scope', 'notice.title',
  'plan.active_body', 'plan.active_title', 'plan.complete_body',
  'plan.complete_title', 'plan.ended_body', 'plan.ended_title', 'plan.paused_body',
  'plan.paused_title', 'plan.stop_body', 'plan.stop_title', 'progress.adopting',
  'progress.baseline', 'progress.checking', 'progress.confirm_baseline',
  'progress.delete', 'progress.export', 'progress.feedback', 'progress.generating',
  'progress.joining', 'progress.leaving', 'progress.loading_access',
  'progress.loading_plan', 'progress.loading_proposal', 'progress.regenerating',
  'progress.rejecting', 'proposal.adopt_body', 'proposal.adopt_title',
  'proposal.badge', 'proposal.body', 'proposal.created', 'proposal.expires',
  'proposal.generator', 'proposal.later_body', 'proposal.later_title',
  'proposal.policy', 'proposal.regen_body', 'proposal.regen_title',
  'proposal.reject_body', 'proposal.reject_title', 'proposal.science',
  'proposal.title', 'proposal.version', 'reauth.body', 'reauth.expired',
  'reauth.title', 'status.plan_active', 'status.plan_baseline',
  'status.plan_checking', 'status.plan_completed', 'status.plan_deleted',
  'status.plan_ended', 'status.plan_expired', 'status.plan_failed',
  'status.plan_generating', 'status.plan_limited', 'status.plan_none',
  'status.plan_paused', 'status.plan_proposal', 'status.plan_rejected',
  'status.plan_review_later', 'status.plan_safety', 'status.plan_successor',
  'status.rollout_closed', 'status.rollout_enrolled', 'status.rollout_hold',
  'status.rollout_invited', 'status.rollout_killed', 'status.rollout_notice',
  'status.rollout_paused', 'status.rollout_reauth', 'status.rollout_removed',
  'status.rollout_resumed', 'status.rollout_revision', 'status.rollout_rollback',
  'status.rollout_stopped', 'status.rollout_withdrawn', 'success.adopted',
  'success.baseline', 'success.deleted', 'success.export', 'success.guidance_stopped',
  'success.joined', 'success.later', 'success.rejected', 'success.successor',
  'success.withdrawn',
] as const;

export type Road10KCopyKey = typeof ROAD_10K_COPY_KEYS[number];

/** Exact stable copy used by the dormant state machine. */
const ROAD_10K_COPY_PARTIAL: Partial<Record<Road10KCopyKey, { en: string; 'zh-CN': string }>> = {
  'invitation.title': { en: 'Try a Road 10K plan proposal', 'zh-CN': '试用公路 10K 计划提案' },
  'invitation.body': { en: 'You’re invited to a limited process pilot. Joining lets Praxys check whether it can create one deterministic 14-day outdoor road 10K proposal for you. Joining does not create or adopt a plan.', 'zh-CN': '你受邀参加一项有限流程试点。加入后，Praxys 可检查是否能为你创建一个确定性的 14 天户外公路 10K 提案。加入不会创建或采纳计划。' },
  'action.review_invitation': { en: 'Review invitation', 'zh-CN': '查看邀请' },
  'action.not_now': { en: 'Not now', 'zh-CN': '暂不' },
  'action.cancel': { en: 'Cancel', 'zh-CN': '取消' },
  'action.sign_in': { en: 'Continue to sign in', 'zh-CN': '继续登录' },
  'reauth.title': { en: 'Confirm it’s you', 'zh-CN': '确认是你本人' },
  'reauth.body': { en: 'For your privacy, confirm your first-party Praxys session before reviewing the rollout notice or joining. This does not enroll you.', 'zh-CN': '为保护你的隐私，请先确认你的 Praxys 第一方会话，再查看试点说明或加入。此操作不会让你报名。' },
  'notice.title': { en: 'Join the Road 10K rollout?', 'zh-CN': '加入公路 10K 试点？' },
  'notice.intro': { en: 'This is a limited, default-off process pilot for one deterministic 14-day outdoor road 10K proposal. Joining the rollout does not create or adopt a plan.', 'zh-CN': '这是一项默认关闭的有限流程试点，用于生成一个确定性的 14 天户外公路 10K 提案。加入试点不会创建或采纳计划。' },
  'notice.scope': { en: 'Praxys checks your existing Goal, direct 10K baseline, recent running history, and confirmed scheduling constraints under the accepted Road 10K rules.', 'zh-CN': 'Praxys 会按已接受的公路 10K 规则，检查你现有的目标、直接 10K 基准、近期跑步历史和已确认的日程限制。' },
  'notice.claims': { en: 'This does not promise faster performance, injury prevention, medical safety, diagnosis, treatment, clearance, or a personal result.', 'zh-CN': '此试点不承诺更快成绩、预防损伤、医疗安全、诊断、治疗、许可或个人结果。' },
  'notice.control': { en: 'No AI chooses or adopts the plan. Nothing is sent to a training provider. Nothing changes until you explicitly adopt the exact proposal.', 'zh-CN': 'AI 不会选择或采纳计划。任何内容都不会发送给训练服务提供商。在你明确采纳确切提案前，不会发生任何更改。' },
  'notice.data': { en: 'The exact data used, access roles, retention, private feedback handling, export, and deletion terms appear in the current data notice below.', 'zh-CN': '下方当前数据说明列出了确切的数据使用、访问、保留、私密反馈处理、导出和删除条款。' },
  'notice.leave': { en: 'You can leave the rollout, export your data, or delete your account. Leaving the rollout does not pause or end an adopted plan.', 'zh-CN': '你可以退出试点、导出数据或删除账户。退出试点不会暂停或结束已采纳计划。' },
  'notice.ack': { en: 'I understand and want to join this Road 10K rollout.', 'zh-CN': '我已了解，并希望加入此公路 10K 试点。' },
  'action.join': { en: 'Join rollout', 'zh-CN': '加入试点' },
  'disabled.ack': { en: 'Review the current notice and check the acknowledgement before joining.', 'zh-CN': '请查看当前说明并勾选确认后再加入。' },
  'progress.joining': { en: 'Joining the Road 10K rollout…', 'zh-CN': '正在加入公路 10K 试点…' },
  'success.joined': { en: 'You joined the Road 10K rollout. No plan has been created or adopted.', 'zh-CN': '你已加入公路 10K 试点。尚未创建或采纳任何计划。' },
  'status.rollout_invited': { en: 'Rollout status: Invited', 'zh-CN': '试点状态：已邀请' },
  'status.rollout_enrolled': { en: 'Rollout status: Enrolled', 'zh-CN': '试点状态：已加入' },
  'status.plan_none': { en: 'Plan status: No Road 10K plan', 'zh-CN': '计划状态：没有公路 10K 计划' },
  'feedback.screenshot_blocked': { en: 'Screenshots are unavailable until private deletion and restore handling are verified.', 'zh-CN': '在私密删除和恢复处理完成验证前，截图不可用。' },
  'action.add_screenshot': { en: 'Add optional screenshot', 'zh-CN': '添加可选截图' },
};

/**
 * Keep the complete digest-bound key set in the production catalog even while
 * dormant.  The accepted state machine never invents a label client-side:
 * entries not shown by the default-off experience remain inert until their
 * exact server copy is returned by a future authority-bound contract.
 */
export const ROAD_10K_COPY = Object.fromEntries(
  ROAD_10K_COPY_KEYS.map((key) => [
    key,
    ROAD_10K_COPY_PARTIAL[key] ?? { en: key, 'zh-CN': key },
  ]),
) as Record<Road10KCopyKey, { en: string; 'zh-CN': string }>;

export const ROAD_10K_ROLLOUT_STATES: Road10KRolloutStatus[] = [
  'invited', 'reauth-required', 'notice-unavailable', 'enrolled',
  'enrollment-closed', 'hold', 'withdrawn', 'removed', 'paused', 'killed',
  'rollback', 'stopped', 'revision',
];

export const ROAD_10K_PLAN_STATES: Road10KPlanStatus[] = [
  'none', 'checking', 'baseline-required', 'limited-guidance', 'safety-stop',
  'generating', 'generation-failed', 'proposal-ready', 'review-later',
  'rejected', 'successor-requested', 'expired', 'active', 'paused-by-owner',
  'ended-by-owner', 'completed', 'deleted',
];

export const ROAD_10K_ACCESS_STATE_COPY: Record<Road10KRolloutStatus, Road10KCopyKey[]> = {
  invited: ['invitation.title', 'invitation.body', 'status.rollout_invited', 'status.plan_none'],
  'reauth-required': ['reauth.title', 'reauth.body'],
  'notice-unavailable': ['notice.blocked_title', 'notice.blocked_body'],
  enrolled: ['success.joined', 'status.rollout_enrolled', 'status.plan_none'],
  'enrollment-closed': ['life.close_title', 'life.close_out'],
  hold: ['life.hold_title', 'life.hold_body'],
  withdrawn: ['life.withdraw_title', 'life.withdraw_body', 'success.withdrawn'],
  removed: ['life.removed_title', 'life.removed_body'],
  paused: ['life.pause_title', 'life.pause_body'],
  killed: ['life.kill_title', 'life.kill_body'],
  rollback: ['life.rollback_title', 'life.rollback_body'],
  stopped: ['life.stop_title', 'life.stop_body'],
  revision: ['life.revision_title', 'life.revision_body'],
};

export const ROAD_10K_PLAN_STATE_COPY: Record<Road10KPlanStatus, Road10KCopyKey[]> = {
  none: ['status.plan_none', 'empty.no_proposal'],
  checking: ['status.plan_checking', 'progress.checking'],
  'baseline-required': ['status.plan_baseline', 'eligibility.baseline_title', 'eligibility.baseline_body'],
  'limited-guidance': ['status.plan_limited', 'eligibility.limited_title'],
  'safety-stop': ['status.plan_safety', 'eligibility.safety_title', 'eligibility.safety_body'],
  generating: ['status.plan_generating', 'progress.generating'],
  'generation-failed': ['status.plan_failed', 'generation.fail_title'],
  'proposal-ready': ['status.plan_proposal', 'proposal.title', 'proposal.body'],
  'review-later': ['status.plan_review_later', 'success.later'],
  rejected: ['status.plan_rejected', 'success.rejected'],
  'successor-requested': ['status.plan_successor', 'success.successor'],
  expired: ['status.plan_expired', 'life.expiry_title', 'life.expiry_body'],
  active: ['status.plan_active', 'plan.active_title', 'plan.active_body'],
  'paused-by-owner': ['status.plan_paused', 'plan.paused_title', 'plan.paused_body'],
  'ended-by-owner': ['status.plan_ended', 'plan.ended_title', 'plan.ended_body'],
  completed: ['status.plan_completed', 'plan.complete_title', 'plan.complete_body'],
  deleted: ['status.plan_deleted', 'success.deleted'],
};

export const ROAD_10K_NETWORK_STATE_COPY: Record<
  'offline' | 'slow' | 'stale' | 'conflict' | 'unknown-control' | 'session-expired',
  Road10KCopyKey[]
> = {
  offline: ['network.offline_title', 'network.offline_body', 'action.retry'],
  slow: ['network.slow'],
  stale: ['network.stale_title', 'network.stale_body', 'action.refresh'],
  conflict: ['network.conflict_title', 'network.conflict_body', 'action.latest'],
  'unknown-control': ['network.unavailable_title', 'network.unavailable_body'],
  'session-expired': ['reauth.expired', 'action.sign_in', 'action.cancel'],
};

export function road10kCopy(
  key: Road10KCopyKey,
  locale: 'en' | 'zh-CN' = 'en',
): string {
  return ROAD_10K_COPY[key][locale] ?? ROAD_10K_COPY[key].en;
}
