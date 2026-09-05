# Trail-running plan-start experience proposal

**Artifact roles:** proposed Design Decision Record and Experience
Specification. **Status:** human Design review required; no rendered or
implemented behavior is claimed.

This specification extends the incumbent Goal to Training plan-start journey.
It does not redesign Praxys, approve Product or Science decisions, activate a
capability, or create a new Design artifact schema.

## Work Contract

- Classification: sha256:55c4da66e7f504dd0d40c681c2a006fdbe7079c0cd06de43cb95802e679f78f5
- Route: sha256:2f237b07f7a41582707e1a647e69aa634749c487c258b555c559f80f98cfc160
- Primary loop: Science; nested loops: Product, Design, Delivery
- Design artifacts: logical-contract Design Decision Record and Experience Specification
- Review route: human-review-required

## Design decision

- **ID:** ddr-owner-trail-plan-start-v1
- **Owner role:** Design
- **Question:** How should an owner understand, complete, review, and adopt a
  course-specific Trail proposal without mistaking unknowns, guardrails, or
  Garmin compatibility for certainty?
- **Recommendation:** extend the existing Field Lab plan-start instrument with
  one progressive course-demand worksheet, an explicit readiness receipt, a
  two-week proposal table, and a separate post-adoption delivery lens.
- **Rationale:** this keeps the highest-risk decision—the meaning of the course
  and available exposure—before schedule generation, while preserving the
  existing proposal/adoption/delivery hierarchy.
- **Dependencies:** accepted Product and Trail Science decisions; backend-owned
  capability, constraint schema, and compatibility responses.
- **Review route:** human-review-required because this creates a new planning
  journey with safety and uncertainty consequences.

## Job, audience, and mode

The first audience is the authenticated owner preparing for the 2026-11-15
Ninghai Trail Challenge. They want to start useful training now but should not
have to understand the science registry or provider APIs. The visitor mode is
Operate: make the course complete enough to assess, understand the resulting
boundary, review a concrete proposal, and choose whether to adopt it.

Success means the owner can answer four questions without assistance:

1. What does Praxys know about this event, and where did it come from?
2. What is still unknown and why does it matter?
3. Why does every proposed session fit current history and available terrain?
4. What changed when the plan was adopted, and what has not been sent to Garmin?

## Visual and interaction direction

Preserve the Field Lab world: warm paper, flat rule-separated instruments,
tabular data numerals, green only for the next action, cobalt for reasoning,
amber for incomplete or bounded states, and rust for stops. Reuse current
cards, alerts, inputs, sheets, structured-workout editor, and ScienceNote.

The memorable interaction is a course-demand ledger, not a generic wizard.
Each row shows value, unit, source badge, confidence/unknown state, and one
edit action. The readiness receipt beneath it updates only after an explicit
check; it never implies that merely entering more fields makes the race safe or
the goal achievable.

Design-system impact: none - existing tokens, cards, alerts, data typography,
forms, and ScienceNote cover this extension. A missing reusable provenance
badge may become a narrowly scoped shared component during implementation; it
does not require a new visual language.

## Journey

### 1. Discover and opt in

- Goal shows the Ninghai race as recorded even while the Trail generator is
  unavailable.
- Training shows authenticated, backend-advertised capabilities only.
- During the pilot, only the owner sees the Trail catalog card.
- The card states: non-ultra Trail performance, 14-day rolling proposal,
  owner-only preview, no finish guarantee, Garmin checked after adoption.
- The primary action is Start course review. There is no invitation, automatic
  enrolment, or preselected provider consent.

### 2. Confirm the course ledger

Seed known values as reviewable, never silently confirmed:

- event date 2026-11-15;
- distance 24.7 km;
- ascent 618 m;
- performance intent.

Show unresolved rows in this order:

1. expected finish-time range;
2. total descent;
3. grade distribution;
4. technicality and surface mix;
5. maximum altitude and expected environment;
6. aid stations, mandatory gear, and external support;
7. accessible training terrain and schedule;
8. recent downhill and technical-terrain exposure;
9. fueling-practice and gastrointestinal experience.

Each row uses one of Course verified, Athlete stated, History observed, Model
inferred, Assumption awaiting confirmation, or Unknown. Inferred rows name the
model version. Assumptions require a checkbox-style explicit confirmation;
Unknown is never rendered as zero, average, easy, road, or nontechnical.

The primary action is Check readiness. Save draft is secondary. A user may
leave with the goal intact and no plan.

### 3. Read the readiness receipt

The top line is a plain verdict:

- Ready for a two-week proposal;
- Clarify course demand;
- Comparable history is insufficient;
- Training terrain cannot support this course demand;
- Current symptoms stop performance planning;
- Event is inside an unapproved taper window; or
- Trail policy is unavailable.

Below it, group rows into Course match, Recent exposure, Schedule constraints,
Module availability, and Hard boundaries. Each group has evidence, unknowns,
and one focused next action. ScienceNote explains why Trail demand cannot be
reduced to distance plus ascent and why uphill/downhill remain separate.

### 4. Review a proposal

