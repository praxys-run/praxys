# Trail v3 Experience amendment

**Status: draft Design Decision Record and Experience Specification; owner: Design.**
ID: `experience-trail-resource-aware-basic-training-v3`.
This persists the Design owner's proposed journey for the
[v3 Product draft](trail-running-plan-product-amendment-v3.md). No component,
translation, rendered UI or visual verification is delivered in this package.

The proposed Design decision is to extend the existing course review with
resource/date confirmation and separate general foundation from specialty gaps.
Alternatives are a new ability-score onboarding or an all-or-nothing readiness
screen; both hide the distinction this proposal must preserve. Product,
Science, Architecture and Trust retain their own decision authority.

## Proposed journey

1. Choose an editable resource preset: frequent trail, city/occasional trail,
   or road/gym. Explain that it organizes questions and does not rate ability.
2. Confirm normal weekdays and concrete date exceptions through the event.
   Show confirmed, tentative, unavailable and unknown separately. An unknown
   date exception replaces the weekly value in full. Do not preselect an
   unprovided mountain trip.
3. Read the first-party history summary and separately ask about gym access,
   familiarity and equipment. Future questions distinguish bodyweight, free
   weights, machines and treadmill availability/familiarity; a statement never
   becomes observed dose history. Unknown familiarity needs clarification and
   must not silently select the introduction template.
4. Explain supported general foundation and trail-specific gaps independently.
   Before generation, describe modules as available/limited. Reserve
   included/omitted for the actual proposal. Never show a race-ready percentage,
   completion tick, or a claim that basic training covers descent preparation.
5. Show the 14-day proposal with actual activity type: running (including
   treadmill), strength, or outdoor trail running. Keep the trail goal label
   distinct. Course cards must expose steps, exercises, sets, repetitions per
   side, rest, time reserve and load-selection cue from the exact SDR template.
6. Ask the owner to explicitly adopt the exact version. A resource edit expires
   a draft; for adopted work, show affected future workouts and preserve them
   until an explicitly adopted successor. Completed training stays intact.
7. Offer the advisory seven-day review with completion/skips, form/tolerance
   adjustments, changed resources and current symptom stop. Show unplaced
   content and capacity reasons when the minimum three runs plus one gym cannot
   fit four separate days. No automatic catch-up, progression or adoption.

## State and visual specification

Reuse the incumbent `TrailCourseReview` and Field Lab visual language. Interpret
first, use green for action and cobalt for reasoning, warm paper and semantic
tokens, `font-data` for numbers and `ScienceNote` for bounded explanations.
No new design-system primitive is proposed by this document.

Future implementation must cover loading, empty, unavailable, disabled,
permission, stale version, save error, slow/offline, success and long-content
states. Offline edits remain in memory marked unsaved; reconnect compares the
server version, identifies the affected section and requires re-confirmation
where needed. Do not imply a successful save/adoption after a network failure.

Rendered acceptance must include English and Simplified Chinese, desktop and
mobile, light and dark, keyboard and visible focus, reduced motion, outdoor
legibility, screen-reader labels, error focus and at least 44px touch targets.
Use the [UI quality harness](../../.github/skills/ui-quality/SKILL.md) and
Impeccable when actual interface implementation begins. This document does not
substitute planned screenshots for rendered evidence.

The native miniapp should honestly continue to the Web experience until its
capability is separately implemented and verified. Keep capability and data
semantics explicit; a partial miniapp editor is not parity.

Gate-off and unsupported schemas retain an owner read/export/delete path;
generation and adoption remain unavailable. Reset copy must explain that it
does not erase snapshots, proposals or completed training. See
[Trust](trail-running-plan-trust-decision-v3.md) for complete rights coverage.
