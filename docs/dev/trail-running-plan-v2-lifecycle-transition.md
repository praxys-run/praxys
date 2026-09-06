# Trail v2 Science 生命周期原子转换清单

- **Subject ID:** `science-lifecycle-trail-v2-transition-v1`
- **Subject kind:** coordinated Science lifecycle transition
- **Status:** `proposed`
- **Required human role:** `decision_approver`
- **Prepared from repository snapshot:**
  `ee21b355621fb09127fddf984c4df49e33df65fd`
- **Transition shape:** all-or-nothing
- **Runtime invariant:** every affected contract remains `inactive`; the Trail
  capability remains undiscoverable and unreachable.

## 审批人实际决定什么

批准本清单，只表示同意把两组已经分别审阅的 v2 Science Decision Record
作为一个不可拆分的生命周期转换接受，同时把对应 v1 标记为 superseded。
Ontology 与 policy 不能只转换其中一个，也不能只改一侧链接。

现有 v2 decision digest 有意排除了 `status`、`supersedes` 和
`superseded_by` 等生命周期字段。因此，现有 v2 决策批准**不能**被推断为已
批准本次转换；本清单的完整 SHA-256 才是新的审批对象。

## 当前四条记录（转换前）

| Record | Status | Runtime | Source decision digest | Current contract digest |
| --- | --- | --- | --- | --- |
| `sdr-trail-running-goal-ontology-v1` | `accepted` | `inactive` | `sha256:cb53936289927d0f5f73268b5b6468e17a5b771532e2eaeee5c5c8781e541774` | `sha256:5bf6b47ede65af84af85fb364d148bffa38c1ea330272a3e71553d091a8695dc` |
| `sdr-trail-running-goal-ontology-v2` | `draft` | `inactive` | `sha256:363d5970c2ad6f7d4a18ced426d4a2996aef3ff116e6a6b112232c9eccaeeca1` | `sha256:e243bf433223452e86ded967c2575b7089f506d2bef248e9f749349cf27bd617` |
| `sdr-non-ultra-trail-plan-generation-policy-v1` | `accepted` | `inactive` | `sha256:afc9fecefd55c699a8fdf3d3ab885968c7f7981fadbcba7bf09494fdfcdcd606` | `sha256:472c895bc4c3d467eac4a59dbacaeaaf665ddee462fdc76bba4cdf772df8e42b` |
| `sdr-non-ultra-trail-plan-generation-policy-v2` | `draft` | `inactive` | `sha256:9e4eef184a94d3f646b9483b569a4751ab2a9939ac509e55b888af6548c888fe` | `sha256:fd2c7966d29e2bcdc3337c46e1f96d5a9aed6289c802bfe34e3a9098ede24f0d` |

两条已有、按角色和 decision digest 绑定的审批来源是：

- Ontology v2:
  <https://github.com/praxys-run/praxys/pull/776#issuecomment-5534653482>
- Policy v2:
  <https://github.com/praxys-run/praxys/pull/776#issuecomment-5534653739>

这些评论批准各自的 v2 决策内容，但明确未批准 lifecycle supersession；它们
是后续 approval ledger 的来源证据，不代替对本清单的批准。

## 拟议的不可拆分转换

同一个候选 patch 必须精确完成以下四项；任意一项缺失均拒绝整个 patch：

| Record | Exact post-transition lifecycle |
| --- | --- |
| `sdr-trail-running-goal-ontology-v1` | `status: superseded`; `superseded_by: sdr-trail-running-goal-ontology-v2`; `supersedes: []` |
| `sdr-trail-running-goal-ontology-v2` | `status: accepted`; `supersedes: [sdr-trail-running-goal-ontology-v1]`; empty `superseded_by` |
| `sdr-non-ultra-trail-plan-generation-policy-v1` | `status: superseded`; `superseded_by: sdr-non-ultra-trail-plan-generation-policy-v2`; `supersedes: []` |
| `sdr-non-ultra-trail-plan-generation-policy-v2` | `status: accepted`; `supersedes: [sdr-non-ultra-trail-plan-generation-policy-v1]`; empty `superseded_by` |

四条记录的 `artifact_policy.runtime_state` 必须继续为 `inactive`。Policy v2
必须继续依赖 ontology v2；不得形成 v1/v2 混搭的当前依赖。

## Evidence 保持不变

本次不新增、不替换、不重写任何 Evidence Review。下列已接受记录及其 claims、
citations、verification notes、approvals 和 lifecycle 必须保持不变：

- `evidence-trail-running-goal-ontology-v1`
- `evidence-non-ultra-trail-plan-generation-policy-v1`
- `evidence-plan-generation-eligibility-safety-v1`

## 后续原子 patch 的受治理文件边界

后续执行者必须在同一个受审候选 patch 中更新以下类别，不能只改 YAML：

1. **Canonical lifecycle source:**
   `data/science/decisions/sdr-trail-running-goal-ontology-v1.yaml`、
   `data/science/decisions/sdr-trail-running-goal-ontology-v2.yaml`、
   `data/science/decisions/sdr-non-ultra-trail-plan-generation-policy-v1.yaml`
   与
   `data/science/decisions/sdr-non-ultra-trail-plan-generation-policy-v2.yaml`。
