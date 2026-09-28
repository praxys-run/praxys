# Cooperative local decision-card trial

## Policy Change Proposal — accepted bounded choice

Meta/Eval's accepted proposal is a local, cooperative presentation comparison.
The user approved this bounded choice with “那就做吧”; the independent Decision
Review route was `human-review-required`. This is a factual conversation record,
not a signed or cryptographically authenticated approval artifact. Engineering
implements the accepted boundary; independent Quality verifies the resulting
change. Existing specialists, Quality, CI, Decision Review, and human authority
remain unchanged. No new approval questions are manufactured for the experiment.

Work Contract `ctr_dc_local_2026_v1`:

- Classification: `sha256:0ad9318cbabe89b8918297e022d356e47ca4d91510fdb983761ba44a53a0e8e5`.
- Route: `sha256:02ae5b927772915aa703344217dd7092151f847719fe05a9d72d43dd6f92949b`.
- Primary object: `agent-system`; impacts: `repository-change`,
  `agent-policy-or-autonomy`; risk triggers: none.
- This implementation task is excluded from its own cohort.

`config/agent-decision-card-cooperative.json` activates only the cooperative
local mode, cohort `decision-card-local-2026-v1`, expiring absolutely at
`2026-10-28T00:00:00Z`. All policy fields including expiry are digest-pinned;
only emergency `status: disabled` preserves that digest. Editing expiry cannot
extend an existing cohort. New cohorts require a separately reviewed decision.
The earlier protected policy remains disabled and separately named.

The SQLite ledger is private local bookkeeping **editable by the same user**.
It does not authenticate identities, reviews, or Work Contracts, resist tampering,
intercept native tools, or establish automatic coverage. No Paseo broker, hook,
installer, Azure resource, protected receipt, new PR gate, or branch change is
required. Only sessions cooperating with the documented local workflow count.
A read-only adapter retains its permissions; unavailable authorized writes mean
baseline rather than permission expansion or an alternate live ledger.

## Local workflow

Use `python scripts/local_decision_trial.py` with the following subcommands.
`status` never creates files. Explicit `init` provisions once under
`git rev-parse --path-format=absolute --git-common-dir`, in
`praxys-decision-trial/<cohort_id>.sqlite3`. All worktrees share this canonical
path. Do not initialize or enroll a real cohort merely to test the implementation.

1. After Work Router supplies the exact deterministic Work Contract and before
   delegation, run `status`. Use authorized `init` only for the first explicit
   setup covered by the existing cooperative authorization; do not ask again.
   Never use initialization to repair missing, corrupt, expired, or reset state.
2. For a genuinely new user task, run `new-task` once. It produces a random
   `tsk_` key without enrolling. Keep the key in the private task handoff across
   sessions. A second task gets a distinct key; a session is not the unit.
3. Run `admit --task-key <key> --contract <contract.json>`. The contract file is
   the complete `TaskRoute` JSON returned by the deterministic router. Each
   resume uses the original key, current contract, and `--resume`. An unknown
   resume cannot allocate a slot. Reroute changed scope through normal governance;
   never mint a new key to evade a changed/excluded contract.
4. A retains existing presentation. B is only a presentation option for an
   **actual**, independently reviewed `human-review-required` decision. No
   human decision means no card: record `no_human_decision`, and continue work.
5. With actual independent evidence, invoke `card --task-key <key> --contract
   <contract.json> --review <review.json>`. It checks current policy, original
   contract, B assignment, expiry/stop, complete card fields, matching subject
   and evidence digests, and separate reviewer identity. It issues at most one
   card and records `card_issued` before returning the text. That is an attempt,
   **not proof of display**. Record `card_displayed` only after actual display;
   interruptions or missing observations remain unknown. No raw card is stored.
6. Append `outcome --task-key <key> --event <event.json>` as facts become known,
   including failures, abandonment, no-PR work, completion, and B fallback.
   PR events require both PR number and exact head SHA. Missing outcomes remain
   unknown and unfinished assignments retain their slot.

A review JSON object contains `card` (the existing `DecisionCard` schema),
`subject_digest`, `evidence_digest`, `review_digest`, and opaque `reviewer`,
`proposer`, `executor` IDs. The card includes question, recommendation, trade-off,
human authority, why human judgment is required, rejection consequence, deferred
choices, evidence references, and known dissent. Digests and distinct IDs are
structural checks and references only: the coordinator must obtain real
independent Decision Review evidence first. Do not fabricate it or persist the
review input in public artifacts. The card is a request, never approval.

An event JSON contains `event_key` (`evt_` plus 64 lowercase hexadecimal random
characters), `kind`, and optional paired `pr_number`/`head_sha`. Supported kinds:
`failed`, `abandoned`, `blocked`, `no_pr`, `pr_open`, `merged`, `completed`,
`baseline_fallback`, `no_human_decision`, `card_displayed`; `card_issued` is
service-generated only. Reuse event identity on retry; conflicting identity is
rejected. No prompts, feedback, task prose, screenshots, credentials, session
URLs, raw review text, or free-form logs belong in the ledger.

