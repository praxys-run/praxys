# Evidence review packet: Adaptive endurance-training load decisions

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-adaptive-training-load-v1`
- **Lifecycle:** `draft`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:101f9e5b3a9eeed9d8777d0cef8cf56f332372568fed32ba812c4f969551d50f`
- **Required role:** `evidence_reviewer`
- **Approval:** _Pending_

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-adaptive-training-load-v1`
- Digest: `sha256:101f9e5b3a9eeed9d8777d0cef8cf56f332372568fed32ba812c4f969551d50f`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:101f9e5b3a9eeed9d8777d0cef8cf56f332372568fed32ba812c4f969551d50f","subject_id":"evidence-adaptive-training-load-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

What evidence supports structured or monitoring-guided endurance-training adjustment, and what limits apply to fixed progression, workload-ratio, and missed-session rules?

Bound when Praxys may use training structure, HRV, subjective monitoring, and repeated execution evidence to propose a change without turning common coaching rules into universal safety laws.

## Scope

## Population

- Adult recreational runners
- Healthy adults in endurance-training studies
- Novice runners in injury-progression research

## Intervention or exposure

- Structured endurance training
- HRV-guided endurance training
- Graded running progression
- Acute-to-chronic workload ratio interpretation
- Missed-session rescheduling and catch-up rules

## Comparator

- Predefined endurance training
- Alternative intensity distributions
- Standard versus graded novice-running progression
- Causal versus associational workload interpretation

## Outcomes

- Endurance performance
- Submaximal physiological response
- Running-related injury
- Validity of automatic adjustment rules

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-08-16`

### Exact searches

- **PubMed**
  - `(running[Title/Abstract] OR endurance[Title/Abstract]) AND (periodization[Title/Abstract] OR progression[Title/Abstract] OR "heart rate variability guided"[Title/Abstract] OR "acute chronic workload"[Title/Abstract] OR "10% rule"[Title/Abstract]) AND adult[MeSH Terms]`
- **PubMed currency window**
  - `((running[Title/Abstract] OR endurance[Title/Abstract]) AND (periodization[Title/Abstract] OR progression[Title/Abstract] OR "heart rate variability guided"[Title/Abstract] OR "acute chronic workload"[Title/Abstract] OR "10% rule"[Title/Abstract])) AND (2026/08/08:2026/08/16[edat])`
- **PubMed missed-session rule search**
  - `((running[Title/Abstract] OR endurance[Title/Abstract]) AND (missed[Title/Abstract] AND (workout*[Title/Abstract] OR "training session"[Title/Abstract] OR "training sessions"[Title/Abstract])) AND (doubl*[Title/Abstract] OR compress*[Title/Abstract] OR replac*[Title/Abstract] OR reschedul*[Title/Abstract] OR "catch-up"[Title/Abstract] OR "make-up"[Title/Abstract]))`
- **PubMed exact identifier verification**
  - `34489178[PMID] OR 23752040[PMID] OR 17940147[PMID] OR 32502973[PMID]`
- **Crossref DOI API**
  - `GET /works/{doi} for 10.1016/j.jsams.2021.04.012, 10.1123/ijspp.2012-0350, 10.1177/0363546507307505, and 10.1123/ijspp.2019-0864`

## Inclusion criteria

- Adult endurance-training systematic reviews, meta-analyses, or controlled studies
- Novice-running randomized progression studies
- Methodological analysis of workload-derived decisions
- Studies directly evaluating how a missed running or endurance-training session should be rescheduled, compressed, doubled, or replaced
- Stable DOI or PMID metadata and an abstract

## Exclusion criteria

- Team-sport associations presented as direct running prescriptions
- Unvalidated coaching progression rules
- Studies that do not distinguish monitoring from a prescribed action
- Medical injury treatment or rehabilitation protocols

## Method limitations

- Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.
- The missed-session search was limited to PubMed title and abstract terms and found no eligible training-adjustment study.
- Full text was not accessed for the four included sources, so claims are restricted to abstract-supported results and limitations.
- Periodization evidence is heterogeneous and not exhaustively reviewed here.
- HRV studies use different devices, protocols, and decision algorithms.
- No reviewed study validates Praxys-specific workout, week, or block triggers.

### Quality appraisal

Claims were appraised for randomization, directness to recreational runners, sample size, monitoring protocol, action-rule transparency, causal identification, and whether performance and safety outcomes were distinguished. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/adaptive-training-load/search-manifest-adaptive-training-load-v1.json.

## Claims

### `load.structured-training-bounded-benefit` — low

Structured endurance training can improve recreational-running performance, but the reviewed evidence does not establish one universally superior intensity distribution or periodization model.

- **Sources:** `munoz-2014`
- **Population:** Recreational adult runners similar to the small controlled study
- **Domain:** Endurance-training structure; Performance
- **Limitations:**
  - The primary between-group performance difference was not significant.
  - A favorable polarized result came from a smaller adherence-defined subset.
  - One study cannot define an adaptive plan policy.

### `load.hrv-guidance-limited` — moderate

HRV-guided endurance training may improve some submaximal physiological outcomes, but reviewed pooled evidence did not establish a significant performance or VO2peak advantage over predefined training.

- **Sources:** `ducking-2021`
- **Population:** Adults in HRV-guided endurance-training studies
- **Domain:** HRV-guided training; Adaptive monitoring
- **Limitations:**
  - Only eight studies and 198 participants were included.
  - Devices, measurement routines, and training algorithms varied.
  - Results do not validate a universal daily HRV cutoff or exact action.
- **Verified effect estimates:**
  - Submaximal physiological outcome effect: 0.296 Hedges g (8 studies, 198 participants; 95% CI 0.031 to 0.562)
  - Performance outcome effect: 0.079 Hedges g (Pooled effect was not statistically significant)

### `load.ten-percent-rule-not-safety-law` — moderate

A progression program based on the 10 percent rule did not reduce running-related injury compared with a standard program in the reviewed novice-runner randomized trial.

- **Sources:** `buist-2008`
- **Population:** Novice adult runners similar to the randomized cohort
- **Domain:** Training progression; Injury prevention
- **Limitations:**
  - This does not show that every faster progression is safe.
  - Injury outcome evidence does not determine optimal performance progression.
- **Verified effect estimates:**
  - Running-related injury incidence: 20.3 to 20.8 percent (Standard versus graded 13-week novice-running programs; p=0.90)

### `load.acwr-not-causal-threshold` — moderate

Acute-to-chronic workload ratios have conceptual and statistical limitations and should not be treated as established causal injury-risk zones or automatic prescription thresholds.

- **Sources:** `impellizzeri-2020`
- **Population:** Athletic workload-monitoring populations
- **Domain:** Workload monitoring; Causal inference
- **Limitations:**
  - This methodological critique does not show that training history is irrelevant.
  - It does not validate an alternative universal load threshold.

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `munoz-2014` | `abstract` | DOI `10.1123/ijspp.2012-0350` | Does polarized training improve performance in recreational runners? (2014) |
| `ducking-2021` | `abstract` | DOI `10.1016/j.jsams.2021.04.012` | Monitoring and adapting endurance training on the basis of heart rate variability monitored by wearable technologies: A systematic review with meta-analysis (2021) |
| `buist-2008` | `abstract` | DOI `10.1177/0363546507307505` | No effect of a graded training program on the number of running-related injuries in novice runners: a randomized controlled trial (2008) |
| `impellizzeri-2020` | `abstract` | DOI `10.1123/ijspp.2019-0864` | Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls (2020) |

## Known gaps

- Evidence-based rules for rescheduling or making up missed workouts
- Exact workout, week, block, goal, or pause triggers
- Representative trials in recreational runners using one stable adaptive policy
- Joint interpretation of HRV, subjective context, performance, and plan execution

## Conflicting findings

