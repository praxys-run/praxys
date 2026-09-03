# Trail-running course-ledger Experience amendment v2

**Status:** proposed Design Decision Record and Experience Specification
successor; human Design review required; runtime inactive and unreachable.
**Evidence:** no implementation or rendered verification is claimed.

**Dependency binding:** [Product v2](trail-running-plan-product-amendment-v2.md)
is `pdr-owner-non-ultra-trail-plan-v2-amendment` at commit `81c58c1b`;
[Architecture v2](trail-running-plan-architecture-decision-v2.md) is
`adr-owner-non-ultra-trail-plan-v2`; [Trust v2](trail-running-plan-trust-decision-v2.md)
is `tdr-owner-non-ultra-trail-plan-v2`; the draft Science decisions at commit
`b5177e40` are `sdr-trail-running-goal-ontology-v2` at decision digest
`sha256:73dd653f8637004ff2ab3a754c3e775225eaf9faa79ccc52c97de3c3dbbf0b7c`
and `sdr-non-ultra-trail-plan-generation-policy-v2` at decision digest
`sha256:8c10f0846e356afa0522025fe2c02f095fe4487537eaae9d7d0203449a36bb56`.
All four v2 specialist decisions remain proposed/draft and require human
acceptance plus an accepted inactive-contract rebind before implementation.

This amendment preserves the Field Lab visual system and the proposal,
adoption, and delivery hierarchy in
`trail-running-plan-experience-spec.md`. It replaces only the v1 course-review
interaction where it conflicts with the proposed Product v2 contract. It does
not redesign Praxys or authorize implementation, activation, dogfood,
production data, catalog visibility, provider consent, or delivery.

## Human decision sheet

Record **approve**, **revise**, or **reject** for each row. One approval does
not imply another.

| # | Design choice | Recommendation |
| --- | --- | --- |
| 1 | Route and hierarchy | Use one progressive full-page course ledger under Training, not the current Goal dialog. |
| 2 | Input meaning | Use the exact bilingual labels, explicit unknown controls, and canonical-unit mappings below. |
| 3 | Confirmation | Confirm each visible section at its exact revision; any edit invalidates that section and readiness. Never offer confirm-all. |
| 4 | Result receipt | Show one natural-language verdict, every matching reason as finding → effect → next action, and readiness modules as Not evaluated, Available, or Limited. Reserve Included/Omitted for an actual proposal. |
| 5 | Responsive and accessibility | Use a desktop ledger plus sticky receipt and a mobile ordered accordion, with the complete state and access requirements below. |
| 6 | Platform boundary | Keep miniapp unavailable with an honest Web handoff; keep Garmin post-adoption, read-only, blocked or unverified, with no provider action in v2. |

## Work Contract and decision

- **Classification:**
  `sha256:d0a83117e8cd681435229fb7fb2c8ddddf4ac8ad8acaba24590079ba1e200607`
- **Route:**
  `sha256:6a022077cd4d910007c63241ee7c4b98773cd587c92450c6acecc778943fe168`
- **ID:** `ddr-owner-trail-course-ledger-v2-amendment`
- **Schema version:** logical-contract.
- **Owner role:** Design.
- **Question:** How should an owner describe a Trail event, confirm each
  revision, and understand every readiness reason without reading machine
  contracts or mistaking a limited module for a safe default?
- **Recommendation:** adopt the full-page progressive ledger and receipt below.
- **Dependencies:** the accepted v1 Trail Science and Product/Experience
  decisions and the exact proposed/draft v2 Product, Architecture, Trust, and
  Science subjects bound above. None is treated as accepted here. Every v2
  decision must be human-accepted and the inactive contracts rebound before
  implementation; a dependency change requires Design re-review.
- **Review route:** human-review-required. Design does not approve this record.
- **Outcome plan:** later independent rendered verification with synthetic
  data; no value telemetry is authorized here.

## Experience thesis and route

