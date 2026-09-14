# Trail program — Experience Specification draft

2026-09-14 · **draft / inactive**, owner Design. This logical handoff specifies
future behavior; no component, user-facing copy or runtime flow is changed here.

| Shared field | Value |
| --- | --- |
| id | `docs/dev/trail-running-program-experience-draft.md` — Trail setup through independent course feedback |
| schema_version | Existing `logical-contract`; no machine schema or approval format allocated |
| decision_type | `experience-specification`, linked to the Design Decision Record |
| owner_role | Design |
| question | What must the conditions → coverage → proposal → adoption → feedback journey communicate in supported and failure states? |
| options | The alternatives in [Design](trail-running-program-design-draft.md): explicit review journey is recommended over preset-first adoption or an unrestricted editor |
| recommendation | Implement the journey and state / parity matrix below only after applicable acceptance |
| rationale | Independent sessions, precise constraints and recoverable errors make the product promise understandable and executable |
| dependencies | [Design](trail-running-program-design-draft.md), [Product](trail-running-program-product-draft.md), [Architecture](trail-running-program-architecture-draft.md), [Trust](trail-running-program-trust-draft.md), [Science bindings](trail-running-program-review-bindings.md), [Work Contract](trail-running-program-work-contract.json) |
| review_route | Independent allocation in [Decision Review](trail-running-program-decision-review.md); this specification grants no approval |
| outcome_plan | Future rendered acceptance below and Product's voluntary journey feedback; no new value telemetry |
| digest | SHA-256 of this complete UTF-8 / LF file in [bindings](trail-running-program-review-bindings.md), matched by path; any edit requires rebinding |

## 1. Goal and conditions

Entry offers **Daily trail training / 日常越野训练** and **Prepare for a race /
越野备赛**. Race intent is **First finish / 首次完赛** or **Improve performance /
提升表现**. Daily has no event date. Race captures date, distance including
50,000 m, expected duration, ascent / descent, terrain and environment, with
unknown choices. Distance alone never establishes eligibility.

Editable presets are **Regular mountain access / 经常进山**, **City with
occasional mountain access / 城市偶尔进山**, and **Road running and gym /
路跑加健身房**. Preview replacements and preserve explicit answers unless each
is selected for replacement. A preset gives neither ability nor confirmation;
gym access is optional. Separate location / resources, equipment capabilities,
movement familiarity, history and dates.

Keep **Unknown / 未知**, **No connected records / 未连接训练记录**, **Reported by
you / 你提供的经历**, **Confirmed no experience / 已确认没有经历**, and observed
real zero distinct. Monthly mountain frequency never creates dates. Reported
history uses only the applicable Science bridge and retains its source label.

Availability uses full weekday rules, exact overrides, editable validity and
cancellation. Explain the 28 inclusive daily-date default, today + 89-day maximum,
event today + 365-day maximum, 8 resources and 14 exceptions per rule as data /
operational bounds. Reject excess without discarding data. Each new 14-day
proposal requires explicit condition confirmation, expiring after 14 elapsed
days or the earliest dependent rule end. Edit, cancellation or source change
invalidates it; day-seven review never extends validity or confirmation.

## 2. Coverage before generation

Show a plain verdict, next action and five rows: basic running, uphill,
downhill-related strength, stability / control and real terrain. Each row shows
provenance, applicability, limits and an actionable link to the relevant field.
Distinguish **Supported under these conditions / 按当前条件可支持**, **Included
in this proposal / 本提案已包含**, and **Scheduled / 已安排**. A qualified module
omitted from the proposal needs a scheduling reason. Purpose tags never imply
acquired capability or duplicate workload.

Keep exact blockers visible: first-50-km admission, long-run / back-to-back,
vertical / descent progression, novel descent, technical terrain, negative
treadmill, performance / race pace, complete event nutrition and environment.
Show **Race preparation remains incomplete / 备赛内容仍不完整**, never a
ready-to-finish verdict. A local gap can leave independent qualified modules
available; global eligibility / stop conditions still apply.

## 3. Proposal and executable course detail

