# 活动详情 · A「跑后报告」体验规格

**2026-09-29 有界修订：**文末 `ddr-activity-ui-refinement-eight-corrections-v1` 将八项明确用户反馈细化为实施条件；仅在这些条件内覆盖下文旧版的列表入口、冗余文案、来源和记录展示规则。A／Field Lab、默认分段表格与真实数据边界继续有效；新修订待父协调者的独立 DRR 范围核对，不代表整份草案获批或发布验收。

**状态：**用户已选定 A 的阅读顺序、默认分段表格、曲线叠加和图内缩放，并于 2026-09-28 同意按此设计实施。API、Web 和小程序的正式详情实现已进入工作区；Trust／Quality 已分别完成此前的有界只读复核，模拟器已核对小程序页面和部分交互，但 Skyline Canvas 曲线绘制、真机辅助功能、独立原生 Quality、决策评审与发布尚未完成。本文件同时承担 Design Decision Record 与 Experience Specification，不是已上线能力的说明。

## Work Contract 与设计决策

- 分类：`user-experience`；影响：`user-visible-experience`、`repository-change`。分类摘要 `sha256:e36ab7436e66e774d67c42da71c9892be286c6562c504988f577e48cda9c4d30`；路由摘要 `sha256:c022991c4db14340a5cc592072dc27a267206da93657b4fdca8a3a5f83bf7929`。
- 主循环 Design，嵌套 Delivery；Design 产出本决策及规格，Engineering 后续实现，Quality 独立验证。决策评审由 Decision Review Router 分配；本文不代替其结论。
- 前置输入：用户已批准以此方向实施单次活动详情；设计阶段的 Work Contract 不代替 Product 决策、隐私评审、独立验证或发布授权。
- **ID：**`ddr-activity-detail-field-lab-v1`。**问题：**如何让跑者在一次活动中按时间回想，核对局部变化与来源，而不把已存汇总误当逐时证据？
- **选择：**以 A 为默认体验；由记录观察进入全程概况、同步叠加曲线、可对照分段表、完整来源记录。沿用 Praxys Field Lab 的平整暖纸、数字字形、两轨语义；不复制探索版 A 的锈红活跃色、衬线页面标题或密集分隔线。保留 A 旧视觉、B、C 仅供原型对比。
- **取舍：**A 比 B 少一屏多轨细看，比 C 不那么以分段为入口；A 的默认表格、双轴叠加和选段返回保留熟悉的核对路径。暂不加 GPS、AI 评价、训练建议或无法溯源的“表现很好”。
- **决策边界：**用户确认的是方向，不是原型模拟数据与实际服务能力。首屏“观察”只能逐字对应已存的来源分圈；不是科学解释、趋势结论或健康判断。

## 使用场景与信息结构

模式是 **Operate → Read**：刚结束跑步、手机在室外，先找“这次跑了什么”，再在安静处用桌面细看功率／心率／配速的时刻与分段。进入路径是 Web 历史活动详情、以及小程序「分析 → 活动」；历史列表只需提供进入详情的入口，本轮不改列表排序或信息结构。演示账户仅有镜像汇总读取权，历史仍可浏览，但两端均不显示必然通向不可用详情的链接；服务端始终独立拒绝其逐时详情请求。

1. **活动与记录观察：**活动名称、可核对的日期／来源、合成数据标签（仅原型）；若有至少两条有效来源设备圈，可并列陈述首末圈配速，同时写明“不代表全程趋势”。只有一圈或配速缺失，则退回已保存的活动事实；绝不补写结论。
2. **整场概要：**距离、时长、平均配速、功率或心率等已存汇总。字段缺失显示“未记录”，不将零视为有效读数；来源和时间语义必须可追溯。四个值用开放式栅格，不用四张同权重卡片。
3. **沿时间回看：**选择一条主曲线，最多叠加一条有逐时采样的对照曲线。默认在演示中用功率 × 心率；正式客户端可优先用户已配置且实际存在的训练基准，随后退回可用采样。绘图、图例、两个独立纵轴和同一时刻读数构成一个完整仪器。
4. **按段回看：**默认表格，设备圈与每公里为不同切法；表格按列对齐段名／距离／用时／配速，来源圈有真实分段汇总时才附均功率和均心率。点击行跳到上方同一时间轴，保留段名、距离、用时、配速与“返回分段表”；原卡片只在原型里作对照，不进入正式默认导航。
5. **其余记录：**折叠入口标明已保存的项目数；按类别展示“可看曲线”或“仅汇总”及来源。RSS／CP 估计如确有来源值，仅保留为整场或来源平台参考，并就地解释，不绘制虚构曲线。

