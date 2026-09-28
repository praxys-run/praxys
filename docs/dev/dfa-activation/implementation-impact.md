# Implementation impact map

Owner: Engineering. Status: implementation in progress; no independent approval.

- Data/analysis: additive implementation-only approval schema and strict duplicate
  rejection. No RR numerical or science parameter change, database migration or
  athlete-data write.
- Approval boundary: trusted projection, immutable binary diff and full-tree
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
  within the file. Non-covered files remain ordinary maintenance; renewal and
  revocation automation are outside this change.
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
