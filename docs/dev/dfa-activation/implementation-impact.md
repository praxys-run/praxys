# Implementation impact map

Owner: Engineering. Status: implementation in progress; no independent approval.

- Data/analysis: additive implementation-only approval schema and strict duplicate
  rejection. No RR numerical or science parameter change, database migration or
  athlete-data write.
- Approval boundary: trusted projection, immutable complete Git tree delta and full-tree
  replay; source identity and independent workflow artifact verification.
  v1 evidence/decision approval still requires its existing exact statement.
- API: existing readiness reports actual `require_policy()` acceptance with only
  boolean/digest metadata and no-store. Existing database/shared-authority checks
  remain; inactive policy does not make the app unready.
- Clients: no web/miniapp UI or build/package change. Existing rollout limitations
  remain disclosed.
- Operations: read-only synthetic validation separates candidate execution from
  trusted collection; post-restoration deployment observation is bounded and
  does not change feedback recovery. No credential/service/setting added.
- Maintenance: trusted explicit coverage binds file contents and modes. Shared
  files are conservatively gated in full, even when an edit appears unrelated
  within the file. Non-covered files remain ordinary maintenance. A terminal stop must land
  before subsequent governed maintenance with actual-guard denial evidence;
  subject renewal is unsupported.
- Tests: synthetic end-to-end approval/replay, stale/tampered/ambiguous source,
  wrong identity/PR/run, exact real projected DFA loader and public observation.
- Release: mechanism must land on trusted main before any activation proposal can
  use it. No approval comments, human attestations, active science records or
  production processing are created by this capability implementation.

Source binding is verified against immutable Git revisions at trusted merge
admission. It does not hash deployed filesystem bytes in `require_policy()`.
The existing Azure/Oryx workflow appends the verified private Stryd wheel path to
`requirements.txt` and generates API build-version/SHA files; these exact trusted
packaging transforms do not become arbitrary source exclusions or a runtime drift
allowlist. Runtime acceptance still checks the approved contract, method and
parameter fingerprint. Deployment observation combines that result with source
SHA and remains sampled evidence, not byte-identical package attestation.

The corrected capability adds an append-only terminal STOP record and deterministic
audit, with no scientific record or runtime activation in this PR. The stop-only
source change must land before later governed maintenance; that later PR supplies
authenticated evidence from a credential-isolated actual-candidate denial test.
The privileged source verifier consumes its trusted collector artifact without
executing candidate code. This provides a maintenance path without deleting
history or assuming that deployment rollback unlocks main. Actual subject renewal
is unsupported.

Subsequent maintenance checks protect enumerated source files only. Changes
elsewhere in the application can affect DFA behavior, including through imports
or shared process state. Such changes require ordinary impact review and renewed
specialist review when they affect the approved implementation; the file guard
does not determine semantic independence.

The authoritative stop-aware route is in
`work-contract-terminal-stop.json`; the first route remains historical. New live
trusted-main workflow execution is intentionally pending until the capability
lands. No impossible premerge self-validation of the new workflow is required.
The separate collector and admission logic are exercised with synthetic GitHub
metadata/artifact fixtures; exact live run/artifact binding remains an activation
prerequisite. Fresh hypothetical active-registry unit fixtures never override a
repository stop: the unchanged stopped candidate receives its own actual-guard
denial check, and the trusted collector rejects activation projection of a stopped
subject.


Structural-review corrections preserve every recursively loaded YAML/YML approval
at its original path, bytes and executable mode after STOP. The authoritative
actual-policy probe now has a fresh hosted runner with pinned checkouts and trusted
dependencies, independent of candidate regression workspace/environment; collector
and admission require both regression and probe success. Full-verifier history
negatives and hostile regression workspace/environment tests cover these reported
bypasses. This is local synthetic evidence; no live trusted-main run is claimed.
