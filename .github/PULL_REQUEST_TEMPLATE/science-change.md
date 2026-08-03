# Science change

Use this template for changes to `analysis/`, `data/science/`, `docs/science/`,
scientific UI copy, or other product claims grounded in exercise science.

## Evidence and decision

- [ ] Linked Evidence Review: <!-- path or N/A with rationale -->
- [ ] Linked Science Decision Record: <!-- path or N/A with rationale -->
- [ ] Sources have stable DOI/PMID/URL metadata and recorded verification levels.
- [ ] Each formula, constant, and user-facing claim has provenance or an explicit estimate/guardrail rationale.
- [ ] Applicability, uncertainty, safety boundaries, and rejected alternatives are documented.
- [ ] Record lifecycle is versioned/superseded; accepted evidence and decisions were not rewritten.
- [ ] A human reviewer is named for any accepted SDR or shipped scientific behavior.

## Product and implementation

- [ ] Model version and migration behavior are documented when behavior changes.
- [ ] The implementation preserves stated non-goals and does not turn group evidence into individual medical or performance guarantees.
- [ ] `analysis/metrics.py` remains pure and never uses activity `avg_power` for intensity analysis.
- [ ] The affected API contract, web type/UI, miniapp parity, and `ScienceNote` are updated or explicitly out of scope.

## Validation and review

- [ ] Tests cover the changed behavior and the stated validation/falsification plan.
- [ ] English and Chinese scientific copy have been reviewed for equivalent meaning.
- [ ] `science-reviewer` ran for `analysis/` or `data/science/` changes and reported its source-verification boundary.
- [ ] `metric-addition-reviewer` and `api-contract-reviewer` ran when their scopes apply.
- [ ] An unresolved disagreement, evidence gap, or missing independent reviewer is visible below.

## Open questions or evidence gaps

<!-- Required when evidence is incomplete, conflicting, safety-sensitive, or awaiting independent human review. -->
