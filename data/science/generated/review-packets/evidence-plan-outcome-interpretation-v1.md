# Evidence review packet: Training-plan outcome interpretation

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-plan-outcome-interpretation-v1`
- **Lifecycle:** `draft`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:46026c614f9be03950e9e2d9f9e4bb6ef29d12f5882432105a5b522b7fb96956`
- **Required role:** `evidence_reviewer`
- **Approval:** _Pending_

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-plan-outcome-interpretation-v1`
- Digest: `sha256:46026c614f9be03950e9e2d9f9e4bb6ef29d12f5882432105a5b522b7fb96956`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:46026c614f9be03950e9e2d9f9e4bb6ef29d12f5882432105a5b522b7fb96956","subject_id":"evidence-plan-outcome-interpretation-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

What evidence supports combining performance, physiological, subjective, and execution observations when interpreting an individual training-plan outcome?

Bound post-plan review so Praxys separates observed outcome, plan execution, athlete context, and causal hypotheses rather than claiming to know why an individual did or did not achieve a goal.

## Scope

## Population

- Adult athletes in training-monitoring studies
- Adults in endurance, interval, and resistance exercise-response research
- Recreational runners as the intended product population

## Intervention or exposure

- Training load
- Subjective well-being monitoring
- Endurance and high-intensity interval training

## Comparator

- Subjective versus common objective monitoring measures
- VO2max versus other response indicators
- Different training modalities and intervention durations

## Outcomes

- Athlete well-being response
- Cardiorespiratory fitness response
- Heterogeneity of response indicators
- Causal-interpretation limits

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-08-16`

### Exact searches

- **PubMed**
  - `(athlete*[Title/Abstract] OR endurance[Title/Abstract]) AND ("training response"[Title/Abstract] OR adherence[Title/Abstract] OR "subjective measures"[Title/Abstract] OR "individual response"[Title/Abstract]) AND (monitoring[Title/Abstract] OR outcome*[Title/Abstract])`
- **PubMed currency window**
  - `((athlete*[Title/Abstract] OR endurance[Title/Abstract]) AND ("training response"[Title/Abstract] OR adherence[Title/Abstract] OR "subjective measures"[Title/Abstract] OR "individual response"[Title/Abstract]) AND (monitoring[Title/Abstract] OR outcome*[Title/Abstract])) AND (2026/08/08:2026/08/16[edat])`
- **PubMed exact identifier verification**
  - `26423706[PMID] OR 34301648[PMID]`
- **PubMed Central**
  - `PMC4789708 OR PMC8728353`
- **Crossref DOI API**
  - `GET /works/{doi} for 10.1136/bjsports-2015-094758 and 10.1136/bmjopen-2020-044676`

## Inclusion criteria

- Systematic reviews comparing athlete monitoring measures
- Systematic reviews or meta-analyses of exercise-response indicators
- Stable DOI or PMID metadata and an abstract or full text

## Exclusion criteria

- Single-factor causal explanations without a causal study design
- Diagnostic mental-health or medical screening instruments
- Vendor-generated readiness or adherence scores
- Coach opinion without empirical review

## Method limitations

- Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.
- Full text was available for both included sources; no inaccessible included source was used beyond its verified access level.
- The monitoring review spans sports and does not validate a Praxys questionnaire.
- Exercise-response evidence focuses strongly on VO2max and laboratory outcomes.
- No reviewed study validates a complete post-plan causal attribution framework.
- The 2026-08-08 through 2026-08-16 currency window returned four clinical, disease-specific, or nutrition-only records that did not match the intended healthy recreational-runner product population.

### Quality appraisal

Claims were appraised for review design, concurrent comparison of measures, heterogeneity, outcome specificity, causal identification, and directness to individual recreational-runner plan review. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/plan-outcome-interpretation/search-manifest-plan-outcome-interpretation-v1.json.

## Claims

### `outcome.subjective-monitoring-adds-signal` — moderate

