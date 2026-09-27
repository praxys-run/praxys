# Activity DFA α1 implementation verification

Owner: Engineering execution evidence, supplied to independent Quality, Trust and
Science. This document records performed checks and review findings; it does not
approve implementation, activate science or claim deployment/native rendering.
Approved contextual specification: [implementation contract](activity-dfa-alpha1-implementation.md).
First reviewed implementation: `9b0ddf7dc6fe3b7816e70f2ce9b4902ff959f865`.

## Independent findings addressed

| Reviewer boundary | Finding and resulting behavior | Regression evidence |
| --- | --- | --- |
| Quality / Science | Native HRV field0 could accept uint32 or malformed definitions. Consumed fields now use native message/field IDs, exact base types and structural sizes; duplicate RR/provenance definitions fail closed. Native compressed record-header timestamps remain supported. | Wrong RR uint32/signed/float/odd/zero/duplicate; wrong provenance base/array; developer names time/manufacturer/product/product_name cannot override native fields; compressed timestamp. |
| Trust / Science | A native Polar handle could change H10↔OH1 without invalidation. Identity aggregation now merges missing information, canonicalizes H10/Polar H10, and rejects contradictory native Polar model names. | Both transition directions, intermediate missing metadata, aliases and split manufacturer/name enrichment. |
| Trust | Rights export suppressed retained numbers when processing or numerical policy became unavailable. Export checks source/owner/expiry/erasure separately and retains historical numerical results plus original revision/provenance. | Processing withdrawal with computational authority deliberately forbidden; ordinary method update; source revocation still removes dependent results. |
| Quality | A surviving source confirmation plus expired cache could trigger automatic computation on opening. First-entry automatic work is now preparation only; retained proof requires explicit Analyse/Recalculate. | Actual compiled web and miniapp components with sole input, proof and latest_run:null; no POST until user action. |
| Quality | Miniapp comparator could relabel HR as power while loading. Dependent rows/series clear before awaiting context. Fresh metadata also clears obsolete active/result state. | Actual component with HR120, delayed Power response, empty interim rows, final Power250. |
| Quality / Trust | Withdrawing processing could hide Cancel together with numbers. Web separates fresh owner action metadata from numerical eligibility; both clients retain Cancel for active owner work. | Actual web/miniapp component tests: withdrawn processing, hidden numbers, exactly one cancellation POST. |
| Science | Local offsets were based on gathered packets but membership could borrow other same-chain intervals. Counts, QC, DFA, RR HR, support and original index diagnostics now use only complete intervals in those exact gathered packets. | Identical reviewed generator: +10s gap339scheduled/314valid/zero crossing; slow4s/hour drift with1s or10s anchors337/337; detected40s gap never bridges. |
| Science | Original search provenance had been reduced to DOI lookup. Restored exact Europe PMC queries, screening limits and PMCID/PMID verification from the original Science handoff. | Strict registry and generated contract/packet checks; all records remain draft/inactive with no signatures. |
| Design verification | Local picker items also needed44px targets. DFA SelectItems use min-h-11 without a global Select change. | Client type/lint checks; final rendered confirmation remains independent. |

The exact boundary tests also cover199/200complete beats,117599/117600ms support,
5000/5001ms local-offset width, private500error headers, resource limits, source
confirmation forgery, queue limits, lease recovery, restore-safe reparse, and
in-flight cancellation/revocation/deletion/reparse before publication.

## Executed checks

- Combined changed-surface suite: **203 passed** with real PostgreSQL enabled:
  `tests/test_activity_dfa.py tests/test_garmin_connectiq.py tests/test_data_export.py
  tests/test_account_deletion.py tests/test_evidence_registry.py tests/test_science_artifacts.py`.
  Command prefix: `DFA_TEST_DATABASE_URL=<isolated local PG URL>
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/praxys-stryd-evidence/python python3 -m pytest`.
  Includes the actual PostgreSQL global-slot claim and multi-session
  revocation-before-publication race; not merely sequential stale-worker checks.