## Field Lab 视觉约束

以 `docs/brand/index.html`、`DESIGN.md` 和 `docs/dev/design-system.md` 为视觉依据。纸色／卡片层级使用既有 `background`、`card`、`border`，让留白和一次轻底色引导观察、曲线及表格；分段行只用柔和行界，不叠卡片、不做斑马色强对比。浅色按钮使用正式 Web 对比度加深后的绿色 `--primary`（`oklch(0.52 0.17 155)`）。主要页面标题用 Geist／Noto Sans SC，数据与日期用 JetBrains Mono 的 `.font-data`；正式 Web 当前仍以 DM Sans 为默认，字体迁移属于设计系统已有待办，不在原型偷改应用字体。

| 层次 | 规则 |
| --- | --- |
| 行动与选中 | 品牌绿只用于实际可操作的选项、选中行、返回或展开交互；不把观察到的“更快”染成正面建议。 |
| 解释与依据 | 钴蓝只用于双纵轴读法、数据来源／局限的解释，不用于心率或配速曲线。没有科学主张时不滥用 ScienceNote；正式科学解释应采用该组件并由 Science 确认。 |
| 观测曲线 | 功率＝暖褐、心率＝浆果紫、配速＝蓝灰绿；附加观测字段使用独立、中性的具名色。仅用于**指标身份**，不编码好坏。浅／深色均需明确变体，正式实现以新具名 `chart-theme.ts` 角色承载，不借用 `fitness`、`fatigue`、`form`。 |
| 叠加可辨 | 主线实线、对照虚线、图例写指标／来源／单位／左右轴；不能只靠颜色。坐标位置只比较走势，不跨单位比较数值；配速越小越快，纵轴方向明确标注。 |

设计系统处置：**新增可复用规则**，已在 `docs/dev/design-system.md` 的 Chart conventions 明确观测曲线的语义边界，并在 `web/src/lib/chart-theme.ts`、`miniapp/utils/theme.ts` 实现具名浅／深色角色。原型的 `field-lab.css` 只作用于品牌版 A，不是全站组件或全站主题的替代实现。

## 交互和反馈

- 主指标按钮、叠加选择和“全部曲线”只列真正有采样的字段；没有另一条曲线时说明“只有一条逐时曲线”，不展示无效叠加。切换指标、分段展示方式或外观不重置当前合法区间、游标和选段。
- 桌面缩放按钮放在**图卡右上**，与图例同一语境；手机放在图下但仍靠近曲线。图中拖选时间区间或点表格行进入局部，点“全程”回到完整范围；达到最小有效窗口时“放大”禁用且仍可阅读理由。不以时刻游标隐式缩放。
- 图内竖线和图下的**等宽滑杆**定位同一时间：悬停／点按图、拖动滑杆或按左右方向键查看当前真实采样；Home／End 到当前范围首末。游标移动更新可用曲线的读数和时间，无样本处显示“—／未采样”；不能插值填洞。范围改变时读数与可见刻度同步。
- 表格行必须由明确按钮可键盘触发；跳回图时焦点落在选段上下文，不消失在已离开的表格。返回链接滚回并聚焦原行。每公里无逐时距离时按钮禁用并说明原因；若没有可靠的分段起止时间，不提供“跳图”误定位，可只查看汇总行。
- 触屏保留纵向自然滚动，点按取样、明显的横向拖选才选局部；不给 320px 手机放横向拖动表格作为唯一阅读方式。键盘焦点清晰可见，语音说明包含值、单位、来源和无采样状态，动态读数用克制的 `aria-live` 提示；尊重减少动态效果设置。

## 证据与缺测规则

