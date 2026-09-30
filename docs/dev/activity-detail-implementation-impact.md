# 活动详情实施影响图

**状态：已授权发布，尚未部署（authorized / not yet deployed）。**用户于 2026-09-28 批准按 `docs/design/activity-detail-experience-spec.md` 的 A「跑后报告」方向实施；该批准保留，产品选择不变。2026-09-29 的发布授权与 Operations 交接见下一节；后文保留此前本地 readiness 的历史证据，不把自测或授权记作上线成功。本次 Operations 仅更新两份交接文档，没有提交、部署、派发子角色或读取线上凭据。

## Operations 发布授权与交接（2026-09-29）

- 用户原话：**“没事，你就直接上线吧。回头我再测试这部分”**（2026-09-29）。既有 A 方案已获上线授权，iPhone 测试安排在之后；不重复索取批准，不把缺失 native 证据另立为阻塞。未测内容仍保持未验证。
- 当前发布合同 `/tmp/activity-detail-release-contract.json`：分类摘要 `sha256:b1c479b28194ddd656ede4fa7c0487da7647c08efccd6c75718ecf3825beb311`，路由摘要 `sha256:f1a3b1563d51fa95d9d7c524f3ab1ba006a84db47a5abce4a627f062ced35a18`；Runtime 主循环、Delivery 嵌套，Operations 牵头、Trust 参与、Operations／Engineering 执行、Quality 独立验证，Decision Review 保留。下节 readiness 合同是此前阶段记录。
- Operations 拥有本节发布交接与 `docs/ops/activity-detail-readiness.md` 的运行决策／待补 Release Evidence；Engineering 仍拥有实施影响图及实现，Quality／Trust 的既有结论不由本节重新签署。
- 父协调者报告：线上 API 版本 `059c8f1`，health／ready 正常，各开关正常；这是发布前旧版本基线，本角色未重读。父协调者报告 `main` 已到 `994d4ded`，相对工作区 HEAD `394a0778` 仅新增 Web lockfile 变更；Engineering 打包时需对齐并核验最终 SHA，不能沿用“已对齐主线”的历史描述。
- 发布范围：Web／API 经 protected `main` 的 `deploy-frontend-appservice.yml`／`deploy-backend.yml`，按 `docs/ops/deploy.md` 保留分支、检查、环境与 provider 门槛。小程序走 `miniapp-publish.yml` 支持的 robot 5 主线开发上传或 robot 1 主线可达 tag 候选上传；体验版提升、提审与正式发布仍由微信 provider 手工完成，上传不等于发布。现有 EdgeOne Git 交付单独记录，不新增中国站启用或 DNS 操作。
- 父协调者负责委派 Engineering 打包／完整 preflight、PR／checks／merge 及工作流执行；此前 103 backend、9 focused Web、319-test Web build、小程序 typecheck 和独立 Trust／Quality／Operations 有界通过仅为本地基线，不代替最终打包版本检查。
- 交给独立 Decision Review：确认上述合同／范围与现有人类授权对应，保留既有评审及 provider 门槛；不重开 A、不新增人类判断或广泛扫描。Operations 不自选路由、不自审；用户原话并非最终构建 SHA 的验证证据。
- 后续由父协调者收集工作流 URL／完整部署 SHA／各端结果，Operations 核对线上版本、health／ready、前端 SHA、开关与发布恢复状态；独立 Quality 核验授权账户详情、owner／demo 隔离及 `private, no-store`。生产 PG 容量／headroom、平台／代理／Azure 日志与有效留存仍待观察，草案阈值不成为生产 SLO。iPhone 曲线／双轴／缺口、触控／缩放／选段及 VoiceOver 留待上线后用户／Quality 验证。
- 回滚由父协调者按 Operations 方案通过 protected `main` revert 或 forward fix；保留遥测最小化、账户隔离、禁缓存、迁移历史及应急开关，不直接恢复会泄露活动标识的旧代码。恢复后重验 SHA、健康及隐私边界；详见运维文档。当前没有部署成功或恢复成功的证据。
- Cooperative trial：缺 task key，保持 **baseline／unenrolled**，不新增 trial entry。保留用户既有改动、`paseo.json` 与 stash。

## 此前 readiness Work Contract

