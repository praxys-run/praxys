# Codex Statsig MCP setup verification — 2026-10-03

This record mirrors the coordinator-supplied conclusion of fresh independent
Quality thread `/root/statsig_setup_quality`. Engineering writes this record and
is not its independent verifier. Scope is the frozen bounded setup, not live
gate approval, merge, deployment or measured runtime parity.

| Binding | Value |
|---|---|
| Classification | `sha256:9c5760a626c81730cfae0585c8cea3d3b2df885b2b3261388cbdb884dc9cde78` |
| Route | `sha256:a34def4290983c74c81d49906a279065f1a7bfb0ae3e9f5a1b197a695a85ea0a` |
| Frozen incremental patch | `/tmp/praxys-statsig-mcp-implementation-20261002-r1.patch` |
| Patch raw SHA-256 | `1bec5030527e1514f7b93b1d36f63190e2007b077016e360b3b3b22f4b6e99d1` |
| Frozen owned-file manifest | `/tmp/praxys-statsig-mcp-owned-files-20261002-r1.json` |
| Manifest raw SHA-256 | `747c2088e524a818d8ee468464f21245301c9853bd89f4f64c800f7d9dd8ddeb` |

Quality reported PASS for all 26 raw owned paths, including eight new files;
five immutable subject/proposal/Evaluation/ADR/TDR bindings; fourteen native
configuration prefixes; 59 DFA non-overlap file hashes; the original overlapping
Operations prefix; and preserved user-owned `paseo.json`. These bind the original
setup patch. The later dated documentation append has its own Delivery evidence
and does not rewrite that frozen setup baseline.

The reviewed configuration declares optional V3 managed OAuth, exactly
`get_context`, `gate_read`, `gate_create`, `gate_update` at root and Operations,
and complete transport with explicit disables in the twelve other roles. Native
default prompting is configured. No secret/header/token/env fallback is added;
Microsoft/Azure approvals, portable exclusions and prior contracts are preserved.
Tool filtering does not reduce the provider OAuth grant or enforce exact-resource
authorization. Static settings do not prove native live prompting or inheritance.

The independent reviewer reported these actual checks:

- `PYTHONDONTWRITEBYTECODE=1 /tmp/praxys-ci-final-venv-20260930/bin/python scripts/check_agent_runtime_parity.py`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 /tmp/praxys-ci-final-venv-20260930/bin/python -m pytest tests/test_agent_runtime_parity.py -q --disable-warnings -p no:cacheprovider`: 103 passed in 38.58 seconds; no skips.
- `git diff --check`: exit 0; unrelated line-ending notices only.

The parent separately reported OAuth login and bounded `get_context` project
observation. Those are coordinator-supplied runtime observations, not this
reviewer's checks, child inheritance evidence, live prompt-enforcement proof,
SDK evaluation or measured parity. No OAuth secrets or broad provider snapshots
are recorded here.

Quality recommended bounded setup acceptance. No live gate, merge or deployment
approval follows. The [DFA rollout observation](../ops/dfa-automatic-analysis-rollout-20261003.md)
records the historical rejected attempt and subsequent confirmed gate creation
and readback; SDK evaluation was not exercised and no science signature or
activation is claimed. The fresh Quality instance assigned
to this four-file documentation delta must verify it separately. Session-only
patch/manifest paths above are not durable repository artifacts.

Governing records remain unchanged: [decision subject](codex-statsig-mcp-extension-decision-v1.json),
[proposal](policy-change-proposal-codex-statsig-mcp-extension-v1.md),
[Evaluation Report](evaluation-report-codex-statsig-mcp-extension-v1.md),
[ADR](architecture-decision-record-codex-statsig-mcp-extension-v1.md),
[TDR](trust-decision-record-codex-statsig-mcp-extension-v1.md) and
[implementation record](codex-statsig-mcp-implementation-v1.md).
