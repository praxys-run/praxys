# Contributing Scientific Evidence

Praxys welcomes corrections from coaches, athletes, researchers, clinicians,
and developers. You do not need to write Python to challenge a scientific
claim or product interpretation.

## Two ways to contribute

### Evidence correction or proposal without code

Open the **Science correction or evidence proposal** issue form. Include the
claim you are challenging, the affected product surface, the proposed
correction, stable source identifiers, what source text you reviewed, the
relevant population/protocol/outcome, conflicts, limitations, and expected
product impact.

A maintainer can accept the correction as an Evidence Review or Science
Decision Record (SDR) update even if no implementation is ready. Implementation
is tracked separately so evidence review does not depend on writing code.

### Recording source verification

When a maintainer transfers a proposal into an Evidence Review, add exactly one
`review_notes` entry for each citation:

```text
Verification: <citation-id> - <full-text|abstract|metadata|inaccessible>;
<where checked>; <YYYY-MM-DD>.
```

Use `full-text` only when the relevant source text was actually reviewed.
`abstract` means an abstract or indexed record was checked, `metadata` means
only bibliographic fields were confirmed, and `inaccessible` must not support a
strong claim or effect estimate. The local science reviewer reports these as
recorded levels, not as independent external verification. It flags missing,
duplicate, malformed, and unknown citation-ID entries.

### Science implementation pull request

Choose the **Science change** pull-request template for a change to a formula,
constant, theory, `docs/science/`, scientific UI copy, or evidence record. The
template links the evidence and decision to the implementation, asks for test
and validation/falsification coverage, and checks web/miniapp and
English/Chinese parity.

## How review works

Praxys uses three distinct review layers:

| Layer | Responsibility | What it cannot do |
| --- | --- | --- |
| Deterministic checks | Validate registry schema, identifiers, references, estimate labels, tests, and source/copy synchronization. | Establish that a paper supports a claim. |
| Research-capable review | Check source quality, claim-to-source correspondence, applicability, omitted conflicts, and reported verification level. | Accept an SDR or merge a science change. |
| Human science approval | Decide whether the evidence supports the product interpretation and accept the SDR. | Be replaced by a citation count or an agent. |

The current science owner is **@dddtc2005**. There is no configured
independent science reviewer or team yet, so submissions must make that
limitation visible rather than imply independent review occurred.

## Disagreement, corrections, and history

Scientific disagreement is expected. Do not overwrite an accepted Evidence
Review or SDR. Create a new version, mark the earlier record as superseded only
when the successor and affected decision are ready together, and record why the
product interpretation changed and which model versions are affected.

An evidence correction can be accepted without an immediate code change. If
the correction needs implementation, the record should link a separate issue
or pull request that owns the behavior change.

## Safety concerns

For a potential urgent safety correction, select the relevant urgency in the
issue form and explain the immediate product risk. A maintainer should triage
it promptly, but urgent handling still requires human approval before a
scientific product claim or safety behavior changes.

Praxys does not provide medical clearance, diagnose heat illness, or turn
population evidence into personal guarantees.