A missing/unavailable/corrupt ledger or invalid input returns baseline and an
unavailable result. The CLI's nonzero exit concerns bookkeeping, not permission
to continue the underlying task. If state cannot be read, enrollment and original
arm are unknown; never count this as an A success. A known assignment's original
arm persists through stop, expiry, or contract drift. Drift falls back and records
`baseline_fallback`; it cannot later obtain B by returning to the old contract.
Do not reset, copy, or restore the ledger to overcome these limits.

## Bounds, checkpoint, and stop

Only the policy's low-risk primary objects with no risk triggers or excluded
impacts may enroll. Allocation alternates the less-filled arm, beginning with A.
Retries keep the original assignment. Assignment eight pauses **new admissions**;
independent review must examine safety, record completeness, and comparability
before `checkpoint --review-digest <digest>`. This digest records a reference to
completed review; it does not authenticate that review. Assignment sixteen closes
new admissions permanently. Existing tasks can finish and issue their one eligible
card until expiry or stop. Never extend the cap to make results look conclusive.

Use `stop` immediately for a critical omission, privacy exposure, authority/review
bypass, serious regression, or unreliable records. Expiry and disabled policy
also suppress admission/cards. Outcome recording continues after stop/expiry.
Stopping is sticky through supported transitions, but same-user edits can bypass
bookkeeping. Stop affects subsequent checks, cannot retract already-issued text,
and is not a linearizable UI guarantee. Continue affected work through baseline
human/Quality review while retaining B attribution.

## Evaluation Report — pretrial, zero efficacy observations

Meta/Eval's pretrial conclusion is **insufficient evidence of benefit**: no real
cohort has been provisioned or enrolled by this implementation and synthetic
tests are not trial outcomes. No human effort, accuracy, quality equivalence,
or savings claim follows from code checks.

Compare by original assignment, retaining failed, abandoned, fallback, no-PR,
and unfinished tasks. Unenrolled/bypassed tasks are outside the denominator,
never successful A tasks. Report enrollment, actual display separately from
issuance, outcome completeness, corrections, overrides, missed/unnecessary
escalations, adverse outcomes, model/provider mix, observable latency and cost.
Human active reading/clarifying/decision minutes and accurate restatement are
reported only when actually supplied; absent data is `unknown`, and a task with
no human decision is `not applicable`. The CLI reports coded observations and
unknown uncollected measures, not zero-valued proxies. Preserve missingness when
combining these counts with independently collected measurements.

At eight, independently assess safety, completeness, and comparability. At
sixteen or expiry, close and evaluate: retain baseline, propose adoption through
a separate decision, propose one new single-factor trial, or report insufficient
evidence and retire. Exploratory screening hopes are at least 25% lower median
human active time, at least 90% accurate restatement, and zero critical omissions.
A small alternating, self-recorded cohort cannot establish causality, long-term
quality equivalence, or justify autonomy promotion. No extra roles, required
prompts, stretched cap, or baseline-only successes may rescue an inconclusive run.

## Implementation Impact Map and change

- Analysis/tooling: reuse pure eligibility, A/B, CAS, monotonic histories,
  checkpoint, cap, coded outcomes, and the existing card renderer. A separate
  cooperative service adds expiry, sticky resume, one-card issuance, and reports.
- Data: existing local SQLite adapter supplies atomic shared-worktree bookkeeping;
  no application database, training data, migration, API, or client change.
- Operations/config: one new local policy/CLI, canonical path, explicit setup,
  stop/expiry and retirement procedure in `docs/ops/change-loop.md`.
- Instructions: local orchestration points to this flow; Work Router taxonomy,
  protected admission guard, Blob API, role boundaries, and native permissions
  stay compatible.
- Tests: focused existing trial/storage regressions and synthetic cooperative CLI,
  expiry, corruption, policy pinning, worktree identity, card and concurrency tests.
  Engineering's test execution is not independent Quality verification. Static
  parity checks do not establish runtime parity or coverage.

For tests only, paired CLI `--test-policy <synthetic.json> --test-store
<temporary.sqlite3>` flags and service path/clock injection isolate all state.
Never use those flags as live alternate-store recovery. No production resources
or real cohort initialization are part of this change.

## Archived protected mode — disabled

`config/agent-decision-card-trial.json`, `load_trial_policy()`, the inspection
CLI `scripts/agent_decision_trial.py`, and Azure Blob APIs retain the original
protected, disabled boundary. The protected SQLite adapter remains available
as groundwork. This cooperative trial does not activate that cohort or satisfy
its former broker, authenticated review, receipt, required-check, or deployment
prerequisites. A future protected deployment needs its own routed and reviewed
proposal. See `docs/ops/change-loop.md` for local retention and retirement.
