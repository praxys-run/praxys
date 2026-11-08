# Trail program — exact review bindings

2026-09-14. **Draft / inactive; no approval or activation.** This is a human-readable
binding table for the existing logical handoffs, not a new approval schema.

**2026-09-20 presentation refresh:** Product and Experience were translated to
English without changing their proposed boundaries. Their current file hashes
below replace the historical 2026-09-14 bindings. All Science subjects, model /
contract digests and other bound files remain unchanged. The separate English
correction contract is recorded in the [current handoff](trail-running-program-review-handoff.md);
it does not replace the parent P1 contract. The [independent routing refresh](trail-running-program-decision-review.md)
of 2026-09-20 binds the translated subjects. The 2026-09-14 receipt remains
explicitly historical and is not evidence of review of the new file tuple.

## Canonical Science subjects

These digests are emitted by the existing `analysis.science_artifacts` helpers
`evidence_review_digest`, `science_decision_digest` and `build_policy_contract`.
They hash canonical model / contract payloads, not YAML or Markdown file bytes.
Human scientific acceptance must bind the generated packet's corresponding
subject digest. None has been accepted in this change.

| Subject | Canonical digest |
| --- | --- |
| `evidence-trail-running-program-v1` | `sha256:8525f2aaf5b608d746564fbf0dbcd54e4a2fc981fcfc28b4fe78ee6360e567eb` |
| `sdr-trail-running-program-policy-v1` | `sha256:b9fd88e07f0bafc6b063a9934ebf9799fd56006f02277f0b28e489cd51962255` |
| Generated inactive policy contract | `sha256:813b0a5bfbc1ba672b2fafaca2d31706be40e2860331b9ac813b6fcb01afe776` |

## Work Contract

The [exact deterministic route](trail-running-program-work-contract.json) binds:

- Classification: `sha256:d2b15692d6d8db1b897b750ce30d6418e9a62e1acf683a4e88fce8f4a7851668`.
- Route: `sha256:172191b42862f63e1368bb23496cb773b1fb7a8e8cd5e1ed2c413b080a5adb72`.
- Base: `5ef9c25d8409ab90c3b9d25f629cdf75d246e290`.
- Primary Product; nested Science, Design and Delivery; Engineering executor;
  independent Quality verifier; Decision Review required.

The temporary native contract ID `c798_54c8e2d1957b43e0` and executor slot
`s798_eng_51f93a06` identify coordination only; they confer no approval authority.

## Canonical file-content hashes

Every hash below is SHA-256 of the complete file after universal newline decoding
and UTF-8 encoding (`Path(path).read_text(encoding="utf-8").encode("utf-8")`).
Git stores LF; a CRLF working checkout therefore has the same reviewed content.
Logical decision `digest` fields resolve to the row for their exact path. The
binding table and mutable routing / verification records are not themselves
self-hashed approval subjects. Any subject edit requires recomputing its row and
renewing any dependent review; do not reuse an earlier binding.

| Subject path | UTF-8 / LF SHA-256 |
| --- | --- |
| [data/science/evidence/trail-running-program/evidence-trail-running-program-v1.yaml](../../data/science/evidence/trail-running-program/evidence-trail-running-program-v1.yaml) | `72b23f2a8b1c29e3f092578e265d6be4dae53e8d061217bc9f49aeb1da18c230` |
| [data/science/evidence/trail-running-program/search-manifest-trail-running-program-v1.json](../../data/science/evidence/trail-running-program/search-manifest-trail-running-program-v1.json) | `32c6285e8fc811dde08582d861fb23177607aaa0f95fa40c2abb6ded773ca9a1` |
| [data/science/decisions/sdr-trail-running-program-policy-v1.yaml](../../data/science/decisions/sdr-trail-running-program-policy-v1.yaml) | `e959776834ade0c7ff7fac225a1975ec62501cdb1a913273544061765f4f0827` |
| [data/science/generated/review-packets/evidence-trail-running-program-v1.md](../../data/science/generated/review-packets/evidence-trail-running-program-v1.md) | `b75e82116b3e6291e5d6b1a1803298c1fa5cc72fc3ac21370049c8a634ad2898` |
| [data/science/generated/review-packets/sdr-trail-running-program-policy-v1.md](../../data/science/generated/review-packets/sdr-trail-running-program-policy-v1.md) | `598e2c8cef0b54438732369e71ff28c1b7dbc079465d00fe1d90b6c2e63b273f` |
| [data/science/generated/contracts/sdr-trail-running-program-policy-v1.json](../../data/science/generated/contracts/sdr-trail-running-program-policy-v1.json) | `a70c7aa1261b70e3535459b85874ef8851805c2d6523ba2e8a19c7f429189e7c` |
| [docs/dev/trail-running-program-product-draft.md](trail-running-program-product-draft.md) | `2a3f0237d126b5b06454f7fa995a529ee41af0b44cda098e1c5fea7efefceac9` |
| [docs/dev/trail-running-program-design-draft.md](trail-running-program-design-draft.md) | `58b180125c47251d475d2bcb0b5bbeabe23f136a82cb590f578927678d2a6daa` |
| [docs/dev/trail-running-program-experience-draft.md](trail-running-program-experience-draft.md) | `f7ec2e2e4900ba9f193714d2f23cfc1a5e0dbdae59e2c26b89c36072d1774526` |
| [docs/dev/trail-running-program-architecture-draft.md](trail-running-program-architecture-draft.md) | `dc394d211faf5b0162a26ee76a0f1a8d14f730e956dea00c18798f5193ad054c` |
| [docs/dev/trail-running-program-trust-draft.md](trail-running-program-trust-draft.md) | `d8ba182665585943d55180bff436b68d4f06561a978be2cfc72feebd329e0e22` |
| [docs/dev/trail-running-program-independent-science-review.md](trail-running-program-independent-science-review.md) | `1ecfce1c3830e0df53592f615b8fe40f677fa3a2d50b4d7681685cffdb999b39` |
| [docs/dev/trail-running-program-work-contract.json](trail-running-program-work-contract.json) | `aefba1c8de22c5206ea13fee5214e7cdfea9abaa20566ccde232e7a0fc40362b` |

The [independent Science record](trail-running-program-independent-science-review.md)
preserves both the initial SDR file hash
`95d91f03616ae997ad03fcd8e2f38ad0a31bb06d6252b720ba4beae33663c38f`
and revised `e959776834ade0c7ff7fac225a1975ec62501cdb1a913273544061765f4f0827`.
The same reviewer found the initial two blockers and spacing clarification resolved
at the revised hash. That record does not approve generated files or runtime work.

The independent [Decision Review routing](trail-running-program-decision-review.md)
refresh is recorded. Human content acceptance where allocated and independent
Quality against the final immutable implementation commit remain required. No old approval, test total or rendered claim
is imported into this new scope.