发布打包增量（Engineering，2026-09-29）：`miniapp/scripts/sync-i18n.cjs`
只省略可由现有 key fallback 等价还原的英文同值条目，保留原型保留字、
非同值英文及全部中文；不改运行时、数据、分析、API、迁移或已接受设计。
`web/tests/miniapp-i18n.test.mjs` 的四项回归覆盖现有全部 key／占位符、
`I18N_EXTRA` 优先级、缺失／不支持消息、locale 回退与原型键，执行者测试通过。
词库源文件从 528,204 降至 261,112 UTF-8 bytes；这不是 provider 包大小。
既有中文检查原样通过；实际上传结果与新增打包增量的独立 Quality 由父协调者完成。
完整 preflight 的最终 commit SHA 与日志在发布 PR／Engineering 交接中绑定，
运维依据及上传限制见 `docs/ops/activity-detail-readiness.md`。
完整检查另发现本任务新增的不可用记录文案违反既有词汇表；将“当前账户无法查看此记录。”
改为“当前账号无法查看此记录。”并同步小程序，保留缺省状态含义及相同源文件字节大小。

- 当前有界任务：`repository-behavior`；影响 `product-value`、`user-visible-experience`、`repository-change`、`production-operation`、`trust-boundary`；风险 `security-or-privacy-boundary`。
- `/tmp/activity-detail-readiness-contract.json` 分类摘要 `sha256:33fd14793a56b7c047078175138ccd97a600a1bef7fd5b5c10a3832842c0a73e`；路由摘要 `sha256:2cf83f88e3cc213d3040ea35af808559830141aa77ce1c40ec161a5607c4792f`。主循环 Delivery，嵌套 Product、Design、Runtime；Engineering 执行此代码／测试／文档修正，Quality 独立验证，Trust 与 Operations 各自评估其边界。
- 原实施路由 `sha256:b0502848b140941673f59f9a61ac9f042bce61815ee803320afc4a18e2839997` 留作历史。当前独立 `/tmp/activity-detail-review-route.md` 为 `agent-resolved`，仅覆盖既有授权边界内的 `contract-consistency`：逐行处理、跨区域活动 URL 最小化、本地后端复现后的窄边界修复。它不授予发布批准，不把执行者自测变成独立验证。
- 输入为 `/tmp/activity-detail-product-handoff.json`、`/tmp/activity-detail-operations-handoff.md`、`/tmp/activity-detail-trust-handoff.md` 与既有 `docs/design/activity-detail-experience-spec.md`。没有重开设计、调路由或派发子角色；父协调者接收独立 Quality／Trust 后续工作。

## Product 原始结构化草案交接

以下 JSON 原样来自 `/tmp/activity-detail-product-handoff.json`；保留 `draft-structured-handoff` 和 `review_route: null`，不替 Product 改为 accepted。

```json
{
  "id": "pdr-activity-detail-readiness-v1",
  "schema_version": 1,
  "decision_type": "product",
  "owner_role": "product",
  "status": "draft-structured-handoff",
  "route_digest": "sha256:2cf83f88e3cc213d3040ea35af808559830141aa77ce1c40ec161a5607c4792f",
  "question": "How can self-coached runners inspect one recorded run and understand its sources and gaps? Implementation exists locally; release readiness remains incomplete.",
  "options": [
    "A running report: observation-first narrative with default split table and overlays; selected.",
    "B multitrack inspection: denser simultaneous comparison, weaker narrative priority; not selected.",
    "C splits-first: quicker segment entry, less whole-run context; not selected."
  ],
  "recommendation": "Complete local readiness for the selected A report on web and miniapp: recorded observation, overview, sampled overlays, default split table, source records; desktop controls inside the chart, equal-width cursor, and Praxys branding. Preserve approved interactions and truthful missing-data fallbacks.",
  "rationale": {
    "observed": "User explicitly chose A, its controls and branding, finalized design, and approved implementation. Latest intent authorizes autonomous local readiness completion.",
    "assumption": "Traceable observations and accessible segment comparison will improve understanding; no usage telemetry or measured benefit is available.",
    "boundary": "The report provides factual product observations, not AI advice. First/last source-lap comparisons explicitly do not establish a whole-run trend. No GPS, AI evaluation, training advice, medical claims, invented samples, formulas, or added collection."
  },
  "dependencies": {
    "evidence": [
      "PRODUCT.md",
      "docs/design/activity-detail-experience-spec.md",
      "docs/dev/activity-detail-implementation-impact.md"
    ],
    "roles": "Design owns experience conformance; Trust owns owner isolation, demo restrictions and disclosure; independent Quality owns verification; Operations owns capacity, activity-ID logging and release readiness.",
    "remaining": "Independent real-device Skyline curves and accessibility evidence remain outstanding. Synthetic/local checks do not establish production capacity or release approval. No new Science or Architecture decision is proposed."
  },
  "review_route": null,
  "handoff": "Parent records this handoff in the existing implementation-impact document and retains independent Decision Review under the supplied contract. Product assigns no review route or acceptance. Do not reopen chosen design or request repeated approval; surface only new material runtime choices or release authorization.",
  "outcome_plan": {
    "target": "Quality verifies every specified journey/state on both clients; subsequent user feedback should demonstrate locating a recorded value, its source and missing-data limits.",
    "guardrails": "Zero fabricated readings, unsupported advice, cross-user disclosures or unresolved critical journey/accessibility defects; preserve gaps, source labels and summary-only fallbacks.",
    "falsification": "Revise the promise if users mistake observations for advice/trends, cannot distinguish missing from recorded data, or cannot complete the approved journey.",
    "measurement": "Use explicit feedback and verification evidence; usage, adoption and comprehension outcomes remain unmeasured. This contract requires no Product Outcome Record."
  },
  "digest_algorithm": "SHA256 of UTF-8 JSON excluding digest, recursively sorted keys, compact separators, no trailing newline.",
  "digest": "sha256:3a77bf45228bd3de0f25c2bdd45ac33caa2aeeae640029fd7eedaf2a1e0b7e30"
}
```

