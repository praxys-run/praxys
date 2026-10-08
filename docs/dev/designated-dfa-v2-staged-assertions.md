# Designated V2 staged assertion representation

This is an inert tooling proposal under contract
`wc_pr871_v2_cutover_20261008_47fffdd7`. Architecture and Science delta proposals
remain unaccepted. Independent review and the existing concrete human bridge
review must assess this representation. It enables no athlete computation and
materializes no canonical Science record or real approval.

Inactive and active decision digests remain different. The existing
`science_decision_payload` and every historical approval/contract digest algorithm
are unchanged. The inactive assertion stays at its original path, byte content,
mode, reviewer, date and source. Only a fresh active decision and exact fresh
implementation assertion satisfy current active authority. After terminal STOP,
those assertions describe previously approved history and cannot revive processing.

`analysis/science_activation_link.py` defines two separate strict schemas. They
apply only to the designated integer-V2 artifact amendment, without supersession.
Both require actual integer schema/version values and reject extra keys, missing
keys, duplicate JSON keys, coerced scalars, unexplained stale assertions, unsupported
paths and incomplete or ambiguous closure.

| Representation | Namespace and content | Authority |
| --- | --- | --- |
| `ActivationLinkInput`, schema 1, `designated_v2_activation_input` | Embedded as `activation_link_input` in the fresh canonical `praxys-science-activation:v2` source. Exact reviewed preapproval Git revision; predecessor path/mode/blob/byte digest and full unchanged inactive decision payload/digest; every retained assertion's original path/mode/byte digest, existing serialized approval, authenticated UTC event timestamp/comment ID; fresh active digest and implementation envelope digest. | Authenticated fresh human source explicitly covers these exact signing inputs. It does not sign output byte hashes or create a general approval mechanism. |
| Fresh active decision assertion | `approvals/sdr-activity-dfa-alpha1-v2--decision_approver--REVIEWER--active-FULL64HEXDIGEST.yaml` | Existing `ScienceApproval` schema 1, fresh authenticated current active digest/source. |
| Fresh implementation assertion | Existing role-scoped YAML path and unchanged schema 2 `ImplementationBinding` | Exact fresh implementation envelope and active contract, through existing authenticated validation and replay. |
| `ActivationLink`, schema 1, `designated_v2_activation_receipt` | `activation-links/sdr-activity-dfa-alpha1-v2--FULL64HEXDIGEST.json`. The exact signed input plus derived fresh decision/implementation assertion descriptors, including output bytes/modes and authenticated source event identities. | Derived append-only provenance and local current/history classification only. It is not a human attestation or a candidate authentication flag. |

The input binds the implementation envelope but contains no receipt hash or fresh
assertion byte digest. Fresh assertion bytes contain the approval source URL and
unchanged implementation binding, never a companion hash. The receipt is produced
last from those outputs. This ordering avoids a source/envelope/link/assertion
self-reference. Deterministic replay must reproduce the complete receipt and its
exact source coverage; a candidate-authored receipt cannot authenticate itself.

The privileged reader obtains retained source comments and human permissions
through the existing read-only GitHub transport. It authenticates each old
assertion against the exact inactive preapproval snapshot and canonical old
statement. A later PR additionally requires byte-identical predecessor assertions
in its exact trusted Git base. Source rechecks retain the original event and
permission. Git ancestry and authenticated UTC source events establish chronology;
comment order, the date-only YAML field, `setdefault`, or latest-wins selection do
not establish authority. The same actual reviewer issues the distinct fresh active
source. A reviewer invented to escape old-file collisions is rejected.

For same-PR staged activation, the parser retains the exact prior comment assertion
as historical evidence and parses the fresh composite as current authority. The
materializer skips only already identical designated assertions, appends the new
content-bound file and receipt, changes only the supported inactive-to-active
lifecycle, and regenerates the designated artifacts. Later-PR staged activation
uses trusted retained files and does not reissue old source comments. The local
loader validates every receipt endpoint and every preserved old byte/mode, then
excludes historical assertions from current role sufficiency. The generated V2
packet labels the old assertions as historical provenance only. Generic records
retain their old filenames, uniqueness and stale-approval rejection.

An identical retry is a no-op only after exact authenticated replay. Publication
failure restores all previous files and modes and removes newly published outputs;
no partial companion can supply current authority. A changed binding, source,
predecessor payload, assertion endpoint or receipt conflicts and fails closed.

The general verifier distinguishes STOP only after `verify_stop_changes` has fully
verified the authorized source, target, immutable history, complete Git/physical
source tree, deterministic record/audit, file modes and exact append-only two-file
delta. Unchanged terminal history must be byte/mode/tree identical. These paths
inspect terminal history and grant no mutation or new role authority. Existing
actual V1 denial evidence remains required. Retained earlier approval comments on
the bound activation PR may be reauthenticated against their exact existing
assertion files and canonical immutable history; fresh or edited source, new
assertion/envelope, extra file, activation, revival and general stopped-V2
maintenance remain denied. Present STOP data or an unchecked context cannot select
this distinction.

Before linked history exists, rollback follows reviewed stopped maintenance and
preserves inactive acceptance/denial. Once the receipt and linked history exist,
do not deploy a history-rejecting older validator as rollback. Use a separately
reviewed compatible validator while retaining every old assertion and companion.
After active approval or STOP, existing Science lifecycle and Operations controls
apply; rollback cannot erase lineage or revive either version.

Tests use explicitly disposable synthetic Science/source fixtures. External
GitHub transport alone is offline; parsing, payload digests, registry/lifecycle
checks, materialization, exact replay and full verifier/CLI paths remain real.
Simulated V2 runtime protocol fixtures do not supply actual future V2 guards. The
shipped guards remain absent and actual V2 probing continues to fail closed.
