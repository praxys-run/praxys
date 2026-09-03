# Trail-running course-ledger Experience amendment v2

**Status:** proposed Design Decision Record and Experience Specification
successor; human Design review required; runtime inactive and unreachable.
**Evidence:** no implementation or rendered verification is claimed.

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
| 4 | Result receipt | Show one natural-language verdict, every matching reason as finding → effect → next action, and each module as Included or Limited. |
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
  decisions, plus human acceptance of
  `trail-running-plan-product-amendment-v2.md`. If Product v2 changes, this
  artifact must be reviewed and rebound before implementation.
- **Review route:** human-review-required. Design does not approve this record.
- **Outcome plan:** later independent rendered verification with synthetic
  data; no value telemetry is authorized here.

## Experience thesis and route

The mode is **Operate**. The owner should finish with one answer—what Praxys
can do next—and a complete receipt showing why. The route is a dedicated page,
`/training/plan-start/trail/course-review`; Goal may link to it but its dialog
does not host the ledger. Browser history, page title, and deep links preserve
the current section and field.

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

### 1. Event & planning duration / 赛事与计划用时

| EN / 中文 label | Product v2 field and UI mapping |
| --- | --- |
| Event / 赛事 | Existing server-stamped event identity; read-only, with **Edit Goal / 编辑目标** deep link. |
| Event date / 比赛日期 | ISO date; locale-formatted display. |
| Race distance / 比赛距离 | Decimal km input; convert exactly to integer `distance_meters`. |
| Total ascent / 累计爬升 | Integer m → `total_ascent_m`. |
| Total descent / 累计下降 | Integer m → `total_descent_m`. |
| Minimum planning duration / 计划用时下限 | Hours/minutes control → integer minimum minutes. |
| Maximum planning duration / 计划用时上限 | Hours/minutes control → integer maximum minutes; must exceed minimum. |
| Event format / 比赛形式 | Closed Product value, rendered in natural language. |
| Distance category / 距离类别 | Closed Product value, rendered in natural language. |
| Planning goal / 计划目标 | Closed Product intent, rendered in natural language. |

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
是**, **No / 否**, and **Not sure / 不确定**, mapping to `yes`, `no`, and
`unknown`.

### 3. When and where you can train / 可训练时间与场地

- **Days available to run / 可跑步的星期** maps Monday through Sunday to
  unique ISO weekday integers `1..7`; **I don't know yet / 目前不确定** is a
  distinct unknown state, never an empty known set.
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

Open this collapsed section before it can be confirmed. All groups support an
explicit unknown state.

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
  Other records presence only; it opens no free-text field.
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
| Readiness blocked | Your current history or access doesn't support a proposal yet / 当前训练历史或场地条件暂不支持生成计划 |
| Clarification required | A few answers are needed before Praxys can check readiness / 还需补充少量信息，Praxys 才能检查准备情况 |
| Eligible | Ready to review a 14-day proposal / 可以查看 14 天计划提案 |

Render every matching reason, not only the primary one, as three labeled lines:

- **Finding / 发现：** the plain-language fact Praxys evaluated;
- **Effect / 影响：** why it blocks, requires clarification, or limits scope;
- **Next action / 下一步：** a focusable deep link to the exact ledger field,
  section, recent-history row, or policy explanation.

Reason order follows the backend receipt and cannot be changed by severity
styling. If a target is outside this route, preserve return focus. Never offer
a road plan, change `trail_running` to `running`, or imply that completing more
fields makes the event safe.

Show four module rows—**Grade-specific training / 坡度专项训练**, **Technical
terrain / 技术路面训练**, **Environment and altitude / 环境与海拔适应**, and
**Fueling practice / 补给练习**—with only **Included / 已包含** or **Limited /
受限**. A Limited row states what is omitted and deep-links to the relevant
unknown; it never substitutes a generic or road module.

## Layout, state space, and accessibility

Desktop is a two-column workbench: the progressive ledger occupies the main
column; a compact readiness receipt is sticky in the secondary column and
never covers page actions. Mobile is one ordered accordion: current verdict,
next required section, remaining sections, recent-experience receipt, then
reasoning. It uses no horizontal table and no floating action over content.

Required states are: stable loading skeleton; online saved; offline/slow;
unsaved memory-only edits; retryable request error; field validation plus
linked error summary; stale section/source/readiness revision; unknown;
blocked; eligible with limited modules; policy unavailable; private/not found;
and version mismatch. Offline copy is **Offline. Changes are kept only on this
page and have not been saved. / 当前离线。更改仅保留在此页面，尚未保存。**
Reloading or leaving warns that memory-only edits will be lost. A stale result
never overwrites edits; offer **Review latest version / 查看最新版本** and a
safe compare/reapply path.

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

## Miniapp and Garmin boundary

Miniapp renders no partial editor. It shows **Trail plan setup is currently
available on Praxys Web. / 越野计划设置目前仅支持 Praxys 网页版。** with an
honest **Open Praxys Web / 打开 Praxys 网页版** handoff that preserves the
authenticated destination when supported. It remains unavailable until API,
write, state, localization, native rendering, and verification parity exist.

Garmin remains absent before adoption. After adoption, v2 may show only a
read-only **Garmin delivery / Garmin 下发** summary with natural **Unverified /
未验证** or **Blocked / 已阻止** states and per-workout reasons. It preserves
the canonical Trail type and offers no connect, preview-consent, send, retry,
or other provider action under this amendment.

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