Use the incumbent Training week/list grammar, labeled Proposal — not on your
calendar. Lead with the 14-day scope and seven-day review date. For each
session show date, activity type, duration, ascent/descent ceiling when
applicable, terrain category, intended effort, and the observed-history reason
that bounds it. Never show a derived road-equivalent pace.

One expandable receipt lists:

- policy, generator, Science decision, and source revision;
- knowns, unknowns, assumptions, and limited modules;
- weekly minutes and vertical caps versus recent history;
- quality count and spacing;
- what target time did not change;
- what new evidence would change the next proposal.

Edit workout opens the existing structured editor with only policy-permitted
fields. Regenerate creates a successor and shows what changed. Reject requires
an optional structured reason, not free-text blame. Decide later preserves the
proposal until expiry. Adopt this version is the only green action.

### 5. Adopt, then choose delivery separately

The confirmation lists the exact proposal version, dates, number of workouts,
and statement that adoption writes the Praxys calendar only. After adoption,
show Plan adopted and a separate Execution platform section. No provider is
preselected and no dispatch starts automatically.

The Garmin lens must separately show:

- account availability;
- integration status and region;
- capability-matrix version;
- experimental/official API status;
- fidelity for the whole rolling window;
- device and Trail-profile verification state;
- each supported, lossy, or blocking path.

Blocking workouts use blocked_unsupported and are not retryable until the
capability changes. trail_running remains visible as the canonical activity
type; the UI never relabels it as running to obtain a green compatibility
state. The actions are Keep in Praxys and, only when every required path is
verified lossless, Review Garmin delivery consent.

## Complete state space

### Data and network

- initial loading skeleton with stable layout;
- slow/offline state that preserves entered local draft without claiming save;
- retryable API failure;
- server validation with field-linked messages;
- owner gate unavailable/private 404;
- policy or schema version mismatch;
- stale Goal, course, history, or proposal source revision;
- adoption idempotent success and version conflict;
- long event names, course-source labels, and ScienceNote content.

### Domain

- no accepted Trail policy;
- catalog entry available but not started;
- partial course draft;
- material unknown requiring clarification;
- inferred value awaiting confirmation;
- contradictory ascent/descent or event context;
- insufficient comparable history;
- insufficient terrain access;
- symptom stop;
- event inside unapproved taper window;
- eligible proposal;
- proposal draft, expired, rejected, superseded, stale, adopted;
- regeneration success and failure;
- no schedule inside the history envelope;
- adopted plan with delivery disabled, compatible, partially compatible,
  blocked, retryable provider failure, stale preview, and calendar conflict.

### Language and content

- natural English and Simplified Chinese for every state;
- units follow locale while canonical values remain metric and unambiguous;
- tabular numerals on dates, distance, ascent/descent, duration, percentages,
  and version identifiers;
- technical terms such as technicality, grade distribution, and eccentric
  load are explained inline once, then used consistently.

## Responsive behavior

Desktop uses a two-column workbench: the editable course ledger on the left
and sticky readiness/proposal receipt on the right. Mobile is one ordered
column: verdict, next unresolved field, remaining ledger, then evidence. The
primary action stays at the end of the current step rather than floating over
content. Proposal tables become date-grouped workout rows; comparison values
remain aligned and never require horizontal scrolling.

## Accessibility and physical context

- Full keyboard order follows the visual journey; no provenance or reason is
  hover-only.
- Every error summary links to its field; focus moves only after submit.
- Visible focus, WCAG AA contrast, non-color status labels, and 44px-equivalent
  touch targets apply in both themes.
- Screen-reader labels include value, unit, source, and state without reading
  visual punctuation.
- Reduced motion removes transitions; state changes remain announced through
  a polite live region.
- Light theme is checked for outdoor legibility; dark theme retains the same
  semantic distinction.
- Destructive/reject actions never share green primary styling.

## Web and miniapp parity

Web is the first owner-only client because the long course ledger and proposal
comparison need room and rapid iteration. Miniapp must use the same API types,
schema IDs, outcome codes, write semantics, adoption fence, and Garmin
compatibility result before any non-owner catalog visibility. Its layout may
be platform-native, but capability and data meaning cannot differ. Until that
parity pass, miniapp shows the existing honest unavailable state rather than a
partial Trail editor.

Plugin and MCP clients may read the same readiness and proposal only after
their proposal/adoption permissions are separately reviewed. They may not
construct an independent prompt-defined plan.

## Design verification required before activation

- Render the real feature with synthetic Trail data at 1440x900 and 390x844.
- Exercise complete, unknown, insufficient-history, stale-proposal, adopted,
  and Garmin-blocked journeys with keyboard and touch.
- Check English and Simplified Chinese long content, light/dark themes,
  reduced motion, console errors, horizontal overflow, and focus recovery.
- Verify proposal/adopted/delivered states remain unmistakable without color.
- Run Web build, matching tests, miniapp typecheck/parity, and the UI-quality
  gate. Native WeChat verification is required before miniapp parity is
  claimed.

## Human Design decision requested

Approve, revise, or reject the journey above. Approval would bind the intended
experience and state space only. It would not accept Science or Product
choices, approve implementation, claim rendered verification, activate a
capability, send Garmin workouts, or broaden owner-only access.