Subjective self-reported well-being measures can detect training-related changes and may add information not captured by common objective measures.

- **Sources:** `saw-2016`
- **Population:** Athletes represented across the included monitoring studies
- **Domain:** Subjective monitoring; Training response
- **Limitations:**
  - Measures and sports were heterogeneous.
  - Subjective response does not establish the cause of a plan outcome.
  - The review does not validate sensitive free-text collection.
- **Verified effect estimates:**
  - Included concurrent monitoring studies: 56.0 studies (Systematic review of athlete well-being measures)

### `outcome.single-indicator-insufficient` — moderate

Exercise response is heterogeneous across indicators, modalities, and intervention durations, so one physiological indicator should not be treated as a complete account of an individual's plan outcome.

- **Sources:** `ardavani-2021`
- **Population:** Adults in endurance, interval, and resistance exercise studies
- **Domain:** Exercise response; Outcome triangulation
- **Limitations:**
  - Heterogeneity was ubiquitous across analyses.
  - Other indicators did not reach statistical significance in pooled analysis.
  - The review does not prescribe a product outcome framework.
- **Verified effect estimates:**
  - Studies in qualitative synthesis: 29.0 studies (Systematic review of exercise-response indicators)
  - Studies in quantitative synthesis: 22.0 studies (Meta-analysis of exercise-response indicators)

### `outcome.observations-not-causal-explanation` — low

Observed monitoring and response indicators describe what changed but do not, without an appropriate causal design, establish why one athlete achieved or missed a goal.

- **Sources:** `saw-2016`, `ardavani-2021`
- **Population:** Individual athletes whose plan review combines monitoring and response indicators
- **Domain:** Causal attribution; Plan review
- **Limitations:**
  - This is an epistemic boundary inferred from non-causal evidence.
  - A ranked hypothesis can guide future observation but is not a diagnosis.
  - Athlete-reported context may be relevant without proving causation.

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `saw-2016` | `full-text` | DOI `10.1136/bjsports-2015-094758` | Monitoring the athlete training response: subjective self-reported measures trump commonly used objective measures: a systematic review (2016) |
| `ardavani-2021` | `full-text` | DOI `10.1136/bmjopen-2020-044676` | Indicators of response to exercise training: a systematic review and meta-analysis (2021) |

## Known gaps

- Prospectively validated multidimensional outcome review for recreational runners
- Validated minimal subjective context with clear retention and deletion rules
- Causal evidence linking a specific adaptive decision to individual goal outcome
- Standard handling of censored outcomes caused by illness, injury, or life constraints

## Conflicting findings

- Subjective measures were more sensitive to training changes in one review, while objective response indicators remained heterogeneous and incompletely differentiated in another.

## Follow-up questions

