# Evidence review packet: Post-run short-scale DFA from ECG chest-strap RR

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-activity-dfa-alpha1-v1`
- **Lifecycle:** `draft`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:dcb55292c89c9721fbf4d7133f94e34487e5de50efd4ffc94b36a5a7eff9a73f`
- **Required role:** `evidence_reviewer`
- **Approval:** _Pending_

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-activity-dfa-alpha1-v1`
- Digest: `sha256:dcb55292c89c9721fbf4d7133f94e34487e5de50efd4ffc94b36a5a7eff9a73f`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:dcb55292c89c9721fbf4d7133f94e34487e5de50efd4ffc94b36a5a7eff9a73f","subject_id":"evidence-activity-dfa-alpha1-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

Can existing archived running FIT RR support bounded post-run DFA alpha1 without threshold or training claims?

Inspect valid running windows and the uncertainty of post-run beat-interval analysis.

## Scope

## Population

- Runners with archived ECG chest-strap RR

## Intervention or exposure

- Post-run raw RR DFA alpha1

## Comparator

- Published exercise DFA/device methods; independent numerical implementation

## Outcomes

- RR fidelity, numerical reproducibility, timing and quality availability; interpretation limits

## Review method

- **Type:** `rapid`
- **Search date:** `2026-09-27`

### Exact searches

- **Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text**
  - `(TITLE_ABS:DFA OR TITLE_ABS:"detrended fluctuation") AND (TITLE_ABS:"heart rate" OR TITLE_ABS:"RR intervals") AND (TITLE_ABS:exercise OR TITLE_ABS:running OR TITLE_ABS:cycling OR TITLE_ABS:threshold) FIRST_PDATE:[2020-01-01 TO 2026-09-27]`
- **Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text**
  - `"heart rate variability threshold"`
- **Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text**
  - `("Polar H10" OR "ECG chest") AND (DFA OR RR OR exercise)`
- **Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text**
  - `("DFA alpha1" OR "DFA a1" OR "DFA α1" OR "detrended fluctuation analysis") AND (exercise OR threshold OR cycling OR running) FIRST_PDATE:[2020-01-01 TO 2026-09-27]`
- **Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text**
  - `(TITLE_ABS:"DFA alpha1" OR TITLE_ABS:"DFA a1" OR TITLE_ABS:"DFA α1" OR TITLE_ABS:"detrended fluctuation") AND (TITLE_ABS:exercise OR TITLE_ABS:threshold OR TITLE_ABS:cycling OR TITLE_ABS:running) FIRST_PDATE:[2020-01-01 TO 2026-09-27]`
- **Crossref DOI bibliography verification**
  - `10.3390/s21030821; 10.3390/s22176536; 10.1007/s00421-024-05592-2; 10.14814/phy2.70777`

## Inclusion criteria

- Primary exercise DFA or ECG chest-strap validation research from the approved planning evidence packet

## Exclusion criteria

- Vendor claims as independent validation
- Threshold equivalence inferred across populations or protocols

## Method limitations

- Bounded rapid review, not an exhaustive systematic search. Original Science planning search/access date2026-09-27; all81 returned titles from the focused query were screened.
- The last exploratory query returned113 records; the first100 were retrieved before narrowing to the focused81-record search.
- Running study was reviewed at abstract level only. Crossref bibliography metadata was verified separately; that verification does not imply full-text access.

### Quality appraisal

Separate device validation, numerical method, physiological interpretation and engineering guardrails.

## Claims

### `dfa.recording-artifacts` — moderate

DFA alpha1 is sensitive to RR artifacts and recording/processing choices; raw ECG-derived intervals require explicit quality checks.

- **Sources:** `rogers-artifacts-2021`, `schaffarczyk-h10-2022`
- **Population:** Studied exercising adults with the tested recording devices and protocols
- **Domain:** exercise RR quality
- **Limitations:**
  - Neither source validates every registered sensor or the complete Praxys pipeline.
  - Passing these checks does not prove absence of artifacts.

### `dfa.short-scale-method` — low

Short-scale DFA over beat intervals is used in exercise research, including running; a 120-second window and scales4–16 are a research-informed analysis recipe.

- **Sources:** `rogers-artifacts-2021`, `van-rassel-running-2024`
- **Population:** Adults in the cited exercise protocols
- **Domain:** short-scale DFA
- **Limitations:**
  - The running paper was examined at abstract level only.
  - Praxys uses raw intervals without correction; it does not claim equivalence to Kubios or another application.
  - Window timing, minimum beats and quality cutoffs are engineering guardrails.

### `dfa.threshold-transfer-limited` — low

Agreement between HRV-derived and physiological thresholds is protocol-dependent; this observational running feature cannot identify individual training thresholds from fixed alpha1 cutoffs.

- **Sources:** `van-rassel-running-2024`, `olieslagers-cycling-2026`
- **Population:** Adults in the cited running and incremental cycling protocols
- **Domain:** exercise threshold interpretation
- **Limitations:**
  - Cycling findings do not automatically transfer to continuous running.
  - No prospective individual threshold or training-prescription validation of the Praxys method exists.

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `rogers-artifacts-2021` | `full-text` | DOI `10.3390/s21030821` | Influence of Artefact Correction and Recording Device Type on the Practical Application of a Non-Linear Heart Rate Variability Biomarker for Aerobic Threshold Determination (2021) |
| `schaffarczyk-h10-2022` | `full-text` | DOI `10.3390/s22176536` | Validity of the Polar H10 Sensor for Heart Rate Variability Analysis during Resting State and Incremental Exercise in Recreational Men and Women (2022) |
| `van-rassel-running-2024` | `abstract` | DOI `10.1007/s00421-024-05592-2` | Quantifying exercise intensity with fractal correlation properties of heart rate variability: a study on incremental and constant-speed running (2024) |
| `olieslagers-cycling-2026` | `full-text` | DOI `10.14814/phy2.70777` | Agreement between heart rate variability-derived and lactate/ventilatory thresholds during a 4-min stepwise incremental cycling test in male adults (2026) |

## Known gaps

- No across-device physiological validation of this complete pipeline.
- Native HRV messages lack direct sensor attribution; factual owner confirmation cannot establish device accuracy.
- A real recording with AlphaHRV disabled remains unverified.

## Conflicting findings

- Protocol and preprocessing differences limit transfer of threshold agreement.

## Follow-up questions

- How often do real archived running files pass source, time and quality checks across devices?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:science"
  ],
  "citations": [
    {
      "authors": [
        "Bruce Rogers",
        "David Giles",
        "Nick Draper",
        "Laurent Mourot",
        "Thomas Gronwald"
      ],
      "doi": "10.3390/s21030821",
      "id": "rogers-artifacts-2021",
      "journal": "Sensors",
      "pmid": null,
      "title": "Influence of Artefact Correction and Recording Device Type on the Practical Application of a Non-Linear Heart Rate Variability Biomarker for Aerobic Threshold Determination",
      "url": "https://doi.org/10.3390/s21030821",
      "year": 2021
    },
    {
      "authors": [
        "Marcelle Schaffarczyk",
        "Bruce Rogers",
        "Rüdiger Reer",
        "Thomas Gronwald"
      ],
      "doi": "10.3390/s22176536",
      "id": "schaffarczyk-h10-2022",
      "journal": "Sensors",
      "pmid": null,
      "title": "Validity of the Polar H10 Sensor for Heart Rate Variability Analysis during Resting State and Incremental Exercise in Recreational Men and Women",
      "url": "https://doi.org/10.3390/s22176536",
      "year": 2022
    },
    {
      "authors": [
        "C. R. van Rassel",
        "O. O. Ajayi",
        "K. M. Sales",
        "C. A. Clermont",
        "M. Rummel",
        "M. J. MacInnis"
      ],
      "doi": "10.1007/s00421-024-05592-2",
      "id": "van-rassel-running-2024",
      "journal": "European Journal of Applied Physiology",
      "pmid": "39235602",
      "title": "Quantifying exercise intensity with fractal correlation properties of heart rate variability: a study on incremental and constant-speed running",
      "url": "https://doi.org/10.1007/s00421-024-05592-2",
      "year": 2024
    },
    {
      "authors": [
        "Anton Olieslagers",
        "Yoram Müller-Jabusch",
        "Margot Vancoillie",
        "Emma Delen",
        "Toon de Beukelaar"
      ],
      "doi": "10.14814/phy2.70777",
      "id": "olieslagers-cycling-2026",
      "journal": "Physiological Reports",
      "pmid": null,
      "title": "Agreement between heart rate variability-derived and lactate/ventilatory thresholds during a 4-min stepwise incremental cycling test in male adults",
      "url": "https://doi.org/10.14814/phy2.70777",
      "year": 2026
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Studied exercising adults with the tested recording devices and protocols"
      ],
      "domain": [
        "exercise RR quality"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "dfa.recording-artifacts",
      "limitations": [
        "Neither source validates every registered sensor or the complete Praxys pipeline.",
        "Passing these checks does not prove absence of artifacts."
      ],
      "source_ids": [
        "rogers-artifacts-2021",
        "schaffarczyk-h10-2022"
      ],
      "statement": "DFA alpha1 is sensitive to RR artifacts and recording/processing choices; raw ECG-derived intervals require explicit quality checks."
    },
    {
      "applicable_population": [
        "Adults in the cited exercise protocols"
      ],
      "domain": [
        "short-scale DFA"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "dfa.short-scale-method",
      "limitations": [
        "The running paper was examined at abstract level only.",
        "Praxys uses raw intervals without correction; it does not claim equivalence to Kubios or another application.",
        "Window timing, minimum beats and quality cutoffs are engineering guardrails."
      ],
      "source_ids": [
        "rogers-artifacts-2021",
        "van-rassel-running-2024"
      ],
      "statement": "Short-scale DFA over beat intervals is used in exercise research, including running; a 120-second window and scales4–16 are a research-informed analysis recipe."
    },
    {
      "applicable_population": [
        "Adults in the cited running and incremental cycling protocols"
      ],
      "domain": [
        "exercise threshold interpretation"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "dfa.threshold-transfer-limited",
      "limitations": [
        "Cycling findings do not automatically transfer to continuous running.",
        "No prospective individual threshold or training-prescription validation of the Praxys method exists."
      ],
      "source_ids": [
        "van-rassel-running-2024",
        "olieslagers-cycling-2026"
      ],
      "statement": "Agreement between HRV-derived and physiological thresholds is protocol-dependent; this observational running feature cannot identify individual training thresholds from fixed alpha1 cutoffs."
    }
  ],
  "conflicting_findings": [
    "Protocol and preprocessing differences limit transfer of threshold agreement."
  ],
  "created_on": "2026-09-27",
  "follow_up_questions": [
    "How often do real archived running files pass source, time and quality checks across devices?"
  ],
  "id": "evidence-activity-dfa-alpha1-v1",
  "intended_product_purpose": "Inspect valid running windows and the uncertainty of post-run beat-interval analysis.",
  "known_gaps": [
    "No across-device physiological validation of this complete pipeline.",
    "Native HRV messages lack direct sensor attribution; factual owner confirmation cannot establish device accuracy.",
    "A real recording with AlphaHRV disabled remains unverified."
  ],
  "method": {
    "exclusion_criteria": [
      "Vendor claims as independent validation",
      "Threshold equivalence inferred across populations or protocols"
    ],
    "inclusion_criteria": [
      "Primary exercise DFA or ECG chest-strap validation research from the approved planning evidence packet"
    ],
    "method_limitations": [
      "Bounded rapid review, not an exhaustive systematic search. Original Science planning search/access date2026-09-27; all81 returned titles from the focused query were screened.",
      "The last exploratory query returned113 records; the first100 were retrieved before narrowing to the focused81-record search.",
      "Running study was reviewed at abstract level only. Crossref bibliography metadata was verified separately; that verification does not imply full-text access."
    ],
    "quality_appraisal": "Separate device validation, numerical method, physiological interpretation and engineering guardrails.",
    "review_type": "rapid",
    "search_date": "2026-09-27",
    "sources": [
      {
        "name": "Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text",
        "search_string": "(TITLE_ABS:DFA OR TITLE_ABS:\"detrended fluctuation\") AND (TITLE_ABS:\"heart rate\" OR TITLE_ABS:\"RR intervals\") AND (TITLE_ABS:exercise OR TITLE_ABS:running OR TITLE_ABS:cycling OR TITLE_ABS:threshold) FIRST_PDATE:[2020-01-01 TO 2026-09-27]"
      },
      {
        "name": "Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text",
        "search_string": "\"heart rate variability threshold\""
      },
      {
        "name": "Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text",
        "search_string": "(\"Polar H10\" OR \"ECG chest\") AND (DFA OR RR OR exercise)"
      },
      {
        "name": "Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text",
        "search_string": "(\"DFA alpha1\" OR \"DFA a1\" OR \"DFA α1\" OR \"detrended fluctuation analysis\") AND (exercise OR threshold OR cycling OR running) FIRST_PDATE:[2020-01-01 TO 2026-09-27]"
      },
      {
        "name": "Europe PMC REST: PubMed-indexed metadata/abstracts and PMC full text",
        "search_string": "(TITLE_ABS:\"DFA alpha1\" OR TITLE_ABS:\"DFA a1\" OR TITLE_ABS:\"DFA α1\" OR TITLE_ABS:\"detrended fluctuation\") AND (TITLE_ABS:exercise OR TITLE_ABS:threshold OR TITLE_ABS:cycling OR TITLE_ABS:running) FIRST_PDATE:[2020-01-01 TO 2026-09-27]"
      },
      {
        "name": "Crossref DOI bibliography verification",
        "search_string": "10.3390/s21030821; 10.3390/s22176536; 10.1007/s00421-024-05592-2; 10.14814/phy2.70777"
      }
    ]
  },
  "research_question": "Can existing archived running FIT RR support bounded post-run DFA alpha1 without threshold or training claims?",
  "review_notes": [
    "Verification: rogers-artifacts-2021 - full-text; Europe PMC PMC7865269, relevant methods/results/limitations; 2026-09-27.",
    "Verification: schaffarczyk-h10-2022 - full-text; Europe PMC PMC9459793, relevant methods/results/limitations; 2026-09-27.",
    "Verification: van-rassel-running-2024 - abstract; Europe PMC/PubMed PMID 39235602; 2026-09-27.",
    "Verification: olieslagers-cycling-2026 - full-text; Europe PMC PMC12910119, relevant methods/results/limitations; 2026-09-27.",
    "Full text endpoint: https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML . These levels and exact search strings restore the original Science handoff; Engineering did not perform a new literature review.",
    "Bibliography independently checked against Crossref DOI metadata2026-09-27.",
    "Native sensor modality provenance: Garmin FIT SDK profile21.217.0, https://raw.githubusercontent.com/garmin/fit-python-sdk/main/garmin_fit_sdk/profile.py . Sensor-type compatibility is not model-specific DFA accuracy certification.",
    "Mechanical materialization by Engineering preserves Science ownership; no signed evidence review or acceptance is claimed."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Published exercise DFA/device methods; independent numerical implementation"
    ],
    "intervention_or_exposure": [
      "Post-run raw RR DFA alpha1"
    ],
    "outcomes": [
      "RR fidelity, numerical reproducibility, timing and quality availability; interpretation limits"
    ],
    "population": [
      "Runners with archived ECG chest-strap RR"
    ]
  },
  "supersedes": [],
  "title": "Post-run short-scale DFA from ECG chest-strap RR",
  "topic": "activity-dfa-alpha1",
  "version": 1
}
```

</details>
