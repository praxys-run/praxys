# Praxys agentic operating model

**Status:** Version 1 is specified and checked into
`config/agentic-operating-model.json`. Role and router manifests are available,
but judgment autonomy remains specification-only and default-human unless a
narrow class is explicitly promoted.

## Core model

An **agent is a role** with bounded decision rights, owned artifacts,
capabilities, constraints, and outcome measures.

A **loop is a learning system** around an object such as a product promise,
scientific evidence, user experience, repository behavior, production health,
or the agent policies themselves.

A **capability or subagent** is a specialization inside a role. It does not need
independent role status unless it acquires distinct recurring authority,
artifact ownership, independence requirements, and outcome measures.

The operating model is not a permanent digital copy of a traditional software
organization. Traditional roles provide the initial vocabulary. The durable
abstractions are decision classes, artifacts, constraints, review independence,
and observed outcomes.

## End-to-end composition

```text
                     AGENTIC OPERATING MODEL

  INPUT SIGNALS
  -----------------------------------------------------------------
  User needs | Feedback | Telemetry | Research | Incidents
  Product strategy | Regulatory changes | Agent outcomes
                              |
                              v
                 +-------------------------+
                 |  Intake / Work Router   |
                 |                         |
                 | - What object changes?  |
                 | - What decisions exist? |
                 | - What risks exist?     |
                 | - Which loop applies?   |
                 +------------+------------+
                              |
                              v
  +---------------------- LOOP INSTANCE ---------------------------+
  |                                                               |
  | SENSE -> FRAME -> INVESTIGATE -> PROPOSE -> REVIEW -> DECIDE  |
  |                                             |                 |
  |                                             v                 |
  |                                  Decision Review Router       |
  |                                                               |
  |                        +-----------------------------------+  |
  |                        | agent-resolved                    |  |
  |                        | agent-reviewed                    |  |
  |                        | human-review-required             |  |
  |                        | blocked                           |  |
  |                        +-----------------------------------+  |
  |                                             |                 |
  |                                             v                 |
  |      PLAN -> ACT -> VERIFY -> RELEASE / OPERATE -> OBSERVE   |
  |                                             |                 |
  |                                             v                 |
  |                                            LEARN ------------+--+
  +---------------------------------------------------------------+  |
                                                                      |
                         +--------------------------------------------+
                         v
              +---------------------------+
              |      Meta / Eval Loop     |
              |                           |
              | - evaluate agent quality  |
              | - replay past decisions   |
              | - detect bad routing      |
              | - tune prompts/policies   |
              | - promote/demote autonomy |
              +-------------+-------------+
                            |
                            v
                  Policy and role updates
```

The Work Router composes the smallest sufficient role set. It does not execute
or review the task. The Decision Review Router allocates review authority after
the proposer and required specialists have produced a durable decision.

## Role slots

Each loop instance fills explicit slots:

| Slot | Responsibility |
|---|---|
| `lead` | Owns the loop object and coordinates the current iteration |
| `contributors` | Supply bounded specialist decisions or evidence |
| `independent_reviewers` | Challenge the proposal without sharing proposer authority |
| `executor` | Performs the accepted action or implementation |
| `verifier` | Checks the exact execution and acceptance evidence |
| `outcome_observer` | Records what users, systems, or reviewers actually did |
| `human_authority` | Resolves irreducible judgment or authenticated authority |

One role may fill different slots in different loops, but the same agent
instance cannot propose and independently review the same decision. High-risk
execution also requires verification independent from the executor.

## Initial role registry

The checked-in role taxonomy is intentionally evolvable:

| Role | Owns |
|---|---|
| **Product** | User problems, prioritization, product promises, value trade-offs, minimum valuable scope, target and guardrail outcomes |
| **Design** | User journeys, information architecture, interaction, visual language, content, accessibility, and rendered experience |
| **Engineering** | Implementation across frontend, backend, API, data, analysis, database, integrations, migrations, and test automation |
| **Architecture** | Cross-cutting boundaries, long-lived technical constraints, non-functional trade-offs, and irreversible technical choices |
| **Quality** | Test strategy, acceptance sufficiency, regression, exploratory validation, and release confidence for the current change |
| **Science** | Evidence claims, applicability, uncertainty, formulas, constants, claim limits, and science-specific runtime boundaries |
| **Trust** | Security, privacy, identity, authorization, sensitive data, threat models, and dependency trust |
| **Operations** | Deployment, runtime configuration, observability, capacity, incidents, mitigation, rollback, and recovery |
| **Meta/Eval** | Evaluation of agents, prompts, policies, routing, review effort, and autonomy across batches of outcomes |

API, frontend, backend, data, and similar technical areas are Engineering
capabilities. They do not become top-level roles merely because they use
different directories or technologies.

Quality and Meta/Eval remain separate:

- Quality asks whether this exact change is correct, complete, and safe to
  release.
- Meta/Eval asks whether agents, prompts, policies, and review routes improve
  across many completed changes.

## Loop family

| Loop | Object being improved | Lead role |
|---|---|---|
| **Product** | Product promise and expected user outcome | Product |
| **Science** | Scientific evidence claims and applicability | Science |
| **Design** | User experience and design system | Design |
| **Delivery** | Repository behavior and implementation quality | Engineering |
| **Runtime** | Production state and service reliability | Operations |
| **Incident** | Production health and mitigation policy | Operations |
| **Meta/Eval** | Agents, prompts, policies, routing, and autonomy | Meta/Eval |