## 影响面

| 层 | 修改和约束 |
| --- | --- |
| 数据与分析 | 仅读取该用户已有 `Activity`、`ActivitySplit`、`ActivitySample`；不改 schema、同步写入、公式或训练判断。逐时点只保留已记录的非位置字段；高密度轨迹保留原始极值与断档，不插值。 |
| API | `GET /api/history/{activity_id}/detail` 使用认证查看者身份查询本人数据，拒绝演示账户读取镜像账户的逐时流；普通账户不见其他用户同名活动。详情包括未捕获 500 在内的成功／失败响应均由路径限定的隐私中间件设置 `private, no-store`，且不含 GPS 或原始累计距离。`GET /api/history` 按查看者返回 `activity_detail_available`，将此能力值加入 ETag 盐，避免镜像汇总在不同权限账户间误复用 304。公里段仅在起点／时长／完整单调距离／总距离可核实时生成；不足表格精度的尾段并入前段，不满足前提时给事实原因。 |
| Web | 本人历史卡片进入独立详情页；演示账户仍显示汇总，但隐藏必然通向 404 的详情链接。整场概况、逐时双轴叠加、图内桌面缩放、等宽游标、可跳图的公里段与默认表格。来源设备圈缺乏时间边界，仅显示汇总；距离单独有采样时，公里段仅是静态表格。重新登录、会话失效与主动登出清除内存中的用户数据查询缓存。 |
| 小程序 | 「分析 → 活动」在允许的账户提供详情入口；演示账户只保留汇总列表并阻止程序化误导航。Canvas 轨迹、触屏游标与缩放、双端同义的缺失原因和分段规则；纯距离段不显示无目标的跳图按钮，没有新主 tab。合成模拟器已核对概况、四列表格、选段与错误态；Skyline Canvas 在安装版 DevTools 无法绘制，真机曲线与辅助功能仍待验收。 |
| 设计系统与文案 | `docs/dev/design-system.md` 记录观测曲线语义；Web／小程序用具名浅深色而不重用行动绿或科学解释蓝；中英双语走现有 Lingui／小程序词库。 |
| 运维与迁移 | 不改部署、数据库迁移、凭据、第三方连接、GPS 存储或现有活动列表排序。此变更尚未上线。 |

## 2026-09-29 readiness 修正与执行者证据