**原型数据是合成的**：`docs/design/activity-detail-prototypes/data.js` 自行生成时间序列和独立距离轨迹，仅用于演示断点、叠加与按公里切分。正式详情现经 `GET /api/history/{activity_id}/detail` 向已认证的非演示账户返回其本人保存的采样读数；演示账户尚无逐时详情披露授权，统一返回不可用。原型数据并不代表真实账户已有完整采样。既有 Web `Activity` 汇总类型本身不包含逐时曲线，不能据汇总值绘图。

| 可用数据 | 允许显示 | 不允许推断 |
| --- | --- | --- |
| 有逐时采样，覆盖完整 | 记录的数值、来源及曲线；实际保存的设备圈汇总。 | 来源圈为自动还是手动；两个量同刻高低的因果。 |
| 采样不完整 | 可用片段；在缺口处断线并说明覆盖／来源。 | 线性补点、跨缺口连线或用全场均值填洞。 |
| 仅一个采样指标 | 单曲线和游标；解释叠加为何不可用。 | 由分圈均值伪造第二曲线。 |
| 有有效连续距离轨迹 | 按真实累计距离每 1 km 切分，末段保留余量，并标记“据距离轨迹生成”。 | 把设备圈叫作公里段；把来源圈功率／心率均值迁移到公里段。 |
| 仅有距离轨迹、没有指标读数 | 可显示据轨迹切出的公里段汇总表，但行不提供无目标的跳图操作。 | 显示空图框或把距离轨迹误称为可绘制的指标曲线。 |
| 无有效距离轨迹 | 设备圈仍可看；每公里不可选并说明需要逐时距离。 | 用整场均速均分公里。 |
| 只有活动汇总 | 跳过空白图框和不可用分段控件，直达可查看的汇总记录。 | 某一时刻、某一公里的精确读数。 |

当前实现仅在活动起点、时长、完整连续且单调的累计距离轨迹与汇总距离可核对时，提供按公里定位；其他情况下由服务端返回明确的不可用原因并保留来源圈汇总表。末段不足表格显示精度 0.01 km 时并入前段；整场不足该精度则不生成无法阅读的 0.00 km 行。`SplitData` 仍没有可核对的时间边界，来源圈不支持跳图；采样缺口保留断线，GPS／原始距离轨迹均不进入响应。暂停期间的对齐没有可核实证据时，不推断公里段。

## 完整状态与双端适配

| 状态 | 视觉和操作回退 |
| --- | --- |
| 初次加载／慢网络 | 保持标题、概况、曲线和表格的稳定骨架；不先画零值曲线。 |
| 离线／可重试错误 | 明示数据尚未加载或快照已过时，允许重试；不把缓存当当前同步成功。 |
| 无权限／活动不存在 | 沿用客户端私有数据边界；不在错误中暴露活动是否属于其他账户。 |
| 无来源分圈／仅汇总 | 概况及“查看已保存的 N 项指标”入口仍在；无不可用控件占位。 |
| 部分来源／字段缺失／长名称 | 来源在指标旁且可折行，缺失留“—”及原因；数字、单位不被省略号截断。 |
| 中英／浅深色／减少动画 | 中文、英文分别是完整的本地化文案；深色只改令牌不改变指标色语义；移动端大触点、无阻断滚动。 |

Web 桌面将图内控件与表格列全部展开；390px 和 320px 手机保留“从观察到图”的首屏节奏，隐藏来源圈额外均值列但在该行次要文本中保留数值与单位。小程序按 Skyline 原生导航和控件实现，活动位于「分析 → 活动」而非另加主 tab；与 Web 对齐字段含义、缺口/来源说明、叠加上限、设备圈与公里段规则、游标及选段能力。主线已取消对授权小程序任务的额外前台批准门槛；Tencent DevTools 仍要求自身登录与授权。已在封闭合成数据下检查模拟器页面、公里段、游标与缩放；安装版 DevTools 明示不支持模拟器调试 Skyline Canvas，因此曲线笔画、真机触感与辅助功能仍须另行验证，不宣称双端通过验收。

## 原型、验证与实施边界

