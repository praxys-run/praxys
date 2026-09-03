# Evidence review packet: History-rich adult non-ultra trail-running plan generation

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Lifecycle:** `accepted`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:51e9349704d969b6524b947311a04e585477cffd7071254a9d2859690d87d78e`
- **Required role:** `evidence_reviewer`
- **Approval:** `github:dddtc2005` on `2026-09-03` ([source](https://github.com/praxys-run/praxys/pull/759#issuecomment-5527638619))

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-non-ultra-trail-plan-generation-policy-v1`
- Digest: `sha256:51e9349704d969b6524b947311a04e585477cffd7071254a9d2859690d87d78e`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:51e9349704d969b6524b947311a04e585477cffd7071254a9d2859690d87d78e","subject_id":"evidence-non-ultra-trail-plan-generation-policy-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

For nonclinical adults with recent, comparable running and trail exposure who are preparing for a single-day non-ultra trail event described by trail_course_demand_v1, what evidence supports and limits a deterministic, suggestion-only, history-anchored plan policy covering terrain specificity, uphill and downhill exposure, intensity, strength, long sessions, taper, fueling practice, reassessment, and typed unavailable outcomes?

Establish whether Praxys may offer one bounded, history-rich non-ultra trail performance policy without copying a road schedule or inventing a universal distance/elevation conversion. Separate published findings from reversible Praxys guardrails, preserve course and athlete unknowns, and identify every unresolved dose, taper, progression, intensity, and rollout decision. The review does not itself authorize implementation or runtime activation.

## Scope

## Population

- Adults aged 18 years or older with recent stable running history
- Adults with recent terrain, ascent, and descent exposure comparable enough for a reviewed capability match
- Single-day non-ultra trail performance intent
- Nonclinical planning only

## Intervention or exposure

- Trail-specific and mixed-terrain running practice
- Uphill, downhill, level, hiking, strength, and multimodal training
- History-anchored volume, duration, frequency, and terrain exposure
- General endurance taper and duration-dependent fueling practice

## Comparator

- Trail versus road training
- Uphill versus downhill versus level demand
- Different trail distances and course profiles
- Strength, high-intensity, and combined training
- Tapered versus maintained endurance load

## Outcomes