- `api/activity_detail.py` 在 owner 条件内用同一 SQL 的 `COUNT(*) OVER ()` 和 `yield_per(512)` 获取一致的数量与逐行数据。每桶只保留首尾、每字段最早的相同极值候选和段编号；公里累计器保留验证标志、端点与必要输出。全部原始行均处理，不设原始行数／并发上限，不插值、不新加客户端状态。数据库窗口运算仍有成本，必要公里输出仍会随活动长度增长。
- 12 个完整响应直接与 `/tmp/activity_detail_before_streaming.py` 比较一致；覆盖 0/1/5,999/6,000/6,001/12,013 点、极值并列、512 行边界缺测／时间缺口、非法值、来源、距离验证及微小尾段。基线 SHA-256 `375bfb9c794844c5b0db249d113130f3da41a5c446fc867b8477a118ffcfc246`；持久化摘要及复现来源见 `tests/fixtures/activity-detail/streaming/README.md`，没有复制整份旧实现入库。
- 浏览器 `web/src/lib/activity-telemetry.ts` 只模板化发出的活动 URL；`web/src/lib/appinsights.ts` 在全球／中国两端覆盖 method-prefixed name、URL/data/target/referrer、properties、SDK operation name，去除活动 URL 参数和 fragment，保留既有中国确认／异常采集限制与关联 ID、状态、计时。未知活动路径的剩余后缀也不保留；真实导航和请求不变。
- 本地真实 Azure FastAPI instrumentation 与 Uvicorn 通过内存 span/log exporter 复现旧版本泄露。`api/activity_telemetry.py` 的 server hook 和访问日志 filter 在实际受支持的 API 边界修正；安装版 Azure `_setup_instrumentations` 不传递 `instrumentation_options` 内的 hooks，因此 `api/main.py` 仅关闭其 FastAPI 自动设置，再显式 `FastAPIInstrumentor.instrument(server_request_hook=...)`。测试遍历完整导出 spans（含内部 ASGI spans）和日志；覆盖 200/401/404/405/500、编码空格／斜杠／问号／井号、未知路径和带敏感合成标记的 query。ASGI scope 和路由匹配不变。
- 聚焦 `/usr/bin/python3 -m pytest tests/test_activity_detail_streaming.py tests/test_activity_analysis_api.py tests/test_activity_telemetry.py -q` 首轮 54 通过，其中原 API 文件 27 项。最终加入实际 ASGI receive/send 断言并连同 `tests/test_telemetry.py` 重跑：**103 通过**（`/tmp/activity-detail-final-backend.log`）。Web 实际 SDK 内存 channel／initializer／pure helper 与区域保护定向测试 9 通过；`npm --prefix web run build` **319 测试、TypeScript、Vite、PWA 与 public build 检查全部通过**（`/tmp/activity-detail-web-build.log`）。`git diff --check`、新增未跟踪文件的 whitespace 检查及嵌入 Product JSON 的原始字节比对通过。这里均为 Engineering 自测，不构成独立 Quality／Trust 接受。
- 父协调者已重算 `/tmp/activity-detail-native-evidence.sha256`：原 26 文件与独立指纹 `sha256:1adaf4bd488ec60b7e4580e6d6805da73bbba7621268a1c4fe21d87e62081dec` 完全一致；本轮不改这些文件。小程序依赖已通过 `npm ci --ignore-scripts` 同步为 `svgo@2.8.4`，类型检查成功记录 `/tmp/activity-detail-miniapp-typecheck-main.log`；本轮不重复生成小程序文件或启动 DevTools。`/usr/bin/python3 scripts/check_agent_runtime_parity.py` 通过，只证明静态 adapter conformance。
- 下一个原生步骤已具体为 **iPhone：Skyline Canvas 曲线／双轴／缺口、触控选点／拖选／缩放／选段及 VoiceOver**，由父协调者安排授权手机操作和独立 Quality。安装版 DevTools 仍不能绘制 Skyline Canvas，已有截图不能填补该证据。
- Operations 提议的 43,201 点本地回归预算：单次 ≤1.5 秒、双并发最大 ≤3.5 秒、进程峰值分别 ≤300/375 MiB，**只是草案，不是已接受生产 SLO**。最终源码独立测量的 12 小时单次／最大双并发为 1.62／3.63 秒，仍不满足两项提议延迟阈值。最终表及日志见 `docs/ops/activity-detail-readiness.md`；本次每尺寸单次测量中，最大并发耗时均比基线改善，24 小时单次耗时变差，不能外推统计改善或生产容量。旧 1.34 秒与此前长活动并发回退结论仅为历史记录。
- 无本地 PostgreSQL 二进制或 Docker socket，不能提供 PG 容量证据。`scripts/appinsights_boundary.sh` 有后端及 workspace 的 30 天 retention 设置与 preflight 检查；本轮未观察线上有效值。生产 PG 容量／headroom、平台日志脱敏／留存及 Release Evidence 仍由 Operations 持有。

## 独立 readiness 快照与 alias 修正

