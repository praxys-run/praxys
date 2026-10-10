# OpenAI Decisions API：Praxys 应用研究

**状态：归档研究，尚未决定采用或启动试点。**

**讨论与接口探测日期：2026-10-08。**

**归档与官方资料复核日期：2026-10-10。**

**仓库参照：`e646278aae7f0e6b9ed32bb038e24ecc808feba1`。**

本文保留 Decisions API 与 Jev 的比较、用户已部署 Azure GPT-6-Luna 的
背景，以及产品、代码开发、服务运维三个方向的候选用途，供之后重新讨论。
文中的用途、评测规模和接入方式均为待验证建议；没有进行模型效果评测、
带鉴权的 Azure 推理、用户数据实验或能力上线。

## 1. 已确认的官方能力

OpenAI 的 [2026 年 10 月更新记录][openai-changelog]记载：Decisions API 于
2026-10-06 发布 Beta，使用 `gpt-6-luna` 和独立的 `/v1/decisions` 端点。
[官方指南][openai-decisions]在本次复核时仍将其标为公开 Beta。

它把输入与问题转成应用可处理的判断，支持文本和图片。三种问题类型分别是：

| 类型 | 用途 |
| --- | --- |
| `predicate` | 估计某个条件成立的概率 |
| `choice` | 从给定类别中选择，返回类别概率分布及单独的 confidence 字段 |
| `score` | 按给定的有序等级评分，返回等级分布及概率加权的分数 |

调用方式是 `POST /v1/decisions`。部署同名模型、能调用 Responses，
以及资源开放 Decisions 端点，是需要分别确认的条件。

概率应结合应用自己的标注样例、误报和漏报代价设置阈值。当前没有证据证明
这些输出已经在 Praxys 的任务上校准；普通 Responses JSON 中由模型自报的
confidence，也不能直接视为原生 Decisions 的概率。

官方指南的基础报价为 **每百万输入 token USD 0.10**，仅计算输入；地区处理
及长上下文可能加价。该报价对应原生 Decisions 请求，不能用于估算 Azure
Responses 的费用。供应商宣传的速度优势也不是 Praxys 的实测结果。

## 2. 与 Jev 的关系

TypeSafe AI 的 [Jev 快速入门][jev-quickstart]提供相近的类型化判断能力：

| 判断用途 | OpenAI Decisions | Jev 示例 |
| --- | --- | --- |
| 条件判断 | `predicate` | `noul` |
| 给定类别选择 | `choice` | `choice` |
| 有序评分 | `score` | `score` |

这是用途上的近似映射，不表示请求或响应可以互换。Jev 示例使用
`POST /v1/systemone` 和 `jev-latest`；两者的字段、分数定义和置信度解释
需在接入时按各自契约核对。

它们都值得作为频繁语义判断的候选。类型化输出有助于减少应用解析的歧义，
但格式有效并不证明判断正确。当前没有同一批 Praxys 样例上的准确率、校准、
延迟或总费用对比；Jev 当前价格及账号开放条件也需要另行复核。

## 3. Azure Luna 部署：可用性仍需分层确认

用户在讨论中报告已部署 Azure GPT-6-Luna，并提供了一个
`/openai/v1/responses` 地址。这是用户报告的部署背景，未在本研究中独立验证
部署名称、模型版本、账号权限或成功推理。本文省略具体资源主机名。

微软的 [Azure 直接销售模型目录][azure-models]列出 `gpt-6-luna` 对
Responses 和结构化输出的支持。这说明可以评估通过普通 Responses 实现
固定类别判断的路径，不能据此确认特定资源已开放 Decisions。

2026-10-08 讨论期间，对同一资源进行过以下**无凭据**探测：

| 方法 | 路径 | 请求上下文 | 返回状态 |
| --- | --- | --- | --- |
| GET | `/openai/v1/responses` | 无 Authorization | 401 |
| GET | `/openai/v1/models` | 无 Authorization | 401 |
| GET | `/openai/v1/decisions` | 无 Authorization | 404 |
| POST | `/openai/v1/responses` | 无 Authorization，空 JSON `{}` | 401 |
| POST | `/openai/v1/decisions` | 无 Authorization，空 JSON `{}` | 404 |

以上结果来自当时的工具执行记录；没有另外留存原始 HTTP 响应或请求 ID，
归档时也未重新探测。因此它们是有日期和条件的历史观察，不是持续监测、
成功推理或可独立重放的认证证据。

404 是资源当时未暴露该路由的迹象，但不构成 Azure 全平台不支持 Decisions
的证明。当前研究结论为：**Azure Luna 的普通结构化分类值得评测，原生
Decisions 在该资源上的支持尚未确认。**

后续确认需要在授权的 Azure 会话中核对实际部署名，以合成、无敏感输入
完成有效的 Responses 和 Decisions 请求，并区分鉴权、路由、模型/参数支持、
配额及暂时故障。401、403、404 或 429 都不能当作已完成能力测试。

仓库当前的 [AI 客户端](../../api/llm.py)使用 Azure OpenAI 和 Entra
身份认证。用户的新增部署不表示 Praxys 运行时已切换模型或支持新端点。
直接接入 OpenAI 服务还会引入不同的供应商边界，须重新核对数据用途、
身份、存储、故障处理及[现有隐私契约](adaptive-plan-personal-context-privacy.md)。

## 4. 三个候选应用方向

### 产品本身：判断下一步是否需要更多背景或计划评审