- Trail performance and course-specific readiness
- Neuromuscular, mechanical, metabolic, and cardiovascular response
- Injury and fatigue observations
- Proposal availability, uncertainty, and post-plan evaluation

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-09-01`

### Exact searches

- **Europe PMC and PubMed - trail policy exact records**
  - `33508776[PMID] OR 35213820[PMID] OR 31114511[PMID] OR 36901510[PMID] OR 35022162[PMID] OR 33538997[PMID] OR 33191845[PMID] OR 34853187[PMID] OR 27396389[PMID] OR 33266272[PMID] OR 41718076[PMID] OR 42479880[PMID]`
- **PubMed Central full text**
  - `PMC6503082 OR PMC10002259 OR PMC7730662 OR PMC12921809`
- **Europe PMC and PubMed - taper and fueling transfer**
  - `37163550[PMID] OR 21660838[PMID] OR 37061651[PMID]`
- **Europe PMC trail training discovery**
  - `(trail running OR mountain running) AND (training intervention OR periodization OR taper OR strength OR downhill OR uphill OR fueling) AND adult`

## Inclusion criteria

- Adult human trail-running performance, training, fatigue, or injury evidence
- Direct trail studies preferred; broader endurance evidence labelled indirect
- Systematic reviews, controlled studies, observational cohorts, and authoritative guidance with stable identifiers
- Numeric findings used only at their verified access level and study context

## Exclusion criteria

- Ultra or multi-day findings converted directly into a non-ultra schedule
- Road-plan percentages or distance-only policies reused as trail prescriptions
- Clinical, rehabilitation, pregnancy-specific, pediatric, or return-to-sport prescription
- Coaching templates, blogs, vendor content, and unverified search snippets

## Method limitations

- Screening and extraction were not independently duplicated by human reviewers.
- SPORTDiscus, Scopus, Embase, and Web of Science were not independently searched in this run.
- Several direct trail records were available only as indexed abstracts.
- Direct non-ultra intervention evidence is sparse, heterogeneous, and often male-heavy.
- No reviewed source validates a complete deterministic trail plan, safe progression law, or personal finish probability.

### Quality appraisal

Evidence was appraised for directness to history-rich adult non-ultra trail runners, course comparability, intervention design, sample size, sex and age representation, terrain realism, confounding, and whether a finding supports a directional module or an exact personal dose. Direct training intervention evidence is sparse and small. Injury and race-fatigue evidence is mainly observational. General taper and fueling evidence is more mature but indirect and cannot choose trail-specific values by itself.

## Claims

### `non-ultra-trail.course-specific-policy-required` — moderate

Trail performance and training demand are course-specific and multifactorial. A policy must match an explicit course-demand vector and comparable exposure rather than distance, level pace, or one physiological marker alone.

- **Sources:** `de-waal-2021-performance-review`, `pastor-2022-distance-determinants`, `bjorklund-2019-short-trail`
- **Population:** Adult trail runners represented by the systematic review and direct studies
- **Domain:** Capability matching; Course specificity
- **Limitations:**
  - Associations and prediction models do not establish causal training dose.
  - The reviewed courses and populations are heterogeneous.

### `non-ultra-trail.uphill-downhill-require-distinct-handling` — moderate

Uphill and downhill running have materially different metabolic, mechanical, cardiovascular, and neuromuscular profiles. Training history and proposed exposure should therefore preserve ascent, descent, grade, and technical context separately.

- **Sources:** `bjorklund-2019-short-trail`, `lemire-2021-downhill-fatigue`, `lemire-2022-slope-energy-cost`
- **Population:** Adult trained trail runners in short field and laboratory studies
- **Domain:** Uphill exposure; Downhill exposure; Fatigue and mechanics
- **Limitations:**
  - Small studies at specific grades do not establish universal progression.
  - Comparable oxygen uptake does not imply comparable mechanical cost.

### `non-ultra-trail.hr-and-road-pace-not-sole-targets` — low

Heart rate can lag or fail to reflect rapid slope-dependent changes, and level-running pace does not preserve trail mechanical demand. Neither should be the sole driver of a hilly or technical prescription.

- **Sources:** `born-2017-hilly-intensity`, `lemire-2022-slope-energy-cost`
- **Population:** Competitive and well-trained adult trail runners in small hilly protocols
- **Domain:** Intensity interpretation; Workout targets
- **Limitations:**
  - This does not prohibit contextual athlete-specific HR or pace use.
  - No reviewed evidence validates one universal trail RPE, power, HR, or pace equivalence.

### `non-ultra-trail.training-specificity-promising-not-prescriptive` — low

Trail-specific and multimodal training can be plausible modules, but the reviewed interventions are too small and heterogeneous to establish a universal session mix, weekly frequency, vertical dose, or superiority over road training.

- **Sources:** `drum-2023-trail-road-rct`, `panthong-2026-masters-training`
- **Population:** Sedentary adult novices in one small trail-versus-road trial; Masters trail runners aged 35 to 55 in one 12-week trial
- **Domain:** Terrain specificity; Strength and high-intensity modules
- **Limitations:**
  - The trail-versus-road study found no significant group-by-time interactions.
  - The masters trial does not define a universal plan or transfer to every age and course.

### `non-ultra-trail.injury-fatigue-no-safe-dose` — low

Trail racing is associated with heterogeneous injury, illness, muscular, and neuromuscular stress observations, but current evidence does not establish a universal injury-preventive plan, safe downhill dose, recovery interval, or progression percentage.

- **Sources:** `viljoen-2022-risk-factors`, `garcia-valiente-2026-damage-review`
- **Population:** Trail runners across heterogeneous race and observational studies
- **Domain:** Safety guardrails; Downhill and recovery uncertainty
- **Limitations:**
  - Associations do not establish causality or individual safety.
  - Race biomarkers cannot be converted into medical clearance or training readiness.

### `non-ultra-trail.observed-load-does-not-prove-prescription` — very_low

Observed trail workload and pacing associations may inform descriptive context, but they do not validate ACWR zones, fixed taper behavior, activity-average-power intensity, or an individual causal prescription.

- **Sources:** `matos-2020-load-profiles`
- **Population:** Recreational male trail runners in one observational season
- **Domain:** Training history; Load interpretation
- **Limitations:**
  - Small observational male sample and heterogeneous events.
  - Correlation and group averages do not select individual dose.

### `non-ultra-trail.taper-direction-indirect` — moderate

Broader endurance evidence supports a pre-event reduction in training volume while generally retaining intensity and frequency, but it does not validate one trail-specific taper duration, reduction percentage, or personal performance gain.

- **Sources:** `wang-2023`
- **Population:** Endurance athletes, indirectly applicable to non-ultra trail runners
- **Domain:** Taper; Event preparation
- **Limitations:**
  - Mixed sports and protocols rather than direct non-ultra trail trials.
  - Subgroup estimates cannot be treated as an individual optimum.

### `non-ultra-trail.fueling-duration-and-practice-context` — moderate

During-exercise carbohydrate strategy depends on expected duration and tolerance, and practice can reduce gastrointestinal problems in some endurance contexts. Distance alone does not select a fueling prescription.

- **Sources:** `burke-2011`, `martinez-2023`
- **Population:** Adult endurance athletes, indirectly including trail runners
- **Domain:** Fueling practice; Expected duration
- **Limitations:**
  - Numeric guidance is not trail-course specific.
  - Practice does not guarantee tolerance or performance for an individual.

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `de-waal-2021-performance-review` | `abstract` | DOI `10.1123/ijspp.2020-0812` | Physiological Indicators of Trail Running Performance: A Systematic Review (2021) |
| `pastor-2022-distance-determinants` | `abstract` | DOI `10.1123/ijspp.2021-0362` | Performance Determinants in Trail-Running Races of Different Distances (2022) |
| `bjorklund-2019-short-trail` | `full-text` | DOI `10.3389/fphys.2019.00506` | Biomechanical Adaptations and Performance Indicators in Short Trail Running (2019) |
| `born-2017-hilly-intensity` | `abstract` | DOI `10.1123/ijspp.2016-0101` | Near-Infrared Spectroscopy: More Accurate Than Heart Rate for Monitoring Intensity in Running in Hilly Terrain (2017) |
| `lemire-2021-downhill-fatigue` | `abstract` | DOI `10.1080/02640414.2020.1847502` | High-intensity downhill running exacerbates heart rate and muscular fatigue in trail runners (2021) |
| `lemire-2022-slope-energy-cost` | `abstract` | DOI `10.1123/ijspp.2021-0047` | Energy Cost of Running in Well-Trained Athletes: Toward Slope-Dependent Factors (2022) |
| `drum-2023-trail-road-rct` | `full-text` | DOI `10.3390/ijerph20054501` | Effects of Trail Running versus Road Running-Effects on Neuromuscular and Endurance Performance-A Two Arm Randomized Controlled Study (2023) |
| `panthong-2026-masters-training` | `abstract` | DOI `10.1519/JSC.0000000000005622` | Comparative Effects of Circuit Training, High-Intensity Interval Training, and Combined Training on Performance and Neuromuscular Function in Masters Trail Runners (2026) |
| `viljoen-2022-risk-factors` | `abstract` | DOI `10.1136/bjsports-2021-104858` | Trail running injury risk factors: a living systematic review (2022) |
| `garcia-valiente-2026-damage-review` | `full-text` | DOI `10.3390/muscles5010009` | Muscle, Neuromuscular, and Cardiac Damage in Trail Running: A Systematic Review (2026) |
| `matos-2020-load-profiles` | `full-text` | DOI `10.3390/ijerph17238902` | Performance and Training Load Profiles in Recreational Male Trail Runners: Analyzing Their Interactions during Competitions (2020) |
| `wang-2023` | `full-text` | DOI `10.1371/journal.pone.0282838` | Effects of tapering on performance in endurance athletes: A systematic review and meta-analysis (2023) |
| `burke-2011` | `abstract` | DOI `10.1080/02640414.2011.585473` | Carbohydrates for training and competition (2011) |
| `martinez-2023` | `full-text` | DOI `10.1007/s40279-023-01841-0` | The Effect of Gut-Training and Feeding-Challenge on Markers of Gastrointestinal Status in Response to Endurance Exercise: A Systematic Literature Review (2023) |

## Known gaps

- A prospectively evaluated deterministic non-ultra trail plan policy
- A validated comparable-history and course-demand matching threshold
- Safe vertical, downhill, technical-terrain, long-session, and weekly progression values
- Direct trail-specific taper duration and reduction values
- Universal HR, pace, power, RPE, hiking, or terrain-substitution equivalences
- Adequate female, older, diverse, and different-access subgroup evidence

## Conflicting findings

- Trail determinants differ by course distance and profile, preventing one universal predictor or plan.
- Small intervention studies suggest possible benefits without establishing one superior training mix.
- Lower metabolic cost downhill can coexist with greater peak force and neuromuscular fatigue.
- General endurance taper and fueling findings are directionally relevant but not trail-specific prescriptions.

## Follow-up questions

- Which exact history window and comparability rules should qualify a bounded policy?
- Which conservative session mix can be piloted without claiming biological optimality?
- How should inaccessible terrain produce alternatives without pretending road running is equivalent?
- Which taper, fueling-practice, and reassessment values are acceptable reversible guardrails?
- Which outcome signals can be compared without reducing trail performance to road pace?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:codex"
  ],
  "citations": [
    {
      "authors": [
        "S. J. de Waal",
        "J. Gomez-Ezeiza",
        "R. E. Venter",
        "R. P. Lamberts"
      ],
      "doi": "10.1123/ijspp.2020-0812",
      "id": "de-waal-2021-performance-review",
      "journal": "International Journal of Sports Physiology and Performance",
      "pmid": "33508776",
      "title": "Physiological Indicators of Trail Running Performance: A Systematic Review",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "F. S. Pastor",
        "T. Besson",
        "G. Varesco",
        "A. Parent",
        "M. Fanget",
        "J. Koral",
        "C. Foschia",
        "T. Rupp",
        "D. Rimaud",
        "L. Feasson",
        "G. Y. Millet"
      ],
      "doi": "10.1123/ijspp.2021-0362",
      "id": "pastor-2022-distance-determinants",
      "journal": "International Journal of Sports Physiology and Performance",
      "pmid": "35213820",
      "title": "Performance Determinants in Trail-Running Races of Different Distances",
      "url": null,
      "year": 2022
    },
    {
      "authors": [
        "G. Bjorklund",
        "M. Swaren",
        "D. P. Born",
        "T. Stoggl"
      ],
      "doi": "10.3389/fphys.2019.00506",
      "id": "bjorklund-2019-short-trail",
      "journal": "Frontiers in Physiology",
      "pmid": "31114511",
      "title": "Biomechanical Adaptations and Performance Indicators in Short Trail Running",
      "url": null,
      "year": 2019
    },
    {
      "authors": [
        "D. P. Born",
        "T. Stoggl",
        "M. Swaren",
        "G. Bjorklund"
      ],
      "doi": "10.1123/ijspp.2016-0101",
      "id": "born-2017-hilly-intensity",
      "journal": "International Journal of Sports Physiology and Performance",
      "pmid": "27396389",
      "title": "Near-Infrared Spectroscopy: More Accurate Than Heart Rate for Monitoring Intensity in Running in Hilly Terrain",
      "url": null,
      "year": 2017
    },
    {
      "authors": [
        "M. Lemire",
        "R. Remetter",
        "T. J. Hureau",
        "B. Y. L. Kouassi",
        "E. Lonsdorfer",
        "B. Geny",
        "M. E. Isner-Horobeti",
        "F. Favret",
        "S. P. Dufour"
      ],
      "doi": "10.1080/02640414.2020.1847502",
      "id": "lemire-2021-downhill-fatigue",
      "journal": "Journal of Sports Sciences",
      "pmid": "33191845",
      "title": "High-intensity downhill running exacerbates heart rate and muscular fatigue in trail runners",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "M. Lemire",
        "R. Remetter",
        "T. J. Hureau",
        "B. Geny",
        "E. Lonsdorfer",
        "F. Favret",
        "S. P. Dufour"
      ],
      "doi": "10.1123/ijspp.2021-0047",
      "id": "lemire-2022-slope-energy-cost",
      "journal": "International Journal of Sports Physiology and Performance",
      "pmid": "34853187",
      "title": "Energy Cost of Running in Well-Trained Athletes: Toward Slope-Dependent Factors",
      "url": null,
      "year": 2022
    },
    {
      "authors": [
        "S. N. Drum",
        "L. Rappelt",
        "S. Held",
        "L. Donath"
      ],
      "doi": "10.3390/ijerph20054501",
      "id": "drum-2023-trail-road-rct",
      "journal": "International Journal of Environmental Research and Public Health",
      "pmid": "36901510",
      "title": "Effects of Trail Running versus Road Running-Effects on Neuromuscular and Endurance Performance-A Two Arm Randomized Controlled Study",
      "url": null,
      "year": 2023
    },
    {
      "authors": [
        "S. Panthong",
        "N. Tongsiri",
        "H. Tanaka",
        "D. Suksom"
      ],
      "doi": "10.1519/JSC.0000000000005622",
      "id": "panthong-2026-masters-training",
      "journal": "Journal of Strength and Conditioning Research",
      "pmid": "42479880",
      "title": "Comparative Effects of Circuit Training, High-Intensity Interval Training, and Combined Training on Performance and Neuromuscular Function in Masters Trail Runners",
      "url": null,
      "year": 2026
    },
    {
      "authors": [
        "C. Viljoen",
        "D. C. C. Janse van Rensburg",
        "W. van Mechelen",
        "E. Verhagen",
        "B. Silva",
        "V. Scheer",
        "M. Besomi",
        "R. Gajardo-Burgos",
        "S. Matos",
        "M. Schoeman",
        "A. Jansen van Rensburg",
        "N. van Dyk",
        "S. Scheepers",
        "T. Botha"
      ],
      "doi": "10.1136/bjsports-2021-104858",
      "id": "viljoen-2022-risk-factors",
      "journal": "British Journal of Sports Medicine",
      "pmid": "35022162",
      "title": "Trail running injury risk factors: a living systematic review",
      "url": null,
      "year": 2022
    },
    {
      "authors": [
        "I. Garcia-Valiente",
        "F. Pradas",
        "M. A. Ortega-Zayas",
        "C. Castellar-Otin",
        "A. Garcia-Gimenez",
        "M. Lecina"
      ],
      "doi": "10.3390/muscles5010009",
      "id": "garcia-valiente-2026-damage-review",
      "journal": "Muscles",
      "pmid": "41718076",
      "title": "Muscle, Neuromuscular, and Cardiac Damage in Trail Running: A Systematic Review",
      "url": null,
      "year": 2026
    },
    {
      "authors": [
        "S. Matos",
        "F. M. Clemente",
        "R. Silva",
        "J. Pereira",
        "J. M. Cancela Carral"
      ],
      "doi": "10.3390/ijerph17238902",
      "id": "matos-2020-load-profiles",
      "journal": "International Journal of Environmental Research and Public Health",
      "pmid": "33266272",
      "title": "Performance and Training Load Profiles in Recreational Male Trail Runners: Analyzing Their Interactions during Competitions",
      "url": null,
      "year": 2020
    },
    {
      "authors": [
        "Z. Wang",
        "Y. Wang",
        "W. Gao",
        "Y. Zhong"
      ],
      "doi": "10.1371/journal.pone.0282838",
      "id": "wang-2023",
      "journal": "PLOS ONE",
      "pmid": "37163550",
      "title": "Effects of tapering on performance in endurance athletes: A systematic review and meta-analysis",
      "url": null,
      "year": 2023
    },
    {
      "authors": [
        "L. M. Burke",
        "J. A. Hawley",
        "S. H. Wong",
        "A. E. Jeukendrup"
      ],
      "doi": "10.1080/02640414.2011.585473",
      "id": "burke-2011",
      "journal": "Journal of Sports Sciences",
      "pmid": "21660838",
      "title": "Carbohydrates for training and competition",
      "url": null,
      "year": 2011
    },
    {
      "authors": [
        "I. G. Martinez",
        "A. S. Mika",
        "J. R. Biesiekierski",
        "R. J. S. Costa"
      ],
      "doi": "10.1007/s40279-023-01841-0",
      "id": "martinez-2023",
      "journal": "Sports Medicine",
      "pmid": "37061651",
      "title": "The Effect of Gut-Training and Feeding-Challenge on Markers of Gastrointestinal Status in Response to Endurance Exercise: A Systematic Literature Review",
      "url": null,
      "year": 2023
    }
  ],
  "claims": [
    {
      "applicable_population": [
        "Adult trail runners represented by the systematic review and direct studies"
      ],
      "domain": [
        "Capability matching",
        "Course specificity"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "non-ultra-trail.course-specific-policy-required",
      "limitations": [
        "Associations and prediction models do not establish causal training dose.",
        "The reviewed courses and populations are heterogeneous."
      ],
      "source_ids": [
        "de-waal-2021-performance-review",
        "pastor-2022-distance-determinants",
        "bjorklund-2019-short-trail"
      ],
      "statement": "Trail performance and training demand are course-specific and multifactorial. A policy must match an explicit course-demand vector and comparable exposure rather than distance, level pace, or one physiological marker alone."
    },
    {
      "applicable_population": [
        "Adult trained trail runners in short field and laboratory studies"
      ],
      "domain": [
        "Uphill exposure",
        "Downhill exposure",
        "Fatigue and mechanics"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "non-ultra-trail.uphill-downhill-require-distinct-handling",
      "limitations": [
        "Small studies at specific grades do not establish universal progression.",
        "Comparable oxygen uptake does not imply comparable mechanical cost."
      ],
      "source_ids": [
        "bjorklund-2019-short-trail",
        "lemire-2021-downhill-fatigue",
        "lemire-2022-slope-energy-cost"
      ],
      "statement": "Uphill and downhill running have materially different metabolic, mechanical, cardiovascular, and neuromuscular profiles. Training history and proposed exposure should therefore preserve ascent, descent, grade, and technical context separately."
    },
    {
      "applicable_population": [
        "Competitive and well-trained adult trail runners in small hilly protocols"
      ],
      "domain": [
        "Intensity interpretation",
        "Workout targets"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "non-ultra-trail.hr-and-road-pace-not-sole-targets",
      "limitations": [
        "This does not prohibit contextual athlete-specific HR or pace use.",
        "No reviewed evidence validates one universal trail RPE, power, HR, or pace equivalence."
      ],
      "source_ids": [
        "born-2017-hilly-intensity",
        "lemire-2022-slope-energy-cost"
      ],
      "statement": "Heart rate can lag or fail to reflect rapid slope-dependent changes, and level-running pace does not preserve trail mechanical demand. Neither should be the sole driver of a hilly or technical prescription."
    },
    {
      "applicable_population": [
        "Sedentary adult novices in one small trail-versus-road trial",
        "Masters trail runners aged 35 to 55 in one 12-week trial"
      ],
      "domain": [
        "Terrain specificity",
        "Strength and high-intensity modules"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "non-ultra-trail.training-specificity-promising-not-prescriptive",
      "limitations": [
        "The trail-versus-road study found no significant group-by-time interactions.",
        "The masters trial does not define a universal plan or transfer to every age and course."
      ],
      "source_ids": [
        "drum-2023-trail-road-rct",
        "panthong-2026-masters-training"
      ],
      "statement": "Trail-specific and multimodal training can be plausible modules, but the reviewed interventions are too small and heterogeneous to establish a universal session mix, weekly frequency, vertical dose, or superiority over road training."
    },
    {
      "applicable_population": [
        "Trail runners across heterogeneous race and observational studies"
      ],
      "domain": [
        "Safety guardrails",
        "Downhill and recovery uncertainty"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "non-ultra-trail.injury-fatigue-no-safe-dose",
      "limitations": [
        "Associations do not establish causality or individual safety.",
        "Race biomarkers cannot be converted into medical clearance or training readiness."
      ],
      "source_ids": [
        "viljoen-2022-risk-factors",
        "garcia-valiente-2026-damage-review"
      ],
      "statement": "Trail racing is associated with heterogeneous injury, illness, muscular, and neuromuscular stress observations, but current evidence does not establish a universal injury-preventive plan, safe downhill dose, recovery interval, or progression percentage."
    },
    {
      "applicable_population": [
        "Recreational male trail runners in one observational season"
      ],
      "domain": [
        "Training history",
        "Load interpretation"
      ],
      "effect_estimates": [],
      "evidence_strength": "very_low",
      "id": "non-ultra-trail.observed-load-does-not-prove-prescription",
      "limitations": [
        "Small observational male sample and heterogeneous events.",
        "Correlation and group averages do not select individual dose."
      ],
      "source_ids": [
        "matos-2020-load-profiles"
      ],
      "statement": "Observed trail workload and pacing associations may inform descriptive context, but they do not validate ACWR zones, fixed taper behavior, activity-average-power intensity, or an individual causal prescription."
    },
    {
      "applicable_population": [
        "Endurance athletes, indirectly applicable to non-ultra trail runners"
      ],
      "domain": [
        "Taper",
        "Event preparation"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "non-ultra-trail.taper-direction-indirect",
      "limitations": [
        "Mixed sports and protocols rather than direct non-ultra trail trials.",
        "Subgroup estimates cannot be treated as an individual optimum."
      ],
      "source_ids": [
        "wang-2023"
      ],
      "statement": "Broader endurance evidence supports a pre-event reduction in training volume while generally retaining intensity and frequency, but it does not validate one trail-specific taper duration, reduction percentage, or personal performance gain."
    },
    {
      "applicable_population": [
        "Adult endurance athletes, indirectly including trail runners"
      ],
      "domain": [
        "Fueling practice",
        "Expected duration"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "non-ultra-trail.fueling-duration-and-practice-context",
      "limitations": [
        "Numeric guidance is not trail-course specific.",
        "Practice does not guarantee tolerance or performance for an individual."
      ],
      "source_ids": [
        "burke-2011",
        "martinez-2023"
      ],
      "statement": "During-exercise carbohydrate strategy depends on expected duration and tolerance, and practice can reduce gastrointestinal problems in some endurance contexts. Distance alone does not select a fueling prescription."
    }
  ],
  "conflicting_findings": [
    "Trail determinants differ by course distance and profile, preventing one universal predictor or plan.",
    "Small intervention studies suggest possible benefits without establishing one superior training mix.",
    "Lower metabolic cost downhill can coexist with greater peak force and neuromuscular fatigue.",
    "General endurance taper and fueling findings are directionally relevant but not trail-specific prescriptions."
  ],
  "created_on": "2026-09-01",
  "follow_up_questions": [
    "Which exact history window and comparability rules should qualify a bounded policy?",
    "Which conservative session mix can be piloted without claiming biological optimality?",
    "How should inaccessible terrain produce alternatives without pretending road running is equivalent?",
    "Which taper, fueling-practice, and reassessment values are acceptable reversible guardrails?",
    "Which outcome signals can be compared without reducing trail performance to road pace?"
  ],
  "id": "evidence-non-ultra-trail-plan-generation-policy-v1",
  "intended_product_purpose": "Establish whether Praxys may offer one bounded, history-rich non-ultra trail performance policy without copying a road schedule or inventing a universal distance/elevation conversion. Separate published findings from reversible Praxys guardrails, preserve course and athlete unknowns, and identify every unresolved dose, taper, progression, intensity, and rollout decision. The review does not itself authorize implementation or runtime activation.",
  "known_gaps": [
    "A prospectively evaluated deterministic non-ultra trail plan policy",
    "A validated comparable-history and course-demand matching threshold",
    "Safe vertical, downhill, technical-terrain, long-session, and weekly progression values",
    "Direct trail-specific taper duration and reduction values",
    "Universal HR, pace, power, RPE, hiking, or terrain-substitution equivalences",
    "Adequate female, older, diverse, and different-access subgroup evidence"
  ],
  "method": {
    "exclusion_criteria": [
      "Ultra or multi-day findings converted directly into a non-ultra schedule",
      "Road-plan percentages or distance-only policies reused as trail prescriptions",
      "Clinical, rehabilitation, pregnancy-specific, pediatric, or return-to-sport prescription",
      "Coaching templates, blogs, vendor content, and unverified search snippets"
    ],
    "inclusion_criteria": [
      "Adult human trail-running performance, training, fatigue, or injury evidence",
      "Direct trail studies preferred; broader endurance evidence labelled indirect",
      "Systematic reviews, controlled studies, observational cohorts, and authoritative guidance with stable identifiers",
      "Numeric findings used only at their verified access level and study context"
    ],
    "method_limitations": [
      "Screening and extraction were not independently duplicated by human reviewers.",
      "SPORTDiscus, Scopus, Embase, and Web of Science were not independently searched in this run.",
      "Several direct trail records were available only as indexed abstracts.",
      "Direct non-ultra intervention evidence is sparse, heterogeneous, and often male-heavy.",
      "No reviewed source validates a complete deterministic trail plan, safe progression law, or personal finish probability."
    ],
    "quality_appraisal": "Evidence was appraised for directness to history-rich adult non-ultra trail runners, course comparability, intervention design, sample size, sex and age representation, terrain realism, confounding, and whether a finding supports a directional module or an exact personal dose. Direct training intervention evidence is sparse and small. Injury and race-fatigue evidence is mainly observational. General taper and fueling evidence is more mature but indirect and cannot choose trail-specific values by itself.",
    "review_type": "rigorous",
    "search_date": "2026-09-01",
    "sources": [
      {
        "name": "Europe PMC and PubMed - trail policy exact records",
        "search_string": "33508776[PMID] OR 35213820[PMID] OR 31114511[PMID] OR 36901510[PMID] OR 35022162[PMID] OR 33538997[PMID] OR 33191845[PMID] OR 34853187[PMID] OR 27396389[PMID] OR 33266272[PMID] OR 41718076[PMID] OR 42479880[PMID]"
      },
      {
        "name": "PubMed Central full text",
        "search_string": "PMC6503082 OR PMC10002259 OR PMC7730662 OR PMC12921809"
      },
      {
        "name": "Europe PMC and PubMed - taper and fueling transfer",
        "search_string": "37163550[PMID] OR 21660838[PMID] OR 37061651[PMID]"
      },
      {
        "name": "Europe PMC trail training discovery",
        "search_string": "(trail running OR mountain running) AND (training intervention OR periodization OR taper OR strength OR downhill OR uphill OR fueling) AND adult"
      }
    ]
  },
  "research_question": "For nonclinical adults with recent, comparable running and trail exposure who are preparing for a single-day non-ultra trail event described by trail_course_demand_v1, what evidence supports and limits a deterministic, suggestion-only, history-anchored plan policy covering terrain specificity, uphill and downhill exposure, intensity, strength, long sessions, taper, fueling practice, reassessment, and typed unavailable outcomes?",
  "review_notes": [
    "Verification: de-waal-2021-performance-review - abstract; Europe PMC PMID 33508776 metadata and abstract; 2026-09-01.",
    "Verification: pastor-2022-distance-determinants - abstract; Europe PMC PMID 35213820 metadata and abstract; 2026-09-01.",
    "Verification: bjorklund-2019-short-trail - full-text; Europe PMC PMID 31114511 metadata and PubMed Central PMC6503082 full text; 2026-09-01.",
    "Verification: born-2017-hilly-intensity - abstract; Europe PMC PMID 27396389 metadata and abstract; 2026-09-01.",
    "Verification: lemire-2021-downhill-fatigue - abstract; Europe PMC PMID 33191845 metadata and abstract; 2026-09-01.",
    "Verification: lemire-2022-slope-energy-cost - abstract; Europe PMC PMID 34853187 metadata and abstract; 2026-09-01.",
    "Verification: drum-2023-trail-road-rct - full-text; Europe PMC PMID 36901510 metadata and PubMed Central PMC10002259 full text; 2026-09-01.",
    "Verification: panthong-2026-masters-training - abstract; Europe PMC PMID 42479880 metadata and abstract; 2026-09-01.",
    "Verification: viljoen-2022-risk-factors - abstract; Europe PMC PMID 35022162 metadata and abstract; 2026-09-01.",
    "Verification: garcia-valiente-2026-damage-review - full-text; Europe PMC PMID 41718076 metadata and PubMed Central PMC12921809 full text; 2026-09-01.",
    "Verification: matos-2020-load-profiles - full-text; Europe PMC PMID 33266272 metadata and PubMed Central PMC7730662 full text; 2026-09-01.",
    "Verification: wang-2023 - full-text; Europe PMC PMID 37163550 metadata and PubMed Central PMC10171681 full text; 2026-09-01.",
    "Verification: burke-2011 - abstract; Europe PMC PMID 21660838 metadata and abstract; 2026-09-01.",
    "Verification: martinez-2023 - full-text; Europe PMC PMID 37061651 metadata and PubMed Central PMC10185635 full text; 2026-09-01."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Trail versus road training",
      "Uphill versus downhill versus level demand",
      "Different trail distances and course profiles",
      "Strength, high-intensity, and combined training",
      "Tapered versus maintained endurance load"
    ],
    "intervention_or_exposure": [
      "Trail-specific and mixed-terrain running practice",
      "Uphill, downhill, level, hiking, strength, and multimodal training",
      "History-anchored volume, duration, frequency, and terrain exposure",
      "General endurance taper and duration-dependent fueling practice"
    ],
    "outcomes": [
      "Trail performance and course-specific readiness",
      "Neuromuscular, mechanical, metabolic, and cardiovascular response",
      "Injury and fatigue observations",
      "Proposal availability, uncertainty, and post-plan evaluation"
    ],
    "population": [
      "Adults aged 18 years or older with recent stable running history",
      "Adults with recent terrain, ascent, and descent exposure comparable enough for a reviewed capability match",
      "Single-day non-ultra trail performance intent",
      "Nonclinical planning only"
    ]
  },
  "supersedes": [],
  "title": "History-rich adult non-ultra trail-running plan generation",
  "topic": "non-ultra-trail-plan-generation-policy",
  "version": 1
}
```

</details>