- 历史独立 Trust `/tmp/activity-detail-trust-review.md` 与 Quality `/tmp/activity-detail-quality-review.md` 均确认 14 项 manifest，绑定快照 `sha256:95103de2ddc889e4f4a3437098acb4ddea549cb1a2636b9c8020ce3a908e4ed9`。Quality 独立通过 103 backend／9 focused web、12 个完整旧新响应、2,000 个公里及 10 个显示差分案例，无其他功能发现；这些证据保留。该轮 P2 的当前并发回退推断已被最终源码测量替代，生产容量接受仍非本地结论。
- Trust 当时对该快照暂不授予本地通过：`/HISTORY/…`、`/%68istory/…` 是 React Router 接受但旧遥测正则遗漏的别名，属 medium 必修，现已由最终独立 Trust 复核解决。修正限于 `web/src/lib/activity-telemetry.ts`：安全地单次解码匹配候选，非法编码保留原片段，静态前缀忽略大小写，输出小写 canonical template；不匹配时原值原样返回。真实请求／导航和 streaming 均不改。
- 现有 pure helper、registered initializer、actual SDK channel 测试扩展至两区域别名／referrer／operation name，保留计时、状态和关联断言；实际 React Router 匹配也验证别名被接受。FastAPI/Uvicorn 的四个 encoded API prefix 均返回 200 且已有边界脱敏通过，所以只扩展 `tests/test_activity_telemetry.py`，不改 backend production code。定向结果：9 web、2 backend 通过。
- 本次 alias 修正执行者检查：定向 web 9、backend telemetry 2 通过；完整 Web build 的 319 测试、TypeScript、Vite/PWA 和 public build 检查通过；改动的 TS helper／MJS 测试 ESLint 与 diff whitespace 检查通过。日志为 `/tmp/activity-detail-alias-{web,backend,build,lint}.log`。Backend production code 未变，未重跑整个 backend 套件或 benchmark。
- 最终独立 `/tmp/activity-detail-quality-final-review.md`、`/tmp/activity-detail-trust-final-review.md`、`/tmp/activity-detail-operations-final-review.md` 已完成有界本地复核。Quality 独立通过 alias 的 9 web／2 backend telemetry 测试及最终源码容量测量；Trust 确认 medium 已解决、无具体残留必修；Operations 确认本地证据缺口填补。没有待完成的本地 alias／Quality／Trust 复核。
- 最终评审绑定文档收尾前的 14 文件摘要 `sha256:ab876b2cba72ca74f3f12235272512679806476be190bc4166103d789f1e6f7a`；代码专用 10 文件 manifest `/tmp/activity-detail-ready-code.sha256` 摘要 `sha256:acbd123837d8c94b66330ab0630de89046535945ee8199db7fbea598edae050f` 保持不变。此次只更新文档，不改代码／测试或重跑测试；不声称新文档字节已获独立复核。
- 最终单次／最大双并发为 12 小时 1.62／3.63 秒、24 小时 3.76／6.38 秒、48 小时 5.81／14.71 秒；内存均改善，24 小时单次慢于原基线，最大并发耗时在这一次测量中均改善。阈值仍未满足且未接受。剩余为生产资源预算、PostgreSQL 容量／headroom、平台日志／有效留存及 iPhone Canvas／触控／VoiceOver；本地评审没有授予生产 SLO 或发布批准，后续用户发布授权见本文开头。

## 此前本地验证与放行门槛（历史证据）

**历史快照，非当前验收：**本节的 314 Web／27 API 测试计数及旧 1.34 秒测量仅记录此前实施阶段；当前 readiness 证据与独立评审快照见前两节。

