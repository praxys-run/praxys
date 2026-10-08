# Implementation impact: private designated DFA V2 bridge

Contract `wc_pr871_v2_cutover_20261008_47fffdd7`, route
`0507fad075c0811453a397fd1d80593fce82456d3e481779505d7d67e3714339`.
This source is proposed tooling; owner decisions remain unaccepted. It contains
no canonical V2 Science record or approval and enables no athlete computation.

| Surface | Files / functions | Effect |
| --- | --- | --- |
| Local scientific consistency | `analysis/science_admission_amendment.py`: strict type, raw prevalidation, local pin validation; `analysis/evidence_registry.py`: loader hooks | Designated-only content validation without historical model/default changes. |
| Projection / comments / replay | `analysis/science_activation.py`: `project_active_registry`, composite parser/renderer/payloads, `ActivationContext.verify`, typed JSON helper | New-only V2 schema/marker, retained ordinary successor and STOP restrictions, exact reviewed projection/replay. |
| Approval transaction | `analysis/science_approval_workflow.py`: comment parser, materializer, transition/lifecycle checks | Authenticated V2 acceptance/activation; shared Evidence cannot be renewed by the composite batch; historical bytes/modes preserved. |
| Authenticated readers | `analysis/science_activation_github.py`, `analysis/science_stop_github.py` | Exact V2 producer/job/artifact types and identities; actual V1-denial requirement in both accepted context paths. Readers never import candidate code. |
| Preparation CLI | `scripts/materialize_science_approvals.py`, `scripts/prepare_science_activation.py` | Trusted base input for decision-only acceptance; V2 renderer labels only the two new assertions. |
| Disposable fixtures | `scripts/check_projected_dfa_policy.py` | Semantic V2 closure pruning for hypothetical V1; separate V2 lifecycle fixture preserves real V1 STOP/shared Evidence. |
| Actual observation protocol | `scripts/run_science_policy_probe.py`, `scripts/observe_science_policy.py` | Exact V2 purpose/subject, independent fresh phases, historical/manual/automatic callable and dependency provenance, nested type checks, bounded resources. Missing shipped guards deny. |
| Trusted collector | `scripts/collect_science_activation_validation.py` | Separate schema-2 static collection binds actual source/base/history, full delta and authenticated completed jobs; candidate source is never imported. |
| CI / import coverage | Both Science workflows; `config/science-implementation-coverage.json` | Job-level and entrypoint bytecode prevention, explicit V2 purpose, governed helper and V2 future runtime module slots. Physical guards stay strict. |
| Tests | Existing selected Science activation, GitHub, approval, policy probe suites; existing activity DFA fixture | Functional hygiene; designated projection/transaction/history, malformed pins, metadata/typed/provenance negatives, actual missing guards and distinctly simulated protocol. |
| Guidance / rollback | This map, protocol guide, Science contributing, Operations DFA guide | Separate admission/migration/activation/drain obligations and reviewed stopped-maintenance rollback. |

Data pipeline, numeric analysis, public API, database/migrations, source admission,
web, miniapp, provider credentials, service settings and deployment are unchanged.
All canonical `data/science` bytes/modes, computed historical digests and the
plugin Gitlink must match the exact base. No approval is materialized outside
disposable tests. The local commit and external evidence freeze exact base/head,
full diff/tree/file modes, test logs and runtime separately; none is human or
independent Trust/Quality acceptance.

Before activation, rollback removes this tooling through reviewed stopped
maintenance while retaining terminal STOP/history. Once V2 is accepted or active,
its separate lifecycle review applies. Global process retirement is UNKNOWN.
Independent Trust and Quality must inspect the immutable proposal in fresh
read-only threads; later provider/publication/merge/release remain coordinated
outside this private executor's scope.
