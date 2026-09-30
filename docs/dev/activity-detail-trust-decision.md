# 活动详情 Trust 决策记录（草案）

**状态：**草案保留；有界本地独立 Trust／Quality／Operations 复核已完成。最终 Trust 确认 alias medium 已解决、无具体残留必修，不构成生产发布批准。当前路由摘要：`sha256:2cf83f88e3cc213d3040ea35af808559830141aa77ce1c40ec161a5607c4792f`；原实施路由 `sha256:b0502848b140941673f59f9a61ac9f042bce61815ee803320afc4a18e2839997` 为历史。

2026-09-29 的 `/tmp/activity-detail-trust-handoff.md` 建议这些本地修正属于既有最小化／私有边界；`/tmp/activity-detail-review-route.md` 独立分配 `agent-resolved`，范围仅为已授权边界内的 `contract-consistency`，无新的收集、披露、产品承诺或生产权限。Engineering 在此记录实施证据，不替 Trust 接受决策或验证自己。

## 受保护对象与边界

一次活动的逐时功率、心率、配速、呼吸率等读数与来源比历史列表汇总敏感。已认证账户只能读取本人已有的活动、分圈及采样；同名活动 ID 不跨用户查询。演示账户可以通过既有 `get_data_user_id` 看到被镜像账户的汇总数据，但**不能据此自动获准查看其逐时健康读数**。GPS、经纬度和原始累计距离不在详情响应中。

## Trust 提议与实施

- 将逐时详情固定为认证查看者本人范围；演示账户默认返回与不存在活动相同的 404。在没有单独、明确的隐私决策前，不扩展演示镜像的逐时披露。现于 `api/routes/history.py` 实施；不改变既有历史汇总的演示权限。
- 为详情路径的成功、未认证、他人活动、演示账户和错误响应统一设置 `Cache-Control: private, no-store`，而不依赖成功分支的路由函数；`api/main.py` 的限定中间件承担该边界。未捕获异常且响应尚未开始时先发送通用禁缓存 500 再重抛，保留现有错误报告；响应已经开始时只重抛，不发送第二个响应。
- 演示账户虽仍可浏览历史汇总，历史 API 按查看者而非数据所属者返回 `activity_detail_available=false`；两端隐藏不可用的详情入口，详情端点仍独立拒绝访问。历史 ETag 同时包含 owner 身份和此能力值，不能跨普通／演示查看者误复用 304。
- Web 在成功切换身份、无效会话清理和主动登出时清空内存查询缓存；小程序以原有 token 失效／重启流程清理在内存中的页面，不将历史逐时记录持久化。
- 当前原始采样 count 与 stream 共用 owner-scoped window SQL；增量保留极值、字段段号、完整公里验证与必要输出，不截断原始记录。12 个完整合成响应与旧模块逐项一致，golden 摘要来源记录于 `tests/fixtures/activity-detail/streaming/README.md`。
- 浏览器全球／中国 emitted payload 将活动路由模板化为 `/history/{activity_id}`、`/api/history/{activity_id}/detail`，移除 query／fragment；未知活动路径同样去掉标识符和剩余后缀。覆盖方法前缀、URL/data/target/referrer、properties 与 SDK operation name；不改导航、请求、关联 ID、状态、耗时或既有中国保护。
- 本地 Azure instrumentation 的内存 exporter 和真实 Uvicorn 日志复现了旧版本活动标识符外泄；窄范围 server hook／access filter 修复已展示的通道。支持 API 是显式 FastAPI instrumentation hook，不能把 hook 置于会被 Azure 忽略的 `instrumentation_options`。测试包含编码空格／斜杠／问号／井号和未知 404、全部导出 spans 与访问日志；它不证明平台／代理日志已脱敏。

## 证据与剩余风险

- 最终独立结论见 `/tmp/activity-detail-trust-final-review.md`、`/tmp/activity-detail-quality-final-review.md` 和 `/tmp/activity-detail-operations-final-review.md`，绑定文档收尾前 14 文件摘要 `sha256:ab876b2cba72ca74f3f12235272512679806476be190bc4166103d789f1e6f7a`。代码专用 10 文件 manifest `/tmp/activity-detail-ready-code.sha256` 摘要 `sha256:acbd123837d8c94b66330ab0630de89046535945ee8199db7fbea598edae050f` 未变。本次仅记录评审，不将新文档字节视为已复核，也不由 Engineering 自行批准。
- Trust 本地 conformance 通过，无残留 alias 必修；Quality 独立通过 9 web／2 backend telemetry 和最终源码 benchmark。旧快照 `95103de2…` 的 103 backend、12 完整基线响应、2,000 公里及 10 显示差分证据保留。Operations 确认本地证据缺口填补；没有待完成的本地 alias／Quality／Trust 复核。
- `tests/test_activity_analysis_api.py` 覆盖匿名 401、他人／演示 404、200/401/404/405 及注入未捕获 500 的 no-store、同名活动 ID 的分圈／覆盖隔离、跨 owner/demo ETag、GPS 与原始距离排除；`web/tests/authenticated-fetch-policy.test.mjs` 防止遗漏三条身份转换的缓存清理；浏览器合成数据验证主动登出后不能重开旧详情，演示账户列表不提供死链接。
- 历史 1.34 秒／最大双并发 3.10 秒／364 MiB 及此前长活动并发回退推断由最终源码证据替代，详见 `docs/ops/activity-detail-readiness.md`。最终 12/24/48 小时单次／最大双并发分别为 1.62／3.63、3.76／6.38、5.81／14.71 秒；内存均改善，24 小时单次变差，最大并发耗时在这一次测量中均改善。12 小时提议的 1.5／3.5 秒仍未满足且未接受；一次 SQLite 测量不证明统计改善或生产容量。6000 点仅约束显示输出，CPU／数据库／必要公里输出仍随输入增长，不新增活动或并发限制。
- 有界代码验证已完成，原生验收尚未完成。Product 原样结构化草案与局部 Decision Review 路由已记录，但不等于正式 accepted 决策或 Release Evidence。剩余为生产 PG／资源预算、平台日志／有效留存和 iPhone Skyline Canvas、触控、VoiceOver；没有已接受生产 SLO 或发布批准。
- `scripts/appinsights_boundary.sh` 明确设置并 preflight 检查后端／workspace 30 天 retention；线上有效设置、平台日志和实际保留范围仍未观察。没有 PG 二进制或 Docker socket，不能声称本地或生产 PostgreSQL 容量通过。任何演示账户逐时披露的放开仍需另行授权。