- 品牌版：`?v=report`（默认浅色），`?v=report&theme=dark`；旧 A 视觉：`?v=report&skin=original`。顶部可不重置游标地切换外观；`?v=console` 与 `?v=chapters` 保留原探索。启动方式见 `docs/design/activity-detail-prototypes/README.md`。
- 演示覆盖多指标、采样不完整、只有汇总；桌面 1440×900、手机 390×844／320×700 检查图内缩放、游标与表格、触摸／键盘、无横向溢出、浏览器错误。原生截图仅保留在 gitignored 的 `test-screenshots/ui-quality/activity-detail-prototypes/`。
- 本次实施在 `api/activity_detail.py` 与 `api/routes/history.py` 提供用户隔离的详情端点，在 `web/src/pages/ActivityDetail.tsx` 和 `miniapp/pages/activity-detail/` 增加正式入口和显示；真实数据只有记录了采样的活动才有曲线，缺失字段不补画。Web 与小程序模拟器合成截图存于 gitignored 的 `test-screenshots/ui-quality/activity-detail-implementation/`。独立 Quality 已复核 Web／API 静态行为，并逐张复核小程序原生截图的可见布局与状态；触控序列及 Canvas 绘制未获独立原生复演，Trust 也仅完成有界只读复核。Product／Decision Review、容量／日志边界、真机曲线与无障碍独立验收仍是发布前提，不标注为已发布或双端验收通过。

## Bounded refinement · eight user corrections · 2026-09-29

### Design Decision Record

- `id`: `ddr-activity-ui-refinement-eight-corrections-v1`; `schema_version`: `1`; `decision_type`: `design`; `owner_role`: `design`.
- `implementation_status`: `logical-contract` for DDR and Experience Specification; ready for parent DRR scope check, not implementation verification or release.
- `route_digest`: `sha256:c022991c4db14340a5cc592072dc27a267206da93657b4fdca8a3a5f83bf7929`, supplied by `/tmp/activity-ui-refinement-contract.json`: Design primary, Delivery nested; Engineering implements, Quality independently verifies.
- `question`: How can the eight explicit corrections simplify the selected A report without losing recorded information or accepted interactions?
- `options`: retain the reported clutter; distill the existing A / Field Lab presentation; replace it with a new visual world or preview imagery. `recommendation`: distill, exactly through AC1–AC8. The alternatives record trade-offs, not another prototype round.
- `rationale`: inspected code and six private reference screenshots support the reported duplication, buried navigation and misleading static affordances. Compact factual entries and disclosure address those defects; comprehension improvement remains unmeasured.
- `dependencies`: `pdr-activity-detail-readiness-v1` from `/tmp/activity-detail-product-handoff.json`, digest `sha256:3a77bf45228bd3de0f25c2bdd45ac33caa2aeeae640029fd7eedaf2a1e0b7e30`, plus actual prior A/default-table/finalize/implement selection and the eight corrections. Parent supplies independent DRR `agent-resolved` / `contract-consistency` input sufficiency for this combination only. Product's `draft-structured-handoff` status is unchanged; no broader acceptance is inferred.
- `review_route`: unassigned for this refinement; parent obtains independent DRR scope check on the returned artifact hash before execution. Design does not approve itself or request repeat generic approval.
- `outcome_plan`: Quality checks all eight conditions on synthetic records in both clients. Success means finding the report, every available curve, distinct summaries and their limits. Lost readings, false provenance, inaccessible controls or history sample-fetch fan-out fail acceptance. No outcome artifact/observer is required; user outcomes remain unmeasured.
- `design_system_impact`: `none - existing design system already covers the change`. UI Quality + Impeccable `distill`; keep A, Field Lab, default table, trace semantics, range/cursor and split-return behavior. Parent already ran context once; legacy PRODUCT warnings authorize no migration.
- `trial`: parent reports admission unavailable, baseline/unassigned, `tsk_7e090823d44e0c207f31c3321ce185f6002372df0fafd020d53e6d5d90c3bbfc`. Static parity passes are parent-reported, not measured runtime parity.
- `digest_algorithm`: SHA-256 of this complete UTF-8 file with LF/final newline, excluding only the single line beginning `- digest: `. The handoff separately hashes the complete file including that line. Neither hash confers authority.
- digest: sha256:e8fbac6b9704514b70eb02bf7ade892d92858a3e2c2133fac813126ab43efe05