- Added native compressed timestamp regression: passed in the subsequent DFA run
  (**73 passed, one optional PG test skipped** on that specific SQLite-only run).
- Web production build: **290 tests passed**, TypeScript/Vite/public-build checks
  passed. The subsequently added registered-native-fixture contract test passed;
  focused `web/tests/activity-dfa.test.mjs`: **9 passed**.
- Miniapp `npm run typecheck`: generated types/shared navigation/i18n/legal sync,
  translation coverage and TypeScript passed. Targeted web ESLint passed.
- Scientific generators `generate_science_artifacts.py --check` and
  `generate_science_registry_index.py --check` validate the exact draft packet and
  inactive contract; they do not constitute signed scientific approval.
- Actual PostgreSQL16 database `praxys_dfa_test` on a local socket was upgraded to
  `b4d5f6a70819`; no production credentials/provider API was used. SQLite creation
  and foreign-key account deletion regression passed.

Local logs: `/tmp/dfa-review-backend.log`, `/tmp/dfa-review-tests.log`,
`/tmp/dfa-web-build.log`, `/tmp/dfa-mini-check.log`, `/tmp/dfa-pg-migration.log`.
These logs are local evidence and are not shipped application artifacts.

## Private feasibility observation

The user-authorized private FIT was decoded and computed in memory only; no raw
file, beat/alpha series, device identifier or private screenshot was copied into
this repository. The corrected path yielded3timer blocks,812scheduled windows,
650valid windows, and actual selected-RR support **0.9811266143911439**.

Before exact gathered membership, the same file yielded0.9817064114391144 actual
support. Eight still-valid windows had narrower interval membership after the
fix; the support union decreased2514ms. The earlier whole-window-support value
0.9824723247 is not the shipped support definition. These observations demonstrate
input/numerical feasibility, not physiological accuracy, cross-device validation
or a production latency guarantee. Independent Science confirmation of the final
observation is performed against the frozen fix revision.

## Remaining review and runtime boundaries

- Independent reviewers confirm their findings against the next immutable commit.
  Root's bounded final desktop/mobile/EN/zh/theme browser pass follows those fixes.
- [Native fixture instructions](../../tests/fixtures/dfa/README.md) and registered
  automator function sources are prepared from installed WeChat skill0.3.11.
  No simulator/foreground call or Windows mirror was created in this preparation.
  Native rendering requires the separately approved foreground pass; Node
  component/fixture tests do not replace that evidence.
- Science evidence/decision/implementation signatures, runtime activation and
  deployment remain unperformed. No accepted/active status or human approval was
  fabricated. Retained raw FIT and additive tables remain available for rollback.

## Narrow review confirmation and delayed manufacturer correction

At `9e0c2a785765a084fde95e549ce79071b6b6b01d`, the independent Quality
confirmation supplied through the Delivery Loop reported all its earlier findings
resolved:74 DFA tests with actual PostgreSQL,9 actual client/fixture tests, client
types, and the exact timing probes passed. Trust confirmed the export and native
field fixes, then identified one remaining case in the original source boundary:
`(unknown manufacturer, OH1) → (unknown manufacturer, H10) → (Polar, no name)`.

The source reader now retains every normalized nonempty native model name for each
recording-local handle. Once Polar manufacturer123 is established, incompatible
names cause rejection even when they preceded the manufacturer metadata. The H10 /
Polar H10 aliases remain one identity; missing fields enrich rather than erase
history. An unrelated watch's optical capability or model names do not establish
RR source and do not reject an otherwise eligible H10.

Engineering's narrow regression command:
`python3 -m pytest tests/test_activity_dfa.py -k 'polar or watch_native or source_identity' -q`
with the existing local fitdecode PYTHONPATH: **15 passed,67 deselected**. Both
transition directions, delayed manufacturer, alias/missing-field enrichment and
unrelated watch metadata were exercised through synthetic native FIT messages.
No UI or UI/native fixture file changed in this correction. Trust's narrow final
confirmation and original Science final verification are still independent
obligations; this evidence is not a release or runtime activation claim.