- 修复后重跑整文件 `pytest tests/test_activity_analysis_api.py -q`（27 通过；包含同名 ID 分圈／覆盖隔离、owner↔demo 和跨 owner ETag、注入未捕获 500 后禁缓存）、`npm run build`（Web 314 个单测及构建通过，新增选段放大边界回归）、`npm run typecheck`（小程序通过）、`git diff --check`（通过）与活动详情 WXML 的 DevTools 单文件编译（通过）。本轮对改动页面、组件及图表逻辑执行定向 ESLint，对 Web／小程序活动页面及其组件执行 Impeccable 检测（0 发现），并以工作区活动页面的显式路径运行 UI quality gate（通过）；以 `origin/main` 对 `HEAD` 执行的 gate 因本轮仍为未提交改动而无法检测这些页面，不能用作通过依据。AuthProvider 和 Web 通用 API 类型文件各有两处在 `origin/main` 已存在的 ESLint 错误；这两文件不计入定向 ESLint 已通过项。
- 浏览器仅使用隔离合成数据，检查桌面 1440×900、手机 390×844 与 320×700、英文／中文、浅／深色、缺指标／无采样、他人活动 404、断网重试、拖选／点击／键盘／触屏及来源表格；本人历史链接由键盘进入详情，演示历史在桌面和手机均保留汇总、隐藏不可用链接，原验收无额外控制台错误。Web 选段缩放修复后另在桌面与 390px 手机实际点选第 3 公里：视窗从 720–1080 秒缩至 720–900 秒，无页面运行异常或横向溢出；此次定向复测不等于重新核对全部浏览器状态。API 集成测试另核验匿名 401。原生分辨率截图及本地索引在 gitignored 的 `test-screenshots/ui-quality/activity-detail-implementation/index.html`。Browser plugin 未提供，本次使用隔离 Playwright；模拟断网及他人活动时的预期 404／网络错误不能当作非预期异常。
- 小程序使用 Tencent DevTools 0.3.11、390×844 逻辑模拟器与封闭 `wx.request`／`getStorageSync` 合成 mock；其他路由固定返回 503，不读取真实 token／账户数据。已点按切换主指标并触发 picker 变更，点按游标、横向拖选、按第 2 公里跳到 390–810 秒、放大后保持在 390–600 秒并返回表格；Flex 修正模拟器中概况与分段表格的纵向塌列，纯距离公里段无虚假跳图按钮。已核对稀疏采样、单指标、纯距离、无采样、404、服务端 503、合成断网回调及重试；英文深色页的图表轴／游标文案也随语言刷新。完整合成夹具在 `tests/fixtures/activity-detail/`，原生分辨率截图置于上述本地索引。验收结束后在 mock 生效时回到登录页，仅移除本任务的合成夹具，恢复两个 wx API mock，并由 DevTools 成功关闭本任务的项目窗口；未清真实存储或操作其他窗口。Tencent 控制台明确报 `[Component] <canvas>: 开发者工具暂未支持 Skyline 下的 canvas 组件调试`：模拟器可验页面状态和手势事件，**不能**据空白画布证明曲线笔画、双轴缩放、缺口形状或真机辅助功能；需在受授权真机预览并由独立 Quality 复核。`compile_wxss` 只接受 `.wxss`，本页 `.scss` 由项目 Sass 插件在模拟器渲染，不能把该工具报错视为样式编译证明。
- 合成高密度成本测量：同一活动 12 小时／43,201 条 14 指标逐时记录，隔离 SQLite/TestClient 单次 200 用时 1.34 秒、进程峰值 291 MiB；双并发分别 3.10／2.23 秒、峰值 364 MiB，响应正文 1.31 MiB。此结果不是生产 PostgreSQL／Azure 负载承诺；原始查询仍无行数上限，发布前需由 Operations 结合容量与请求遥测设定预算和观察过载风险。
- 独立 Quality 首轮发现两处 P1：纯距离公里段死按钮和精度以下的 0.00 km 尾段；修复后同一 reviewer 对 18 个核心文件独立复核，API `-k activity_detail` 8 通过、Web 定向 6 通过，未发现新 P0／P1（代码内容摘要 `sha256:12f61c243a486198a60b785db2183cea264e4848ffd5a7121ef9aa4581265aa8`）。Quality 检视了已有截图，但未重新演练浏览器或小程序原生交互。独立 Trust 两轮只读复核确认本轮没有剩余必修 P0／P1，可进入发布评审，但不代替容量验收、活动 ID 日志边界确认及 Decision Review。Impeccable 的 Geist 通用字体告警与用户批准的 Field Lab 字体选择冲突，已在 `.impeccable/config.json` 将 `overused-font=Geist` 例外严格限定到本页 CSS 并写明原因；其余检测继续生效。
- 末轮独立只读 Quality 按验证专用合同 `sha256:7940212873cca2ea192c0888a476e609093889371399af5cd6a24294b8725036` 逐张查看 12 幅小程序原始 PNG（363×785），核对四列表格、A 概况、可见选段和中英轴文案、稀疏／单指标／纯距离／无采样及 404／503／断网错误态；在此有界范围内未发现新 P0／P1。其对第 2 公里 390–810 秒缩至 390–600 秒及返回行的判断只有代码静态佐证；截图本身不证明触控序列、实时换语言、断网回调或重试成功。独立审查的 26 个实现、夹具与截图文件读时指纹为 `sha256:1adaf4bd488ec60b7e4580e6d6805da73bbba7621268a1c4fe21d87e62081dec`；审查确认 HEAD 相同，但原先提供的不同作用域摘要缺少文件清单，无法独立证明两者等同或截图生成于当前源码。操作者的模拟器交互记录、测试结果与 mock 清理未由该只读复核重演，真机验证仍未完成。
- 当前主线已对齐，Product 草案及本地 corrections 的独立 Decision Review 路由已记录，本地独立 Quality／Trust／Operations 有界复核已完成；剩余为 Operations 的生产容量／日志证据与 iPhone 真机曲线／触控／VoiceOver 验收。主线已允许授权的小程序任务使用前台 DevTools，无额外前台批准开关，但 Tencent 自身登录、权限与敏感操作确认照常适用。以上本地验证与有界独立复核不等于正式发布授权。

## UI quality

- Impeccable: `polish web/src/pages/ActivityDetail.tsx`; 新增 Web／小程序界面的定向检测及 UI quality gate 已通过。
- Visual review: Web desktop 1440×900；mobile 390×844／320×700；小程序 390×844 模拟器合成页面（截图 363×785），Canvas 线条需真机核对。
- Primary journey: 历史活动 → 详情概况 → 双轴叠加及游标 → 公里段表格 → 返回表格；演示账户只见汇总，不提供无法访问的链接。
- Reviewer handoff: local-only - `test-screenshots/ui-quality/activity-detail-implementation/index.html`（原生分辨率合成数据截图）。
- States checked: Web 加载、空采样、指标缺测、纯距离轨迹、404、断网重试、正常交互、英语／简中、浅色／暗色、窄屏；小程序合成正常、稀疏、单指标、纯距离、无采样、404、503／断网、中文浅色与英文暗色，交互只覆盖模拟器可观察部分。
- Accessibility: Web 键盘进入详情及图表游标、分段回焦、触摸选点、可见焦点、无横向溢出已检查；减少动画规则已静态检查，小程序模拟器触控与控件文字已核对，真实 VoiceOver／TalkBack、Skyline Canvas 笔画待真机验收。
- Design system impact: updated in this PR - `docs/dev/design-system.md` 记录具名浅深色观测曲线，不借用行动绿或推理钴蓝。
- Miniapp parity: partial - 与 Web 同步指标、缺失原因、双轴文案／分段与演示账户入口语义；类型检查、模拟器游标／选段／缩放事件通过，真机 Canvas 双轴曲线、缺口与无障碍仍未验证，依 2026-09-29 用户授权延后至上线后测试，不宣称 parity 完成。
- Exceptions: `.impeccable/config.json` 只为已批准的 Field Lab 活动详情 CSS 豁免 Geist 通用字体告警；其余规则不豁免。

