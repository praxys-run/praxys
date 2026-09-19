# Trail v3：资源适配训练评审表

> 后继产品范围见 [通用越野训练交接](trail-running-program-scope.md)。本页保留早期
> 宁海资源适配草案的精确范围与候选值；同日两课、日常、50 公里和完整周期不由本页授权。

**状态：draft，全部新增科学合同 inactive。** 本轮已获授权准备评审材料与独立候选校验器；
没有记录新增剂量的人类批准、v2 替代、运行时启用、本人试用或部署。此页可逐项作出
“接受 / 修改 / 拒绝”判断，实际授权仍须由 Decision Review 和对应责任人记录。

## 这次希望解决的问题

有稳定跑步基础、主要在城市训练、偶尔进山的人，应能获得具体的基础跑与健身房课程，
同时清楚知道下降、技术路面或赛事专项准备有哪些缺口。资源不足不必抹掉基础训练的价值，
资源丰富也不能被当作已具备越野能力。本轮先把这个承诺、科学候选值与机器边界变成可评审对象。

既有宁海目标是 2026-11-15、24.7 km、本人曾提供累计爬升 618 m，仍须本人核对。
本轮没有猜测真实器械、健身经历、进山日期、下降历史或个人适用性。

## 待评审决定

| 项目 | 提议 | 本轮边界 |
| --- | --- | --- |
| 三个预设 | 常进山、城市偶尔进山、路跑/健身房，仅用于可编辑资源填表 | 不分能力等级，不补齐未知资源 |
| 首版价值 | 优先城市偶尔进山，包含具体 gym strength 和可选 treadmill；基础可用与专项缺口分开 | 不宣称跑步基础足就一定能排满 |
| 日期与节奏 | 常规星期加具体日期例外保存到比赛日；每次 14 天，7 天复核 | 不猜进山日，不自动追补/进阶/采用 |
| 最小排程 | 每七天至少三次跑步加一次 gym；当前一日一课至少需要四天，两次 gym 目标需要五天 | 产品/API 容量限制；还须满足时间、间隔、历史上限；排不下保留未排内容与原因 |
| 新科学候选 | 审查下表精确剂量与适用限制，独立于 v2 既有批准 | 本页不是生效、疗效或安全证明 |
| 明确采用 | 仅采用 exact version 才能写日历；资源变更使旧草稿失效，已采用课程标影响，明确采用后继才改未来未完成课 | 已完成训练保留；本轮无日历写入 |
| 运行与权利 | 将来复用 Statsig SDK 的本人 gate；关 gate/未知 schema 仍可原样读、导出、删除 | 无 Trail 属性遥测；Garmin 和其他 provider 零投递 |
| 下一步 | 按 handoff 补齐历史、完整排程、存储、采用、权利、UI、独立验证及发布依赖 | 评审通过不等于一键激活 |

责任文件：[Product](trail-running-plan-product-amendment-v3.md)、
[Design/Experience](trail-running-plan-experience-amendment-v3.md)、
[Architecture](trail-running-plan-architecture-decision-v3.md)、
[Trust](trail-running-plan-trust-decision-v3.md)、
[工程影响图与后续任务](trail-running-plan-v3-implementation-handoff.md)。它们均为草案。

## 支持与限制矩阵

| 场景 | 候选中可以表达/校验 | 仍需明确的限制 |
| --- | --- | --- |
| 当前 14 天无山，有城市跑与 gym | 基础跑、具体力量课、已确认资源日期 | 不生成下降/技术路面能力，不保证完整赛事准备 |
| 熟悉 gym | 有限熟悉模板、结构化组次休息和选负重提示 | 本人自述不是已观测剂量；不规定 kg/1RM 或自动加量 |
| gym 不熟悉 | 独立介绍模板 | 与新的正坡度跑台模板不在同一块引入 |
| gym 熟悉度/必要器械未知 | 保留 unknown，要求补充 | 不能默认新手；不能把未完成 gym 宣称为完整基础加力量方案 |
| 水平跑台 | 支持基础跑的实际活动类型 running | 机器须明确支持 0%；不能算作户外下降或技术路面 |
| 已确认兼容跑台 | 可选精确坡度模板 | 非户外等价，不能加一天或质量课，不能伪装 trail_running |
| 偶尔有真实户外记录 | 可表达 observed_outdoor_trail 候选，实际活动 trail_running | 本轮未实现下降/footing 观测与完整预算，不能据此执行 |
| tentative、取消或未知资源日 | 保留状态并拒绝依赖它的课程 | 不移到猜测日期、不补课 |
| 少于四个可用日 | 可以保留模块内容和容量原因 | 当前接口不能声称排成三跑加一 gym |

“review_valid”仅表示本次结构、模板与日期局部检查通过。每份机器回执均声明：
offline、inactive、未评估个人历史/赛事、未评估完整排程/暴露预算、未授权采用。
它不是 `eligible_proposal`，也不是训练计划。

## 新候选值：请连同限制一起审查

