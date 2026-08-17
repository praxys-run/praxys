# Product loop

**Status:** The Product role, loop contract, and shared Product Decision Record
fields are specified in the Praxys agentic operating model. Task routing is
active; judgment autonomy remains default-human for unpromoted classes.

## Purpose

Scientific evidence constrains what Praxys may claim, but it does not determine
which user problem to solve or which evidence-consistent product experience to
choose. The Product loop converts evidence, product context, and user signals
into a falsifiable product recommendation before the Delivery loop writes
implementation code.

The loop object is the **product promise and expected user outcome**. The
Product Agent leads; other roles contribute only their bounded decisions:

| Role or participant | Responsibility |
|---|---|
| Athlete or end user | Supplies needs, feedback, context, and observed outcomes |
| Product Agent | Owns user value, scenarios, options, prioritization, and outcomes |
| Design Agent | Owns the journey, interaction, content, accessibility, and rendered experience |
| Science Agent | Owns evidence claims, uncertainty, applicability, and scientific limits |
| Trust Agent | Owns privacy, security, identity, consent, and sensitive-data boundaries |
| Architecture Agent | Owns triggered cross-cutting or irreversible technical decisions |
| Engineering Agent | Implements accepted decisions without reopening them |
| Quality Agent | Independently verifies the exact implementation and acceptance evidence |
| Operations Agent | Owns rollout and runtime decisions when they apply |
| Independent review router | Decides whether agent review is sufficient or a human judgment remains |
| Product owner | Resolves genuinely novel, high-impact, or normative trade-offs |
| Meta/Eval Agent | Evaluates role, routing, policy, and autonomy quality across outcomes |

## Position in the loop family

```text
user feedback / telemetry / product goal
                    |
                    v
              product loop
             |              |
             | needs evidence
             v              |
          science loop ------+
                    |
                    v
        accepted product decision
                    |
                    v
              delivery loop
             /             \
         design loop       runtime loop
             \             /
                    v
                  release
                    |
                    v
        outcomes -> product/meta loops
```

- Science owns evidence and scientific decisions. It does not choose product
  value.
- Product recommends what Praxys should provide and why.
- Design owns the intended experience; Engineering implements it.
- Quality independently verifies the current change.
- The delivery loop implements accepted decisions; it must not invent them.
- UI quality is the mandatory rendered Design harness, not product authority.
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
8. **Implement and observe.** The Delivery loop consumes the accepted decision.
   Post-release outcomes feed the product and meta loops.

## Product Decision Record

A Product Decision Record is owned by Product even when it depends on Science.
It links Evidence Reviews and Science Decision Records instead of embedding or
replacing their authority. Existing accepted science records remain immutable.

The product specialization adds:

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

The shared record fields and specialization ownership are declared in
`config/agentic-operating-model.json`. The first persisted Product Decision
Record and generated product review packet will be introduced with the adult
running population-routing application. Product prose remains reviewable and
digest-bound but is never parsed into a science runtime contract.

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

The role and loop model is declared in
`config/agentic-operating-model.json`; review autonomy remains in
`config/agent-loop-policies.json`. Its objective is:

> Minimize human attention subject to quality, safety, reversibility, and
> authenticated authority.

The router returns:

| Route | Meaning |
|---|---|
| `agent-resolved` | Deterministic validation or an explicitly promoted narrow class |
| `agent-reviewed` | An explicitly listed class passes all independent-review requirements |
| `human-review-required` | A novel or high-impact judgment remains |
| `blocked` | Required evidence, authority, or safe execution conditions are missing |

Human review is normally required for a new product promise, material user-value
trade-off, sensitive-data collection, safety or medical boundary, security or
privacy boundary, irreversible action, unresolved reviewer disagreement, or an
out-of-policy decision.

The proposer cannot select its own review route or review its own decision. An
executor cannot verify its own high-risk work. Routers cannot approve, and
agents cannot materialize human approval. Current science approval artifacts
remain human-authenticated. Agent-only judgment classes require a future
explicit promotion; they are not created by this specification. The
`agent-reviewed` eligibility list is also empty, so current product judgment
continues to route to a human.

## Outer-loop improvement

Product owns whether its value hypothesis worked. The Meta/Eval loop separately
improves role assignment and review routing from batches of outcomes:

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
