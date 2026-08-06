# AI-native runbook contract

Praxys uses a **hybrid runbook** format for operational procedures that an
incident agent may execute. Human-first Markdown remains the source of
judgment, caveats, escalation guidance, and novel-situation reasoning. A fenced
`ops-runbook` YAML block in the same file supplies the deterministic skeleton:

- signals the agent can observe;
- routes from observations to hypotheses and actions;
- policy-scoped actions;
- verification signals and the escalation exit.

Only runbooks with bounded autonomous actions need this block. Destructive or
operator-judgment procedures such as disaster recovery, secret rotation, and
scaling remain prose-only.

## Validation

`python scripts/validate_ops_runbooks.py` checks every structured block against
[`tool-registry.yaml`](./tool-registry.yaml), rejects unresolved tools, signals,
actions, verification checks, or policy tiers, and verifies that committed eval
fixtures match the routes.

After changing a route, regenerate fixtures:

```bash
python scripts/validate_ops_runbooks.py --write-fixtures
```

Fixtures under [`evals/`](./evals/) turn each route's observations into an
expected action and verification set. They are deliberately simple regression
oracles: richer incident-agent evaluations can consume them without maintaining
a second hand-authored decision tree.

## Packaging decision

Runbooks are not currently duplicated into `plugins/praxys`. That plugin is a
separate public repository and packaging a single pilot there would create a
second versioned artifact before retrieval semantics are stable. Agent
retrieval should read these repository-owned artifacts directly; reconsider a
plugin skill after at least two autonomous runbooks share this contract.
