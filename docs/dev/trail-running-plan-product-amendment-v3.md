# Trail v3 Product amendment

**Status: draft; Product Decision Record proposal.** Owner: Product.
ID: `pdr-trail-resource-aware-basic-training-v3`.
This records the Product owner's proposed boundaries for the authorized review
package. It records no human acceptance of new prescriptions or runtime use.
The [exact Work Contract](trail-running-plan-v3-exact-work-contract.json) and
[review sheet](trail-running-plan-v3-review-sheet.md) bind this package.

## Problem and proposed promise

A runner with an adequate general running basis may have little recent trail
or descent experience, an occasional mountain date, and reliable access to a
gym. The proposed experience should organize useful basic running and concrete
gym work while clearly identifying the unsupported trail-specific preparation.
Missing descent must not turn into measured zero or an inferred capability.

Three editable presets—frequent trail, city with occasional trail, and road/gym—
only prefill a resource form. They are not athlete ability classes and cannot
supply missing confirmation, dates, equipment, or observed history. First
delivery prioritizes city/occasional trail with executable gym strength and
optional bounded treadmill content. A foundation proposal may remain explicitly
limited when general running is supported but trail/descent history is absent.

Resource dates, equipment, independently stated gym familiarity, observed
training history, and event demand are distinct inputs. The Ninghai event on
2026-11-15, 24.7 km and stated 618 m ascent is an existing goal awaiting the
owner's confirmation; it is not a freshly verified course or personal history.
Do not assume the owner's gym equipment, familiarity, access, or descent record.

## Minimum valuable scope and trade-offs

Save normal weekly resource patterns plus date exceptions through the event
date. Generate one 14-day proposal at a time and offer an advisory review after
seven completed days. With no mountain access in the current block, supported
city basic running and gym content can remain useful. Never invent a mountain
date, transfer outdoor descent credit from gym/treadmill, or schedule catch-up.

The new candidate asks for at least three running sessions and one gym session
per seven-day unit. The current service supports one workout per day, so this
requires at least four distinct available days; the two-gym target requires
five. These are Product/interface capacity limits, not physiological readiness
thresholds. Four days are necessary, not sufficient: spacing, time and observed
history caps still apply. Adequate running history alone never guarantees a
complete schedule. If the minimum cannot fit, retain reviewable unplaced module
content and reasons, with an explicit schedule limitation; do not silently drop
gym, lower the run-day floor, or flatten same-day run plus gym into one workout.

Science owns all candidate doses and applicability in
`sdr-non-ultra-trail-plan-generation-policy-v3`; this Product record does not
duplicate those parameters or approve them.

## Adoption, edits and owner rights

Only explicit adoption of the exact proposal version may write the calendar in
a future implementation. Changed resource dates invalidate an old draft. For
an adopted plan, mark the affected future work and retain it until the owner
explicitly adopts a successor; only then replace future uncompleted workouts.
Preserve completed training. Review never automatically progresses or adopts.

Future exposure uses the existing Statsig SDK and an owner gate, with no Trail
attributes or value telemetry. Gate-off preserves read/export/delete. Garmin
and every other provider receive zero delivery or access from this scope.
The future rights implementation must cover current context, goal snapshots,
proposals, audits, `PlanRevision.proposal_snapshot`, caches and unknown schemas;
reset is not deletion. See the [Trust draft](trail-running-plan-trust-decision-v3.md).

## Future outcome observation

After separate runtime authorization, the owner completes one 14-day
generate/adopt journey and the seven-day review, and actively reports sessions
that cannot be executed. Product records whether the proposed experience is
useful and understandable; these observations are not efficacy, adaptation or
safety proof. No new analytics collection is authorized by this package.

Dependencies are the Science v3 proposals, Design experience, Architecture and
Trust drafts, independent Quality, Decision Review, future Operations release
evidence and explicit activation authority. Existing v2 records remain intact.
