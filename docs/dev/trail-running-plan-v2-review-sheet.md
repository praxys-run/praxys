# 越野托管计划 v2 合并审阅稿

**状态：** 待人工批准；所有合同仍为 `draft + inactive`。

这份文件是本轮的主要人工审阅材料。两个 Science review packet 的完整
附录、JSON contract、registry 和测试仍保留作审计证据，但不需要逐页阅读。

## 为什么需要 v2

v1 已经批准了越野计划的科学边界和 14 天训练框架，但有两个实现缺口：

- `grade_distribution`、技术路面和训练场地只有字段名称，没有可填写、可校验的
  rubric；
- Product 与 Science 对部分结果码的命名不完全一致。

因此 v1 纯核心可以确定性排程和验证，却不能诚实地把真实宁海输入判断为
`eligible_proposal`。v2 只补齐输入和结果合同，不扩大人群、剂量、训练模板或
运行权限。

## 六项需要批准的决定

### 1. 统一准备情况结果

每次检查只返回一个主状态，同时保留所有可安全判断的原因：

1. `validation_failed`：输入或结果无法可靠解释；
2. `policy_unavailable`：策略未启用，或目标超出本策略；
3. `readiness_blocked`：当前症状、历史、场地或时间条件不支持计划；
4. `clarification_required`：还需补充或重新确认信息；
5. `eligible_proposal`：核心条件通过，可以生成提案。

21 个固定原因覆盖版本、未知项、过期确认、历史、下降经历、场地、症状、
日程、taper 窗口和不支持的人群/赛事。UI 显示自然语言，不显示机器码。

### 2. 明确哪些信息必须知道

生成核心计划前必须确认：

- 赛事、日期、距离、累计爬升、累计下降；
- 用于制定计划的预计时长范围；它不是完赛预测；
- 18 岁以上、非医疗、单日、非超长距离、竞速目标；
- 赛道是否需要用手辅助或固定绳索；
- 每周可跑日期、每周时间上限、单次时间上限和不可训练日期；
- 是否能使用连续 3 分钟的非技术上坡和受控下坡场地；
- 当前是否有应停止竞速计划的症状；
- 服务端观察到的近期跑步、爬升和下降历史。

未知的核心项不会被默认成 0、简单、公路或“应该没问题”。

### 3. 允许非核心模块诚实受限

以下信息可以明确选择“不知道”，而不阻止 14 天核心提案：

- 五档坡度分布；
- 普通路面类型；
- 环境和海拔；
- 赛事补给支持；
- 已练习的补给及粗粒度胃肠反馈。

对应模块会显示 `Limited / 受限` 并被省略或仅作描述，绝不使用公路训练或其他
地形静默替代。准备情况只显示 `Not evaluated / Available / Limited`；只有实际
提案才能显示某模块 `Included / Omitted`。

坡度只使用五个描述性区间，按赛道距离的整数 basis points 保存：

- `< -10%`；
- `-10% 至 < -3%`；
- `-3% 至 < 3%`；
- `3% 至 < 10%`；
- `>= 10%`。

它们合计必须为 `10000`，但不是难度分、配速换算、安全阈值或训练剂量。
路面只是六个无顺序标记：坚实平整、松散碎石、泥地、岩石/树根、人工台阶、
涉水。没有综合技术难度分。

### 4. 全程使用 Praxys UI

Web 使用一个完整页面，而不是把复杂表单塞进 Goal 弹窗：

1. 赛事与计划用时；
2. 坡度与路面；
3. 可训练时间与场地；
4. 近期训练经历；
5. 环境、支持与补给；
6. 准备情况回执。

每节单独确认；任何值或来源变化都会使该节确认过期。每个失败原因都提供
“发现 → 影响 → 下一步”，并定位到固定字段或只读解释。Web 覆盖中英文、
桌面/移动、键盘、44px 触控、离线未保存、版本冲突和恢复状态。

小程序第一阶段只诚实提示转到 Praxys Web，不提供半套编辑器。

### 5. 固定隐私与架构边界

- 只有真实、非 demo 的第一方登录 owner 能访问；无 MCP、管理员或跨用户回退；
- 客户端只能提交值、未知状态和确认动作；来源、历史、revision 与结果由服务端
  生成；