## 2026-09-29 八项 UI 修订 · Engineering 本地执行证据

- 严格绑定 `/tmp/activity-ui-refinement-contract.json` 路由 `sha256:c022991c4db14340a5cc592072dc27a267206da93657b4fdca8a3a5f83bf7929`；接受的 Design 文件完整 SHA-256 仍为 `681a11e71777cf4cc9690f253c806053996083f6a415a21f58243eda76f34c5d`。父协调者提供独立 DRR 的 `agent-resolved / contract-consistency` 本地实施边界；本节是执行者自测，独立 Quality 由父协调者在本实例终止后另行安排。trial 为 baseline/unassigned：`tsk_7e090823d44e0c207f31c3321ce185f6002372df0fafd020d53e6d5d90c3bbfc`。
- 影响限于 Web `ActivityCard`、`ActivityDetail`、`ActivityTraceChart`、新的来源／展示辅助代码与 `ActivityDataInformation`，小程序对应 history/detail/trace、展示辅助代码、两端本地化及 Web 测试。数据管线、分析公式、API、鉴权、依赖／锁文件、迁移、工作流和运维均未改；不修改冻结 Design，不提交、推送、部署或操作分支／stash。
- AC1–8：原生报告入口包含运动图标及真实汇总，分段和 DFA 独立；去掉时间口号与无比较占位；活动来源仅在头部友好显示，采样／环境来源分开保留；使用“记录分段”；所有曲线从顶部选择；补充汇总按字段去重、准确计数且为静态定义列表；详细解释集中在默认折叠的“数据信息”，真实缺口／精简／时间起点及禁用理由仍可直接阅读。分段选择／返回、区间、游标、叠加上限与原绘线算法保持不变。
- 自动检查：19 项定向测试通过（`/tmp/activity-ui-refinement-focused.log`）；完整 Web build 的 **336 项测试**、TypeScript、Vite/PWA、public build 检查通过（`/tmp/activity-ui-refinement-web-build.log`）；小程序 typecheck 与词库检查通过（`/tmp/activity-ui-refinement-miniapp.log`）；相关 Web ESLint 通过（`/tmp/activity-ui-refinement-lint.log`）。最初 React-refresh 的混合导出错误通过将 `useRecordSourceName` 移入独立 hook 解决，未抑制规则。i18n 确定性检查通过，3034 个 active entries、0 human-review routes（`/tmp/activity-ui-refinement-i18n-check.log`）。
- 渲染路线：本实例无 common Chrome MCP／Browser plugin，按已授权先例使用现有隔离 Python Playwright；全部请求由封闭合成 mock 接管，无真实账户／训练数据请求。`/tmp/activity-ui-refinement-browser.py` 完成 18 组场景，包含 1440×900／390×844／320×700 × EN／zh × 浅／深色、reduced motion、浏览器 accessibility tree 的历史链接名称与数值单位、Enter／modifier-click、分段／DFA 独立、14 指标可达、区间／游标保留、选段回焦、hover／拖选／触屏自然纵向滚动、静态汇总无 hover／tab stop、缺口／精简／summary-only／distance-only／single-metric／demo。无非预期请求、浏览器异常或水平溢出；三活动中文历史另核对唯一 split IDs、行间隔离和零列表 detail 请求。
- 原始证据：`test-screenshots/ui-quality/activity-ui-refinement/`，优先查看 `history-desktop-zh-three-activities.png`、`report-desktop-zh-light.png`、`report-desktop-zh-disclosures.png`、`report-390-zh-light.png`；该目录另有 320px 深色、稀疏记录与 accessibility／interaction JSON。执行日志 `/tmp/activity-ui-refinement-browser.log`。本次按 Impeccable distill 完成一次桌面／手机合并检查、一次集中修正及一次确认，未新增 gallery。
- UI quality：现有设计系统足够，`none - existing design system already covers the change`。显式未提交改动路径 gate 通过（`/tmp/activity-ui-refinement-ui-check.log`），含小程序 SCSS 的定向 detector 返回零项（`/tmp/activity-ui-refinement-impeccable.json`）。运行时 hook 对既有页面细字号及 JetBrains Mono 字体拼写的提示按保留的 Field Lab 排版判断为上下文误报／既有取值，未新增抑制或设计系统迁移；新披露正文使用既有 `.875rem` 档位。
- 未验证：本次没有安全的任务专用 DevTools 窗口，未启动／访问个人小程序账户；小程序只有实现、执行式 view-data／导航测试和静态／类型证据，不能称原生通过。Skyline 绘线、iPhone 触控／VoiceOver、完整真人读屏／对比度验收及独立 Quality 均仍未完成。加载／离线重试／404 行为保留，本轮浏览器未重新覆盖这三个状态。生产／发布接受不在此次本地任务内。
- `http://127.0.0.1:5188` 仅为独立 Quality 使用同一 mock harness 的验证服务器，**不是用户可直接浏览的合成预览**。临时 `/tmp/activity-ui-refinement-vite.mjs` 禁用代理，直接 `/api/*` 一律 503（`/tmp/activity-ui-refinement-server-guard.log`）；合成响应只存在于 Playwright 拦截中。工作树及证据清单／摘要见 `/tmp/activity-ui-refinement-engineering.md`。