以下是 SDR 参数的人类阅读投影，**不是第二份可执行配置**。除“研究背景”外，精确计数、
时间窗、组次、RIR、间隔和坡度均为 Praxys 候选 guardrail，并非研究证明的个体安全剂量。
唯一机器值源为两个新 SDR 的 `model_parameters`。

| 参数组 | 本轮提出的值与行为 | 证据和不确定性 |
| --- | --- | --- |
| 基础历史与跑步 | 回看 8 个完整周，至少 4 个可用周、每可用周至少 3 次跑，最近跑步不超过 10 个完整日；纳入合格且明确模式/正时长的跑台历史 | 延续可观测性 guardrail；资源、本人自述不替代观测 |
| 跑步候选 | 每七天目标/最低 3 次、最多 6 次；单次最低 20 分；周跑量不超过近期可用周中位跑步分钟及扣除 gym 后可用时间的较小值；单次不超过已完成最长跑和本人上限 | 不自动增加总量或最长跑；默认轻松可交谈，质量课默认 0、最多 1；低强度至少跑步分钟的 75%，gym 不进分母 |
| 联合排程 | gym 每七天目标 2 次、最低 1、最多 2；力量课至少隔 2 个日历日；gym 与强负荷跑/最长跑/户外 trail 之间至少 1 个完整间隔日 | 易跑可在间隔日；一日最多一课；优先减可选专项，再 gym 2→1 并标 limited，再限内减易跑；仍放不下不得补天/偷偷删 gym |
| gym 动作 | 坐凳深蹲、臀桥、扶稳分腿蹲、站姿提踵；分腿蹲按每侧计次 | 四个可重复执行动作的支持模块，不是全面力量指南或下降替代 |
| gym 初次/熟悉 | 每动作分别 1/2 组，每组 8 次，组/动作间休息 120 秒；热身 5 分；预留课程 25/35 分 | 初次自重、至少保留 4 次；熟悉可自选可控阻力、至少保留 3 次。RIR 是主观提示；无 kg、1RM、力竭、加组加重、压缩休息或补做 |
| 跑台介绍 | 总计 20 分：5 分 0% → 3 分 2% → 2 分 0% → 3 分 2% → 2 分 0% → 5 分 0%；每七天最多 1 次 | 仅 6 分坡度段；全程轻松可交谈，由本人选稳定速度；无需速度/HR/power/RPE 数值目标；无 1% 等价默认；与初次 gym 互斥 |
| 户外预算候选 | 回看 56 完整日、至少 2 次可比观测、最近一次不超过 42 完整日；任何涉及候选的重叠 28 日窗，次数/爬升/下降上限分别为该 56 日观测总量除二向下取整 | 单次垂直量不超可比历史最大值、时长另受上限；合计历史实际、未取消已采用与新候选并去重；未知下降/footing 不产生数字预算；本轮不实现预算器 |
| 整体阻断与专项缺口 | 成人非临床、单日 non-ultra、performance 意图；当前症状停、已知攀扶/固定绳、基础历史不足、范围不支持或比赛距块起点不超过 14 天阻断 | 未知赛事下降/路面/危害及缺乏下降记录限制相应专项；不把未知改 0，不以周垂直中位数必须大于 0 作基础门槛 |
| 延后 | 无观测历史的新下降剂量、户外徒步/楼梯剂量或等价、taper 处方、补给量、后续力量/垂直进阶、个人疗效/安全预测、provider 投递 | 仍为 `not_accepted` |
| 研究背景 | ACSM 汇总干预常见 6–52 周；跑者力量综述 6–40 周、每周 1–4 次 | 研究范围只是解释背景，不可转成个人自动目标；不承诺 14 天表现改善或防伤 |

结构限制由 Architecture/Trust 提出：资源每 kind 一条、最多 8 条，ISO 星期 1–7 恰好七条；
每资源最多 14 条唯一排序例外；known 的 confirmed/tentative/unavailable 或 unknown 完整封套。
有效期为 trusted today 至 today+365（含端点），不越已知比赛日；单次 review 展开最多 56 天、
proposal 最多 14 天。跑台能力 -30..40%、最多两位小数只是器械描述范围。
严格 32 KiB UTF-8、depth 8/object 64/array 32/string 128 NFC；拒绝重复键/NFC 冲突、额外字段、
指数/非有限/布尔数值，数值词元最多 16 ASCII 字符，int32，decimal 绝对值≤1e6 且≤2位小数。

## 证据、来源核验与边界

新 [Evidence Review](../../data/science/evidence/trail-training-resource-adaptation/evidence-trail-training-resource-adaptation-v1.yaml)
和 [检索 manifest](../../data/science/evidence/trail-training-resource-adaptation/search-manifest-trail-training-resource-adaptation-v1.json)
记录 11 次检索、12 个选定来源（9 个全文、3 个摘要）。这是有针对性的增量评审，未进行
独立双人筛选、穷尽检索或新荟萃分析；宽检索只取前 20 条，未取回命中数明确保留。
既有证据用于继承边界，其全部参考文献未在本轮重新核验。

