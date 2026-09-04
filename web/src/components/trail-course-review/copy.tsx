import { useCallback, useMemo } from 'react';
import { useLingui } from '@lingui/react/macro';
import type {
  TrailAidAvailability,
  TrailAidSupportMode,
  TrailConditionsBasis,
  TrailDistanceFamily,
  TrailEventFormat,
  TrailFooting,
  TrailGastrointestinalExperience,
  TrailIntakeForm,
  TrailMandatoryGear,
  TrailModuleKey,
  TrailPlanningIntent,
  TrailProvenance,
  TrailReasonCode,
  TrailSunExposure,
  TrailWindExposure,
} from '@/types/trail-plan';
import type { GradeKey, Option, ReasonCopy } from './model';

export function useTrailCourseReviewCopy() {
  const { i18n, t } = useLingui();
  const isZh = i18n.locale.toLowerCase().startsWith('zh');
  const l = useCallback(
    (english: string, chinese: string) => isZh ? chinese : english,
    [isZh],
  );

  return useMemo(() => {

  const copy = {
    title: l(t`Review Trail event`, t`核对越野赛事`),
    support: l(
      t`Describe the course and where you can train. Praxys will keep unknowns visible.`,
      t`填写赛道情况和可训练条件。Praxys 会明确保留未知项。`,
    ),
    eventSection: l(t`Event & planning duration`, t`赛事与计划用时`),
    gradeSection: l(t`Grade & footing`, t`坡度与路面`),
    trainingSection: l(t`When and where you can train`, t`可训练时间与场地`),
    recentSection: l(t`Recent experience`, t`近期训练经历`),
    optionalSection: l(t`Conditions, support, and fueling`, t`环境、支持与补给`),
    unknown: l(t`I don't know yet`, t`目前不确定`),
    yes: l(t`Yes`, t`是`),
    no: l(t`No`, t`否`),
    notSure: l(t`Not sure`, t`不确定`),
    hours: l(t`Hours`, t`小时`),
    minutes: l(t`Minutes`, t`分钟`),
    choose: l(t`Choose one`, t`请选择`),
    event: l(t`Event`, t`赛事`),
    currentEvent: l(t`Current Trail race goal`, t`当前越野赛事目标`),
    editGoal: l(t`Edit Goal`, t`编辑目标`),
    eventDate: l(t`Event date`, t`比赛日期`),
    raceDistance: l(t`Race distance`, t`比赛距离`),
    totalAscent: l(t`Total ascent`, t`累计爬升`),
    totalDescent: l(t`Total descent`, t`累计下降`),
    planningMinimum: l(t`Minimum planning duration`, t`计划用时下限`),
    planningMaximum: l(t`Maximum planning duration`, t`计划用时上限`),
    planningHelp: l(
      t`The range you want Praxys to plan around—not a finish-time prediction.`,
      t`这是你希望 Praxys 用于制定计划的时长范围，并非完赛时间预测。`,
    ),
    eventFormat: l(t`Event format`, t`比赛形式`),
    distanceCategory: l(t`Distance category`, t`距离类别`),
    planningGoal: l(t`Planning goal`, t`计划目标`),
    gradeDistribution: l(t`Course grade distribution`, t`赛道坡度分布`),
    gradeExplanation: l(
      t`Enter percentages for the five fixed grade bands. The total must be exactly 100.00%.`,
      t`为五个固定坡度区间输入百分比，合计必须正好为 100.00%。`,
    ),
    total: l(t`Total`, t`合计`),
    footing: l(t`Course footing`, t`赛道路面`),
    hands: l(
      t`Does any section require hands for progress?`,
      t`是否有路段需要用手辅助通过？`,
    ),
    rope: l(
      t`Does any section use fixed ropes?`,
      t`是否有路段需要使用固定绳索？`,
    ),
    availableDays: l(t`Days available to run`, t`可跑步的星期`),
    weeklyTime: l(t`Weekly training time available`, t`每周可训练时间`),
    longestSession: l(t`Longest training session available`, t`单次最长可训练时间`),
    unavailableDates: l(t`Dates you cannot train`, t`无法训练的日期`),
    noDates: l(t`No dates`, t`无`),
    addDate: l(t`Add date`, t`添加日期`),
    removeDate: l(t`Remove date`, t`移除日期`),
    preferredDay: l(
      t`Preferred day for the longest easy session`,
      t`最长轻松训练的首选星期`,
    ),
    noPreference: l(t`No preference`, t`无偏好`),
    uphillAccess: l(
      t`Can you access a continuous, nontechnical uphill for at least 3 minutes?`,
      t`你能使用可连续进行至少 3 分钟、非技术性的上坡路线吗？`,
    ),
    downhillAccess: l(
      t`Can you access terrain for controlled downhill training?`,
      t`你能使用适合受控下坡训练的路线吗？`,
    ),
    trainingFooting: l(t`Footing available for training`, t`可用于训练的路面`),
    adultScope: l(
      t`I confirm I am 18 or older and this is not clinical or return-to-sport planning.`,
      t`我确认本人已满 18 岁，且这不是医疗或重返运动计划。`,
    ),
    performanceScope: l(
      t`I confirm the goal is race performance.`,
      t`我确认目标是提升比赛表现。`,
    ),
    symptoms: l(
      t`Do you currently have symptoms that should stop performance planning?`,
      t`你目前是否有应停止竞速计划的症状？`,
    ),
    continuity: l(t`Recent running continuity`, t`近期跑步连续性`),
    ascentExposure: l(t`Recent ascent exposure`, t`近期爬升训练`),
    descentExposure: l(t`Recent descent exposure`, t`近期下降训练`),
    observedFooting: l(t`Recently observed footing`, t`近期记录到的路面`),
    observationWindow: l(t`Observation window`, t`观察窗口`),
    freshness: l(t`Freshness`, t`新鲜度`),
    serverSource: l(t`Server source`, t`服务端来源`),
    sourceRevision: l(t`Source revision`, t`来源版本`),
    notEvaluated: l(t`Not evaluated`, t`尚未评估`),
    compareHistory: l(
      t`Requested versus observed comparison`,
      t`请求与已观察情况对照`,
    ),
    historyComparisonHelp: l(
      t`The requested weekly and single-session limits are shown beside the server-observed history. This comparison does not increase the accepted history envelope.`,
      t`请求的每周和单次训练上限与服务端观察历史并列显示。此对照不会提高已接受的历史边界。`,
    ),
    environment: l(t`Environment`, t`环境`),
    supportGroup: l(t`Support`, t`支持`),
    fueling: l(t`Fueling`, t`补给`),
    setGroupUnknown: l(t`Set this group to unknown`, t`将本组设为未知`),
    maximumAltitude: l(t`Maximum course altitude`, t`赛道最高海拔`),
    temperatureRange: l(t`Expected temperature range`, t`预计气温范围`),
    minimumTemperature: l(t`Minimum temperature`, t`最低气温`),
    maximumTemperature: l(t`Maximum temperature`, t`最高气温`),
    humidityRange: l(t`Expected humidity range`, t`预计湿度范围`),
    minimumHumidity: l(t`Minimum humidity`, t`最低湿度`),
    maximumHumidity: l(t`Maximum humidity`, t`最高湿度`),
    sunExposure: l(t`Sun exposure`, t`日晒暴露`),
    windExposure: l(t`Wind exposure`, t`风力暴露`),
    conditionsBasis: l(t`Conditions based on`, t`环境信息依据`),
    assumptionHelp: l(
      t`Your assumption requires confirmation at this exact section revision.`,
      t`你的假设需要按本节的确切版本确认。`,
    ),
    supportSetup: l(t`Support setup`, t`补给支持方式`),
    aidCount: l(t`Number of aid stations`, t`补给站数量`),
    aidGap: l(t`Longest gap between aid stations`, t`最长补给站间距`),
    notApplicable: l(t`Not applicable`, t`不适用`),
    enterDistance: l(t`Enter a distance`, t`输入距离`),
    water: l(t`Water availability`, t`饮水供应`),
    food: l(t`Food availability`, t`食物供应`),
    requiredEquipment: l(t`Required equipment`, t`强制装备`),
    noEquipment: l(t`No required equipment listed`, t`未列出强制装备`),
    fuelingDuration: l(t`Longest practiced fueling duration`, t`最长补给练习时长`),
    fuelingSessions: l(
      t`Fueling practice sessions in the past 42 days`,
      t`过去 42 天的补给练习次数`,
    ),
    intake: l(t`Practiced intake`, t`已练习的摄入形式`),
    gutIssue: l(
      t`Did stomach or gut issues change your plan?`,
      t`胃肠不适是否曾让你改变计划？`,
    ),
    confirmSection: l(t`Confirm this section`, t`确认本节`),
    confirmedRevision: l(t`Confirmed for revision`, t`已确认版本`),
    changedConfirmAgain: l(t`Changed—confirm again`, t`已更改，请重新确认`),
    saveBeforeConfirming: l(t`Save this section before confirming`, t`确认前请先保存本节`),
    readinessTitle: l(t`Readiness receipt`, t`准备情况回执`),
    checkReadiness: l(t`Check readiness`, t`检查准备情况`),
    saveLeave: l(t`Save and leave`, t`保存并稍后继续`),
    save: l(t`Save changes`, t`保存更改`),
    pending: l(t`Pending changes`, t`待保存更改`),
    onlineSaved: l(t`Online · saved`, t`在线 · 已保存`),
    notSaved: l(t`No course review has been saved yet`, t`尚未保存赛道核对`),
    offline: l(
      t`Offline. Changes are kept only on this page and have not been saved.`,
      t`当前离线。更改仅保留在此页面，尚未保存。`,
    ),
    slow: l(
      t`This request is taking longer than usual. Do not close this page.`,
      t`此请求用时较长，请勿关闭本页面。`,
    ),
    errorSummary: l(t`Review these fields`, t`请检查以下字段`),
    fieldError: l(
      t`This value is missing, outside the accepted range, or conflicts with another answer.`,
      t`此值缺失、超出允许范围，或与另一项回答冲突。`,
    ),
    moreActions: l(t`More actions`, t`更多操作`),
    reset: l(t`Reset course review`, t`重置赛道核对`),
    export: l(t`Export my Trail plan data`, t`导出我的越野计划数据`),
    exportUnavailable: l(
      t`Export isn't available in this private preview yet.`,
      t`当前私密预览暂不支持导出。`,
    ),
    delete: l(t`Delete Trail goal`, t`删除越野目标`),
    resetTitle: l(t`Reset course review?`, t`重置赛道核对？`),
    resetExplanation: l(
      t`Reset replaces the current editable answers with unknowns. It does not erase source activities or retained proposal records.`,
      t`重置会把当前可编辑回答改为未知；不会删除来源活动或已保留的提案记录。`,
    ),
    deleteTitle: l(t`Delete Trail goal?`, t`删除越野目标？`),
    deleteExplanation: l(
      t`Deleting the Trail goal is different from deleting your account. This requests removal of its owned draft, snapshots, proposals, audits, indexes, and caches. Praxys reports completion only from the server response; rollback or cleanup-pending must remain visible.`,
      t`删除越野目标不同于删除账号。此操作请求移除该目标拥有的草稿、快照、提案、审计、索引和缓存。Praxys 只依据服务端响应报告完成；回滚或清理待处理状态必须保持可见。`,
    ),
    cancel: l(t`Cancel`, t`取消`),
    confirmReset: l(t`Confirm reset`, t`确认重置`),
    confirmDelete: l(t`Confirm deletion`, t`确认删除`),
    reviewLatest: l(t`Review latest version`, t`查看最新版本`),
    restorePending: l(t`Restore pending changes`, t`恢复待保存更改`),
    discardPending: l(t`Discard pending changes`, t`放弃待保存更改`),
    staleTitle: l(t`The Trail course review changed`, t`越野赛道核对已更改`),
    staleExplanation: l(
      t`Pending edits were kept only in this page. Compare the latest server version, then reapply or discard them. Reapplying does not save or confirm.`,
      t`待保存编辑仅保留在本页面。请对照最新服务端版本，再重新应用或放弃。重新应用不会保存或确认。`,
    ),
    noReceipt: l(
      t`Confirm every visible editable section to check readiness. Confirmation is review, not proof of safety or eligibility.`,
      t`请确认每个可见可编辑分段后检查准备情况。确认表示已核对，不代表安全或符合生成条件。`,
    ),
    finding: l(t`Finding`, t`发现`),
    effect: l(t`Effect`, t`影响`),
    nextAction: l(t`Next action`, t`下一步`),
    modules: l(t`Authoritative readiness modules`, t`权威准备情况模块`),
    available: l(t`Available`, t`可用于生成`),
    limited: l(t`Limited`, t`受限`),
    moduleLimitedHelp: l(
      t`This module would be omitted from generation unless its linked reason is resolved.`,
      t`如未解决所链接原因，生成时将省略此模块。`,
    ),
    moduleAvailableHelp: l(
      t`Generation may consider this module. It is not yet included in a proposal.`,
      t`生成时可考虑此模块；它尚未包含在任何提案中。`,
    ),
    moduleNotEvaluatedHelp: l(
      t`This module has not been evaluated for the current revision.`,
      t`尚未针对当前版本评估此模块。`,
    ),
    retry: l(t`Retry`, t`重试`),
    fromHistory: l(t`From your activity history`, t`来自你的活动历史`),
    modelVersion: l(t`Model version`, t`模型版本`),
  };

  const provenanceLabels: Record<TrailProvenance, string> = {
    athlete_stated: l(t`You entered this`, t`由你填写`),
    course_verified: l(t`Verified course information`, t`已核实的赛道信息`),
    history_observed: l(t`From your activity history`, t`来自你的活动历史`),
    model_inferred: l(t`Estimated by Praxys`, t`由 Praxys 推断`),
    explicit_assumption: l(
      t`Your assumption—confirmation required`,
      t`你的假设—需要确认`,
    ),
    unknown: l(t`Unknown`, t`未知`),
  };

  const eventFormatOptions: readonly Option<TrailEventFormat>[] = [
    { value: 'single_day', label: l(t`One-day event`, t`单日赛事`) },
    { value: 'multi_day', label: l(t`Multi-day event`, t`多日赛事`) },
  ];
  const distanceFamilyOptions: readonly Option<TrailDistanceFamily>[] = [
    { value: 'non_ultra', label: l(t`Non-ultra Trail`, t`非超长距离越野`) },
    { value: 'ultra', label: l(t`Ultra-distance Trail`, t`超长距离越野`) },
  ];
  const planningIntentOptions: readonly Option<TrailPlanningIntent>[] = [
    { value: 'performance', label: l(t`Improve race performance`, t`提升比赛表现`) },
    { value: 'first_completion', label: l(t`Finish the event`, t`完成赛事`) },
    { value: 'return_to_consistency', label: l(t`Rebuild training consistency`, t`恢复训练规律`) },
  ];
  const footingOptions: readonly Option<TrailFooting>[] = [
    { value: 'firm_smooth', label: l(t`Firm, smooth trail`, t`坚实平整路面`) },
    { value: 'loose_gravel', label: l(t`Loose gravel`, t`松散碎石`) },
    { value: 'mud', label: l(t`Mud`, t`泥地`) },
    { value: 'rocks_or_roots', label: l(t`Rocks or roots`, t`岩石或树根`) },
    { value: 'built_steps', label: l(t`Built steps`, t`人工台阶`) },
    { value: 'water_crossing', label: l(t`Water crossings`, t`涉水路段`) },
  ];
  const weekdayOptions: readonly Option<number>[] = [
    { value: 1, label: l(t`Monday`, t`星期一`) },
    { value: 2, label: l(t`Tuesday`, t`星期二`) },
    { value: 3, label: l(t`Wednesday`, t`星期三`) },
    { value: 4, label: l(t`Thursday`, t`星期四`) },
    { value: 5, label: l(t`Friday`, t`星期五`) },
    { value: 6, label: l(t`Saturday`, t`星期六`) },
    { value: 7, label: l(t`Sunday`, t`星期日`) },
  ];
  const sunOptions: readonly Option<TrailSunExposure>[] = [
    { value: 'low', label: l(t`Low`, t`低`) },
    { value: 'mixed', label: l(t`Mixed`, t`混合`) },
    { value: 'high', label: l(t`High`, t`高`) },
  ];
  const windOptions: readonly Option<TrailWindExposure>[] = [
    { value: 'sheltered', label: l(t`Sheltered`, t`遮蔽`) },
    { value: 'mixed', label: l(t`Mixed`, t`混合`) },
    { value: 'exposed', label: l(t`Exposed`, t`暴露`) },
  ];
  const conditionsOptions: readonly Option<TrailConditionsBasis>[] = [
    { value: 'organizer_information', label: l(t`Organizer information`, t`赛事方信息`) },
    { value: 'seasonal_expectation', label: l(t`Seasonal expectation`, t`季节预期`) },
    { value: 'athlete_assumption', label: l(t`My assumption`, t`我的假设`) },
  ];
  const supportOptions: readonly Option<TrailAidSupportMode>[] = [
    { value: 'organized_aid', label: l(t`Organized aid`, t`赛事补给`) },
    { value: 'mixed', label: l(t`Mixed`, t`混合`) },
    { value: 'self_supported', label: l(t`Self-supported`, t`自助`) },
  ];
  const availabilityOptions: readonly Option<TrailAidAvailability>[] = [
    { value: 'none', label: l(t`None`, t`无`) },
    { value: 'some_stations', label: l(t`Some stations`, t`部分站点`) },
    { value: 'all_stations', label: l(t`Every station`, t`每个站点`) },
  ];
  const gearOptions: readonly Option<TrailMandatoryGear>[] = [
    { value: 'water_carry', label: l(t`Carry water`, t`携水`) },
    { value: 'food_carry', label: l(t`Carry food`, t`携带食物`) },
    { value: 'weather_shell', label: l(t`Weather shell`, t`防风雨外套`) },
    { value: 'lighting', label: l(t`Lighting`, t`照明`) },
    { value: 'navigation_device', label: l(t`Navigation device`, t`导航设备`) },
    { value: 'other_required', label: l(t`Other required`, t`其他必需装备`) },
  ];
  const intakeOptions: readonly Option<TrailIntakeForm>[] = [
    { value: 'none', label: l(t`None`, t`无`) },
    { value: 'fluids_only', label: l(t`Fluids only`, t`仅液体`) },
    { value: 'carbohydrate_drink', label: l(t`Carbohydrate drink`, t`碳水饮料`) },
    { value: 'mixed_food_and_drink', label: l(t`Mixed food and drink`, t`食物与饮品混合`) },
  ];
  const gutOptions: readonly Option<TrailGastrointestinalExperience>[] = [
    { value: 'no_plan_altering_issue', label: l(t`No plan-altering issue`, t`未影响计划`) },
    { value: 'plan_altering_issue', label: l(t`Plan-altering issue`, t`曾影响计划`) },
  ];

  const gradeLabels: Record<GradeKey, string> = {
    below_neg_10: l(t`Steep downhill (below −10%)`, t`陡下坡（低于 −10%）`),
    neg_10_to_below_neg_3: l(t`Downhill (−10% to below −3%)`, t`下坡（−10% 至低于 −3%）`),
    neg_3_to_below_pos_3: l(t`Near level (−3% to below 3%)`, t`近似平缓（−3% 至低于 3%）`),
    pos_3_to_below_pos_10: l(t`Uphill (3% to below 10%)`, t`上坡（3% 至低于 10%）`),
    pos_10_and_above: l(t`Steep uphill (10% and above)`, t`陡上坡（10% 及以上）`),
  };

  const reasonCatalog = {
    'validation_failed.invalid_field_value': {
      finding: l(
        t`One or more values is outside the accepted format or range.`,
        t`一项或多项数据不符合格式或范围要求。`,
      ),
      effect: l(
        t`Praxys cannot interpret this revision safely.`,
        t`Praxys 无法安全解释当前版本。`,
      ),
      target: 'action.first-invalid-field',
      action: l(t`Review the first invalid value`, t`查看首个无效值`),
    },
    'validation_failed.schema_version_mismatch': {
      finding: l(
        t`This course review was created with an unsupported version.`,
        t`此赛道核对使用了不受支持的版本。`,
      ),
      effect: l(
        t`Praxys will not guess how old or future fields map to v2.`,
        t`Praxys 不会猜测旧版或未来字段如何映射到 v2。`,
      ),
      target: 'action.reload-supported-version',
      action: l(t`Reload the supported version`, t`重新加载受支持版本`),
    },
    'validation_failed.deterministic_invariant_failed': {
      finding: l(
        t`Praxys could not reproduce the same readiness receipt.`,
        t`Praxys 无法复现同一份准备情况回执。`,
      ),
      effect: l(
        t`No proposal can be trusted from this result.`,
        t`无法信任基于此结果生成的提案。`,
      ),
      target: 'action.retry-readiness',
      action: l(t`Retry the readiness check`, t`重新检查准备情况`),
    },
    'policy_unavailable.policy_inactive': {
      finding: l(t`This Trail policy is not active.`, t`此越野策略尚未启用。`),
      effect: l(
        t`No proposal is available from this inactive slice.`,
        t`此未启用切片不能生成提案。`,
      ),
      target: 'section.policy-receipt',
      action: l(t`Review policy status`, t`查看策略状态`),
    },
    'policy_unavailable.event_inside_unapproved_taper_window': {
      finding: l(
        t`The event is inside a period without an accepted taper policy.`,
        t`比赛已进入尚无获批减量策略的阶段。`,
      ),
      effect: l(
        t`This policy cannot organize the event-near period.`,
        t`此策略无法安排临赛阶段。`,
      ),
      target: 'field.event-date',
      action: l(t`Review the event date`, t`查看比赛日期`),
    },
    'policy_unavailable.unsupported_ultra_or_multiday': {
      finding: l(
        t`This event is ultra-distance or multiday.`,
        t`此赛事属于超长距离或多日赛。`,
      ),
      effect: l(
        t`It is outside the non-ultra, one-day policy.`,
        t`它超出非超长距离单日策略范围。`,
      ),
      target: 'field.event-scope',
      action: l(t`Review event scope`, t`查看赛事范围`),
    },
    'policy_unavailable.unsupported_population_or_intent': {
      finding: l(
        t`The confirmed context or goal is outside this performance policy.`,
        t`已确认的适用场景或目标不在此竞速策略范围内。`,
      ),
      effect: l(
        t`Praxys will not substitute another population or intent.`,
        t`Praxys 不会替换为其他人群或目标。`,
      ),
      target: 'field.adult-performance-scope',
      action: l(t`Review planning scope`, t`查看计划适用范围`),
    },
    'policy_unavailable.technical_features_outside_v2': {
      finding: l(
        t`The course requires hands assistance or fixed ropes.`,
        t`赛道需要用手辅助或使用固定绳索。`,
      ),
      effect: l(t`Those technical features are outside v2.`, t`这些技术特征超出 v2 范围。`),
      target: 'action.first-confirmed-hazard',
      action: l(t`Review the technical feature`, t`查看技术特征`),
    },
    'readiness_blocked.insufficient_recent_running_history': {
      finding: l(
        t`Recent running continuity is below the accepted history gate.`,
        t`近期跑步连续性未达到已接受的历史门槛。`,
      ),
      effect: l(
        t`Praxys cannot anchor a proposal to enough recent running.`,
        t`Praxys 无法用足够的近期跑步记录约束提案。`,
      ),
      target: 'field.history-running',
      action: l(t`Review recent running`, t`查看近期跑步记录`),
    },
    'readiness_blocked.insufficient_comparable_trail_history': {
      finding: l(
        t`Comparable Trail, ascent, or footing history is insufficient.`,
        t`可比的越野、爬升或路面训练历史不足。`,
      ),
      effect: l(
        t`Course-specific work cannot be bounded from observed experience.`,
        t`无法依据已观察经历约束赛道专项训练。`,
      ),
      target: 'field.history-comparable-trail',
      action: l(t`Review comparable experience`, t`查看可比训练经历`),
    },
    'readiness_blocked.insufficient_descent_history': {
      finding: l(
        t`Recent descent exposure is insufficient.`,
        t`近期下降训练经历不足。`,
      ),
      effect: l(
        t`Downhill work cannot be bounded from observed history.`,
        t`无法依据已观察历史约束下坡训练。`,
      ),
      target: 'field.history-descent',
      action: l(t`Review descent experience`, t`查看下降训练经历`),
    },
    'readiness_blocked.insufficient_terrain_access': {
      finding: l(
        t`Required uphill, downhill, or footing access is unavailable.`,
        t`缺少所需的上坡、下坡或路面训练条件。`,
      ),
      effect: l(
        t`Praxys will not replace the course demand with road training.`,
        t`Praxys 不会用公路训练替代赛道需求。`,
      ),
      target: 'section.training-access',
      action: l(t`Review training access`, t`查看训练场地条件`),
    },
    'readiness_blocked.current_symptom_stop': {
      finding: l(
        t`You confirmed a current symptom that should stop performance planning.`,
        t`你确认目前有应停止竞速计划的症状。`,
      ),
      effect: l(
        t`Performance planning stops; Praxys makes no diagnosis.`,
        t`竞速计划将停止；Praxys 不作诊断。`,
      ),
      target: 'field.symptom-stop',
      action: l(t`Review your response`, t`查看你的回答`),
    },
    'readiness_blocked.no_schedule_within_envelope': {
      finding: l(
        t`No 14-day schedule fits the confirmed availability and accepted limits.`,
        t`没有 14 天安排能同时满足已确认时间和已接受限制。`,
      ),
      effect: l(
        t`Praxys will not compress, stack, or substitute sessions.`,
        t`Praxys 不会压缩、堆叠或替换训练。`,
      ),
      target: 'section.training-access',
      action: l(t`Review your schedule`, t`查看训练时间安排`),
    },
    'clarification_required.material_course_demand_unknown': {
      finding: l(t`A core course detail is still unknown.`, t`仍有核心赛道信息未知。`),
      effect: l(
        t`Readiness cannot be decided without that detail.`,
        t`缺少该信息时无法判断准备情况。`,
      ),
      target: 'action.first-unknown-core-field',
      action: l(t`Complete the next course detail`, t`补充下一项赛道信息`),
    },
    'clarification_required.assumption_confirmation_required': {
      finding: l(
        t`A course or conditions assumption has not been confirmed.`,
        t`一项赛道或环境假设尚未确认。`,
      ),
      effect: l(
        t`Praxys will not treat an assumption as reviewed fact.`,
        t`Praxys 不会把未确认假设当作已核对事实。`,
      ),
      target: 'action.first-unconfirmed-assumption',
      action: l(t`Review the assumption`, t`查看该假设`),
    },
    'clarification_required.adult_scope_or_constraints_unconfirmed': {
      finding: l(
        t`Adult, non-clinical performance scope is not confirmed.`,
        t`尚未确认成人、非医疗的竞速适用范围。`,
      ),
      effect: l(t`This policy cannot be applied yet.`, t`暂时无法应用此策略。`),
      target: 'field.adult-performance-scope',
      action: l(t`Confirm planning scope`, t`确认计划适用范围`),
    },
    'clarification_required.training_constraints_missing': {
      finding: l(
        t`A required schedule, access, or symptom answer is missing.`,
        t`缺少必填的时间、场地或症状回答。`,
      ),
      effect: l(
        t`Praxys cannot evaluate the complete planning envelope.`,
        t`Praxys 无法评估完整计划边界。`,
      ),
      target: 'action.first-missing-training-field',
      action: l(t`Complete the next training detail`, t`补充下一项训练信息`),
    },
    'clarification_required.training_constraints_outside_history_envelope': {
      finding: l(
        t`A requested workload or edit is above recent observed history.`,
        t`请求的训练量或编辑超出近期已观察历史。`,
      ),
      effect: l(
        t`Praxys will not increase the accepted history envelope.`,
        t`Praxys 不会提高已接受的历史边界。`,
      ),
      target: 'action.review-history-envelope',
      action: l(t`Compare the request with recent history`, t`对照近期历史查看请求`),
    },
    'clarification_required.stale_confirmation_or_source_revision': {
      finding: l(
        t`A confirmed section or source changed after review.`,
        t`已确认的分段或来源在核对后发生变化。`,
      ),
      effect: l(
        t`Readiness is stale and cannot be silently rebound.`,
        t`准备情况已过期，不能静默重新绑定。`,
      ),
      target: 'action.first-stale-section',
      action: l(t`Review the latest revision`, t`查看最新版本`),
    },
    'clarification_required.contradictory_input': {
      finding: l(t`Two otherwise valid answers conflict.`, t`两项各自有效的回答彼此冲突。`),
      effect: l(
        t`Praxys cannot choose which answer should govern the plan.`,
        t`Praxys 无法自行选择哪项回答应约束计划。`,
      ),
      target: 'action.first-conflicting-field',
      action: l(t`Resolve the first conflict`, t`处理首个冲突`),
    },
  } satisfies Record<TrailReasonCode, ReasonCopy>;

  const moduleLabels: Record<TrailModuleKey, string> = {
    grade_specificity: l(t`Grade-specific training`, t`坡度专项训练`),
    technical_terrain: l(t`Technical terrain`, t`技术路面训练`),
    environment_altitude: l(t`Environment and altitude`, t`环境与海拔适应`),
    fueling: l(t`Fueling practice`, t`补给练习`),
  };
    return {
    copy,
    provenanceLabels,
    eventFormatOptions,
    distanceFamilyOptions,
    planningIntentOptions,
    footingOptions,
    weekdayOptions,
    sunOptions,
    windOptions,
    conditionsOptions,
    supportOptions,
    availabilityOptions,
    gearOptions,
    intakeOptions,
    gutOptions,
    gradeLabels,
    reasonCatalog,
    moduleLabels,
    };
  }, [l, t]);
}