The mode is **Operate**. The owner should finish with one answer—what Praxys
can do next—and a complete receipt showing why. The route is a dedicated page,
`/training/plan-start/trail/course-review`; Goal may link to it but its dialog
does not host the ledger. The path has no variable segment or query string.
Optional hashes are limited to `#event`, `#grade-footing`,
`#training-access`, `#recent-experience`, and
`#conditions-support-fueling`. In-page focus and browser navigation state may
carry only the fixed section/field/action target keys defined below—never a
value, unknown state, date, identifier, revision, digest, DTO, token, or source
metadata.

The page title is **Review Trail event / 核对越野赛事**. Supporting copy is
**Describe the course and where you can train. Praxys will keep unknowns
visible. / 填写赛道情况和可训练条件。Praxys 会明确保留未知项。**

The page has five ordered sections:

1. Event & planning duration / 赛事与计划用时
2. Grade & footing / 坡度与路面
3. When and where you can train / 可训练时间与场地
4. Recent experience / 近期训练经历
5. Conditions, support, and fueling / 环境、支持与补给

The fifth section is collapsed initially. Recent experience is read-only. All
other sections use locale-only product chrome; the paired labels below are the
translation contract, not simultaneous bilingual UI.

## Field and unit contract

Every reviewable value offers **I don't know yet / 目前不确定** when Product
v2 permits `state: unknown`. Selecting it removes the value rather than
submitting an empty string, zero, or placeholder. Core unknowns remain visible
and prevent eligibility; optional unknowns limit only their named modules.

Server response provenance always uses these labels: **You entered this /
由你填写** (`athlete_stated`), **Verified course information / 已核实的赛道信息**
(`course_verified`), **From your activity history / 来自你的活动历史**
(`history_observed`), **Estimated by Praxys / 由 Praxys 推断**
(`model_inferred`, with model version), **Your assumption—confirmation
required / 你的假设—需要确认** (`explicit_assumption`), and **Unknown / 未知**
(`unknown`). Clients never author provenance.

### 1. Event & planning duration / 赛事与计划用时

| EN / 中文 label | Product v2 field and UI mapping |
| --- | --- |
| Event / 赛事 | Existing server-stamped event identity; read-only, with **Edit Goal / 编辑目标** deep link. |
| Event date / 比赛日期 | ISO date; locale-formatted display. |
| Race distance / 比赛距离 | Decimal km with at most 3 decimals; convert exactly to integer meters `1..49999`. |
| Total ascent / 累计爬升 | Integer meters `0..20000`. |
| Total descent / 累计下降 | Integer meters `0..20000`. |
| Minimum planning duration / 计划用时下限 | Hours/minutes control → integer minutes `1..1440`. |
| Maximum planning duration / 计划用时上限 | Hours/minutes control → integer minutes `1..1440`, strictly greater than minimum. |
| Event format / 比赛形式 | `single_day` → **One-day event / 单日赛事**. |
| Distance category / 距离类别 | `non_ultra` → **Non-ultra Trail / 非超长距离越野**. |
| Planning goal / 计划目标 | `performance` → **Improve race performance / 提升比赛表现**. |

Planning-duration help is **The range you want Praxys to plan around—not a
finish-time prediction. / 这是你希望 Praxys 用于制定计划的时长范围，并非完赛时间预测。**

### 2. Grade & footing / 坡度与路面

**Course grade distribution / 赛道坡度分布** uses five percentage inputs:

- **Steep downhill (below −10%) / 陡下坡（低于 −10%）**
- **Downhill (−10% to below −3%) / 下坡（−10% 至低于 −3%）**
- **Near level (−3% to below 3%) / 近似平缓（−3% 至低于 3%）**
- **Uphill (3% to below 10%) / 上坡（3% 至低于 10%）**
- **Steep uphill (10% and above) / 陡上坡（10% 及以上）**

Display percentages accept at most two decimal places and convert exactly to
five integer basis-point shares. The live summary is **Total / 合计**; the five
values must equal `100.00%` (`10000` basis points). The entire distribution may
instead be explicitly unknown. Boundaries are explanatory text, not sliders
or inferred route geometry.

**Course footing / 赛道路面** is a multi-select with exactly these six
plain-language values:

| EN / 中文 | Product value |
| --- | --- |
| Firm, smooth trail / 坚实平整路面 | `firm_smooth` |
| Loose gravel / 松散碎石 | `loose_gravel` |
| Mud / 泥地 | `mud` |
| Rocks or roots / 岩石或树根 | `rocks_or_roots` |
| Built steps / 人工台阶 | `built_steps` |
| Water crossings / 涉水路段 | `water_crossing` |

The set may be explicitly unknown; there is no Other or free text. Use
**Does any section require hands for progress? / 是否有路段需要用手辅助通过？**
for `hands_assist`, and **Does any section use fixed ropes? /
是否有路段需要使用固定绳索？** for `fixed_rope`. Both offer exactly **Yes /
是**, **No / 否**, and **Not sure / 不确定**. They serialize only as known
`true`, known `false`, or the strict unknown envelope.

### 3. When and where you can train / 可训练时间与场地

- **Days available to run / 可跑步的星期** maps Monday through Sunday to a
  known, non-empty, unique set of ISO weekday integers `1..7`; **I don't know
  yet / 目前不确定** is distinct from an empty known set.
- **Weekly training time available / 每周可训练时间** maps hours/minutes to
  integer `weekly_time_limit_min` in `1..10080`.
- **Longest training session available / 单次最长可训练时间** maps
  hours/minutes to integer `maximum_session_duration_min` in `1..1440` and
  cannot exceed the weekly limit.
- **Dates you cannot train / 无法训练的日期** maps to a known, sorted, unique
  set of at most 14 ISO dates inside the displayed 14-day horizon; **No dates /
  无** is a valid known-empty set.
- **Preferred day for the longest easy session / 最长轻松训练的首选星期** is
  optional; **No preference / 无偏好** omits it, while a chosen ISO weekday
  must also be available.
- **Can you access a continuous, nontechnical uphill for at least 3 minutes? /
  你能使用可连续进行至少 3 分钟、非技术性的上坡路线吗？** maps Yes/No/Not
  sure to known `true`, known `false`, or unknown.
- **Can you access terrain for controlled downhill training? /
  你能使用适合受控下坡训练的路线吗？** uses the same mapping and asks for no
  slope, speed, distance, or duration.
- **Footing available for training / 可用于训练的路面** uses the same six
  footing values or explicit unknown.
- **I confirm this is an adult, non-clinical planning context. /
  我确认这是成人、非医疗场景的训练计划。** binds the scope confirmation.
- **I confirm the goal is race performance. / 我确认目标是提升比赛表现。**
  binds the intent confirmation.
- **Do you currently have symptoms that should stop performance planning? /
  你目前是否有应停止竞速计划的症状？** offers Yes/No/Not sure without asking
  for diagnosis or free text.

### 4. Recent experience / 近期训练经历

This read-only receipt shows **Recent running continuity / 近期跑步连续性**,
**Recent ascent exposure / 近期爬升训练**, **Recent descent exposure /
近期下降训练**, and **Recently observed footing / 近期记录到的路面**. Every
row shows the observation window, freshness, server source, and source
revision. It may deep-link to owner-visible Activities, but offers no edit,
correction, attestation, or athlete-entered replacement inside plan start.

### 5. Conditions, support, and fueling / 环境、支持与补给

Open this collapsed section before it can be confirmed. Environment, support,
and fueling must each be explicitly completed or set to unknown; opening one
group never reviews another. Each group offers **Set this group to unknown /
将本组设为未知**, which writes strict unknown envelopes for that group's
fields, creates a new section revision, and never supplies defaults.

- Environment: **Maximum course altitude / 赛道最高海拔** (integer m),
  **Expected temperature range / 预计气温范围** (°C min/max), **Expected
  humidity range / 预计湿度范围** (% min/max), **Sun exposure / 日晒暴露**
  (Low/Mixed/High / 低/混合/高), **Wind exposure / 风力暴露**
  (Sheltered/Mixed/Exposed / 遮蔽/混合/暴露), and **Conditions based on /
  环境信息依据** (Organizer information/Seasonal expectation/My assumption /
  赛事方信息/季节预期/我的假设). My assumption requires explicit confirmation.