2. **Approval ledger:** 新增且只新增两条 v2 `decision_approver` artifact：
   `data/science/approvals/sdr-trail-running-goal-ontology-v2--decision_approver--github-dddtc2005.yaml`
   与
   `data/science/approvals/sdr-non-ultra-trail-plan-generation-policy-v2--decision_approver--github-dddtc2005.yaml`；
   `source_ref` 必须分别是上面的两个评论 URL。
3. **Inactive implementation binding:**
   `analysis/non_ultra_trail_contract.py` 中的 accepted decision IDs、model/schema
   IDs、source/contract digests 与参数投影，以及
   `analysis/non_ultra_trail_plan_generation.py` 中消费这些投影、验证输入和写入
   replay/provenance receipt 的绑定。任何不完整的 v1/v2 混用都必须 fail closed。
4. **Lifecycle、artifact 与纯核心测试:** 至少包括
   `tests/test_evidence_registry.py`、`tests/test_science_artifacts.py`、
   `tests/test_science_approval_workflow.py` 和
   `tests/test_non_ultra_trail_plan_generation.py` 中对应断言。
5. **确定性派生文件:** `data/science/REGISTRY.md`，四条 SDR 的
   `data/science/generated/review-packets/*.md` 与
   `data/science/generated/contracts/*.json`。

已经按各自 digest 批准的 Product、Design、Architecture、Trust 文档和 v2 合并
审阅稿是历史审核输入，不得为刷新状态说明而原地改写。

## 派生 digest 预测（不是审批对象）

下列值只是从当前 snapshot 将 `decision_status` 改为目标状态后得到的确定性预测。
可信生成器必须在后续 patch 中重新计算；任何不一致都必须停止，不得“采用最接近
的值”或自动扩大本批准。

| Post-transition contract | Predicted digest |
| --- | --- |
| Ontology v1, `superseded + inactive` | `sha256:e341c379d8f60a27ee5919beab4800721c96b79458c861237d6e14800cdcd752` |
| Ontology v2, `accepted + inactive` | `sha256:0d3e4056e081e07bb52cbda15fc161ff9584a50f25f97f39fd513e1dad404c9c` |
| Policy v1, `superseded + inactive` | `sha256:2035f855cea2c1c117bd092796615148e98e59f1536013f86fb2bba1cab73ce2` |
| Policy v2, `accepted + inactive` | `sha256:1952421299cb59ddfea00115b6824d3116bd6e5f9175741916aa6f1015f8f9f9` |

Approval YAML、REGISTRY、packets、contracts 和这些 digest 都是本清单批准后
重新生成或核验的输出，不是本次 human approval 的独立 subjects。

## 执行前置条件

- 生命周期 patch 必须位于同仓库、`base=main`、带 `science` label 的开放 PR；
  其 head 必须包含执行时的 current `main`。当前 stacked PR #776 的 base 不是
  `main`，因此本身不满足此条件。
- PR head 在身份、权限、评论来源和 exact candidate 校验期间不得变化。
- GitHub 必须验证评论作者身份与仓库权限；两条 source decision digest 必须仍
  与当前 v2 records 完全匹配。
- 转换前四条记录、linked evidence、runtime 和 current contract digests 必须
  与本清单表格完全一致；否则停止并提交新的清单审核。
- 同一 patch 必须同时包含 reciprocal lifecycle、approval ledger、所有 governed
  references、派生 artifacts 与测试更新。

## All-or-nothing 验证与回滚

提交前必须全部通过：registry schema、reciprocal/acyclic supersession、authenticated
approval source verification、`generate_science_artifacts.py --check`、
`generate_science_registry_index.py --check`、上述四组定向测试、完整相关 Python
测试、`git diff --check`，以及 inactive implementation 的 exact ID/digest/schema
replay 测试。还必须证明没有 catalog/discovery/route 注册，并且两个 v2 contracts
都是 `accepted + inactive`。

任一前置条件、digest 或验证失败时，不得提交部分转换：恢复整个候选 diff 到转换
前状态，保留现有 v1 `accepted + inactive` 与 v2 `draft + inactive`。如果完整转换
已合并后发现缺陷，回滚单位是整个 lifecycle transition commit；不得手工只撤销
一条记录、一个 reciprocal link、一个 approval artifact 或一个 implementation pin。

## 明确不授权

本清单及其批准不构成 implementation approval，也不授权 merge、deployment、
activation、production data、owner dogfood、discovery/catalog、Garmin credentials、
adapter、network、provider、consent 或 delivery-ledger 的任何读写，也不授权任何
delivery。它不授权改变 Product/Design/Architecture/Trust 决策，不授权 Evidence
变更，不授权 miniapp 或生产 Web 路由。能力必须继续不可发现且不可到达。

## 可复制的批准语句

> 我以 `decision_approver` 身份批准
> `science-lifecycle-trail-v2-transition-v1`，manifest digest
> `<MANIFEST_SHA256>`。我批准按该 manifest 将 Trail ontology 与 policy 两对
> SDR 做 all-or-nothing 的 reciprocal v1→superseded / v2→accepted 转换，并始终
> 保持 contracts `inactive`、capability 不可发现且不可到达。本批准不扩大该
> manifest 的明确边界或 no-authority 列表。
