# Universal trail training: product scope handoff

> **2026-09-14 successor review progress:** The new [P1 review entry and decision
> sheet](trail-running-program-review-sheet.md) contains separate new Evidence /
> SDR records, an inactive contract and concrete role drafts. Independent Science
> re-review is complete with no unresolved findings; complete 50 km prescriptions,
> required content acceptance and P1 acceptance remain incomplete.
> The text below retains the historical 2026-09-09 handoff context and does not
> extend old v3 verification to the new scope.

**Status: Product successor proposal, draft.** Engineering persisted Product's
read-only handoff, recording the product direction the user confirmed in the
2026-09-09 session. It is not an acceptance record for new scientific parameters,
architecture or experience decisions, and grants no runtime activation or
deployment authority.

This scope succeeds the [v3 Ninghai resource-adaptation review
package](trail-running-plan-v3-review-sheet.md). The exact v3 scientific files,
offline validator and tests retain their original scope. This page neither
replaces their history nor extends their verification to the universal product.

## Problem, choices and promise

The user needs executable training for city life and occasional mountain access,
with uphill / downhill-related strength and stability / control. They want to
reuse a general running base and support same-day running and strength. The
product serves Praxys users with different experience, resources and goals;
Ninghai is one real validation path.

Product compared a Ninghai-specific end-to-end flow, universal modules with
staged availability, and covering all trail populations and distances at once.
The confirmed direction is the second: prioritize a shared model and explicit
support boundaries without turning one person's venue constraints into public
rules. This remains a product hypothesis; there are no representative user
surveys or observations of adherence, training effects or safety yet.

| Dimension | User-confirmed product direction | Specialist rules still requiring acceptance |
| --- | --- | --- |
| Population | Adults with a running base in nonclinical settings, including trail and strength beginners | Baseline history, reported experience, sparse-device-record applicability and limited paths |
| Goals | Daily trail training without a race; first race finish or improved performance | Goal matching, outcome interpretation and specific policies for each goal |
| Events | Single-day trail events from common short distances through **50 km, including exactly 50 km** | Assess expected duration, ascent, technical terrain, environment and experience; being within the distance range does not confer eligibility |
| Resources | Three editable presets: regular mountain access, city with occasional mountain access, road running and gym; no gym or specialized equipment required | Exercises and substitutions, equipment requirements and specific resource limits |
| Modules | Five combinable modules: basic running, uphill, downhill-related strength, stability / control and real terrain | Exact admission, exercises, dose, recovery, progression and feedback rules |
| Same-day sessions | At most one running-type session and one strength session, completed independently | Pairing, order / spacing, total time and cross-session load; remove the at-least-four-day restriction derived from one session per day |
| Rhythm | Generate 14 days at a time, review on day 7, and continue rolling daily training | Resource validity without a race, review and cycle-state rules |
| Complete race preparation | The publicly stated capability covers through race day, including applicable progression, run / walk, fueling practice and taper | Stage triggers, doses, exclusions and reassessment rules |
| Changes | Revalidate after resource changes; replace future uncompleted sessions only after explicit successor adoption | Exact versions, snapshots and transactions; preserve completed training, with no automatic catch-up or stacked load |

Resources, equipment, familiarity, actual dates and training history are entered
separately. Presets do not establish ability or fill unknown values. “Twice a
month in the mountains” cannot establish dates. Missing device records, confirmed
no experience, reported history and valid observations remain distinct;
disconnection does not mean the person has no running base.

A session may serve several modules without duplicating load or actual exposure.
Specialized work shares the whole plan's time and recovery tradeoffs; it is not
strength or climbing stacked onto a complete road plan. Gym and treadmill work
cannot add actual outdoor descent or technical-terrain history. Limited resources
preserve supported training with explicit module gaps; a basic plan is not
complete race preparation.

The minimum complete value is **set conditions → understand support and gaps →
generate executable sessions → review and adopt → complete and give feedback per
session → review and adjust**. A template display or passing validator does not
complete that flow.

## First release and rollout boundaries

Web first provides the complete editing and adoption flow. Miniapp retains
compatible reading and clear guidance to edit on Web. Older clients must not lose
one of two same-day sessions. Native miniapp editing and delivery to devices such
as Garmin or Stryd are separate deliverables. Distances over 50 km, multi-day
races, no running base, minors and clinical rehabilitation are outside this scope.

Use the existing server-side Statsig wrapper for gradual availability. Account
ownership always means each user can access only their own data. The personal
Ninghai account is only the first rollout cohort, not the public algorithm's sole
user. Existing read, export and delete rights remain available when the feature
is off.

The Ninghai personal path retains the user's previously supplied 2026-11-15,
24.7 km and 618 m ascent, still requiring personal confirmation for a trial.
Actual equipment, strength experience, available time and mountain dates have not
been obtained and must not be prefilled as known.

## Success and observation

- Each claimed supported path produces sessions matching confirmed dates, time,
  equipment and accepted policy, or an explicit actionable limitation.
- Users distinguish support before generation, actual proposal inclusion,
  scheduling after adoption and specialized demands still uncovered.
- Complete generation, adoption, per-session feedback, review and adjustments
  after resource changes; record unexecutable sessions and their reasons.
- No invented history or dates, false full-coverage promise, cross-owner access,
  completed-session loss, duplicate sessions or provider delivery.
- One successful Ninghai path demonstrates usability for that path, not
  applicability to other users, efficacy or safety.

If common city conditions repeatedly cannot produce executable schedules, or
users mistake basic training for complete specialized preparation, Product
should revise the promise and experience. No new training-value telemetry or
cross-user learning authority is added.

## Delivery status and decision dependencies

Follow-up work is tracked by [Epic #797](https://github.com/praxys-run/praxys/issues/797)
and the [eight deliverables and session handoff](trail-running-program-delivery.md).
Role boundaries and open Science questions are in the [review
handoff](trail-running-program-review-handoff.md). Current progress covers P1
scope and review foundations only. Before P1 closes, the required successor
Science, Experience, Architecture and Trust decisions need independent routing,
required acceptance and exact version bindings. The current draft PR does not
close P1 or activate new prescriptions.

Governance retains the enumerated role composition in the [exact Work
Contract](trail-running-plan-v3-exact-work-contract.json):
classification `sha256:d2b15692d6d8db1b897b750ce30d6418e9a62e1acf683a4e88fce8f4a7851668`;
route `sha256:172191b42862f63e1368bb23496cb773b1fb7a8e8cd5e1ed2c413b080a5adb72`.
An identical classification digest does not extend approval of the old scope.
Product proposals, Science judgment, Engineering implementation and independent
Quality verification remain separate; the independent Router allocates the
specific Decision Review route.