- HRV-guided training showed a pooled submaximal effect but no significant pooled performance or VO2peak advantage.
- Small endurance studies differ on which training-intensity distribution performs best.

## Follow-up questions

- Which narrow suggestion-only policy should be tested prospectively first?
- How should no-change behavior be compared with adaptive proposals?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:github-copilot"
  ],
  "citations": [
    {
      "authors": [
        "I. Munoz",
        "S. Seiler",
        "J. Bautista",
        "J. Espana",
        "E. Larumbe",
        "J. Esteve-Lanao"
      ],
      "doi": "10.1123/ijspp.2012-0350",
      "id": "munoz-2014",
      "journal": "International Journal of Sports Physiology and Performance",
      "pmid": "23752040",
      "title": "Does polarized training improve performance in recreational runners?",
      "url": null,
      "year": 2014
    },
    {
      "authors": [
        "P. Düking",
        "C. Zinner",
        "K. Trabelsi",
        "J. L. Reed",
        "H. C. Holmberg",
        "P. Kunz",
        "B. Sperlich"
      ],
      "doi": "10.1016/j.jsams.2021.04.012",
      "id": "ducking-2021",
      "journal": "Journal of Science and Medicine in Sport",
      "pmid": "34489178",
      "title": "Monitoring and adapting endurance training on the basis of heart rate variability monitored by wearable technologies: A systematic review with meta-analysis",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "I. Buist",
        "S. W. Bredeweg",
        "W. van Mechelen",
        "K. A. P. M. Lemmink",
        "G. J. Pepping",
        "R. L. Diercks"
      ],
      "doi": "10.1177/0363546507307505",
      "id": "buist-2008",
      "journal": "The American Journal of Sports Medicine",
      "pmid": "17940147",
      "title": "No effect of a graded training program on the number of running-related injuries in novice runners: a randomized controlled trial",
      "url": null,
      "year": 2008
    },
    {
      "authors": [
        "F. M. Impellizzeri",
        "M. S. Tenan",
        "T. Kempton",
        "A. Novak",
        "A. J. Coutts"
      ],
      "doi": "10.1123/ijspp.2019-0864",
      "id": "impellizzeri-2020",
      "journal": "International Journal of Sports Physiology and Performance",
      "pmid": "32502973",
      "title": "Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls",
      "url": null,
      "year": 2020
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Recreational adult runners similar to the small controlled study"
      ],
      "domain": [
        "Endurance-training structure",
        "Performance"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "load.structured-training-bounded-benefit",
      "limitations": [
        "The primary between-group performance difference was not significant.",
        "A favorable polarized result came from a smaller adherence-defined subset.",
        "One study cannot define an adaptive plan policy."
      ],
      "source_ids": [
        "munoz-2014"
      ],
      "statement": "Structured endurance training can improve recreational-running performance, but the reviewed evidence does not establish one universally superior intensity distribution or periodization model."
    },
    {
      "applicable_population": [
        "Adults in HRV-guided endurance-training studies"
      ],
      "domain": [
        "HRV-guided training",
        "Adaptive monitoring"
      ],
      "effect_estimates": [
        {
          "context": "8 studies, 198 participants; 95% CI 0.031 to 0.562",
          "estimate": 0.296,
          "metric": "Submaximal physiological outcome effect",
          "range_high": null,
          "range_low": null,
          "unit": "Hedges g"
        },
        {
          "context": "Pooled effect was not statistically significant",
          "estimate": 0.079,
          "metric": "Performance outcome effect",
          "range_high": null,
          "range_low": null,
          "unit": "Hedges g"
        }
      ],
      "evidence_strength": "moderate",
      "id": "load.hrv-guidance-limited",
      "limitations": [
        "Only eight studies and 198 participants were included.",
        "Devices, measurement routines, and training algorithms varied.",
        "Results do not validate a universal daily HRV cutoff or exact action."
      ],
      "source_ids": [
        "ducking-2021"
      ],
      "statement": "HRV-guided endurance training may improve some submaximal physiological outcomes, but reviewed pooled evidence did not establish a significant performance or VO2peak advantage over predefined training."
    },
    {
      "applicable_population": [
        "Novice adult runners similar to the randomized cohort"
      ],
      "domain": [
        "Training progression",
        "Injury prevention"
      ],
      "effect_estimates": [
        {
          "context": "Standard versus graded 13-week novice-running programs; p=0.90",
          "estimate": null,
          "metric": "Running-related injury incidence",
          "range_high": 20.8,
          "range_low": 20.3,
          "unit": "percent"
        }
      ],
      "evidence_strength": "moderate",
      "id": "load.ten-percent-rule-not-safety-law",
      "limitations": [
        "This does not show that every faster progression is safe.",
        "Injury outcome evidence does not determine optimal performance progression."
      ],
      "source_ids": [
        "buist-2008"
      ],
      "statement": "A progression program based on the 10 percent rule did not reduce running-related injury compared with a standard program in the reviewed novice-runner randomized trial."
    },
    {
      "applicable_population": [
        "Athletic workload-monitoring populations"
      ],
      "domain": [
        "Workload monitoring",
        "Causal inference"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "load.acwr-not-causal-threshold",
      "limitations": [
        "This methodological critique does not show that training history is irrelevant.",
        "It does not validate an alternative universal load threshold."
      ],
      "source_ids": [
        "impellizzeri-2020"
      ],
      "statement": "Acute-to-chronic workload ratios have conceptual and statistical limitations and should not be treated as established causal injury-risk zones or automatic prescription thresholds."
    }
  ],
  "conflicting_findings": [
    "HRV-guided training showed a pooled submaximal effect but no significant pooled performance or VO2peak advantage.",
    "Small endurance studies differ on which training-intensity distribution performs best."
  ],
  "created_on": "2026-08-08",
  "follow_up_questions": [
    "Which narrow suggestion-only policy should be tested prospectively first?",
    "How should no-change behavior be compared with adaptive proposals?"
  ],
  "id": "evidence-adaptive-training-load-v1",
  "intended_product_purpose": "Bound when Praxys may use training structure, HRV, subjective monitoring, and repeated execution evidence to propose a change without turning common coaching rules into universal safety laws.",
  "known_gaps": [
    "Evidence-based rules for rescheduling or making up missed workouts",
    "Exact workout, week, block, goal, or pause triggers",
    "Representative trials in recreational runners using one stable adaptive policy",
    "Joint interpretation of HRV, subjective context, performance, and plan execution"
  ],
  "method": {
    "exclusion_criteria": [
      "Team-sport associations presented as direct running prescriptions",
      "Unvalidated coaching progression rules",
      "Studies that do not distinguish monitoring from a prescribed action",
      "Medical injury treatment or rehabilitation protocols"
    ],
    "inclusion_criteria": [
      "Adult endurance-training systematic reviews, meta-analyses, or controlled studies",
      "Novice-running randomized progression studies",
      "Methodological analysis of workload-derived decisions",
      "Studies directly evaluating how a missed running or endurance-training session should be rescheduled, compressed, doubled, or replaced",
      "Stable DOI or PMID metadata and an abstract"
    ],
    "method_limitations": [
      "Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.",
      "The missed-session search was limited to PubMed title and abstract terms and found no eligible training-adjustment study.",
      "Full text was not accessed for the four included sources, so claims are restricted to abstract-supported results and limitations.",
      "Periodization evidence is heterogeneous and not exhaustively reviewed here.",
      "HRV studies use different devices, protocols, and decision algorithms.",
      "No reviewed study validates Praxys-specific workout, week, or block triggers."
    ],
    "quality_appraisal": "Claims were appraised for randomization, directness to recreational runners, sample size, monitoring protocol, action-rule transparency, causal identification, and whether performance and safety outcomes were distinguished. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/adaptive-training-load/search-manifest-adaptive-training-load-v1.json.",
    "review_type": "rigorous",
    "search_date": "2026-08-16",
    "sources": [
      {
        "name": "PubMed",
        "search_string": "(running[Title/Abstract] OR endurance[Title/Abstract]) AND (periodization[Title/Abstract] OR progression[Title/Abstract] OR \"heart rate variability guided\"[Title/Abstract] OR \"acute chronic workload\"[Title/Abstract] OR \"10% rule\"[Title/Abstract]) AND adult[MeSH Terms]"
      },
      {
        "name": "PubMed currency window",
        "search_string": "((running[Title/Abstract] OR endurance[Title/Abstract]) AND (periodization[Title/Abstract] OR progression[Title/Abstract] OR \"heart rate variability guided\"[Title/Abstract] OR \"acute chronic workload\"[Title/Abstract] OR \"10% rule\"[Title/Abstract])) AND (2026/08/08:2026/08/16[edat])"
      },
      {
        "name": "PubMed missed-session rule search",
        "search_string": "((running[Title/Abstract] OR endurance[Title/Abstract]) AND (missed[Title/Abstract] AND (workout*[Title/Abstract] OR \"training session\"[Title/Abstract] OR \"training sessions\"[Title/Abstract])) AND (doubl*[Title/Abstract] OR compress*[Title/Abstract] OR replac*[Title/Abstract] OR reschedul*[Title/Abstract] OR \"catch-up\"[Title/Abstract] OR \"make-up\"[Title/Abstract]))"
      },
      {
        "name": "PubMed exact identifier verification",
        "search_string": "34489178[PMID] OR 23752040[PMID] OR 17940147[PMID] OR 32502973[PMID]"
      },
      {
        "name": "Crossref DOI API",
        "search_string": "GET /works/{doi} for 10.1016/j.jsams.2021.04.012, 10.1123/ijspp.2012-0350, 10.1177/0363546507307505, and 10.1123/ijspp.2019-0864"
      }
    ]
  },
  "research_question": "What evidence supports structured or monitoring-guided endurance-training adjustment, and what limits apply to fixed progression, workload-ratio, and missed-session rules?",
  "review_notes": [
    "Verification: munoz-2014 - abstract; PubMed PMID 23752040 and Crossref metadata; 2026-08-08.",
    "Verification: ducking-2021 - abstract; PubMed PMID 34489178 and Crossref metadata; 2026-08-08.",
    "Verification: buist-2008 - abstract; PubMed PMID 17940147 and Crossref metadata; 2026-08-08.",
    "Verification: impellizzeri-2020 - abstract; PubMed PMID 32502973 and Crossref metadata; 2026-08-08.",
    "Currency check: a title/abstract query without the Adult MeSH indexing requirement found PMIDs 42596196, 42577566, 42572667, and 42568394 newly indexed from 2026-08-08 through 2026-08-16; physics, cirrhosis, knee-osteoarthritis review, and oncology scope respectively excluded them from the adaptive action-rule evidence.",
    "Missed-session rule search: PMID 30380356 was excluded because it evaluated yeast beta-glucan and cold/flu symptom days after intense exercise, not rescheduling, compression, doubling, or replacement of a missed training session; no eligible source validated an automatic catch-up rule."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Predefined endurance training",
      "Alternative intensity distributions",
      "Standard versus graded novice-running progression",
      "Causal versus associational workload interpretation"
    ],
    "intervention_or_exposure": [
      "Structured endurance training",
      "HRV-guided endurance training",
      "Graded running progression",
      "Acute-to-chronic workload ratio interpretation",
      "Missed-session rescheduling and catch-up rules"
    ],
    "outcomes": [
      "Endurance performance",
      "Submaximal physiological response",
      "Running-related injury",
      "Validity of automatic adjustment rules"
    ],
    "population": [
      "Adult recreational runners",
      "Healthy adults in endurance-training studies",
      "Novice runners in injury-progression research"
    ]
  },
  "supersedes": [],
  "title": "Adaptive endurance-training load decisions",
  "topic": "adaptive-training-load",
  "version": 1
}
```

</details>