- What smallest structured context vocabulary helps interpretation without inviting diagnosis?
- Which outcome hypotheses can be prospectively tested in later plans?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:github-copilot"
  ],
  "citations": [
    {
      "authors": [
        "A. E. Saw",
        "L. C. Main",
        "P. B. Gastin"
      ],
      "doi": "10.1136/bjsports-2015-094758",
      "id": "saw-2016",
      "journal": "British Journal of Sports Medicine",
      "pmid": "26423706",
      "title": "Monitoring the athlete training response: subjective self-reported measures trump commonly used objective measures: a systematic review",
      "url": null,
      "year": 2016
    },
    {
      "authors": [
        "A. Ardavani",
        "H. Aziz",
        "B. E. Phillips",
        "B. Doleman",
        "I. Ramzan",
        "B. Mozaffar",
        "P. J. Atherton",
        "I. Idris"
      ],
      "doi": "10.1136/bmjopen-2020-044676",
      "id": "ardavani-2021",
      "journal": "BMJ Open",
      "pmid": "34301648",
      "title": "Indicators of response to exercise training: a systematic review and meta-analysis",
      "url": null,
      "year": 2021
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Athletes represented across the included monitoring studies"
      ],
      "domain": [
        "Subjective monitoring",
        "Training response"
      ],
      "effect_estimates": [
        {
          "context": "Systematic review of athlete well-being measures",
          "estimate": 56.0,
          "metric": "Included concurrent monitoring studies",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        }
      ],
      "evidence_strength": "moderate",
      "id": "outcome.subjective-monitoring-adds-signal",
      "limitations": [
        "Measures and sports were heterogeneous.",
        "Subjective response does not establish the cause of a plan outcome.",
        "The review does not validate sensitive free-text collection."
      ],
      "source_ids": [
        "saw-2016"
      ],
      "statement": "Subjective self-reported well-being measures can detect training-related changes and may add information not captured by common objective measures."
    },
    {
      "applicable_population": [
        "Adults in endurance, interval, and resistance exercise studies"
      ],
      "domain": [
        "Exercise response",
        "Outcome triangulation"
      ],
      "effect_estimates": [
        {
          "context": "Systematic review of exercise-response indicators",
          "estimate": 29.0,
          "metric": "Studies in qualitative synthesis",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        },
        {
          "context": "Meta-analysis of exercise-response indicators",
          "estimate": 22.0,
          "metric": "Studies in quantitative synthesis",
          "range_high": null,
          "range_low": null,
          "unit": "studies"
        }
      ],
      "evidence_strength": "moderate",
      "id": "outcome.single-indicator-insufficient",
      "limitations": [
        "Heterogeneity was ubiquitous across analyses.",
        "Other indicators did not reach statistical significance in pooled analysis.",
        "The review does not prescribe a product outcome framework."
      ],
      "source_ids": [
        "ardavani-2021"
      ],
      "statement": "Exercise response is heterogeneous across indicators, modalities, and intervention durations, so one physiological indicator should not be treated as a complete account of an individual's plan outcome."
    },
    {
      "applicable_population": [
        "Individual athletes whose plan review combines monitoring and response indicators"
      ],
      "domain": [
        "Causal attribution",
        "Plan review"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "outcome.observations-not-causal-explanation",
      "limitations": [
        "This is an epistemic boundary inferred from non-causal evidence.",
        "A ranked hypothesis can guide future observation but is not a diagnosis.",
        "Athlete-reported context may be relevant without proving causation."
      ],
      "source_ids": [
        "saw-2016",
        "ardavani-2021"
      ],
      "statement": "Observed monitoring and response indicators describe what changed but do not, without an appropriate causal design, establish why one athlete achieved or missed a goal."
    }
  ],
  "conflicting_findings": [
    "Subjective measures were more sensitive to training changes in one review, while objective response indicators remained heterogeneous and incompletely differentiated in another."
  ],
  "created_on": "2026-08-08",
  "follow_up_questions": [
    "What smallest structured context vocabulary helps interpretation without inviting diagnosis?",
    "Which outcome hypotheses can be prospectively tested in later plans?"
  ],
  "id": "evidence-plan-outcome-interpretation-v1",
  "intended_product_purpose": "Bound post-plan review so Praxys separates observed outcome, plan execution, athlete context, and causal hypotheses rather than claiming to know why an individual did or did not achieve a goal.",
  "known_gaps": [
    "Prospectively validated multidimensional outcome review for recreational runners",
    "Validated minimal subjective context with clear retention and deletion rules",
    "Causal evidence linking a specific adaptive decision to individual goal outcome",
    "Standard handling of censored outcomes caused by illness, injury, or life constraints"
  ],
  "method": {
    "exclusion_criteria": [
      "Single-factor causal explanations without a causal study design",
      "Diagnostic mental-health or medical screening instruments",
      "Vendor-generated readiness or adherence scores",
      "Coach opinion without empirical review"
    ],
    "inclusion_criteria": [
      "Systematic reviews comparing athlete monitoring measures",
      "Systematic reviews or meta-analyses of exercise-response indicators",
      "Stable DOI or PMID metadata and an abstract or full text"
    ],
    "method_limitations": [
      "Titles and abstracts were manually screened against the criteria; screening and appraisal were not duplicated by independent reviewers.",
      "Full text was available for both included sources; no inaccessible included source was used beyond its verified access level.",
      "The monitoring review spans sports and does not validate a Praxys questionnaire.",
      "Exercise-response evidence focuses strongly on VO2max and laboratory outcomes.",
      "No reviewed study validates a complete post-plan causal attribution framework.",
      "The 2026-08-08 through 2026-08-16 currency window returned four clinical, disease-specific, or nutrition-only records that did not match the intended healthy recreational-runner product population."
    ],
    "quality_appraisal": "Claims were appraised for review design, concurrent comparison of measures, heterogeneity, outcome specificity, causal identification, and directness to individual recreational-runner plan review. The complete PubMed result sets, digests, and inclusion decisions are bound in data/science/evidence/plan-outcome-interpretation/search-manifest-plan-outcome-interpretation-v1.json.",
    "review_type": "rigorous",
    "search_date": "2026-08-16",
    "sources": [
      {
        "name": "PubMed",
        "search_string": "(athlete*[Title/Abstract] OR endurance[Title/Abstract]) AND (\"training response\"[Title/Abstract] OR adherence[Title/Abstract] OR \"subjective measures\"[Title/Abstract] OR \"individual response\"[Title/Abstract]) AND (monitoring[Title/Abstract] OR outcome*[Title/Abstract])"
      },
      {
        "name": "PubMed currency window",
        "search_string": "((athlete*[Title/Abstract] OR endurance[Title/Abstract]) AND (\"training response\"[Title/Abstract] OR adherence[Title/Abstract] OR \"subjective measures\"[Title/Abstract] OR \"individual response\"[Title/Abstract]) AND (monitoring[Title/Abstract] OR outcome*[Title/Abstract])) AND (2026/08/08:2026/08/16[edat])"
      },
      {
        "name": "PubMed exact identifier verification",
        "search_string": "26423706[PMID] OR 34301648[PMID]"
      },
      {
        "name": "PubMed Central",
        "search_string": "PMC4789708 OR PMC8728353"
      },
      {
        "name": "Crossref DOI API",
        "search_string": "GET /works/{doi} for 10.1136/bjsports-2015-094758 and 10.1136/bmjopen-2020-044676"
      }
    ]
  },
  "research_question": "What evidence supports combining performance, physiological, subjective, and execution observations when interpreting an individual training-plan outcome?",
  "review_notes": [
    "Verification: saw-2016 - full-text; PubMed Central PMC4789708 and PubMed metadata; 2026-08-08.",
    "Verification: ardavani-2021 - full-text; PubMed Central PMC8728353 and PubMed metadata; 2026-08-08.",
    "Currency check: four records newly indexed from 2026-08-08 through 2026-08-16 were screened and excluded as clinical, disease-specific, or nutrition-only evidence; none changed the plan-outcome claim boundary.",
    "Execution adherence is an exposure record, not evidence that adaptation occurred or that the plan caused the result."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Subjective versus common objective monitoring measures",
      "VO2max versus other response indicators",
      "Different training modalities and intervention durations"
    ],
    "intervention_or_exposure": [
      "Training load",
      "Subjective well-being monitoring",
      "Endurance and high-intensity interval training"
    ],
    "outcomes": [
      "Athlete well-being response",
      "Cardiorespiratory fitness response",
      "Heterogeneity of response indicators",
      "Causal-interpretation limits"
    ],
    "population": [
      "Adult athletes in training-monitoring studies",
      "Adults in endurance, interval, and resistance exercise-response research",
      "Recreational runners as the intended product population"
    ]
  },
  "supersedes": [],
  "title": "Training-plan outcome interpretation",
  "topic": "plan-outcome-interpretation",
  "version": 1
}
```

</details>