Not every role needs its own loop, and no loop belongs to only one role.
Architecture, Quality, Science, and Trust frequently participate as
cross-cutting roles. A Design or Trust loop can become a stronger independent
outer loop when repeated outcomes begin changing its policy or source of truth.

`docs/dev/agentic-loops.md` describes the shared learning substrate: trace logs,
outcome capture, replay, shadow comparison, policy PRs, metrics, and autonomy.
This document describes how roles are composed into those loops.

## Durable artifacts are the interfaces

```text
Evidence Review
      |
      v
Science Decision Record --------+
                                 |
User signal -> Product Decision Record
                                 |
                  +--------------+--------------+
                  |              |              |
                  v              v              v
          Design Decision      ADR       Trust Decision
                  |              |              |
                  +--------------+--------------+
                                 |
                                 v
                       Implementation Change
                                 |
                                 v
                       Verification Evidence
                                 |
                                 v
                         Release Evidence
                                 |
                                 v
                    Product / Runtime Outcomes
                                 |
                                 v
                     Evaluation Report -> Policy PR
```

The diagram is dependency-based rather than strictly linear. A product decision
may not need science, architecture, or trust input. The Work Router includes a
role only when its decision class or activation trigger is present.

### Shared decision-record contract

Product, Design, Architecture, Science, Trust, and Operations decisions share
these logical fields:

```text
id
schema_version
decision_type
owner_role
question
options
recommendation
rationale
dependencies
review_route
outcome_plan
digest
```

Each specialization owns additional typed content. For example, an existing
Science Decision Record keeps evidence claims, applicability, parameters, claim
limits, and its runtime contract. A Product Decision Record owns the user
problem, scenarios, product promise, trade-offs, non-goals, minimum valuable
scope, and target/guardrail metrics. Product does not absorb Science authority,
and Science does not choose product value.

The common contract is specified in
`config/agentic-operating-model.json`. Concrete record schemas are introduced
when a loop first needs to persist that artifact. Existing accepted science
records remain immutable.

Every artifact also declares an implementation status:

- `logical-contract`: ownership and required meaning are specified, but no
  persistence or approval format exists yet;
- `repository-native`: the artifact already exists as a PR, commit, check,
  workflow result, or other repository-native evidence;
- `schema-backed`: the artifact has a validated, versioned machine schema.

A router or role must not invent persistence or approval semantics for a
`logical-contract` artifact.

## Governance and human attention

The control plane has two independent routers:

1. **Work Router:** selects the object, primary loop, decision classes, role
   slots, required artifacts, risks, and entry/exit criteria.
2. **Decision Review Router:** returns exactly one review route:
   `agent-resolved`, `agent-reviewed`, `human-review-required`, or `blocked`.

Human review remains required by default for unpromoted judgment classes,
including new product promises, material value trade-offs, safety or medical
boundaries, sensitive-data collection, privacy/security boundaries,
irreversible high-blast-radius choices, unresolved independent-agent
disagreement, and out-of-policy decisions.

`agent-reviewed` is also default-off. A decision class must be explicitly
listed in `agent_reviewed_classes`, use the Work Router's independent-reviewer
assignment, pass deterministic validation, carry a digest-bound Decision
Record, and trigger none of the human-review factors. No class is currently
listed.

The objective is not the fewest reviews:

> Minimize human attention subject to quality, safety, reversibility, and
> authenticated authority.

When human authority is required, the router returns one bounded decision at a
time with a recommendation, realistic alternatives, user impact, explicit
deferrals, and the immutable subject/digest when approval is artifact-bound.

## Evolving beyond traditional roles

Create a new role only when all or most of these become true:

1. a distinct decision class recurs;
2. independence from the executor is required;
3. a durable artifact needs clear ownership;
4. the work has distinct outcome measures.

Keep work as a capability or subagent when it remains a specialization inside an
existing authority boundary, does not need an independent artifact or review,
or is infrequent and task-local.

Retire or merge a role when it no longer owns a distinct decision, its decision
class becomes deterministic and policy-resolved, or another role can own the
artifact without losing necessary independence.

Role changes are policy changes. They require an Evaluation Report, a versioned
policy proposal, independent review, and the same promotion/demotion safeguards
as other autonomy changes.

## Example: population routing

For a future running-plan population-routing decision:

1. Work Router selects the Product loop and detects Science, Design, Trust,
   Engineering, and Quality decision classes.
2. Product owns whether every athlete may select the goal and what value each
   routed experience should provide.
3. Science owns what training history or personal characteristics can support
   and what cannot be inferred.
4. Trust owns whether age, sex, reproductive state, or related data is
   necessary, proportionate, consented, and minimized.
5. Design owns automatic assessment, confirmation, correction, uncertainty,
   and unsupported-state interactions.
6. Architecture participates only if profile or routing storage creates a
   cross-cutting long-lived technical choice.
7. Decision Review Router surfaces only the remaining irreducible decisions.
8. Engineering implements accepted artifacts; Quality verifies scenarios and
   regressions; Operations participates only when rollout or runtime policy is
   affected.
9. Product observes user outcomes, while Meta/Eval observes routing quality and
   human review effort.

## Current boundary

Version 1 defines and validates the operating model, role manifests, routers,
artifacts, and independence policy. It does not promote a judgment class,
authorize agent-created human approvals, or make every role autonomous.

The first product-specific application will convert the pending adult running
population-routing work into a Product Decision Record linked to its existing
Evidence Review and any required Science Decision Record.