Each proposal has at most 14 dates and 28 sessions. Its summary shows dates,
exact replacement set, completed sessions preserved, resources and gaps. Race
roadmaps describe future stages and review obligations; daily training uses
rolling development. Neither creates future executable prescriptions.

Each course shows actual activity, purpose, local date, times, total duration
including rest / transit, equipment, ordered steps, dose, intensity / load,
substitutions, stop cues and Science reasoning from structured accepted fields.
Do not extract executable instructions from prose.

The current **inactive illustration** reserves 25 minutes for introductory
strength: squat, calf raise and hip extension each 1 × 6, lowering 3 seconds,
rising 1 second, with 120 seconds rest; supported balance 20 seconds per side.
Show bodyweight rehearsal, permitted substitutions and omitted patterns. The
exact SDR remains authoritative. Introductory exposure does not select the
familiar 2-set template. Acquired per-pattern dose persists, first two weeks stay
once weekly, and any later frequency increase uses the sole approved transition
at that review. Explain that increased frequency increases weekly exposure.

Separate **Treadmill / 跑步机** capability from **Training incline / 训练坡度**.
The inactive example is 5 minutes at 0%, three repetitions of 2 minutes at 2%
plus 2 minutes at 0%, then 3 minutes at 0% cooldown. Device levels are not
percentages. Stairs show ascent, flat recovery, return path and extra transit.

Two same-day sessions have sibling cards, separate IDs, detail, completion,
skip, activity links and feedback. The candidate combines short easy running
then qualified familiar-dose strength, using unambiguous start / end instants
and timezone with at least 4 elapsed hours from end to start. Unknown timing
blocks pairing. Cross-session 48 / 72-hour rules apply symmetrically, including
neighboring dates and proposals, with the largest applicable interval. Show total
time and separate running / mechanical budgets; no universal four-training-day
minimum. A new proposal cannot reset scientific baseline or progression state.

**Adopt this proposal / 采用此提案** previews the exact replacement set. Show
“scheduled” only on server success. Revalidate edits; preserve completed courses
and siblings. Collect per-course and next-day feedback. Day-seven review offers
maintain / progress / regress / hold only from accepted policy; no catch-up load.

## 4. State and recovery matrix

| State | Required behavior |
| --- | --- |
| Loading / empty | Skeleton while loading; clear setup action for empty context |
| Missing input, capacity or module limit | Specific explanation and field / scheduling action; preserve independent qualified work |
| Expired / canceled dependency | Needs review, without automatic replacement |
| Save failure | Preserve pending edits in memory only; show retry status |
| Offline | Disable confirmation / adoption; reconnect compares versions and requires explicit reconciliation |
| Uncertain request outcome | Reload authoritative state before retry; canceling a request is not server rollback |
| Retention capacity | At 128 unexpired bundles, explain capacity, export / delete and expiry dates; do not silently evict |
| Retention expiry | Explain 30 / 180 days from proposal creation or earlier source deadline, and Trust's current-context purge rules |
| Cleanup pending | Never report successful deletion while affected copies remain |
| Reset | **Reset answers; retained proposals and activities remain / 重置回答；保留的提案和活动仍在** |
| Withdrawal / scoped deletion | Preview affected context / rationale cascade and independent facts preserved; distinguish from reset |
| Unknown schema / gate-off | Preserve raw read / export / delete; explain unsupported edit / generation / adoption |
| Session / account change | Clear private local draft state |

## 5. Future rendered acceptance

P7 must exercise desktop 1440 × 900 and mobile 390 × 844, both themes, EN / zh
semantic parity, long wrapping, 200% zoom, keyboard / focus, announced errors /
status, non-color labels, reduced motion and at least 44 px targets. Mobile
stacks independent sibling cards. Verify the whole journey and every recovery
state, not only static templates.

Before dual writes, miniapp must read both sessions and independent states,
preserve owner rights and give explicit Web editing guidance. An unsupported
reader offers update guidance instead of dropping a session. Current evidence
is source / context and planning only: no screenshots, browser acceptance or
miniapp rendered verification are claimed.
