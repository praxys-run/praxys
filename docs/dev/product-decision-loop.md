# Product decision loop

**Status:** Product-policy workflow and schema defined; decision-autonomy
routing remains specification-only and default-human for judgment classes.

## Purpose

Scientific evidence constrains what Praxys may claim, but it does not determine
which user problem to solve or which evidence-consistent product experience to
choose. The product decision loop converts evidence, product context, and user
signals into a falsifiable product recommendation before the change loop writes
implementation code.

The loop object is the **product promise and expected user outcome**. Agents and
humans are participants:

| Participant | Responsibility |
|---|---|
| Athlete or end user | Supplies needs, feedback, context, and observed outcomes |
| Product-policy agent | Proposes user value, scenarios, options, and outcome measures |
| Science-research agent | Supplies evidence claims, uncertainty, and claim limits |
| Independent review router | Decides whether agent review is sufficient or a human judgment remains |
| Product owner | Resolves genuinely novel, high-impact, or normative trade-offs |
| Change-loop agent | Implements the accepted behavior without reopening the decision |
| Outcome observer / meta agent | Measures results and proposes policy improvements |

## Position in the loop family

```text
user feedback / telemetry / product goal
                    |
                    v
           product decision loop
             |              |
             | needs evidence
             v              |
        science-research ----+
                    |
                    v
        accepted product decision
                    |
                    v
               change loop
             /             \
       rendered UI       deploy/config
        UI quality           ops
             \             /
                    v
                  release
                    |
                    v
        outcomes -> product/meta loops
```

- Science research is upstream evidence work. It does not choose product value.
- The product-policy agent recommends what Praxys should provide and why.
- The change loop implements an accepted decision; it must not invent one.
- UI quality is a nested implementation harness, not the product-prioritization
  authority.
- Ops is involved only when deployment, runtime configuration, monitoring, or
  incident response is affected.
- The meta/eval outer loop improves all of these policies from accumulated
  outcomes; it does not silently approve an individual decision.

## Inner-loop workflow

1. **Sense the user problem.** Record the affected user, current experience,
   observed signal, and why the gap matters. Do not substitute a technology or
   research topic for a user problem.
2. **Acquire evidence.** Reuse accepted Evidence Reviews. Invoke
   `science-research` for a bounded gap. Evidence output must distinguish what
   is established, uncertain, unsupported, or a safety boundary.
3. **Generate options.** Identify materially different product experiences that
   fit the evidence and current constraints.
4. **Recommend value.** State the proposed user experience, expected value,
   minimum valuable slice, non-goals, and trade-offs.
5. **Define outcomes.** Name success metrics, guardrail metrics, and
   falsification conditions before implementation.
6. **Route review independently.** The proposer cannot decide that its own
   judgment is safe to skip. The review router returns one policy-owned route.
7. **Ask humans narrowly.** When human judgment is required, ask one bounded
   decision with a recommendation, alternatives, consequences, and explicit
   deferrals. Do not ask the reviewer to infer the decision from an audit
   appendix.
8. **Implement and observe.** The change loop consumes the accepted decision.
   Post-release outcomes feed the product and meta loops.

## Product-first SDR schema

New evidence-backed product decisions use science-decision `schema_version: 2`.
Existing accepted schema-v1 records remain immutable.

A schema-v2 SDR retains the exact evidence, parameter, contract, approval, and
activation boundaries established by schema v1, and additionally requires
`product_context`:

| Field | Review purpose |
|---|---|
| `user_problem` | The user problem being solved |
| `current_product_gap` | Why the current experience fails to deliver value |
| `value_hypothesis` | The falsifiable reason the proposed behavior should help |
| `primary_user_outcomes` | What should improve for users |
| `scenarios` | Current and proposed experience for representative user states |
| `minimum_valuable_slice` | Smallest complete behavior worth shipping |
| `product_non_goals` | What the product intentionally will not provide |
| `success_metrics` | Signals that the value hypothesis is working |
| `guardrail_metrics` | Signals that should narrow, stop, or reverse rollout |

The generated packet presents product value and scenarios before the decision
sheet. The audit appendix still contains every evidence, parameter, and exact
machine-contract field. Product prose is digest-bound for review but is never
parsed into runtime behavior.

## Evidence-to-product mapping

Every proposed behavior must identify its basis:

| Basis | Product treatment |
|---|---|
| Established evidence | Keep the claim within the studied population and protocol |
| Uncertain or conflicting evidence | Surface uncertainty, test as a hypothesis, or omit |
| Praxys heuristic | Label the product choice and define validation |
| Safety or privacy guardrail | Keep it independent from performance inference |
| Implementation constraint | Do not present it as science or user value |

Lack of a published optimum does not prohibit a product choice. Praxys may
select a reversible estimate or guardrail when the value and trade-off are
clear, but it must label the choice, validate it prospectively, and avoid
presenting it as established science.

## Human-attention routing

The shared policy is declared in `config/agent-loop-policies.json`. Its
objective is:

> Minimize human attention subject to quality, safety, and reversibility.

The router returns:

| Route | Meaning |
|---|---|
| `agent-resolved` | Deterministic validation or an explicitly promoted narrow class |
| `agent-reviewed` | Accepted policy plus independent specialist review is sufficient |
| `human-review-required` | A novel or high-impact judgment remains |
| `blocked` | Required evidence, authority, or safe execution conditions are missing |

Human review is normally required for a new product promise, material user-value
trade-off, sensitive-data collection, safety or medical boundary, security or
privacy boundary, irreversible action, unresolved reviewer disagreement, or an
out-of-policy decision.

The proposer, implementation agent, and router cannot approve their own work.
Current science approval artifacts remain human-authenticated. Agent-only
judgment classes require a future explicit promotion; they are not created by
this specification.

## Outer-loop improvement

The meta/eval loop improves review routing from batches of outcomes:

- human acceptance without changes;
- human corrections and overrides;
- unnecessary escalations;
- missed escalations;
- post-decision reverts, incidents, complaints, or evidence revisions;
- target and guardrail metric movement;
- review latency and human effort.

Promotion follows shadow evaluation, replay evidence, enough observed
decisions, an independent policy PR, and a kill switch. Any correction, adverse
outcome, policy escape, or missing observation can demote the class.

The optimization target is not the lowest review count. It is the lowest human
attention cost that preserves the required quality and safety outcomes.