- Support: **Support setup / 补给支持方式** (Organized aid/Mixed/Self-supported
  / 赛事补给/混合/自助), **Number of aid stations / 补给站数量**,
  **Longest gap between aid stations / 最长补给站间距** (km value, No
  applicable gap / 不适用, or Not sure / 不确定), **Water availability /
  饮水供应** and **Food availability / 食物供应** (None/Some stations/Every
  station/Not sure / 无/部分站点/每个站点/不确定), and **Required equipment /
  强制装备** (Carry water/Carry food/Weather shell/Lighting/Navigation
  device/Other required / 携水/携带食物/防风雨外套/照明/导航设备/其他必需装备).
  Other records presence only; it opens no free-text field. **No required
  equipment listed / 未列出强制装备** is a known-empty set and is distinct from
  **I don't know yet / 目前不确定**.
- Fueling: **Longest practiced fueling duration / 最长补给练习时长** (integer
  minutes), **Fueling practice sessions in the past 42 days /
  过去 42 天的补给练习次数** (integer), **Practiced intake / 已练习的摄入形式**
  (None/Fluids only/Carbohydrate drink/Mixed food and drink /
  无/仅液体/碳水饮料/食物与饮品混合), and **Did stomach or gut issues change
  your plan? / 胃肠不适是否曾让你改变计划？** (No plan-altering issue/Plan-
  altering issue/Not sure / 未影响计划/曾影响计划/不确定). Copy remains
  non-diagnostic and gives no quantity prescription.

## Section confirmation and revision behavior

Each editable section ends with **Confirm this section / 确认本节** and shows
**Confirmed for revision {n} / 已确认版本 {n}** only after the server accepts
that exact visible revision. Editing a value, choosing unknown, or receiving a
new server-stamped source invalidates only that section's confirmation and any
downstream readiness receipt. The state becomes **Changed—confirm again /
已更改，请重新确认**.

There is no page-level confirm-all, and confirming an open section never
confirms collapsed or unseen content. **Check readiness / 检查准备情况** becomes
the one green action only when every required visible section is confirmed;
**Save and leave / 保存并稍后继续** remains secondary. Confirmation attests
review, not truth, safety, eligibility, or likely performance.

## Readiness receipt

The receipt never displays machine status or reason identifiers. Its stable
headline is one of:

| Result | EN / 中文 label |
| --- | --- |
| Validation failure | We couldn't check this information / 暂时无法检查这些信息 |
| Policy unavailable | Trail planning isn't available for this case / 此情况暂不支持越野计划 |
| Readiness blocked | Your symptoms, schedule, history, or terrain access blocks a proposal for now / 当前症状、时间安排、训练历史或场地条件暂时阻止生成计划 |
| Clarification required | A few answers are needed before Praxys can check readiness / 还需补充少量信息，Praxys 才能检查准备情况 |
| Eligible | Ready to review a 14-day proposal / 可以查看 14 天计划提案 |

Every matching reason renders as three labeled lines: **Finding / 发现**,
**Effect / 影响**, and a focusable **Next action / 下一步**. The table below is
the complete copy and target contract. Codes appear only for implementation;
they are never user-visible. Target keys are fixed internal keys, not URLs or
personal state. `first-*` actions resolve from the server's closed field-error
or reason-target data and never from client-authored strings.