- 只保留当前尚未生成提案的草稿；保存会覆盖旧草稿，不保留编辑历史；
- 创建提案后才保留不可变 snapshot 和最小化 audit；
- Reset 只把当前草稿恢复成未知，不等于删除历史提案；Export 与 Delete 覆盖所有
  当前和已保留数据；
- 不收集自由文本、GPS、路线、URL、provider payload/ID、诊断或值级 telemetry；
- URL、浏览器历史和日志只允许固定低基数键，不含赛事值、ID、revision 或 token；
- 请求有 32 KiB、深度、集合、字符串和数值边界，防止解析和规范化滥用。

### 6. Garmin 仍是独立边界

本轮只允许在采纳后读取 Praxys 已保存的 canonical workout 和内部 compatibility
matrix，显示 `Unverified / Blocked` 及逐训练原因。它必须保持：

- 零 Garmin credential/token 读取；
- 零 adapter、网络或 provider 读写；
- 零 connection、region、device、consent 或 delivery-ledger 读写；
- 零 provider ID；
- `trail_running` 不得改名为 `running`。

真实 Garmin 下发仍由 #680 和单独的账户/设备验证与人类批准处理。

## 没有改变的训练规则

v2 完整继承 v1：

- 一次只生成 14 天，完成 7 天后建议复核；
- 查看最近 8 个完整周，至少 4 个可用周、每周至少 3 次跑步；
- 最近一次跑步不超过 10 天；
- 42 天内至少 2 次可比越野经历，其中 1 次在 21 天内；
- 首块不增加近期典型训练量；
- 每 7 天最多一个质量刺激；
- 至少 75% 跑步时间为低强度；
- 不生成连续跑步日或补课堆叠；
- 爬升和下降分别受近期周中位数、周最大值和单次最大值约束；
- 唯一质量模板仍为 10 分钟热身、4 ×（3 分钟受控上坡 + 2 分钟轻松恢复）、
  8 分钟放松；无固定心率、配速、功率或 RPE 目标；
- hiking、strength、taper、超历史进阶、固定补给量和真实 Garmin 下发继续禁用。

## 精确审核对象

- Product amendment：
  `sha256:d029b72ec58ee1a04a0035412367bb80cf498dff2a74d85d0e5bb2a63d781bbc`
- Experience amendment：
  `sha256:3e30519aa68199916c226c2306360c4911c6aeeec4f0fb40bf2da6dce9197e1f`
- Architecture decision：
  `sha256:506e87fc08f6414db6beb12bdedce2d9184bda0a1c0567b8fa2cdc0a3360ed72`
- Trust decision：
  `sha256:f3241d753cbb76d16d0908ddef29417f6af967da5fc8e3014aac054244e2627c`
- Science ontology v2 decision：
  `sha256:363d5970c2ad6f7d4a18ced426d4a2996aef3ff116e6a6b112232c9eccaeeca1`
  （当前 draft contract：
  `sha256:e243bf433223452e86ded967c2575b7089f506d2bef248e9f749349cf27bd617`）
- Science policy v2 decision：
  `sha256:9e4eef184a94d3f646b9483b569a4751ab2a9939ac509e55b888af6548c888fe`
  （当前 draft contract：
  `sha256:fd2c7966d29e2bcdc3337c46e1f96d5a9aed6289c802bfe34e3a9098ede24f0d`）

注意：Product、Experience 与 Architecture 的文件摘要会在任何内容修改后失效；
Science decision digest 同样绑定完整决策。Science contract 在审批物化生命周期
状态后会重新生成，后续 implementation approval 必须绑定物化后的 accepted +
inactive contract digest。

## 审阅与权限结论

对 exact head `6c4bcf64` 的独立 Science、Product、Design、Trust review 均无
阻塞；本地相关测试 `191 passed`。这不是批准，也不授权运行时行为。

批准本页列出的六项决定，只允许继续准备并审查 inactive implementation；不允许
合并、部署、生产数据、owner dogfood、目录曝光、能力激活、提案采纳或 Garmin
下发。
