# Readiness recovery implementation impact

Owner: Engineering. Status: the original 5600f247 focused results (48 parser/
workflow cases, 60 existing policy/operations guards and 3 additional parser cases)
are historical. Quality subsequently found the recovery transport-completion P2;
the bounded correction passed 50 focused workflow/Operations checks in 5.90s
and still requires fresh independent closure.
Final preflight/CI and recovery remain pending.

- Analysis: select the available safe C YAML backend, retaining the existing
  duplicate constructor and all validation. No cache, fallback after rejection,
  formula, parameter, decision, approval, STOP record or dependency change.
- API/data/clients: no API shape, database schema, athlete-data access, web or
  miniapp change. Readiness continues through the real policy guard.
- Operations: one default-off dispatch option changes predeployment transport
  only under exact incident prerequisites. Normal transport and post-repair
  cutover/restoration/observation predicates remain unchanged. GitHub reruns are
  rejected; a distinct dispatch's one-use authority is an Operations receipt
  obligation, not a new technical ledger.
- Tests: parser selection/fallback, typed payload equivalence, malformed/unsafe
  input and duplicate/merge rejection; actual quiescence shell with local fake
  Azure/HTTP commands; default/incident bounds and negative prerequisites;
  existing real inactive and stopped policy guards. No live probes are tests.
- Governance: new tests join the explicit implementation coverage manifest and
  isolated science validation invocation. The new incident Work Contract and
  accepted specialist boundaries are preserved beside this map; the enclosing
  activation contract remains unchanged.
- Release: first ordinary automatic corrected deployment. Only Operations may
  consume the one conditional incident dispatch. Recovery is not claimed until
  the reviewed repair SHA passes normal cutover, original feedback intent is
  restored respecting the kill switch, and actual inactive policy is observed.


The correction rejects recovery responses whenever curl fails, even if stdout
contains valid quiescence JSON. The normal transport branch and every downstream
gate are unchanged. It adds no parser, science, service or dispatch scope.