### 独立 Quality Q1 对比度修正 · 待独立复核

- 输入为 `/tmp/activity-ui-refinement-quality-review.md` 的唯一 P1：Web 历史卡片 12px 日期／次要事实在深色卡片上只有 **3.882:1**。此前 19 项测试、18 组浏览器复演、11 组探索检查为 Quality 对旧候选的独立证据，不是本修正的接受。恢复执行时旧候选全部 24 项摘要匹配；HEAD 仍为 `bf1557dfb550e042b82a273094418ff392e845a2`。
- 唯一产品代码改动：`web/src/components/ActivityCard.tsx` 的日期及完整次要事实行使用已有 `dark:text-foreground`；浅色继续原 `text-muted-foreground`，12px 常规字重、布局和图标不变。新增一项回归覆盖本人／demo 卡片的两类文字及所有次要数值。没有全局主题、本地化、原生或其他页面改动，也未抑制任何规则。
- 执行者当前检查：20/20 定向测试，337/337 完整 Web build 测试及 TypeScript／Vite/PWA／public build，通过相关 ESLint、显式改动路径 UI gate、detector（0 项）、diff whitespace。日志统一为 `/tmp/activity-ui-refinement-q1-{focused,web-build,lint,ui-check,contrast,whitespace}.log`，detector 为 `/tmp/activity-ui-refinement-q1-impeccable.json`；此前 React-refresh 修正仍无抑制。
- 封闭合成 Chromium 实测六组历史场景（EN／zh 浅深色，320／390px，并补桌面 1440px），每组检查三张卡片全部 11 个小字节点的默认／hover／键盘焦点态，共 **198 次**。从实际 computed style 经 Canvas 转换 sRGB，并合成透明 hover 背景后计算 WCAG：浅色最低 **6.849:1**，深色最低 **14.169:1**；日期及次要事实深色默认 **15.264:1**。全部高于 4.5:1；无非预期请求、控制台错误、溢出或列表 detail 请求。仅作缺陷定向确认，没有新一轮外观修订。
- 小程序并无相同 token 缺陷：现有 `--text-muted`／`--surface` 静态计算为浅色 **5.357:1**、深色 **5.551:1**，无需修改。此计算不是原生渲染验证；Skyline／iPhone／VoiceOver 仍延后，图标不按普通文字阈值处理。
- 当前截图与逐节点测量保存在 `test-screenshots/ui-quality/activity-ui-refinement/q1/`，其中 `history-320-en-dark.png`、`history-390-zh-dark.png`、`history-1440-zh-light.png` 是本修正的原始截图，`contrast-results.json` 保留完整计算值。父目录旧历史截图和先前日志仅作旧候选证据，未覆盖。测量 harness `/tmp/activity-ui-refinement-q1-contrast.py` 复用原封闭 mocks；恢复服务器只使用已有 guarded config／Quality bundled-loader runner，直连 `/api/*` 503 已再次确认。初次测量脚本的原生 token 段落定位误匹配注释，修正后完整定向运行成功，未因此修改产品代码。
- 当前候选／证据 manifest 已随本节更新，完整摘要与三个精确增量路径见 `/tmp/activity-ui-refinement-engineering.md`；旧 manifests 与 handoff 另存 `/tmp/activity-ui-refinement-pre-q1-*`。冻结 Design、用户 `paseo.json`、三份 stash 均保持原摘要。Engineering 仅提供实施与自测，Q1 是否关闭由父协调者安排同一独立 Quality 在本实例终止后复核，不作发布声明。