最直接的候选是已有的[个人背景分类](../../api/personal_context_processing.py)：
当前模型输出固定的 `clarification`、`no_change`、`insufficient_evidence`
或 `suggestion` 等结果，再由服务器检查和处理。

例如，用户确认“某天最多有 30 分钟”，分类器可以辅助判断是否追问、保持
计划，或进入有范围限制的调整评审。它不能从未完成训练的设备记录中猜出
原因；日期、可用时长等背景仍需要用户提供和确认。

未来评测可沿用[现有 suggestion-first pilot](adaptive-plan-context-pilot.md)
的范围。病痛等安全类别仍走既有安全路径；模型判断不修改计划，也不替代
用户接受提案。收益假设是更及时、少无效追问、类别判断更可靠，尚未验证。
其他候选包括检查 Coach 文案是否超出输入证据，以及排序需要详细解释的
发现；确定性指标和既有数据充分性检查仍保持权威。

### 代码开发：任务分流与重复语义审核

候选用途包括识别变更涉及的风险、给出适用上下文和补充验证建议、归类
CI 失败，以及辅助[翻译语义审核](i18n-automation-hardening.md)。例如，
检查中文翻译是否丢失条件，或把“可以”变成“必须”。

原讨论曾将 Work Router 作为任务分类接入点；归档时 main 的 PR #890 已
简化为[单会话执行模型](../../AGENTS.md)。未来应接入当前会话工具或检查
脚本，不能因本文恢复旧角色循环。分类结果只能提供候选和证据，不能跳过
必需检查、独立审查、科学接受契约或 GitHub 合并权限。

模型部署本身也不会让 Codex/Copilot 自动调用该能力。若以后选择试验，
仍需明确调用位置、输入范围和故障处理，并测量额外调用是否真正节省工作。

### 服务运维：匹配排障入口与识别缺失证据

可以用脱敏的错误类别、失败范围、健康检查结果和发布时间，辅助选择已有
runbook，列出下一项有区分力的观测，整理事件摘要或建议升级处理。

例如，[Garmin 排障手册](../ops/sync-troubleshooting.md)明确区分认证门禁、
限流和部分接口失败；`auth_required` 需要遵循既有重连路径，不能把不断
重试当作恢复。分类器可辅助匹配路径，而不能把其判断当成已证实的根因。

[事件响应手册](../ops/incident-response.md)仍约束动作和恢复验证。
模型输出不增加重启、回滚、配置或数据库操作的权限；一次健康检查成功也
不证明完整恢复。运维数据与运动员私人背景应保持各自的数据用途和权限边界。

## 5. 之后可讨论的评测建议

以下是**未执行、未批准启动的候选评测**，用于明确下次讨论的问题：

- 每个方向先选择一个窄问题，约 100 条公开或合成的中英文样例，合计约
  300 条；不得把私人背景记录直接变成跨用户评测语料。
- 比较现有方法与已验证可调用的 Azure Luna。原生 Decisions 和 Jev 只有
  在访问条件确认后才加入对照；尽可能分离模型变化和接口变化的贡献。
- 产品观察错误建议和无效追问；开发观察风险漏报和语义误判；运维观察
  错误排障路径和漏升级。共同记录不确定样例处理、P95 延迟及总费用。
- 使用留出的标注样例决定阈值，增加有针对性的边界样例。小规模样本不
  能证明罕见风险已解决，也不能据此授予新的自动执行或合并权限。
- 后续接入可考虑“最小必要证据 → 类型化候选判断 → 确定性策略 → 原有
  执行与验证流程”。共用问题模板和评测方法，各领域保留自己的数据权限。

目前已有[内容指纹和缓存](../../analysis/insight_hash.py)等减少重复生成的
机制，因此不能预设再加一次分类调用一定节省成本。应按完整调用链测量，
同时核对因跳过生成而引入的过期内容或漏报。

## 6. 再次讨论时需要回答的问题

1. 实际 Azure 部署名、身份权限及有效合成请求是否已确认？该资源是否
   原生支持 Decisions，还是仅使用 Responses 的结构化分类？
2. 三个方向中哪个具体判断最频繁、代价最高，现有错误和延迟基线是什么？
3. 同一批样例上的质量、校准、P95 延迟和完整费用，是否优于当前方法？
4. 是否需要新增供应商边界？用户数据用途、存储、身份及停机处理是否
   被现有契约覆盖，哪些需要单独评审？
5. 只有上述证据支持时，才选择后续试点范围；本文不作为上线或自治授权。

## 资料来源

以下为 2026-10-10 复核的官方资料，在线内容可能继续变化。价格、Beta 状态
与模型/端点支持在再次讨论时应重新核对。

[openai-changelog]: https://developers.openai.com/api/docs/changelog
[openai-decisions]: https://developers.openai.com/api/docs/guides/decisions
[jev-quickstart]: https://docs.typesafe.ai/introduction/quickstart
[azure-models]: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure

- [OpenAI API 更新记录][openai-changelog]
- [OpenAI Decisions API 指南][openai-decisions]
- [TypeSafe AI / Jev 快速入门][jev-quickstart]
- [Microsoft Azure 直接销售模型目录][azure-models]
- [此前的 Microsoft Foundry adoption study](microsoft-foundry-adoption-study.md)

这里的仓库链接反映上方注明的代码快照；文件会继续演进，不证明线上生产
状态与该快照相同。后续审阅时应结合 Git 历史确认变化。