| Reason code | Finding — EN / 中文 | Effect — EN / 中文 | Fixed target; action — EN / 中文 |
| --- | --- | --- | --- |
| `validation_failed.invalid_field_value` | One or more values is outside the accepted format or range. / 一项或多项数据不符合格式或范围要求。 | Praxys cannot interpret this revision safely. / Praxys 无法安全解释当前版本。 | `action.first-invalid-field`; **Review the first invalid value / 查看首个无效值** |
| `validation_failed.schema_version_mismatch` | This course review was created with an unsupported version. / 此赛道核对使用了不受支持的版本。 | Praxys will not guess how old or future fields map to v2. / Praxys 不会猜测旧版或未来字段如何映射到 v2。 | `action.reload-supported-version`; **Reload the supported version / 重新加载受支持版本** |
| `validation_failed.deterministic_invariant_failed` | Praxys could not reproduce the same readiness receipt. / Praxys 无法复现同一份准备情况回执。 | No proposal can be trusted from this result. / 无法信任基于此结果生成的提案。 | `action.retry-readiness`; **Retry the readiness check / 重新检查准备情况** |
| `policy_unavailable.policy_inactive` | This Trail policy is not active. / 此越野策略尚未启用。 | No proposal is available from this inactive slice. / 此未启用切片不能生成提案。 | `section.policy-status`; **Review policy status / 查看策略状态** |
| `policy_unavailable.event_inside_unapproved_taper_window` | The event is inside a period without an accepted taper policy. / 比赛已进入尚无获批减量策略的阶段。 | This policy cannot organize the event-near period. / 此策略无法安排临赛阶段。 | `field.event-date`; **Review the event date / 查看比赛日期** |
| `policy_unavailable.unsupported_ultra_or_multiday` | This event is ultra-distance or multiday. / 此赛事属于超长距离或多日赛。 | It is outside the non-ultra, one-day policy. / 它超出非超长距离单日策略范围。 | `field.event-scope`; **Review event scope / 查看赛事范围** |
| `policy_unavailable.unsupported_population_or_intent` | The confirmed context or goal is outside this performance policy. / 已确认的适用场景或目标不在此竞速策略范围内。 | Praxys will not substitute another population or intent. / Praxys 不会替换为其他人群或目标。 | `field.adult-performance-scope`; **Review planning scope / 查看计划适用范围** |
| `policy_unavailable.technical_features_outside_v2` | The course requires hands assistance or fixed ropes. / 赛道需要用手辅助或使用固定绳索。 | Those technical features are outside v2. / 这些技术特征超出 v2 范围。 | `action.first-confirmed-hazard`; **Review the technical feature / 查看技术特征** |
| `readiness_blocked.insufficient_recent_running_history` | Recent running continuity is below the accepted history gate. / 近期跑步连续性未达到已接受的历史门槛。 | Praxys cannot anchor a proposal to enough recent running. / Praxys 无法用足够的近期跑步记录约束提案。 | `field.history-running`; **Review recent running / 查看近期跑步记录** |
| `readiness_blocked.insufficient_comparable_trail_history` | Comparable Trail, ascent, or footing history is insufficient. / 可比的越野、爬升或路面训练历史不足。 | Course-specific work cannot be bounded from observed experience. / 无法依据已观察经历约束赛道专项训练。 | `field.history-comparable-trail`; **Review comparable experience / 查看可比训练经历** |
| `readiness_blocked.insufficient_descent_history` | Recent descent exposure is insufficient. / 近期下降训练经历不足。 | Downhill work cannot be bounded from observed history. / 无法依据已观察历史约束下坡训练。 | `field.history-descent`; **Review descent experience / 查看下降训练经历** |
| `readiness_blocked.insufficient_terrain_access` | Required uphill, downhill, or footing access is unavailable. / 缺少所需的上坡、下坡或路面训练条件。 | Praxys will not replace the course demand with road training. / Praxys 不会用公路训练替代赛道需求。 | `section.training-access`; **Review training access / 查看训练场地条件** |
| `readiness_blocked.current_symptom_stop` | You confirmed a current symptom that should stop performance planning. / 你确认目前有应停止竞速计划的症状。 | Performance planning stops; Praxys makes no diagnosis. / 竞速计划将停止；Praxys 不作诊断。 | `field.symptom-stop`; **Review your response / 查看你的回答** |
| `readiness_blocked.no_schedule_within_envelope` | No 14-day schedule fits the confirmed availability and accepted limits. / 没有 14 天安排能同时满足已确认时间和已接受限制。 | Praxys will not compress, stack, or substitute sessions. / Praxys 不会压缩、堆叠或替换训练。 | `section.training-schedule`; **Review your schedule / 查看训练时间安排** |
| `clarification_required.material_course_demand_unknown` | A core course detail is still unknown. / 仍有核心赛道信息未知。 | Readiness cannot be decided without that detail. / 缺少该信息时无法判断准备情况。 | `action.first-unknown-core-field`; **Complete the next course detail / 补充下一项赛道信息** |
| `clarification_required.assumption_confirmation_required` | A course or conditions assumption has not been confirmed. / 一项赛道或环境假设尚未确认。 | Praxys will not treat an assumption as reviewed fact. / Praxys 不会把未确认假设当作已核对事实。 | `action.first-unconfirmed-assumption`; **Review the assumption / 查看该假设** |
| `clarification_required.adult_scope_or_constraints_unconfirmed` | Adult, non-clinical performance scope is not confirmed. / 尚未确认成人、非医疗的竞速适用范围。 | This policy cannot be applied yet. / 暂时无法应用此策略。 | `field.adult-performance-scope`; **Confirm planning scope / 确认计划适用范围** |
| `clarification_required.training_constraints_missing` | A required schedule, access, or symptom answer is missing. / 缺少必填的时间、场地或症状回答。 | Praxys cannot evaluate the complete planning envelope. / Praxys 无法评估完整计划边界。 | `action.first-missing-training-field`; **Complete the next training detail / 补充下一项训练信息** |
| `clarification_required.training_constraints_outside_history_envelope` | A requested workload or edit is above recent observed history. / 请求的训练量或编辑超出近期已观察历史。 | Praxys will not increase the accepted history envelope. / Praxys 不会提高已接受的历史边界。 | `action.review-history-envelope`; **Compare the request with recent history / 对照近期历史查看请求** |
| `clarification_required.stale_confirmation_or_source_revision` | A confirmed section or source changed after review. / 已确认的分段或来源在核对后发生变化。 | Readiness is stale and cannot be silently rebound. / 准备情况已过期，不能静默重新绑定。 | `action.first-stale-section`; **Review the latest revision / 查看最新版本** |
| `clarification_required.contradictory_input` | Two otherwise valid answers conflict. / 两项各自有效的回答彼此冲突。 | Praxys cannot choose which answer should govern the plan. / Praxys 无法自行选择哪项回答应约束计划。 | `action.first-conflicting-field`; **Resolve the first conflict / 处理首个冲突** |

