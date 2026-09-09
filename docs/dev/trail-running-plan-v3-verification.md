# Trail v3 评审包验证记录

**记录角色：Engineering；独立判断归 Quality，审查路由归 Decision Review Router。**
本文件转录父协调者提交的验证结果，不是执行者自审、人类批准或运行启用。
核对时刻：2026-09-08 16:07:50 UTC，即 2026-09-09 00:07:50 Asia/Shanghai。
内容入口：[评审表](trail-running-plan-v3-review-sheet.md)、[实施 handoff](trail-running-plan-v3-implementation-handoff.md)、
[编译器](../../analysis/trail_training_context.py)、[针对性测试](../../tests/test_trail_training_context.py)。

## 验证对象与来源

| 对象 | 精确标识 |
| --- | --- |
| 隔离验证副本 | `/tmp/praxys-trail-v3-validation` |
| Baseline commit | `1efd8c0196316c83115366f1192bb0827643bac5` |
| 验证 snapshot commit | `60a619f5296bdb2197ac42f3710ff496e6ac1394` |
| 验证 snapshot tree | `c2d77967c9860afd6439393ac22e936b62aef728` |
| 仓库锁定 plugin commit | `a074ce4f018d3811f9f8af840c156ff98a335dd9` |
| 编译器文件 SHA-256 | `45ab399ed5e3a978be5cfa36f92d6b4bd65b94f4edd8da675e8fce1711d056d6` |
| 测试文件 SHA-256 | `332dee9fc4d8e8e8221c232a194aa1b79be7d971e83a300edc0f9f789f9c25b3` |
| 最终 preflight log SHA-256 | `34a97a4269e1cde39d7cde4fb77568892d9df97c8ba5e558797ffa2a2246b384` |

Snapshot 的 commit 仅存在于验证副本，不是源工作分支提交。副本初始化了仓库锁定的 plugin，
未修改 submodule pointer。原始结果保存在 `/tmp/praxys-trail-v3-preflight-verified.log`。
本地 `/tmp/praxys-trail-v3-source-manifest.json` 列出 20 个任务文件；核对时它们均与通过的
隔离 snapshot 字节匹配。用户的 `paseo.json` 保留，未纳入 snapshot。
**本验证记录是在上述 20 文件 snapshot 之后新增的元数据，不属于该次测试对象。**

## 独立 Quality

最终结论：**PASS_WITHIN_REVIEW_PACKAGE_BOUNDS**，两项 P2 均已关闭。

- 初审：独立 104 tests、742 次客户端输入 probes；114 个既有科学文件在按既定换行规则处理后
  与 baseline 字节一致；核对 26 个文档链接及 5 个科学摘要值。
- 来源核验：12 个来源的 DOI/PMID、标题与 full-text 身份和核验级别；另核对 3 篇全文相关段落，
  未发现与评审包相关解释矛盾。此记录没有把摘要来源提升为全文证据。
- 初审发现：深层 YAML/JSON 的 `RecursionError` 未封闭；原始合同版本类型可被共享加载器归一化，
  使错误的布尔、字符串或浮点版本仍通过旧的摘要绑定检查。
- Engineering 仅修复新编译器边界并补回归，未改变科学剂量；修复详情见实施 handoff。
- 独立复核：**27 compiler regression tests passed，94 deselected**；**32 raw-contract probes passed**。
  执行者另有最新 focused **121 passed**；这是开发检查，不能替代独立 Quality 判断。

## 最终完整 preflight 与尝试历史

在上述隔离副本执行：

```text
python scripts/agent_preflight.py --base 1efd8c0196316c83115366f1192bb0827643bac5
```

最终完整 **PASS：3601 passed，1 skipped，837.67 秒**；`git diff --check` 及最终 clean worktree 检查通过。
唯一 skip 是 `tests/test_pg_migration.py`：未配置 scratch `PRAXYS_TEST_POSTGRES_URL`，
因此未宣称验证 PostgreSQL migration。没有 Web/miniapp 源码变化，本轮没有新增 rendered/build 验收。

此前尝试均保留在 `/tmp` 原始日志中，不计作成功：

1. 首次完整运行在编译器待修时主动中断，exit 130。
2. 第二次因验证副本尚未初始化 plugin，缺少 `server.py`；单例复现 **1 failed**，随后中断 exit 130。
3. 初始化仓库锁定 submodule 后，该单例 **1 passed**；随后最终完整 preflight 才获得上述 PASS。

## Decision Review 与后续责任

最终路由：**human-review-required**。本轮评审材料准备已授权，Quality 和 preflight 通过后可交付；
该路由不是当前新增范围或许可请求，也不把草案变为 accepted、active 或 superseded。
后续科学审查队列的 subject 均为对应来源摘要，不能用生成合同摘要替代 SDR approval subject：

| Subject | Review role | Source digest |
| --- | --- | --- |
| `evidence-trail-training-resource-adaptation-v1` | `evidence_reviewer` | `sha256:021e84168d4500ed80edb8f667731afc15eb5a036338ce4393ac33a7f9ea9aa1` |
| `sdr-trail-running-goal-ontology-v3` | `decision_approver` | `sha256:ce47bdf570a307d91e76ad229d48f88871ea49dd7d01f97fdcfac90feb40e301` |
| `sdr-non-ultra-trail-plan-generation-policy-v3` | `decision_approver` | `sha256:38e62a7634c4a174ec7d1af50e20ee403b65f790da9f7da31cc0f48c6a222d06` |

PDR、DDR、ADR、TDR 各自仍有后续审查责任。没有记录任何人类批准、源分支 commit/push、部署或启用。
本轮未验证个体疗效、安全、完整历史/户外预算、完整 scheduler、存储/采用、未来鉴权/Statsig/provider
集成、UI 或部署。未来本人完成 14 天生成/采用与七天复核的 Product Outcome 尚未发生。