| 来源 | 本轮核验 | 支持的解释 |
| --- | --- | --- |
| [Currier 2026 / ACSM](https://doi.org/10.1249/mss.0000000000003897) | 全文 | 健康成人力量训练概览；不是精确初次 gym 模板验证 |
| [Llanos-Lagos 2024](https://doi.org/10.1007/s40279-024-02018-z) | 全文 | 跑者力量训练效果；不是 14 天保证 |
| [Blagrove 2018](https://doi.org/10.1007/s40279-017-0835-7) | 全文 | 训练处方、组间与课间安排背景 |
| [Stohanzl 2018](https://doi.org/10.23736/s0022-4707.17.07124-9) | 摘要 | 最小力量剂量直接研究；全文未访问，结论受限 |
| [Toresdahl 2020](https://doi.org/10.1177/1941738119877180) | 全文 | 不能保证力量方案防止跑步伤病 |
| [Van Hooren 2020](https://doi.org/10.1007/s40279-019-01237-z) | 全文 | 跑台与户外生物力学存在环境/任务差异 |
| [Miller 2019](https://doi.org/10.1007/s40279-019-01087-9) | 摘要 | 生理/知觉比较；无精确户外剂量等价 |
| [Lu 2025](https://doi.org/10.3389/fbioe.2025.1690023) | 全文 | 上下坡特异性与调节因素 |
| [Tham 2026](https://doi.org/10.1097/md.0000000000049977) | 全文 | 上坡研究背景；未验证本案 2%/20 分模板 |
| [Bontemps 2025](https://doi.org/10.1002/ejsc.12240) | 全文 | 酸痛与神经肌肉疲劳反应不同，不能据酸痛消失认定恢复 |
| [Tallis 2024](https://doi.org/10.3390/sports12060169) | 全文 | 女性跑者重复下降研究及适用范围限制 |
| [Bok 2022](https://doi.org/10.1007/s40279-022-01690-3) | 摘要 | 主观强度不是人人通用的数值训练区间 |

逐来源核验级别、DOI/PMID、检索计数、已读部分、内容提取摘要值和 claim 映射均在 manifest；
读者可以从 [生成的 Evidence packet](../../data/science/generated/review-packets/evidence-trail-training-resource-adaptation-v1.md)
继续审查。摘要来源没有被提升为全文依据。

## 精确版本与摘要值

| 对象 | 精确标识 |
| --- | --- |
| Work classification | `sha256:d2b15692d6d8db1b897b750ce30d6418e9a62e1acf683a4e88fce8f4a7851668` |
| Work route | `sha256:172191b42862f63e1368bb23496cb773b1fb7a8e8cd5e1ed2c413b080a5adb72` |
| 新 Evidence Review | `sha256:021e84168d4500ed80edb8f667731afc15eb5a036338ce4393ac33a7f9ea9aa1` |
| Ontology v3 source | `sha256:ce47bdf570a307d91e76ad229d48f88871ea49dd7d01f97fdcfac90feb40e301` |
| Ontology v3 contract | `sha256:e7cd3b9e3d6503ca72008818072bb830bb6fea18df64c69813329afba4471abd` |
| Policy v3 source | `sha256:38e62a7634c4a174ec7d1af50e20ee403b65f790da9f7da31cc0f48c6a222d06` |
| Policy v3 contract | `sha256:9a2c669727ed5f5338f6fe63c99aa786cfd5ef547a12726f6f4c9cf7da3667c1` |

[Ontology SDR](../../data/science/decisions/sdr-trail-running-goal-ontology-v3.yaml) /
[机器合同](../../data/science/generated/contracts/sdr-trail-running-goal-ontology-v3.json) /
[逐项评审 packet](../../data/science/generated/review-packets/sdr-trail-running-goal-ontology-v3.md)；
[Policy SDR](../../data/science/decisions/sdr-non-ultra-trail-plan-generation-policy-v3.yaml) /
[机器合同](../../data/science/generated/contracts/sdr-non-ultra-trail-plan-generation-policy-v3.json) /
[逐项评审 packet](../../data/science/generated/review-packets/sdr-non-ultra-trail-plan-generation-policy-v3.md)。

## 已实施与下一轮工作

已实施：新评审文档与科学 artifacts、exact Work Contract、独立 Python 候选合同编译器、
资源日期/输入/模板/实际活动类型局部校验、相应开发回归。v2、现有 API/UI、provider、部署保持原状。

仍须实施：真实下降/footing 观测、完整基础历史与专项预算、联合 scheduler、版本化 workout
存储兼容、生成 snapshot/audit、adopt revision fences、完整权利 cascade、Statsig/所有 provider
fence、UI 实现与 rendered verification、独立 Quality、activation attestation 和 Operations release。
本轮并未测试未来的本人/跨用户鉴权、gate 权利、日历写入或浏览器体验。

未来本人完成一次 14 天生成并采用、七天复核，主动报告不可执行课程，才形成 Product Outcome
观察材料；这些是产品可用性观察，不是疗效或安全证据。