Reason order follows the authoritative backend receipt and is never reordered
by styling. A focus target outside the current viewport opens its section and
focuses the labeled control; return focus uses only the fixed target key.
Never offer a road plan, change `trail_running` to `running`, or imply that
completing fields makes the event safe.

Readiness shows all four authoritative module rows: **Grade-specific training
/ 坡度专项训练**, **Technical terrain / 技术路面训练**, **Environment and altitude
/ 环境与海拔适应**, and **Fueling practice / 补给练习**. Each uses exactly
**Not evaluated / 尚未评估**, **Available / 可用于生成**, or **Limited / 受限**
from `module_availability`; it never infers state from `limited_modules`.
Available means only that generation may consider the module. Limited states
what would be omitted and links to the authoritative fixed reason target.

Only an immutable proposal may label a module **Included / 已包含** or
**Omitted / 未包含**, using the proposal's explicit selection. A readiness
module marked Limited cannot be Included; Available does not require Included.
Neither surface substitutes a generic or road module.

## Layout, state space, and accessibility

Desktop is a two-column workbench: the progressive ledger occupies the main
column; a compact readiness receipt is sticky in the secondary column and
never covers page actions. Mobile is one ordered accordion: current verdict,
next required section, remaining sections, recent-experience receipt, then
reasoning. It uses no horizontal table and no floating action over content.

Required states are: stable loading skeleton; online saved; offline/slow;
unsaved memory-only edits; retryable request error; field validation plus
linked error summary; stale section/source/readiness revision; unknown;
blocked; eligible with authoritative module availability; policy unavailable;
private/not found; and version mismatch. Offline copy is **Offline. Changes are
kept only on this page and have not been saved. /
当前离线。更改仅保留在此页面，尚未保存。**
Offline edits are labeled **Pending changes / 待保存更改** and remain only in
page memory—not local/session storage, a URL, or browser history. Reloading or
leaving warns that they will be lost. After reconnect, fetch the current
server revision before offering **Restore pending changes / 恢复待保存更改**;
offer **Discard pending changes / 放弃待保存更改** at the same level. Restore
reapplies the in-memory values to the visible editor but does not silently save
or confirm them. A server change opens **Review latest version / 查看最新版本**
and a compare/reapply path; it never overwrites pending edits.

