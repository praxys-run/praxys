# 通用越野训练：Product Decision Record 草案

2026-09-14 · **draft / inactive**。Product 提案由 Engineering 持久化。
本文件定义待评审的产品承诺；P1、P2–P8 和运行启用均未完成。

| Shared field | Value |
| --- | --- |
| id | `docs/dev/trail-running-program-product-draft.md` — 通用越野训练产品承诺草案 |
| schema_version | 现有 `logical-contract`；共享字段来自 `config/agentic-operating-model.json`，未分配新的机器 schema |
| decision_type | `product-decision-record` |
| owner_role | Product |
| question | 是否以明确的模块支持和缺口交付通用成年越野训练，同时保留完整备赛承诺的验收要求？ |
| options | 宁海专用；通用模块逐步交付（建议）；一次覆盖所有人群和距离 |
| recommendation | 提交通用范围、具体 inactive 核心和剩余阻断，保持 #798 打开 |
| rationale | 城市跑者可从基础跑步、居家力量和受控上坡获得明确下一步；单一路线不足以代表需求，无边界覆盖缺乏依据 |
| dependencies | [精确 Work Contract](trail-running-program-work-contract.json)、[Science 包与绑定](trail-running-program-review-bindings.md)、[Design](trail-running-program-design-draft.md)、[Experience](trail-running-program-experience-draft.md)、[Architecture](trail-running-program-architecture-draft.md)、[Trust](trail-running-program-trust-draft.md)、独立 Science / Quality 与 Decision Review |
| review_route | 由独立 Decision Review Router 分配；以[评审记录](trail-running-program-decision-review.md)为准，Product 未选择或接受自身提案 |
| outcome_plan | 下文的成功、约束与证伪计划；未来观察义务，无运行结果 |
| digest | 本文件完整 UTF-8 / LF 内容的 SHA-256，见[精确绑定表](trail-running-program-review-bindings.md)同名路径行；任何内容修改均须重新绑定 |

## 建议承诺与价值

范围是有跑步基础的成年非医疗场景，含无赛事日常训练、首次完赛和表现目标，
单日赛事包含恰好 **50,000 米**。资格仍取决于经历、预计时长、爬升、下降、技术路面
和环境。保存 50 公里目标不能证明已能提供完整备赛。

资源可编辑，不强制健身房；资源、器械、熟悉度、历史和真实日期分别表达。
同日跑步与力量独立完成，每次 14 天提案、第 7 天复核。Science 的本人陈述路径、
家用动作、受控上坡、熟悉地形维持、双课、进退阶、跑走、补给练习和减量均是
有适用边界的候选，剂量以精确 SDR / 契约为准。

最小价值路径是：设置条件 → 理解支持与缺口 → 审阅可执行课程 → 明确采用 →
分课完成反馈 → 复核。界面分别表达“按当前条件可支持”“本提案已包含”“已安排”。
局部缺口可保留独立合格模块；全局资格或停止条件仍全局阻断。

完整比赛准备仍是产品目标。首次 50 公里准入与长课 / 连续长课、垂直与技术进阶、
新下降、负坡跑步机、表现 / 配速进阶、完整比赛营养和环境处方的缺口，不能以
“部分模块可用”满足验收。界面持续显示“备赛内容仍不完整”，不承诺防伤、完赛或个人安全。

Product 建议接受 Architecture / Trust 提出的有效期、每次确认、稳定身份、事务、
客户端兼容和全部派生副本删除的取舍。有限保留牺牲无限重放；采用前必须解释
保留期、导出和删除。这里的支持是提案意见，专业边界仍需独立接受。

## 验收依赖与观察

P1 科学主张及核心候选已经过[独立 Science 审查](trail-running-program-independent-science-review.md)，
修订版没有未解决的审查发现。这不填补上述处方缺口，也不替代人类内容接受、
最终角色版本校验或独立 Quality。旧 accepted v2 和 draft / inactive v3 保持原样。

相关决定接受后，P2 / P3 可共同实现身份、兼容、资源、来源和权利；P4 / P5 逐模块
等待精确处方；P6 等待事务和授权合同；P7 等待 Experience 与渲染验证；P8 另需
Operations 及发布权限。详见[影响与阻断矩阵](trail-running-program-implementation-impact.md)。

成功要求每条承诺均映射到精确规则、排除条件和验收场景。约束是没有虚构历史或日期、
虚假备赛完整性、完成记录丢失、跨用户读取、过期采用和 provider 调用。未来 Product
通过自愿反馈观察 14 天路径及第 7 天复核，不增加训练值遥测。反复出现城市条件无法排课、
误读部分覆盖时应修改产品假设；宁海路径可用不能证明效果或安全。

Refs #798；本提案不满足关闭条件。
