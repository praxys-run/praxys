# Evidence review packet: Running field tests for plan baselines and outcomes

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-running-field-tests-v1`
- **Lifecycle:** `accepted`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:734d2abf59bab4b371ff8dbf5db1ae39ce5c9d82ae85593a66063687ea664ccc`
- **Required role:** `evidence_reviewer`
- **Approval:** `github:dddtc2005` on `2026-08-16` ([source](https://github.com/praxys-run/praxys/pull/714#issuecomment-5307155039))

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-running-field-tests-v1`
- Digest: `sha256:734d2abf59bab4b371ff8dbf5db1ae39ce5c9d82ae85593a66063687ea664ccc`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:734d2abf59bab4b371ff8dbf5db1ae39ce5c9d82ae85593a66063687ea664ccc","subject_id":"evidence-running-field-tests-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

Which field-test properties support using a running test as direct or supporting evidence of change across an adaptive training plan?

Define when Praxys may compare field-test results across a plan and prevent unlike protocols, model estimates, or environmental conditions from being presented as equivalent direct performance evidence.

## Scope

## Population

- Healthy adults and children in walk/run field-test validation research
- Trained adult runners in critical-speed research
- Recreational runners as the intended product population

## Intervention or exposure

- Distance- and time-based walk/run tests
- Time trials and time-to-exhaustion tests
- Field-based critical-speed protocols
- Treadmill-derived critical-speed models

## Comparator

- Laboratory cardiorespiratory fitness
- Race-like performance
- Alternative critical-speed models
- Repeated measurements under defined protocols

## Outcomes

- Validity
- Reliability
- Sensitivity to change
- Running-performance prediction

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-08-16`

### Exact searches

- **PubMed**
  - `(running[Title/Abstract] OR runner*[Title/Abstract]) AND ("field test"[Title/Abstract] OR "time trial"[Title/Abstract] OR "critical speed"[Title/Abstract]) AND (validity[Title/Abstract] OR reliability[Title/Abstract] OR repeatability[Title/Abstract])`
- **PubMed systematic-review update**
  - `(running[Title/Abstract] OR runners[Title/Abstract]) AND (validity[Title/Abstract] OR reliability[Title/Abstract] OR sensitivity[Title/Abstract]) AND systematic review[Publication Type]`
- **PubMed currency window**
  - `((running[Title/Abstract] OR runner*[Title/Abstract]) AND ("field test"[Title/Abstract] OR "time trial"[Title/Abstract] OR "critical speed"[Title/Abstract]) AND (validity[Title/Abstract] OR reliability[Title/Abstract] OR repeatability[Title/Abstract])) AND (2026/08/08:2026/08/16[edat])`
- **PubMed exact identifier verification**
  - `18348590[PMID] OR 26987118[PMID] OR 40134905[PMID] OR 27379951[PMID] OR 38324270[PMID]`
- **PubMed Central**
  - `PMC4795745 OR PMC11933073`
- **Crossref DOI API**
  - `GET /works/{doi} for 10.2165/00007256-200838040-00003, 10.1371/journal.pone.0151671, 10.3389/fspor.2025.1520914, 10.1519/JSC.0000000000001529, and 10.23736/S0022-4707.23.15619-2`

## Inclusion criteria

- Human running or walk/run field-test validity or reliability research
- Reviews of sport-performance test validity, reliability, and sensitivity
- Stable DOI or PMID metadata and an abstract or full text

## Exclusion criteria

- Tests requiring a laboratory as the proposed product endpoint
- Cycling-only or team-sport protocols
- Vendor estimates without a reproducible protocol
- Studies without criterion, repeatability, or performance interpretation

## Method limitations

- Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.
- Full text was not accessed for currell-2008, nimmerichter-2017, or benhammou-2024, so claims from those sources are limited to their abstracts.
- The search did not exhaust every race-distance time-trial protocol.
- Some reviews mix children and adults or trained and recreational runners.
- Environmental standardization and minimal detectable change remain protocol specific.

### Quality appraisal

Claims were appraised for construct match, protocol standardization, directness to running performance, test-retest reliability, sensitivity, sample size, setting, model dependence, and applicability to recreational runners. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/running-field-tests/search-manifest-running-field-tests-v1.json.

## Claims

### `field-test.protocol-validity-reliability-sensitivity` — moderate

A performance test used to detect change should match the target performance and establish protocol-specific validity, reliability, and sensitivity; time trials are generally more reliable than time-to-exhaustion protocols.

- **Sources:** `currell-2008`, `benhammou-2024`
- **Population:** Sports-performance testing populations represented by the review
- **Domain:** Performance testing; Measurement error
- **Limitations:**
  - Exact error depends on sport, distance, protocol, and population.
  - The review does not define one preferred running test for Praxys.
  - Many runner-test studies do not report repeatability or sensitivity.

### `field-test.running-reliability-and-sensitivity-underreported` — moderate

Running-test validity is more often reported than test-retest reliability or sensitivity, so a valid construct alone is insufficient to classify an individual change as meaningful.

- **Sources:** `benhammou-2024`
- **Population:** Track and road runners; Trail runners; Inexperienced runners represented by the included studies
- **Domain:** Running-test reliability; Sensitivity to change
- **Limitations:**
  - The review does not validate one universal test or minimal detectable change.
  - The included methods and runner backgrounds were heterogeneous.
  - Abstract access limits detailed appraisal of individual study quality.
- **Verified effect estimates:**
  - Included runner-test studies: 23.0 studies (Systematic review across track/road, trail, and inexperienced runners)
  - Studies that ignored test-retest reliability: 87.0 percent (Benhammou systematic review)
  - Studies reporting test sensitivity: 0.0 studies (Benhammou systematic review)

### `field-test.vo2-estimate-not-direct-performance` — moderate

Distance- and time-based walk/run tests can estimate cardiorespiratory fitness, but the resulting score is an estimate rather than a direct laboratory measure or a complete measure of goal performance.

- **Sources:** `mayorga-vega-2016`
- **Population:** Apparently healthy children and adults represented by the review
- **Domain:** Cardiorespiratory fitness estimation; Field testing
- **Limitations:**
  - Results combine diverse ages and protocols.
  - Estimated VO2max is not equivalent to race-goal completion.
- **Verified effect estimates:**
  - Criterion-related validity correlation range: 0.42 to 0.79 correlation (Walk/run field tests estimating maximal oxygen uptake)

### `field-test.critical-speed-protocol-dependent` — moderate

Field critical-speed assessment can be reliable under specified conditions, but protocol, trial selection, mathematical model, and environment constrain interpretation and comparability.

- **Sources:** `lipkova-2025`, `nimmerichter-2017`
- **Population:** Trained runners using matched field critical-speed protocols
- **Domain:** Critical speed; Performance prediction
- **Limitations:**
  - The Nimmerichter sample included 16 trained athletes.
  - A treadmill-derived estimate is not interchangeable with a track time trial.
  - The 2025 systematic review is recent and includes heterogeneous protocols.
- **Verified effect estimates:**
  - Included field critical-speed studies: 19.0 studies (Lipkova systematic review)
  - Simple critical-speed model 5000 m time prediction error: 5.7 to 9.4 percent (16 trained athletes; treadmill-derived models versus track performance)

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `currell-2008` | `abstract` | DOI `10.2165/00007256-200838040-00003` | Validity, reliability and sensitivity of measures of sporting performance (2008) |
| `mayorga-vega-2016` | `full-text` | DOI `10.1371/journal.pone.0151671` | Criterion-Related Validity of the Distance- and Time-Based Walk/Run Field Tests for Estimating Cardiorespiratory Fitness: A Systematic Review and Meta-Analysis (2016) |
| `lipkova-2025` | `full-text` | DOI `10.3389/fspor.2025.1520914` | Field-based tests for determining critical speed among runners and its practical application: a systematic review (2025) |
| `nimmerichter-2017` | `abstract` | DOI `10.1519/JSC.0000000000001529` | Validity of Treadmill-Derived Critical Speed on Predicting 5000-Meter Track-Running Performance (2017) |
| `benhammou-2024` | `abstract` | DOI `10.23736/S0022-4707.23.15619-2` | Is test specificity the issue in assessing aerobic fitness and performance of runners? A systematic review (2024) |

## Known gaps

- Protocol-specific repeatability in Praxys recreational-runner populations
- Protocol-specific sensitivity and minimal detectable change in Praxys populations
- Comparable baseline and outcome protocols for trail and ultra-distance goals
- Environmental and fatigue-state standardization rules
- Validity of provider-estimated critical power as an outcome endpoint

## Conflicting findings

- Critical-speed methods can show high reliability under specified conditions while still producing material prediction error when transferred across protocols or environments.

## Follow-up questions

- Which single same-protocol field test should be piloted for each supported goal type?
- What repeatability study is required before classifying a change as meaningful?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:github-copilot"
  ],
  "citations": [
    {
      "authors": [
        "K. Currell",
        "A. E. Jeukendrup"
      ],
      "doi": "10.2165/00007256-200838040-00003",
      "id": "currell-2008",
      "journal": "Sports Medicine",
      "pmid": "18348590",
      "title": "Validity, reliability and sensitivity of measures of sporting performance",
      "url": null,
      "year": 2008
    },
    {
      "authors": [
        "D. Mayorga-Vega",
        "R. Bocanegra-Parrilla",
        "M. Ornelas",
        "J. Viciana"
      ],
      "doi": "10.1371/journal.pone.0151671",
      "id": "mayorga-vega-2016",
      "journal": "PLOS ONE",
      "pmid": "26987118",
      "title": "Criterion-Related Validity of the Distance- and Time-Based Walk/Run Field Tests for Estimating Cardiorespiratory Fitness: A Systematic Review and Meta-Analysis",
      "url": null,
      "year": 2016
    },
    {
      "authors": [
        "L. Lipkova",
        "I. Struhar",
        "J. Krajnak",
        "D. Puda",
        "M. Kumstat"
      ],
      "doi": "10.3389/fspor.2025.1520914",
      "id": "lipkova-2025",
      "journal": "Frontiers in Sports and Active Living",
      "pmid": "40134905",
      "title": "Field-based tests for determining critical speed among runners and its practical application: a systematic review",
      "url": null,
      "year": 2025
    },
    {
      "authors": [
        "A. Nimmerichter",
        "N. Novak",
        "C. Triska",
        "B. Prinz",
        "B. C. Breese"
      ],
      "doi": "10.1519/JSC.0000000000001529",
      "id": "nimmerichter-2017",
      "journal": "Journal of Strength and Conditioning Research",
      "pmid": "27379951",
      "title": "Validity of Treadmill-Derived Critical Speed on Predicting 5000-Meter Track-Running Performance",
      "url": null,
      "year": 2017
    },
    {
      "authors": [
        "S. Benhammou",
        "L. Mourot",
        "F. M. Clemente",
        "J. Coquart",
        "A. Belkadi"
      ],
      "doi": "10.23736/S0022-4707.23.15619-2",
      "id": "benhammou-2024",
      "journal": "The Journal of Sports Medicine and Physical Fitness",
      "pmid": "38324270",
      "title": "Is test specificity the issue in assessing aerobic fitness and performance of runners? A systematic review",
      "url": null,
      "year": 2024
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Sports-performance testing populations represented by the review"
      ],
      "domain": [
        "Performance testing",
        "Measurement error"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "field-test.protocol-validity-reliability-sensitivity",
      "limitations": [
        "Exact error depends on sport, distance, protocol, and population.",
        "The review does not define one preferred running test for Praxys.",
        "Many runner-test studies do not report repeatability or sensitivity."
      ],
      "source_ids": [
        "currell-2008",
        "benhammou-2024"
      ],
      "statement": "A performance test used to detect change should match the target performance and establish protocol-specific validity, reliability, and sensitivity; time trials are generally more reliable than time-to-exhaustion protocols."
    },
    {
      "applicable_population": [
        "Track and road runners",
        "Trail runners",
        "Inexperienced runners represented by the included studies"
      ],
      "domain": [
        "Running-test reliability",
        "Sensitivity to change"
      ],
      "effect_estimates": [
        {
          "context": "Systematic review across track/road, trail, and inexperienced runners",
          "estimate": 23.0,
          "metric": "Included runner-test studies",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        },
        {
          "context": "Benhammou systematic review",
          "estimate": 87.0,
          "metric": "Studies that ignored test-retest reliability",
          "range_high": null,
          "range_low": null,
          "unit": "percent"
        },
        {
          "context": "Benhammou systematic review",
          "estimate": 0.0,
          "metric": "Studies reporting test sensitivity",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        }
      ],
      "evidence_strength": "moderate",
      "id": "field-test.running-reliability-and-sensitivity-underreported",
      "limitations": [
        "The review does not validate one universal test or minimal detectable change.",
        "The included methods and runner backgrounds were heterogeneous.",
        "Abstract access limits detailed appraisal of individual study quality."
      ],
      "source_ids": [
        "benhammou-2024"
      ],
      "statement": "Running-test validity is more often reported than test-retest reliability or sensitivity, so a valid construct alone is insufficient to classify an individual change as meaningful."
    },
    {
      "applicable_population": [
        "Apparently healthy children and adults represented by the review"
      ],
      "domain": [
        "Cardiorespiratory fitness estimation",
        "Field testing"
      ],
      "effect_estimates": [
        {
          "context": "Walk/run field tests estimating maximal oxygen uptake",
          "estimate": null,
          "metric": "Criterion-related validity correlation range",
          "range_high": 0.79,
          "range_low": 0.42,
          "unit": "correlation"
        }
      ],
      "evidence_strength": "moderate",
      "id": "field-test.vo2-estimate-not-direct-performance",
      "limitations": [
        "Results combine diverse ages and protocols.",
        "Estimated VO2max is not equivalent to race-goal completion."
      ],
      "source_ids": [
        "mayorga-vega-2016"
      ],
      "statement": "Distance- and time-based walk/run tests can estimate cardiorespiratory fitness, but the resulting score is an estimate rather than a direct laboratory measure or a complete measure of goal performance."
    },
    {
      "applicable_population": [
        "Trained runners using matched field critical-speed protocols"
      ],
      "domain": [
        "Critical speed",
        "Performance prediction"
      ],
      "effect_estimates": [
        {
          "context": "Lipkova systematic review",
          "estimate": 19.0,
          "metric": "Included field critical-speed studies",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        },
        {
          "context": "16 trained athletes; treadmill-derived models versus track performance",
          "estimate": null,
          "metric": "Simple critical-speed model 5000 m time prediction error",
          "range_high": 9.4,
          "range_low": 5.7,
          "unit": "percent"
        }
      ],
      "evidence_strength": "moderate",
      "id": "field-test.critical-speed-protocol-dependent",
      "limitations": [
        "The Nimmerichter sample included 16 trained athletes.",
        "A treadmill-derived estimate is not interchangeable with a track time trial.",
        "The 2025 systematic review is recent and includes heterogeneous protocols."
      ],
      "source_ids": [
        "lipkova-2025",
        "nimmerichter-2017"
      ],
      "statement": "Field critical-speed assessment can be reliable under specified conditions, but protocol, trial selection, mathematical model, and environment constrain interpretation and comparability."
    }
  ],
  "conflicting_findings": [
    "Critical-speed methods can show high reliability under specified conditions while still producing material prediction error when transferred across protocols or environments."
  ],
  "created_on": "2026-08-08",
  "follow_up_questions": [
    "Which single same-protocol field test should be piloted for each supported goal type?",
    "What repeatability study is required before classifying a change as meaningful?"
  ],
  "id": "evidence-running-field-tests-v1",
  "intended_product_purpose": "Define when Praxys may compare field-test results across a plan and prevent unlike protocols, model estimates, or environmental conditions from being presented as equivalent direct performance evidence.",
  "known_gaps": [
    "Protocol-specific repeatability in Praxys recreational-runner populations",
    "Protocol-specific sensitivity and minimal detectable change in Praxys populations",
    "Comparable baseline and outcome protocols for trail and ultra-distance goals",
    "Environmental and fatigue-state standardization rules",
    "Validity of provider-estimated critical power as an outcome endpoint"
  ],
  "method": {
    "exclusion_criteria": [
      "Tests requiring a laboratory as the proposed product endpoint",
      "Cycling-only or team-sport protocols",
      "Vendor estimates without a reproducible protocol",
      "Studies without criterion, repeatability, or performance interpretation"
    ],
    "inclusion_criteria": [
      "Human running or walk/run field-test validity or reliability research",
      "Reviews of sport-performance test validity, reliability, and sensitivity",
      "Stable DOI or PMID metadata and an abstract or full text"
    ],
    "method_limitations": [
      "Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.",
      "Full text was not accessed for currell-2008, nimmerichter-2017, or benhammou-2024, so claims from those sources are limited to their abstracts.",
      "The search did not exhaust every race-distance time-trial protocol.",
      "Some reviews mix children and adults or trained and recreational runners.",
      "Environmental standardization and minimal detectable change remain protocol specific."
    ],
    "quality_appraisal": "Claims were appraised for construct match, protocol standardization, directness to running performance, test-retest reliability, sensitivity, sample size, setting, model dependence, and applicability to recreational runners. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/running-field-tests/search-manifest-running-field-tests-v1.json.",
    "review_type": "rigorous",
    "search_date": "2026-08-16",
    "sources": [
      {
        "name": "PubMed",
        "search_string": "(running[Title/Abstract] OR runner*[Title/Abstract]) AND (\"field test\"[Title/Abstract] OR \"time trial\"[Title/Abstract] OR \"critical speed\"[Title/Abstract]) AND (validity[Title/Abstract] OR reliability[Title/Abstract] OR repeatability[Title/Abstract])"
      },
      {
        "name": "PubMed systematic-review update",
        "search_string": "(running[Title/Abstract] OR runners[Title/Abstract]) AND (validity[Title/Abstract] OR reliability[Title/Abstract] OR sensitivity[Title/Abstract]) AND systematic review[Publication Type]"
      },
      {
        "name": "PubMed currency window",
        "search_string": "((running[Title/Abstract] OR runner*[Title/Abstract]) AND (\"field test\"[Title/Abstract] OR \"time trial\"[Title/Abstract] OR \"critical speed\"[Title/Abstract]) AND (validity[Title/Abstract] OR reliability[Title/Abstract] OR repeatability[Title/Abstract])) AND (2026/08/08:2026/08/16[edat])"
      },
      {
        "name": "PubMed exact identifier verification",
        "search_string": "18348590[PMID] OR 26987118[PMID] OR 40134905[PMID] OR 27379951[PMID] OR 38324270[PMID]"
      },
      {
        "name": "PubMed Central",
        "search_string": "PMC4795745 OR PMC11933073"
      },
      {
        "name": "Crossref DOI API",
        "search_string": "GET /works/{doi} for 10.2165/00007256-200838040-00003, 10.1371/journal.pone.0151671, 10.3389/fspor.2025.1520914, 10.1519/JSC.0000000000001529, and 10.23736/S0022-4707.23.15619-2"
      }
    ]
  },
  "research_question": "Which field-test properties support using a running test as direct or supporting evidence of change across an adaptive training plan?",
  "review_notes": [
    "Verification: currell-2008 - abstract; PubMed PMID 18348590 and Crossref metadata; 2026-08-08.",
    "Verification: mayorga-vega-2016 - full-text; PubMed Central PMC4795745 and PubMed metadata; 2026-08-08.",
    "Verification: lipkova-2025 - full-text; PubMed Central PMC11933073 and PubMed metadata; 2026-08-08.",
    "Verification: nimmerichter-2017 - abstract; PubMed PMID 27379951 and Crossref metadata; 2026-08-08.",
    "Verification: benhammou-2024 - abstract; PubMed PMID 38324270 and DOI metadata; 2026-08-16.",
    "Currency check: the complete PubMed searches were rerun through 2026-08-16; no record newly indexed from 2026-08-08 through 2026-08-16 changed the reviewed boundary."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Laboratory cardiorespiratory fitness",
      "Race-like performance",
      "Alternative critical-speed models",
      "Repeated measurements under defined protocols"
    ],
    "intervention_or_exposure": [
      "Distance- and time-based walk/run tests",
      "Time trials and time-to-exhaustion tests",
      "Field-based critical-speed protocols",
      "Treadmill-derived critical-speed models"
    ],
    "outcomes": [
      "Validity",
      "Reliability",
      "Sensitivity to change",
      "Running-performance prediction"
    ],
    "population": [
      "Healthy adults and children in walk/run field-test validation research",
      "Trained adult runners in critical-speed research",
      "Recreational runners as the intended product population"
    ]
  },
  "supersedes": [],
  "title": "Running field tests for plan baselines and outcomes",
  "topic": "running-field-tests",
  "version": 1
}
```

</details>
