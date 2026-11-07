# One working loop

Task execution is **understand the value → implement simply → verify the outcome**.
See `AGENTS.md` for acceptance criteria and material-risk review. Product, design,
engineering and science are concerns in the same session, not nested loops.

The useful feedback path remains: private user feedback → scrubbed qualifying
bug → `agent-ready` → Copilot implementation → tests and review → protected merge.
Existing eligibility, privacy and selective-review enforcement remain in place;
no automatic merge class is promoted by this simplification.

Automatic outcome-report issues, policy-tuning PRs, CI diagnosis comments
and duplicate invariant reviews are removed. The main session reads failures and fixes them directly. Existing
Admin learning data and regression corpora remain available when investigating
an actual problem. Native Quality review covers invariants within the one
material-risk review; no separate invariant workflow remains.

Use user feedback, task time, regressions and CI results when deciding whether a
specific constraint is useful. Change the smallest relevant check, add a real
regression test where appropriate and validate it. Do not require a separate
Meta/Eval agent, promotion packet or task ledger to improve session instructions.