### Eight acceptance conditions

**AC1 — Compact history; obvious detail entry.** Use a small existing sport glyph, localized type/date, then real distance/duration/pace, with other existing list facts in a quiet wrapping line. Reuse Field Lab surfaces, roughly 16px padding and 8px text gaps; content determines height. Desktop: glyph → flexible summary → `View report →` / `查看报告 →`. Mobile wraps the cue beside/below the summary, before secondary actions; no separate tall metric/report/DFA blocks. No photos, maps, fabricated charts or per-row detail/sample fetches. One native Web `Link` wraps the primary body and cue, preserving Enter, modifier-click and Back; accessible name includes type/date. Explicit `Recorded splits (N)` / `记录分段（N）` disclosure and `DFA α1` are independent siblings, never nested controls or card-wide click handlers. Miniapp uses native navigation plus sibling actions, retaining its DFA host behavior. Keep pagination/order, existing list facts and split preview. When detail capability is false, the primary body is static with no report cue; existing permitted secondary behavior remains.

**AC2 — Remove the timeline slogan.** Remove `沿着时间，读一遍` / `Read the run over time` and its heading space. The top chooser leads straight into the existing chart title. Keep an accessible section name `Recorded curves` / `记录曲线` without another prominent heading; no empty slot in the no-curve state.

**AC3 — Remove the empty observation.** Remove `这次活动有可查看的已存记录。` / `This activity's saved record is ready to inspect.`. If the existing valid first/last comparison predicate is false, omit the complete observation container, fallback scope and spacing. Add no replacement sentence or repeated hero. Otherwise keep actual `First recorded split` / `首个记录分段` and `Last recorded split` / `末个记录分段` values with `Not an overall trend` / `不代表全程趋势`. One recorded split remains in the table without implying a comparison.

**AC4 — One canonical source; precise provenance.** Header metadata reads date · `Activity source: Garmin` / `活动来源：Garmin` using the actual source's friendly name, ordinary text and natural wrapping. Remove repeated activity-source labels from observation/footer. Missing source: `Source unavailable` / `来源不明`. In AC8's disclosure preserve distinct `Sample records` / `采样记录` and `Environment records` / `环境记录` provenance using friendly names, not raw technical IDs: e.g. Stryd; `Garmin activity weather` / `Garmin 活动天气`. For a known source equal to the header use `Same as activity record` / `同活动记录`; absence never establishes equality. An unmapped identifier gets `Unrecognized source name` / `来源名称未识别`, not guessed attribution. Keep `Record sources do not verify every field's source.` / `记录来源不代表每个字段的来源都已核实。` in disclosure. A genuinely distinct environmental record may name the same provider; never flatten all fields under the header source.

**AC5 — Rename 设备圈 to 记录分段.** Use `Recorded splits` / `记录分段` consistently in affected controls, history preview and comparison labels. Retain distinct `Each kilometer` / `每公里`, its actual derivation and default table. No manual/automatic/kilometer origin is inferred for recorded splits. Keep a short local limit for static source rows: `Split times unverified; chart jump unavailable.` / `分段起止时间未核实，无法定位图表。`. Derived mode says `From recorded distance` / `根据已记录距离划分`. Its disabled control retains the actual existing reason visibly adjacent, not tooltip-only. Kilometer rows without metric curves remain static summaries; valid jump/selection/return behavior stays intact.

**AC6 — Remove duplicate bottom curve inventory.** Delete the bottom `Recorded curves` list and jump buttons. All currently available trace keys remain reachable through the existing top chooser, `More curves (N)` and overlay selector, including cadence, speed, altitude/grade, temperature, running dynamics and respiration. Keep active-extra visibility and one-overlay maximum. Opening disclosures or changing metrics preserves the legal range/cursor and selected split. More-curves count means extra choices, not saved summaries. Removing duplicate navigation removes no metric capability.