All interactive targets are at least 44px in both dimensions. Keyboard order
follows the visible ledger; accordion, multi-select, percentages, unknown
controls, confirmation, errors, and deep links have visible focus. Submit
moves focus to the error-summary heading, whose links return to fields. Status
is never color-only. Long English and Simplified Chinese labels wrap without
truncation at 320px; numeric values use tabular type. Light/dark themes retain
WCAG AA meaning. Reduced motion removes accordion and receipt transitions;
live regions announce save, invalidation, and readiness changes without moving
focus.

Design-system impact: none—existing Field Lab tokens, flat rule-separated
surfaces, inputs, accordion/collapsible behavior, Alerts, ScienceNote, and
receipt grammar cover the route. Green remains action; cobalt remains
reasoning. No nested cards, new tokens, or ambient shadows are introduced.

## Owner data controls

The page's locale-only **More actions / 更多操作** menu contains:

- **Reset course review / 重置赛道核对**. Its confirmation states **Reset
  replaces the current editable answers with unknowns. It does not erase
  source activities or retained proposal records. / 重置会把当前可编辑回答改为
  未知；不会删除来源活动或已保留的提案记录。** Success invalidates all current
  confirmations and readiness.
- **Export my Trail plan data / 导出我的越野计划数据**. This uses the existing
  authenticated owner export and explains that current values, unknowns,
  provenance, confirmations, retained snapshots, audits, and receipts are
  included.
- **Delete Trail goal / 删除越野目标**. A destructive confirmation distinguishes
  goal deletion from account deletion and states that owned draft, snapshots,
  proposals, audits, indexes, and caches are removed. Rollback or durable
  cleanup-pending is shown honestly; success is never reported while known
  owned data remains.

These controls accept no owner identifier and create no administrator, MCP,
demo, or support-user Trail surface.

## Miniapp and Garmin boundary

Miniapp renders no partial editor. It shows **Trail plan setup is currently
available on Praxys Web. / 越野计划设置目前仅支持 Praxys 网页版。** with an
honest **Open Praxys Web / 打开 Praxys 网页版** handoff to the fixed route when
the platform supports it. The URL carries no authentication, owner/event
identifier, state, or return token. If deep opening is unavailable, show
**Open Praxys Web in your browser and sign in to continue. /
请在浏览器中打开 Praxys 网页版并登录后继续。** It remains unavailable until
API, write, state, localization, native rendering, and verification parity
exist.

Garmin remains absent before adoption. After adoption, v2 may show only a
read-only **Garmin compatibility / Garmin 兼容性** summary with **Internal
check only. Praxys has not contacted Garmin. / 仅为内部检查，Praxys 尚未连接
Garmin。**, natural **Unverified / 未验证** or **Blocked / 已阻止** states, and
closed per-workout reasons. It is a pure projection over the owner's stored
canonical workouts and the versioned internal matrix.

The projection performs zero token, credential, tokenstore, adapter, network,
provider, consent, or delivery-ledger reads or writes; accesses or emits zero
provider/account/device/workout/region identifiers; persists nothing; and
cannot claim actual Garmin support. It preserves `trail_running` and offers no
connect, consent, send, schedule, retry, replace, reconcile, delete, or other
provider action under v2.

## Verification and handoff

Engineering must not invent labels, confirmation scope, result priority,
unknown behavior, provider actions, or a road fallback. Before any later
activation, Quality independently renders synthetic complete, unknown,
blocked, limited, error, stale, offline, and post-adoption Garmin states at
desktop and mobile sizes; verifies EN/zh, keyboard/focus, touch, wrapping,
light/dark, reduced motion, console, and no overflow; and performs native
WeChat verification before claiming miniapp parity.

## Human Design decision requested

Approve, revise, or reject the six rows in the decision sheet. Approval binds
only this intended inactive experience. It does not approve Product v2,
implementation, rendered quality, merge, deployment, activation, production
data, dogfood, catalog exposure, Garmin integration, consent, or delivery.
