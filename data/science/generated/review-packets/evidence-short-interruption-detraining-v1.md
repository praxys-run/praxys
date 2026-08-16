# Evidence review packet: Short training interruption and detraining

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-short-interruption-detraining-v1`
- **Lifecycle:** `accepted`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:a68cb7a7655e1980c0ecd8cf7dfb737015b000ea9609572e460fabd13e932fb9`
- **Required role:** `evidence_reviewer`
- **Approval:** `github:dddtc2005` on `2026-08-16` ([source](https://github.com/praxys-run/praxys/pull/714#issuecomment-5307154937))

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-short-interruption-detraining-v1`
- Digest: `sha256:a68cb7a7655e1980c0ecd8cf7dfb737015b000ea9609572e460fabd13e932fb9`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:a68cb7a7655e1980c0ecd8cf7dfb737015b000ea9609572e460fabd13e932fb9","subject_id":"evidence-short-interruption-detraining-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

What does adult endurance research support about short interruptions, reduced training, detraining, and non-medical return-to-training boundaries?

Prevent Praxys from applying a fixed fitness-loss or return percentage after missed days, while supporting conservative reassessment after a meaningful non-medical interruption.

## Scope

## Population

- Trained adult endurance athletes
- General healthy adults in reduced-training research
- Recreational runners as the intended product population

## Intervention or exposure

- Short-term insufficient training stimulus
- Reduced training frequency or volume
- Partial versus complete training cessation

## Comparator

- Normal training
- Complete cessation
- Maintained intensity with reduced frequency or volume

## Outcomes

- Endurance performance
- VO2max and cardiovascular adaptations
- Running economy
- Limits of individual return prescription

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-08-16`

### Exact searches

- **PubMed**
  - `(running[Title/Abstract] OR endurance[Title/Abstract]) AND (detraining[Title/Abstract] OR "training cessation"[Title/Abstract] OR "reduced training"[Title/Abstract] OR "training interruption"[Title/Abstract]) AND adult[MeSH Terms]`
- **PubMed systematic-review update**
  - `(detraining[Title/Abstract] AND endurance[Title/Abstract]) AND (systematic review[Publication Type] OR review[Publication Type])`
- **PubMed currency window**
  - `((running[Title/Abstract] OR endurance[Title/Abstract]) AND (detraining[Title/Abstract] OR "training cessation"[Title/Abstract] OR "reduced training"[Title/Abstract] OR "training interruption"[Title/Abstract]) AND adult[MeSH Terms]) AND (2026/08/08:2026/08/16[edat])`
- **PubMed exact identifier verification**
  - `10966148[PMID] OR 33629972[PMID] OR 33374897[PMID] OR 38344385[PMID]`
- **PubMed Central**
  - `PMC7821917 OR PMC10853933`
- **Crossref DOI API**
  - `GET /works/{doi} for 10.2165/00007256-200030020-00002, 10.1519/JSC.0000000000003964, 10.3390/sports9010001, and 10.3389/fphys.2023.1334766`

## Inclusion criteria

- Adult human detraining or reduced-training reviews
- Endurance or running performance outcomes
- Stable DOI or PMID metadata and an abstract or full text

## Exclusion criteria

- Children-only studies
- Injury rehabilitation and disease-specific return protocols
- Claims based only on resistance training
- Exact return prescriptions without direct validation

## Method limitations

- Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.
- Full text was not accessed for mujika-2000 or spiering-2021, so claims from those sources are limited to their abstracts.
- Classic detraining synthesis is narrative and focused heavily on trained athletes.
- The Barbieri systematic review includes multiple endurance sports and heterogeneous total-cessation or reduced-training protocols.
- Maintenance evidence includes general adults and may not transfer to athletes.
- Female-specific, older recreational, and novice-running evidence is sparse.

### Quality appraisal

Claims were appraised for training status, type and duration of reduction, distinction between partial and complete cessation, outcome specificity, sample size, and directness to recreational running. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/short-interruption-detraining/search-manifest-short-interruption-detraining-v1.json.

## Claims

### `detraining.short-term-system-specific` — moderate

Less than four weeks of insufficient training can reduce some cardiorespiratory and endurance adaptations, but the time course and magnitude differ by outcome, cessation versus reduction, and prior training status.

- **Sources:** `mujika-2000`, `barbieri-2023`
- **Population:** Trained and recently trained adults represented by the review
- **Domain:** Detraining; Short interruption
- **Limitations:**
  - The review does not establish a fixed loss per day.
  - Highly trained athletes are overrepresented.
  - The evidence does not define an individual return progression.

### `detraining.reduced-dose-maintenance` — low

Reduced training frequency or volume may preserve endurance for a period when sufficient intensity is maintained, but athlete-specific evidence is limited and this is not equivalent to complete cessation.

- **Sources:** `spiering-2021`, `barbieri-2023`
- **Population:** Healthy general adult populations represented by the review
- **Domain:** Reduced training; Performance maintenance
- **Limitations:**
  - The review states that data are insufficient for athletes.
  - It does not support a universal minimum dose or return rule.

### `detraining.partial-not-complete-cessation` — very_low

Stopping one training component while continuing running is not evidence about the effect of stopping all endurance training.

- **Sources:** `berryman-2021`
- **Population:** Trained male middle-distance runners similar to the small case series
- **Domain:** Partial training cessation; Running performance
- **Limitations:**
  - Eight participants and no control group
  - Running continued while explosive-strength training stopped
  - The study cannot define general interruption or return policy

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `mujika-2000` | `abstract` | DOI `10.2165/00007256-200030020-00002` | Detraining: loss of training-induced physiological and performance adaptations. Part I: short term insufficient training stimulus (2000) |
| `spiering-2021` | `abstract` | DOI `10.1519/JSC.0000000000003964` | Maintaining Physical Performance: The Minimal Dose of Exercise Needed to Preserve Endurance and Strength Over Time (2021) |
| `berryman-2021` | `full-text` | DOI `10.3390/sports9010001` | Effects of Short-Term Concurrent Training Cessation on the Energy Cost of Running and Neuromuscular Performances in Middle-Distance Runners (2021) |
| `barbieri-2023` | `full-text` | DOI `10.3389/fphys.2023.1334766` | Cardiorespiratory and metabolic consequences of detraining in endurance athletes (2023) |

## Known gaps

- Individual loss and recovery trajectories after common real-life interruptions
- Recreational-runner evidence by sex, age, and training history
- Validated non-medical return rules after specific interruption durations
- Exact reduced-training strategies that preserve each outcome in recreational runners
- Separation of schedule interruption from illness or injury

## Conflicting findings

- Outcomes decline at different rates, total cessation and partial reduction are not equivalent, and partial training may preserve some capacities, so one interruption-day or return-dose boundary cannot represent every system.

## Follow-up questions

- Which observed outcomes should trigger reassessment after a non-medical interruption?
- What symptom boundary should route the athlete away from performance planning?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:github-copilot"
  ],
  "citations": [
    {
      "authors": [
        "I. Mujika",
        "S. Padilla"
      ],
      "doi": "10.2165/00007256-200030020-00002",
      "id": "mujika-2000",
      "journal": "Sports Medicine",
      "pmid": "10966148",
      "title": "Detraining: loss of training-induced physiological and performance adaptations. Part I: short term insufficient training stimulus",
      "url": null,
      "year": 2000
    },
    {
      "authors": [
        "B. A. Spiering",
        "I. Mujika",
        "M. A. Sharp",
        "S. A. Foulis"
      ],
      "doi": "10.1519/JSC.0000000000003964",
      "id": "spiering-2021",
      "journal": "Journal of Strength and Conditioning Research",
      "pmid": "33629972",
      "title": "Maintaining Physical Performance: The Minimal Dose of Exercise Needed to Preserve Endurance and Strength Over Time",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "N. Berryman",
        "I. Mujika",
        "L. Bosquet"
      ],
      "doi": "10.3390/sports9010001",
      "id": "berryman-2021",
      "journal": "Sports",
      "pmid": "33374897",
      "title": "Effects of Short-Term Concurrent Training Cessation on the Energy Cost of Running and Neuromuscular Performances in Middle-Distance Runners",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "A. Barbieri",
        "A. Fuk",
        "G. Gallo",
        "D. Gotti",
        "A. Meloni",
        "A. La Torre",
        "L. Filipas",
        "R. Codella"
      ],
      "doi": "10.3389/fphys.2023.1334766",
      "id": "barbieri-2023",
      "journal": "Frontiers in Physiology",
      "pmid": "38344385",
      "title": "Cardiorespiratory and metabolic consequences of detraining in endurance athletes",
      "url": null,
      "year": 2023
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Trained and recently trained adults represented by the review"
      ],
      "domain": [
        "Detraining",
        "Short interruption"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "detraining.short-term-system-specific",
      "limitations": [
        "The review does not establish a fixed loss per day.",
        "Highly trained athletes are overrepresented.",
        "The evidence does not define an individual return progression."
      ],
      "source_ids": [
        "mujika-2000",
        "barbieri-2023"
      ],
      "statement": "Less than four weeks of insufficient training can reduce some cardiorespiratory and endurance adaptations, but the time course and magnitude differ by outcome, cessation versus reduction, and prior training status."
    },
    {
      "applicable_population": [
        "Healthy general adult populations represented by the review"
      ],
      "domain": [
        "Reduced training",
        "Performance maintenance"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "detraining.reduced-dose-maintenance",
      "limitations": [
        "The review states that data are insufficient for athletes.",
        "It does not support a universal minimum dose or return rule."
      ],
      "source_ids": [
        "spiering-2021",
        "barbieri-2023"
      ],
      "statement": "Reduced training frequency or volume may preserve endurance for a period when sufficient intensity is maintained, but athlete-specific evidence is limited and this is not equivalent to complete cessation."
    },
    {
      "applicable_population": [
        "Trained male middle-distance runners similar to the small case series"
      ],
      "domain": [
        "Partial training cessation",
        "Running performance"
      ],
      "effect_estimates": [],
      "evidence_strength": "very_low",
      "id": "detraining.partial-not-complete-cessation",
      "limitations": [
        "Eight participants and no control group",
        "Running continued while explosive-strength training stopped",
        "The study cannot define general interruption or return policy"
      ],
      "source_ids": [
        "berryman-2021"
      ],
      "statement": "Stopping one training component while continuing running is not evidence about the effect of stopping all endurance training."
    }
  ],
  "conflicting_findings": [
    "Outcomes decline at different rates, total cessation and partial reduction are not equivalent, and partial training may preserve some capacities, so one interruption-day or return-dose boundary cannot represent every system."
  ],
  "created_on": "2026-08-08",
  "follow_up_questions": [
    "Which observed outcomes should trigger reassessment after a non-medical interruption?",
    "What symptom boundary should route the athlete away from performance planning?"
  ],
  "id": "evidence-short-interruption-detraining-v1",
  "intended_product_purpose": "Prevent Praxys from applying a fixed fitness-loss or return percentage after missed days, while supporting conservative reassessment after a meaningful non-medical interruption.",
  "known_gaps": [
    "Individual loss and recovery trajectories after common real-life interruptions",
    "Recreational-runner evidence by sex, age, and training history",
    "Validated non-medical return rules after specific interruption durations",
    "Exact reduced-training strategies that preserve each outcome in recreational runners",
    "Separation of schedule interruption from illness or injury"
  ],
  "method": {
    "exclusion_criteria": [
      "Children-only studies",
      "Injury rehabilitation and disease-specific return protocols",
      "Claims based only on resistance training",
      "Exact return prescriptions without direct validation"
    ],
    "inclusion_criteria": [
      "Adult human detraining or reduced-training reviews",
      "Endurance or running performance outcomes",
      "Stable DOI or PMID metadata and an abstract or full text"
    ],
    "method_limitations": [
      "Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.",
      "Full text was not accessed for mujika-2000 or spiering-2021, so claims from those sources are limited to their abstracts.",
      "Classic detraining synthesis is narrative and focused heavily on trained athletes.",
      "The Barbieri systematic review includes multiple endurance sports and heterogeneous total-cessation or reduced-training protocols.",
      "Maintenance evidence includes general adults and may not transfer to athletes.",
      "Female-specific, older recreational, and novice-running evidence is sparse."
    ],
    "quality_appraisal": "Claims were appraised for training status, type and duration of reduction, distinction between partial and complete cessation, outcome specificity, sample size, and directness to recreational running. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/short-interruption-detraining/search-manifest-short-interruption-detraining-v1.json.",
    "review_type": "rigorous",
    "search_date": "2026-08-16",
    "sources": [
      {
        "name": "PubMed",
        "search_string": "(running[Title/Abstract] OR endurance[Title/Abstract]) AND (detraining[Title/Abstract] OR \"training cessation\"[Title/Abstract] OR \"reduced training\"[Title/Abstract] OR \"training interruption\"[Title/Abstract]) AND adult[MeSH Terms]"
      },
      {
        "name": "PubMed systematic-review update",
        "search_string": "(detraining[Title/Abstract] AND endurance[Title/Abstract]) AND (systematic review[Publication Type] OR review[Publication Type])"
      },
      {
        "name": "PubMed currency window",
        "search_string": "((running[Title/Abstract] OR endurance[Title/Abstract]) AND (detraining[Title/Abstract] OR \"training cessation\"[Title/Abstract] OR \"reduced training\"[Title/Abstract] OR \"training interruption\"[Title/Abstract]) AND adult[MeSH Terms]) AND (2026/08/08:2026/08/16[edat])"
      },
      {
        "name": "PubMed exact identifier verification",
        "search_string": "10966148[PMID] OR 33629972[PMID] OR 33374897[PMID] OR 38344385[PMID]"
      },
      {
        "name": "PubMed Central",
        "search_string": "PMC7821917 OR PMC10853933"
      },
      {
        "name": "Crossref DOI API",
        "search_string": "GET /works/{doi} for 10.2165/00007256-200030020-00002, 10.1519/JSC.0000000000003964, 10.3390/sports9010001, and 10.3389/fphys.2023.1334766"
      }
    ]
  },
  "research_question": "What does adult endurance research support about short interruptions, reduced training, detraining, and non-medical return-to-training boundaries?",
  "review_notes": [
    "Verification: mujika-2000 - abstract; PubMed PMID 10966148 and Crossref metadata; 2026-08-08.",
    "Verification: spiering-2021 - abstract; PubMed PMID 33629972 and Crossref metadata; 2026-08-08.",
    "Verification: berryman-2021 - full-text; PubMed Central PMC7821917 and PubMed metadata; 2026-08-08.",
    "Verification: barbieri-2023 - full-text; PubMed Central PMC10853933 and PubMed metadata; 2026-08-16.",
    "Currency check: the complete PubMed searches were rerun through 2026-08-16; no record newly indexed from 2026-08-08 through 2026-08-16 changed the reviewed boundary.",
    "Illness, injury, and medical return-to-sport are intentionally outside this review's product recommendation."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Normal training",
      "Complete cessation",
      "Maintained intensity with reduced frequency or volume"
    ],
    "intervention_or_exposure": [
      "Short-term insufficient training stimulus",
      "Reduced training frequency or volume",
      "Partial versus complete training cessation"
    ],
    "outcomes": [
      "Endurance performance",
      "VO2max and cardiovascular adaptations",
      "Running economy",
      "Limits of individual return prescription"
    ],
    "population": [
      "Trained adult endurance athletes",
      "General healthy adults in reduced-training research",
      "Recreational runners as the intended product population"
    ]
  },
  "supersedes": [],
  "title": "Short training interruption and detraining",
  "topic": "short-interruption-detraining",
  "version": 1
}
```

</details>