**AC7 — Static additional summaries, without hero duplicates.** Rename the bottom disclosure `Additional summaries (N)` / `补充汇总（N 项）`; count only additional displayed fields. Deduplicate by field key against the actual hero: remove repeated average pace and the hero's chosen average power/heart rate; preserve the other average and all existing distinct maxima, elevation, environment and source-reference values. A sample and an activity average remain different readings. Web uses a real `dl`/`dt`/`dd`; miniapp uses static associated labels/values. Two columns desktop, one narrow; labels wrap and units remain visible. No row links/buttons, tab stops, arrows, pointer cursor, hover underline/background or repeated “whole-activity summary” subtitles. Only the disclosure is interactive. Hide it when count is zero; any `View summaries` / `查看汇总` shortcut must have a real target and open it. RSS/source CP retain the brief nearby qualifier `Source reference; not a training assessment.` / `来源参考值，不是训练评价。`. Keep Data information independently available; do not recalculate or change field validity.

**AC8 — Short visible limits; detailed notes on demand.** Retain metric/axis labels, units, solid/dashed distinction and actual cursor readouts. Replace prose with `Independent axes` / `独立纵轴` only for overlays, and `Pace: faster ↑` / `配速：越快越靠上` only when applicable. Below the cursor show only relevant short status clauses: `Gaps in recorded data` / `记录有缺口`; `Reduced display` / `采样点已精简显示`; `Time from first sample; activity start unverified` / `首个采样点起算；活动开始时间未核实`. Use actual coverage/gap, reduction and time-origin evidence; no generic default paragraphs or unsupported completeness claim. Real limits may wrap and must remain visible with disclosure closed. Keep `Not sampled` / `未采样`, empty-window feedback and short accessible reasons beside unavailable overlay/zoom/cursor/kilometer controls.

Empty-interval copy: `No readings in this interval; zoom out.` / `此区间无读数，请缩小视图`.

Provide one default-collapsed `Data information` / `数据信息` disclosure immediately after chart statuses, or after the no-curve state. Web uses native details/summary; miniapp uses a native expanded-state button and static content. It contains applicable sample counts/reduction method; omitted points not interpolated; gaps never filled; time-origin details; scoped friendly provenance/field qualification; unverified recorded-split boundaries and recording method; kilometer first-reaching-sample derivation; and RSS/CP scope. Consolidate existing explanations here, once each; do not reset chart state or hide the essential short limits. No chart: show `No recorded curves` / `无记录曲线` and existing real summaries/tables, never an empty fake graph.

### Implementation and independent acceptance

Engineering implements these eight conditions in Web `ActivityCard.tsx`, `ActivityDetail.tsx`/`.css`, `ActivityTraceChart.tsx`; miniapp history/detail/trace components and their affected localization/view data. Key observed defects are the card-wide split handler, shared static-row hover styling, and curves-plus-summaries count. This handoff does not replace Engineering's Impact Map. No API, source-data, formula, authorization or broad brand change is specified.

Both clients use locale-only EN/zh, existing light/dark tokens and tabular numerals. Preserve loading/slow/retry/empty/private-error/demo behavior; no stale-success or fabricated interim data. Cover zero/one/multiple recorded splits, summary-only and distance-only records, partial/reduced/single-time samples, one/many curves, missing/mixed sources, and zero/many additional summaries. Missing data never becomes zero or a fabricated series. No summary target or chart-jump action points to absent content.

Quality checks the eight conditions at desktop 1440×900, mobile 390×844/320×700 and native miniapp equivalents, with long EN/zh, both themes and reduced motion. Preserve native Link and disclosure keyboard semantics, focus/jump-return, spoken labels/units/missing states, AA contrast, at least 44px-equivalent control targets and natural vertical scrolling. Static summaries have no tab stops. Check report/split/DFA separation, top-chooser completeness, corrected counts, friendly source scopes, closed-disclosure limits, and no list sample-fetch fan-out.

Evidence inspected: the named actual files, neighboring `LastActivityCard.tsx`, existing spec and six latest private user images. Images and their training values are not copied into this artifact, repo evidence or uploads. This refinement has not been implemented or rendered; no builds/tests/live accounts/commits/push/deploy were run by Design. Earlier static or simulator observations do not verify it; independent Skyline drawing and real-device accessibility remain outstanding. Return this artifact and its hash to the parent; no children or new prototype/review round.
