# Science change

Use this template for changes to `analysis/`, `data/science/`, `docs/science/`,
scientific UI copy, or other product claims grounded in exercise science.
Do not check any item that was not actually performed.

## Evidence and decision

- [ ] Linked Evidence Review: <!-- path or N/A with rationale -->
- [ ] Linked Science Decision Record: <!-- path or N/A with rationale -->
- [ ] Linked Product Decision Record when product value or user behavior changes: <!-- path or N/A with rationale -->
- [ ] Sources have stable DOI/PMID/URL metadata and recorded verification levels.
- [ ] Each formula, constant, and user-facing claim has provenance or an explicit estimate/guardrail rationale.
- [ ] Applicability, uncertainty, safety boundaries, and rejected alternatives are documented.
- [ ] Record lifecycle is versioned/superseded; accepted evidence and decisions were not rewritten.
- [ ] Artifact-mode review packets and machine contracts were regenerated and carry matching source/contract digests.
- [ ] The SDR decision sheet states the reviewer task, proposed approvals, explicit deferrals, approval effects, and non-authorizations.
- [ ] Every machine-contract parameter group is mapped to at least one decision-sheet item.
- [ ] Every code-consumed field appears verbatim in the generated human review packet.
- [ ] Human approvals explicitly name the role, subject, and digest in an authenticated source; automation materialized the matching artifact without widening scope.
- [ ] Accepted artifact-mode records include the required digest-bound `evidence_reviewer` or `decision_approver`; active contracts include a separately approved `implementation_reviewer`.
- [ ] Accepted legacy records still identify their human reviewer and review date.

## Product and implementation

- [ ] The proposed product value is explicit; scientific prohibitions are not presented as the product recommendation.
- [ ] The Work Router assigned Product, Science, Design, Trust, Architecture, Engineering, Quality, and Operations only where their decision classes were triggered.
- [ ] The independent decision-review router recorded whether agent review is sufficient or a bounded human decision remains.
- [ ] Model version and migration behavior are documented when behavior changes.
- [ ] The implementation preserves stated non-goals and does not turn group evidence into individual medical or performance guarantees.
- [ ] `analysis/metrics.py` remains pure and never uses activity `avg_power` for intensity analysis.
- [ ] The affected API contract, web type/UI, miniapp parity, and `ScienceNote` are updated or explicitly out of scope.

## Validation and review

- [ ] Tests cover the changed behavior and the stated validation/falsification plan.
- [ ] `python scripts/generate_science_artifacts.py --check` passes.
- [ ] English and Chinese scientific copy have been reviewed for equivalent meaning.
- [ ] `science-reviewer` ran for `analysis/` or `data/science/` changes and reported its source-verification boundary.
- [ ] `metric-addition-reviewer` and `api-contract-reviewer` ran when their scopes apply.
- [ ] An unresolved disagreement, evidence gap, or missing independent reviewer is visible below.

## Open questions or evidence gaps

<!-- Required when evidence is incomplete, conflicting, safety-sensitive, or awaiting independent human review. -->

## UI quality

<!-- Required when web/ or miniapp/ user-visible behavior changes. Delete only when no rendered UI changed. -->
- Impeccable: <!-- command and target, for example `polish web/src/pages/Today.tsx` -->
- Visual review: <!-- web: desktop + mobile dimensions; miniapp: WeChat/Skyline device -->
- Primary journey: <!-- concise reviewer path, for example Goal -> plan preview -> readiness -->
- Reviewer handoff: <!-- local-only - path/session; PR media - links/summary; CI artifact - run; preview - URL; none - reason -->
- States checked: <!-- loading, empty, error, success, disabled, long EN/zh, as applicable -->
- Accessibility: <!-- keyboard, focus, contrast, reduced motion, touch targets -->
- Design system impact: <!-- none - reason / updated in this PR - changed path / follow-up #123 - gap -->
- Miniapp parity: <!-- updated / follow-up #123 / not applicable - reason -->
- Exceptions: <!-- none, or a narrow intentional exception and rationale -->
