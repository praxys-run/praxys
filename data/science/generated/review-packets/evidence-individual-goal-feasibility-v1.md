# Evidence review packet: Individual goal feasibility and prediction limits

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-individual-goal-feasibility-v1`
- **Lifecycle:** `accepted`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:68dabbd3bed068c2829d6b77d9b0ee2503e8ae3874b745d2b61f5420680b94ba`
- **Required role:** `evidence_reviewer`
- **Approval:** `github:dddtc2005` on `2026-08-16` ([source](https://github.com/praxys-run/praxys/pull/714#issuecomment-5307154729))

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-individual-goal-feasibility-v1`
- Digest: `sha256:68dabbd3bed068c2829d6b77d9b0ee2503e8ae3874b745d2b61f5420680b94ba`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:68dabbd3bed068c2829d6b77d9b0ee2503e8ae3874b745d2b61f5420680b94ba","subject_id":"evidence-individual-goal-feasibility-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

What does exercise and prediction-method research support about translating population evidence and observed training response into an individual endurance athlete's goal-feasibility assessment?

Bound the claims Praxys may make before and during an adaptive plan without presenting population associations or noisy individual changes as a calibrated personal probability of goal achievement.

## Scope

## Population

- Adults participating in exercise training
- Endurance athletes where represented by the reviewed literature
- Recreational runners as the intended product population

## Intervention or exposure

- Standardized exercise-training interventions
- Individual response classification
- Multivariable individual prediction

## Comparator

- Group-average versus individual-response inference
- Response classifications with and without measurement error
- Developed versus externally validated prediction models

## Outcomes

- Individual response classification
- Calibration and discrimination of prediction
- Goal-feasibility claim boundaries

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-08-16`

### Exact searches

- **PubMed**
  - `("exercise training"[Title/Abstract] OR "endurance training"[Title/Abstract]) AND (interindividual[Title/Abstract] OR "individual response"[Title/Abstract] OR trainability[Title/Abstract]) AND adult[MeSH Terms]`
- **PubMed systematic-review update**
  - `(("individual response"[Title/Abstract] OR "inter-individual heterogeneity"[Title/Abstract] OR trainability[Title/Abstract]) AND ("aerobic training"[Title/Abstract] OR "exercise interventions"[Title/Abstract] OR "exercise training"[Title/Abstract]) AND ("systematic review"[Title/Abstract] OR "meta-analysis"[Title/Abstract]))`
- **PubMed currency window**
  - `(("exercise training"[Title/Abstract] OR "endurance training"[Title/Abstract]) AND (interindividual[Title/Abstract] OR "individual response"[Title/Abstract] OR trainability[Title/Abstract]) AND adult[MeSH Terms]) AND (2026/08/08:2026/08/16[edat])`
- **PubMed exact identifier verification**
  - `34819869[PMID] OR 25823596[PMID] OR 25560714[PMID] OR 39160296[PMID] OR 41465870[PMID]`
- **PubMed Central**
  - `PMC8606564 OR PMC12734763`
- **Crossref DOI API**
  - `GET /works/{doi} for 10.3389/fphys.2021.665044, 10.1113/EP085070, 10.7326/M14-0697, 10.1007/s40279-024-02089-y, and 10.3390/life15121932`

## Inclusion criteria

- Adult human exercise-training response research
- Systematic reviews of individual response classification
- Prediction-model reporting and validation guidance
- Stable DOI or PMID metadata and an abstract or full text

## Exclusion criteria

- Claims based only on group means without individual-response methods
- Children-only populations
- Disease-specific prognosis presented as athletic-goal validation
- Vendor predictions, coaching rules, and unverified web summaries

## Method limitations

- Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.
- This targeted review did not directly search SPORTDiscus, Embase, or Scopus.
- Full text was not accessed for atkinson-2015 or collins-2015, so claims from those sources are limited to abstract-supported methodology.
- Full text was not accessed for renwick-2024, so its conclusions are limited to the indexed abstract.
- Xiao and Ren reviewed broad aerobic-training outcomes rather than a runner-specific managed-plan policy.
- Prediction guidance is general methodology rather than a validated running-goal model.
- Exercise-response evidence spans aerobic, resistance, and clinical research.

### Quality appraisal

Claims were appraised for study design, directness to individual athletic prediction, treatment of measurement error and within-person variation, external validation, calibration, and applicability to recreational runners. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/individual-goal-feasibility/search-manifest-individual-goal-feasibility-v1.json.

## Claims

### `feasibility.group-evidence-not-personal-probability` — high

Group-average exercise response and population associations do not by themselves estimate one athlete's probability of attaining a goal.

- **Sources:** `bonafiglia-2021`, `atkinson-2015`, `renwick-2024`, `xiao-ren-2025`
- **Population:** Adults completing standardized exercise interventions; Endurance athletes only to the extent represented by the included studies
- **Domain:** Individual response; Goal feasibility
- **Limitations:**
  - The review was not specific to race-goal prediction.
  - This boundary does not identify which qualitative category is appropriate.
  - It does not show that individual response differences never exist.

### `feasibility.error-aware-response-classification` — high

Individual response classification should account for random measurement error, within-person variability, and a meaningful-change threshold; zero-based thresholds inflate apparent response rates.

- **Sources:** `bonafiglia-2021`, `atkinson-2015`, `renwick-2024`, `xiao-ren-2025`
- **Population:** Adults in supervised standardized exercise training
- **Domain:** Response classification; Measurement uncertainty
- **Limitations:**
  - Meaningful-change thresholds are outcome and protocol specific.
  - Classification after one plan does not identify an intrinsic responder trait.
  - Failure to detect heterogeneity does not prove that no person-by-protocol interaction exists.
- **Verified effect estimates:**
  - Studies statistically estimating interindividual trainability: 9.0 studies (9 of 149 studies in the Bonafiglia systematic review)
  - Studies in the Renwick VO2max meta-analysis: 24.0 studies (The pooled SDIR analysis did not provide strong evidence for a positive individual-response variance.)

### `feasibility.no-permanent-responder-label` — high

One observed training response does not support assigning a permanent responder or non-responder identity because measurement error, within-person variation, protocol choice, and context can contribute to the observed change.

- **Sources:** `bonafiglia-2021`, `renwick-2024`, `xiao-ren-2025`
- **Population:** Adults completing standardized aerobic exercise interventions
- **Domain:** Individual response; Athlete profiling
- **Limitations:**
  - The reviewed evidence does not establish that all athletes respond identically.
  - Behavioral fit, constraints, and within-person state may still justify changing how a strategy is delivered.
  - This claim does not validate a specific adaptive selection algorithm.

### `feasibility.calibration-required` — high

A numerical individual prediction requires a defined outcome, representative development data, validation, and reported calibration as well as discrimination before it can support a personal probability.

- **Sources:** `collins-2015`
- **Population:** Developers and evaluators of multivariable individual prediction models
- **Domain:** Prediction-model validation; Personal probability claims
- **Limitations:**
  - TRIPOD is reporting guidance and does not validate a Praxys model.
  - No reviewed source provides running-goal probability thresholds.

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `bonafiglia-2021` | `full-text` | DOI `10.3389/fphys.2021.665044` | A Systematic Review Examining the Approaches Used to Estimate Interindividual Differences in Trainability and Classify Individual Responses to Exercise Training (2021) |
| `atkinson-2015` | `abstract` | DOI `10.1113/EP085070` | True and false interindividual differences in the physiological response to an intervention (2015) |
| `collins-2015` | `abstract` | DOI `10.7326/M14-0697` | Transparent Reporting of a multivariable prediction model for Individual Prognosis or Diagnosis (TRIPOD): the TRIPOD statement (2015) |
| `renwick-2024` | `abstract` | DOI `10.1007/s40279-024-02089-y` | Standard Deviation of Individual Response for VO2max Following Exercise Interventions: A Systematic Review and Meta-analysis (2024) |
| `xiao-ren-2025` | `full-text` | DOI `10.3390/life15121932` | Inter-Individual Heterogeneity in Aerobic Training Adaptations: Systematic Review of the Evidence Base for Personalized Exercise Prescription (2025) |

## Known gaps

- Prospectively calibrated goal-achievement models for recreational runners
- External and temporal validation across training history, sex, age, and race type
- Evidence-based cut points for named qualitative feasibility categories
- Prospectively validated person-by-protocol selection rather than permanent response labels

## Conflicting findings

- Earlier studies reported apparent response heterogeneity, while the Renwick and Xiao systematic reviews found no strong statistical evidence for stable between-person aerobic-training response after accounting for measurement error and within-person variation. This does not establish that every athlete, context, outcome, or protocol responds identically.

## Follow-up questions

- Which outcome and population should the first prospective feasibility evaluation target?
- What test-retest evidence is required before a baseline is considered comparable?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:github-copilot"
  ],
  "citations": [
    {
      "authors": [
        "J. T. Bonafiglia",
        "N. Preobrazenski",
        "B. J. Gurd"
      ],
      "doi": "10.3389/fphys.2021.665044",
      "id": "bonafiglia-2021",
      "journal": "Frontiers in Physiology",
      "pmid": "34819869",
      "title": "A Systematic Review Examining the Approaches Used to Estimate Interindividual Differences in Trainability and Classify Individual Responses to Exercise Training",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "G. Atkinson",
        "A. M. Batterham"
      ],
      "doi": "10.1113/EP085070",
      "id": "atkinson-2015",
      "journal": "Experimental Physiology",
      "pmid": "25823596",
      "title": "True and false interindividual differences in the physiological response to an intervention",
      "url": null,
      "year": 2015
    },
    {
      "authors": [
        "G. S. Collins",
        "J. B. Reitsma",
        "D. G. Altman",
        "K. G. M. Moons"
      ],
      "doi": "10.7326/M14-0697",
      "id": "collins-2015",
      "journal": "Annals of Internal Medicine",
      "pmid": "25560714",
      "title": "Transparent Reporting of a multivariable prediction model for Individual Prognosis or Diagnosis (TRIPOD): the TRIPOD statement",
      "url": null,
      "year": 2015
    },
    {
      "authors": [
        "J. R. M. Renwick",
        "N. Preobrazenski",
        "Z. Wu",
        "A. Khansari",
        "M. A. LeBouedec",
        "J. M. G. Nuttall",
        "K. R. Bancroft",
        "N. Simpson-Stairs",
        "P. A. Swinton",
        "B. J. Gurd"
      ],
      "doi": "10.1007/s40279-024-02089-y",
      "id": "renwick-2024",
      "journal": "Sports Medicine",
      "pmid": "39160296",
      "title": "Standard Deviation of Individual Response for VO2max Following Exercise Interventions: A Systematic Review and Meta-analysis",
      "url": null,
      "year": 2024
    },
    {
      "authors": [
        "H. Xiao",
        "J. Ren"
      ],
      "doi": "10.3390/life15121932",
      "id": "xiao-ren-2025",
      "journal": "Life",
      "pmid": "41465870",
      "title": "Inter-Individual Heterogeneity in Aerobic Training Adaptations: Systematic Review of the Evidence Base for Personalized Exercise Prescription",
      "url": null,
      "year": 2025
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Adults completing standardized exercise interventions",
        "Endurance athletes only to the extent represented by the included studies"
      ],
      "domain": [
        "Individual response",
        "Goal feasibility"
      ],
      "effect_estimates": [],
      "evidence_strength": "high",
      "id": "feasibility.group-evidence-not-personal-probability",
      "limitations": [
        "The review was not specific to race-goal prediction.",
        "This boundary does not identify which qualitative category is appropriate.",
        "It does not show that individual response differences never exist."
      ],
      "source_ids": [
        "bonafiglia-2021",
        "atkinson-2015",
        "renwick-2024",
        "xiao-ren-2025"
      ],
      "statement": "Group-average exercise response and population associations do not by themselves estimate one athlete's probability of attaining a goal."
    },
    {
      "applicable_population": [
        "Adults in supervised standardized exercise training"
      ],
      "domain": [
        "Response classification",
        "Measurement uncertainty"
      ],
      "effect_estimates": [
        {
          "context": "9 of 149 studies in the Bonafiglia systematic review",
          "estimate": 9.0,
          "metric": "Studies statistically estimating interindividual trainability",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        },
        {
          "context": "The pooled SDIR analysis did not provide strong evidence for a positive individual-response variance.",
          "estimate": 24.0,
          "metric": "Studies in the Renwick VO2max meta-analysis",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        }
      ],
      "evidence_strength": "high",
      "id": "feasibility.error-aware-response-classification",
      "limitations": [
        "Meaningful-change thresholds are outcome and protocol specific.",
        "Classification after one plan does not identify an intrinsic responder trait.",
        "Failure to detect heterogeneity does not prove that no person-by-protocol interaction exists."
      ],
      "source_ids": [
        "bonafiglia-2021",
        "atkinson-2015",
        "renwick-2024",
        "xiao-ren-2025"
      ],
      "statement": "Individual response classification should account for random measurement error, within-person variability, and a meaningful-change threshold; zero-based thresholds inflate apparent response rates."
    },
    {
      "applicable_population": [
        "Adults completing standardized aerobic exercise interventions"
      ],
      "domain": [
        "Individual response",
        "Athlete profiling"
      ],
      "effect_estimates": [],
      "evidence_strength": "high",
      "id": "feasibility.no-permanent-responder-label",
      "limitations": [
        "The reviewed evidence does not establish that all athletes respond identically.",
        "Behavioral fit, constraints, and within-person state may still justify changing how a strategy is delivered.",
        "This claim does not validate a specific adaptive selection algorithm."
      ],
      "source_ids": [
        "bonafiglia-2021",
        "renwick-2024",
        "xiao-ren-2025"
      ],
      "statement": "One observed training response does not support assigning a permanent responder or non-responder identity because measurement error, within-person variation, protocol choice, and context can contribute to the observed change."
    },
    {
      "applicable_population": [
        "Developers and evaluators of multivariable individual prediction models"
      ],
      "domain": [
        "Prediction-model validation",
        "Personal probability claims"
      ],
      "effect_estimates": [],
      "evidence_strength": "high",
      "id": "feasibility.calibration-required",
      "limitations": [
        "TRIPOD is reporting guidance and does not validate a Praxys model.",
        "No reviewed source provides running-goal probability thresholds."
      ],
      "source_ids": [
        "collins-2015"
      ],
      "statement": "A numerical individual prediction requires a defined outcome, representative development data, validation, and reported calibration as well as discrimination before it can support a personal probability."
    }
  ],
  "conflicting_findings": [
    "Earlier studies reported apparent response heterogeneity, while the Renwick and Xiao systematic reviews found no strong statistical evidence for stable between-person aerobic-training response after accounting for measurement error and within-person variation. This does not establish that every athlete, context, outcome, or protocol responds identically."
  ],
  "created_on": "2026-08-08",
  "follow_up_questions": [
    "Which outcome and population should the first prospective feasibility evaluation target?",
    "What test-retest evidence is required before a baseline is considered comparable?"
  ],
  "id": "evidence-individual-goal-feasibility-v1",
  "intended_product_purpose": "Bound the claims Praxys may make before and during an adaptive plan without presenting population associations or noisy individual changes as a calibrated personal probability of goal achievement.",
  "known_gaps": [
    "Prospectively calibrated goal-achievement models for recreational runners",
    "External and temporal validation across training history, sex, age, and race type",
    "Evidence-based cut points for named qualitative feasibility categories",
    "Prospectively validated person-by-protocol selection rather than permanent response labels"
  ],
  "method": {
    "exclusion_criteria": [
      "Claims based only on group means without individual-response methods",
      "Children-only populations",
      "Disease-specific prognosis presented as athletic-goal validation",
      "Vendor predictions, coaching rules, and unverified web summaries"
    ],
    "inclusion_criteria": [
      "Adult human exercise-training response research",
      "Systematic reviews of individual response classification",
      "Prediction-model reporting and validation guidance",
      "Stable DOI or PMID metadata and an abstract or full text"
    ],
    "method_limitations": [
      "Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.",
      "This targeted review did not directly search SPORTDiscus, Embase, or Scopus.",
      "Full text was not accessed for atkinson-2015 or collins-2015, so claims from those sources are limited to abstract-supported methodology.",
      "Full text was not accessed for renwick-2024, so its conclusions are limited to the indexed abstract.",
      "Xiao and Ren reviewed broad aerobic-training outcomes rather than a runner-specific managed-plan policy.",
      "Prediction guidance is general methodology rather than a validated running-goal model.",
      "Exercise-response evidence spans aerobic, resistance, and clinical research."
    ],
    "quality_appraisal": "Claims were appraised for study design, directness to individual athletic prediction, treatment of measurement error and within-person variation, external validation, calibration, and applicability to recreational runners. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/individual-goal-feasibility/search-manifest-individual-goal-feasibility-v1.json.",
    "review_type": "rigorous",
    "search_date": "2026-08-16",
    "sources": [
      {
        "name": "PubMed",
        "search_string": "(\"exercise training\"[Title/Abstract] OR \"endurance training\"[Title/Abstract]) AND (interindividual[Title/Abstract] OR \"individual response\"[Title/Abstract] OR trainability[Title/Abstract]) AND adult[MeSH Terms]"
      },
      {
        "name": "PubMed systematic-review update",
        "search_string": "((\"individual response\"[Title/Abstract] OR \"inter-individual heterogeneity\"[Title/Abstract] OR trainability[Title/Abstract]) AND (\"aerobic training\"[Title/Abstract] OR \"exercise interventions\"[Title/Abstract] OR \"exercise training\"[Title/Abstract]) AND (\"systematic review\"[Title/Abstract] OR \"meta-analysis\"[Title/Abstract]))"
      },
      {
        "name": "PubMed currency window",
        "search_string": "((\"exercise training\"[Title/Abstract] OR \"endurance training\"[Title/Abstract]) AND (interindividual[Title/Abstract] OR \"individual response\"[Title/Abstract] OR trainability[Title/Abstract]) AND adult[MeSH Terms]) AND (2026/08/08:2026/08/16[edat])"
      },
      {
        "name": "PubMed exact identifier verification",
        "search_string": "34819869[PMID] OR 25823596[PMID] OR 25560714[PMID] OR 39160296[PMID] OR 41465870[PMID]"
      },
      {
        "name": "PubMed Central",
        "search_string": "PMC8606564 OR PMC12734763"
      },
      {
        "name": "Crossref DOI API",
        "search_string": "GET /works/{doi} for 10.3389/fphys.2021.665044, 10.1113/EP085070, 10.7326/M14-0697, 10.1007/s40279-024-02089-y, and 10.3390/life15121932"
      }
    ]
  },
  "research_question": "What does exercise and prediction-method research support about translating population evidence and observed training response into an individual endurance athlete's goal-feasibility assessment?",
  "review_notes": [
    "Verification: bonafiglia-2021 - full-text; PubMed Central PMC8606564 and PubMed metadata; 2026-08-08.",
    "Verification: atkinson-2015 - abstract; PubMed PMID 25823596 and Crossref metadata; 2026-08-08.",
    "Verification: collins-2015 - abstract; PubMed PMID 25560714 and Crossref metadata; 2026-08-08.",
    "Verification: renwick-2024 - abstract; PubMed PMID 39160296 and DOI metadata; 2026-08-16.",
    "Verification: xiao-ren-2025 - full-text; PubMed Central PMC12734763 and PubMed metadata; 2026-08-16.",
    "Currency check: the complete PubMed searches were rerun through 2026-08-16; no newly indexed source in the 2026-08-08 to 2026-08-16 window changed the claim boundary.",
    "Product scope is defined in"
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Group-average versus individual-response inference",
      "Response classifications with and without measurement error",
      "Developed versus externally validated prediction models"
    ],
    "intervention_or_exposure": [
      "Standardized exercise-training interventions",
      "Individual response classification",
      "Multivariable individual prediction"
    ],
    "outcomes": [
      "Individual response classification",
      "Calibration and discrimination of prediction",
      "Goal-feasibility claim boundaries"
    ],
    "population": [
      "Adults participating in exercise training",
      "Endurance athletes where represented by the reviewed literature",
      "Recreational runners as the intended product population"
    ]
  },
  "supersedes": [],
  "title": "Individual goal feasibility and prediction limits",
  "topic": "individual-goal-feasibility",
  "version": 1
}
```

</details>
