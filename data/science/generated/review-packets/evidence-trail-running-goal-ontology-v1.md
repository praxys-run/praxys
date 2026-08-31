# Evidence review packet: Trail-running course-demand ontology and generation boundary

> Generated from the canonical Evidence Review. Review this packet, not the raw YAML. Any source change invalidates the digest below.

- **Record:** `evidence-trail-running-goal-ontology-v1`
- **Lifecycle:** `draft`
- **Review mode:** `artifact`
- **Reviewed content digest:** `sha256:60f0e785e4fc2b4226fed3bb30750191195cffbb0236b4a81d34431c0002c87a`
- **Required role:** `evidence_reviewer`
- **Approval:** _Pending_

## Approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML; reviewers do not edit it by hand.

```markdown
Praxys science approval — **APPROVE**

- Role: `evidence_reviewer`
- Subject: `evidence-trail-running-goal-ontology-v1`
- Digest: `sha256:60f0e785e4fc2b4226fed3bb30750191195cffbb0236b4a81d34431c0002c87a`

> I approve this Evidence Review's search method, evidence claims, citation verification, limitations, and gaps for the displayed digest.

<!-- praxys-science-approval:v1
{"role":"evidence_reviewer","subject_digest":"sha256:60f0e785e4fc2b4226fed3bb30750191195cffbb0236b4a81d34431c0002c87a","subject_id":"evidence-trail-running-goal-ontology-v1","subject_kind":"evidence_review"}
-->
```

## Question and product purpose

For nonclinical adults preparing for a single-day trail-running event, which course, environment, support, access, and prior-exposure dimensions must be represented before Praxys may match a governed plan-generation policy, and what does the literature not justify converting or inferring?

Define one versioned, provider-neutral trail_course_demand_v1 contract that preserves course specificity and unknowns. It must prevent distance-only routing, silent road-plan fallback, universal distance-to-vertical conversion, and unsupported personal performance or safety claims. This review does not select a plan, dose, user experience, rollout, or provider delivery behavior.

## Scope

## Population

- Adults aged 18 years or older preparing for a single-day trail-running event
- Recreational and trained trail runners represented by the reviewed evidence
- Nonclinical planning only

## Intervention or exposure

- Event distance, elevation gain and loss, grade distribution, technical terrain, altitude, and environment
- Expected event duration, aid and external support, terrain access, downhill exposure, and fueling-practice history
- Uphill, downhill, and level trail-running demands

## Comparator

- Trail courses with different distance, elevation, grade, technicality, altitude, environment, and support
- Uphill versus downhill versus level running
- Trail versus road running or distance-only representation

## Outcomes

- Course-demand description and capability matching
- Physiological, biomechanical, neuromuscular, and performance demands
- Explicit uncertainty, unknown-field behavior, and generation availability

## Review method

- **Type:** `rigorous`
- **Search date:** `2026-09-01`

### Exact searches

- **Europe PMC and PubMed - exact included records**
  - `33508776[PMID] OR 35213820[PMID] OR 31114511[PMID] OR 31666898[PMID] OR 12183501[PMID] OR 36901510[PMID] OR 35022162[PMID] OR 32059243[PMID] OR 33191845[PMID] OR 34853187[PMID] OR 27396389[PMID] OR 38979439[PMID] OR 33829868[PMID] OR 16311764[PMID] OR 21660838[PMID] OR 37061651[PMID]`
- **PubMed Central full text**
  - `PMC6503082 OR PMC6815081 OR PMC10002259 OR PMC11228266 OR PMC10185635`
- **Europe PMC trail demand discovery**
  - `(trail running OR off-road running) AND (performance OR biomechanics OR injury OR elevation OR slope OR technical terrain) AND adult`

## Inclusion criteria

- Adult human trail- or hill-running evidence that distinguishes material course demands
- Systematic reviews, position statements, controlled studies, and direct field or laboratory studies
- Stable DOI or PMID metadata verified against Europe PMC or PubMed

## Exclusion criteria

- Road-only evidence used to define trail equivalence
- Ultra-only findings promoted into non-ultra dose rules
- Coaching templates, vendor guidance, blogs, and unverified search snippets
- Metadata-only records used for effect estimates or strong conclusions

## Method limitations

- Screening and extraction were not independently duplicated by human reviewers.
- SPORTDiscus, Scopus, Embase, and Web of Science were not independently searched in this run.
- Several systematic reviews and primary studies were available only as indexed abstracts.
- Evidence underrepresents women and does not validate sex-specific automatic modifiers.
- No reviewed source validates one universal technicality scale, grade-bin schema, or distance-elevation equivalence.

### Quality appraisal

Evidence was appraised for course specificity, directness to adult trail running, study design, sample size, sex representation, terrain realism, and whether it supports an ontology dimension versus an individual prescription. The direct evidence is heterogeneous and often small; it supports keeping course dimensions distinct more strongly than any exact conversion or training dose.

## Claims

### `trail-ontology.course-demand-is-multidimensional` — moderate

Trail-running performance and exposure are course-specific and multifactorial. Distance alone does not preserve elevation, grade, surface, technicality, altitude, environment, event format, or support.

- **Sources:** `scheer-2020-off-road-definition`, `de-waal-2021-performance-review`, `pastor-2022-distance-determinants`, `scheer-2019-threshold-prediction`
- **Population:** Adult trail runners represented by reviews and direct competition studies
- **Domain:** Course-demand representation; Capability matching
- **Limitations:**
  - The literature does not provide one validated machine-readable schema.
  - Performance associations do not establish individual plan dose.

### `trail-ontology.uphill-downhill-demands-differ` — moderate

Uphill and downhill running impose different metabolic, biomechanical, and neuromuscular demands; total elevation gain cannot stand in for descent exposure or grade distribution.

- **Sources:** `minetti-2002`, `bjorklund-2019-short-trail`, `lemire-2021-downhill-fatigue`, `lemire-2022-slope-energy-cost`
- **Population:** Adult trained runners in laboratory and short-trail studies
- **Domain:** Elevation gain and loss; Grade distribution; Downhill exposure
- **Limitations:**
  - Studies use small, selected samples and specific grades.
  - Results do not validate a universal vertical conversion or progression rate.

### `trail-ontology.technicality-and-downhill-vary-performance` — low

Technical terrain and downhill sections can materially change between- runner performance and mechanical exposure, so technicality and descent cannot be inferred safely from distance and gain alone.

- **Sources:** `bjorklund-2019-short-trail`, `de-waal-2021-performance-review`, `genitrini-2024-race-stage`
- **Population:** Adult trail runners in the reviewed field studies
- **Domain:** Technical terrain; Downhill demand
- **Limitations:**
  - Technicality measurement is inconsistent across studies.
  - The evidence does not establish an exact technical-terrain training dose.

### `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone` — low

Rapidly changing slope can decouple heart rate and level-running pace from the metabolic and mechanical demands of hilly running; neither is a sufficient sole representation of course demand or training intensity.

- **Sources:** `born-2017-hilly-intensity`, `lemire-2022-slope-energy-cost`
- **Population:** Competitive and well-trained adult trail runners in short hilly protocols
- **Domain:** Intensity interpretation; Slope specificity
- **Limitations:**
  - Small studies do not invalidate athlete-specific heart-rate or pace context in all settings.
  - NIRS findings do not authorize a consumer prescription.

### `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose` — low

Direct trail-training evidence is small, and trail-injury evidence is heterogeneous and substantially observational. Neither establishes a universal safe downhill, vertical, technical-terrain, or weekly progression dose, an individualized injury probability, or an injury-prevention guarantee.

- **Sources:** `drum-2023-trail-road-rct`, `viljoen-2022-risk-factors`
- **Population:** Adult novices in one small training trial and trail runners in heterogeneous injury studies
- **Domain:** Training history; Terrain access; Safety boundary
- **Limitations:**
  - The randomized study found no significant group-by-time interactions.
  - Observational injury associations do not establish causal prevention rules.
  - This absence of a validated universal dose does not show that every exposure is equally appropriate.

### `trail-ontology.environment-and-altitude-are-distinct-context` — low

Heat exposure depends on multiple environmental and athlete factors, while acute altitude can reduce aerobic capacity in controlled endurance protocols. Expected environment and maximum altitude are therefore distinct context dimensions; the evidence does not validate a personal trail pace correction, acclimation schedule, or safety threshold.

- **Sources:** `periard-2021`, `wehrlin-2006-altitude`
- **Population:** Adult endurance athletes represented by the reviewed heat and altitude literature
- **Domain:** Environmental demand; Maximum altitude; Claim limits
- **Limitations:**
  - The evidence is not a direct validation of a trail-course matching schema.
  - Controlled acute-altitude findings do not establish self-paced trail performance effects.
  - Heat response varies with metabolic rate, clothing, wind, solar load, acclimation, and individual context.

### `trail-ontology.duration-and-fueling-practice-are-context` — moderate

Endurance carbohydrate strategy varies with expected exercise duration, feeding opportunity, and prior tolerance. Repeated feeding practice may reduce gastrointestinal problems in some protocols, but distance alone does not establish a personal fueling amount, timing rule, tolerance, or performance benefit.

- **Sources:** `burke-2011`, `martinez-2023`
- **Population:** Adult endurance athletes represented by the reviewed nutrition literature
- **Domain:** Expected duration; Fueling-practice experience; Claim limits
- **Limitations:**
  - The evidence is broader endurance evidence rather than a trail-course ontology validation.
  - Reviewed protocols, carbohydrate forms, event durations, and populations vary.
  - Practice does not guarantee individual gastrointestinal tolerance or performance.

## Citations and verification level

| ID | Verification | Stable identifier | Citation |
|---|---|---|---|
| `scheer-2020-off-road-definition` | `abstract` | DOI `10.1055/a-1096-0980` | Defining Off-road Running: A Position Statement from the Ultra Sports Science Foundation (2020) |
| `de-waal-2021-performance-review` | `abstract` | DOI `10.1123/ijspp.2020-0812` | Physiological Indicators of Trail Running Performance: A Systematic Review (2021) |
| `pastor-2022-distance-determinants` | `abstract` | DOI `10.1123/ijspp.2021-0362` | Performance Determinants in Trail-Running Races of Different Distances (2022) |
| `scheer-2019-threshold-prediction` | `full-text` | DOI `10.2478/hukin-2019-0092` | Predicting Competition Performance in Short Trail Running Races with Lactate Thresholds (2019) |
| `minetti-2002` | `abstract` | DOI `10.1152/japplphysiol.01177.2001` | Energy cost of walking and running at extreme uphill and downhill slopes (2002) |
| `bjorklund-2019-short-trail` | `full-text` | DOI `10.3389/fphys.2019.00506` | Biomechanical Adaptations and Performance Indicators in Short Trail Running (2019) |
| `born-2017-hilly-intensity` | `abstract` | DOI `10.1123/ijspp.2016-0101` | Near-Infrared Spectroscopy: More Accurate Than Heart Rate for Monitoring Intensity in Running in Hilly Terrain (2017) |
| `lemire-2021-downhill-fatigue` | `abstract` | DOI `10.1080/02640414.2020.1847502` | High-intensity downhill running exacerbates heart rate and muscular fatigue in trail runners (2021) |
| `lemire-2022-slope-energy-cost` | `abstract` | DOI `10.1123/ijspp.2021-0047` | Energy Cost of Running in Well-Trained Athletes: Toward Slope-Dependent Factors (2022) |
| `drum-2023-trail-road-rct` | `full-text` | DOI `10.3390/ijerph20054501` | Effects of Trail Running versus Road Running-Effects on Neuromuscular and Endurance Performance-A Two Arm Randomized Controlled Study (2023) |
| `viljoen-2022-risk-factors` | `abstract` | DOI `10.1136/bjsports-2021-104858` | Trail running injury risk factors: a living systematic review (2022) |
| `genitrini-2024-race-stage` | `full-text` | DOI `10.3389/fspor.2024.1406824` | Spatiotemporal parameters and kinematics differ between race stages in trail running-a field study (2024) |
| `periard-2021` | `abstract` | DOI `10.1152/physrev.00038.2020` | Exercise under heat stress: thermoregulation, hydration, performance implications, and mitigation strategies (2021) |
| `wehrlin-2006-altitude` | `abstract` | DOI `10.1007/s00421-005-0081-9` | Linear decrease in VO2max and performance with increasing altitude in endurance athletes (2006) |
| `burke-2011` | `abstract` | DOI `10.1080/02640414.2011.585473` | Carbohydrates for training and competition (2011) |
| `martinez-2023` | `full-text` | DOI `10.1007/s40279-023-01841-0` | The Effect of Gut-Training and Feeding-Challenge on Markers of Gastrointestinal Status in Response to Endurance Exercise: A Systematic Literature Review (2023) |

## Known gaps

- A validated universal technicality scale or grade-distribution schema
- A universal distance-to-vertical or trail-to-road equivalence
- Validated safe vertical, downhill, technical-terrain, or weekly progression doses
- Prospective validation of trail_course_demand_v1 capability matching
- Adequate female-specific and diverse-population training evidence

## Conflicting findings

- Physiological predictors and their explanatory value differ across trail distances and course contexts.
- Similar metabolic demand can coexist with different uphill and downhill mechanical demands.
- Trail-versus-road training evidence is too small to establish a universal superior modality.

## Follow-up questions

- Which grade bins and technicality rubric can be collected reproducibly without false precision?
- Which course fields may be inferred from a verified route file, and what uncertainty must remain visible?
- What comparable-history boundary should a non-ultra trail generator require?
- How should altitude, heat, support, terrain access, and fueling experience limit only dependent modules?

<details><summary>Exact reviewed evidence payload</summary>

```json
{
  "authors": [
    "agent:codex"
  ],
  "citations": [
    {
      "authors": [
        "V. Scheer",
        "P. Basset",
        "N. Giovanelli",
        "G. Vernillo",
        "G. P. Millet",
        "R. J. S. Costa"
      ],
      "doi": "10.1055/a-1096-0980",
      "id": "scheer-2020-off-road-definition",
      "journal": "International Journal of Sports Medicine",
      "pmid": "32059243",
      "title": "Defining Off-road Running: A Position Statement from the Ultra Sports Science Foundation",
      "url": null,
      "year": 2020
    },
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
        "V. Scheer",
        "S. Vieluf",
        "T. I. Janssen",
        "H. C. Heitkamp"
      ],
      "doi": "10.2478/hukin-2019-0092",
      "id": "scheer-2019-threshold-prediction",
      "journal": "Journal of Human Kinetics",
      "pmid": "31666898",
      "title": "Predicting Competition Performance in Short Trail Running Races with Lactate Thresholds",
      "url": null,
      "year": 2019
    },
    {
      "authors": [
        "Alberto E. Minetti",
        "Christian Moia",
        "Giulio S. Roi",
        "Davide Susta",
        "Guido Ferretti"
      ],
      "doi": "10.1152/japplphysiol.01177.2001",
      "id": "minetti-2002",
      "journal": "Journal of Applied Physiology",
      "pmid": "12183501",
      "title": "Energy cost of walking and running at extreme uphill and downhill slopes",
      "url": null,
      "year": 2002
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
        "M. Genitrini",
        "J. Fritz",
        "T. Stoggl",
        "H. Schwameder"
      ],
      "doi": "10.3389/fspor.2024.1406824",
      "id": "genitrini-2024-race-stage",
      "journal": "Frontiers in Sports and Active Living",
      "pmid": "38979439",
      "title": "Spatiotemporal parameters and kinematics differ between race stages in trail running-a field study",
      "url": null,
      "year": 2024
    },
    {
      "authors": [
        "Julien D. Periard",
        "Thijs M. H. Eijsvogels",
        "Hein A. M. Daanen"
      ],
      "doi": "10.1152/physrev.00038.2020",
      "id": "periard-2021",
      "journal": "Physiological Reviews",
      "pmid": "33829868",
      "title": "Exercise under heat stress: thermoregulation, hydration, performance implications, and mitigation strategies",
      "url": null,
      "year": 2021
    },
    {
      "authors": [
        "J. P. Wehrlin",
        "J. Hallén"
      ],
      "doi": "10.1007/s00421-005-0081-9",
      "id": "wehrlin-2006-altitude",
      "journal": "European Journal of Applied Physiology",
      "pmid": "16311764",
      "title": "Linear decrease in VO2max and performance with increasing altitude in endurance athletes",
      "url": null,
      "year": 2006
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
        "Adult trail runners represented by reviews and direct competition studies"
      ],
      "domain": [
        "Course-demand representation",
        "Capability matching"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "trail-ontology.course-demand-is-multidimensional",
      "limitations": [
        "The literature does not provide one validated machine-readable schema.",
        "Performance associations do not establish individual plan dose."
      ],
      "source_ids": [
        "scheer-2020-off-road-definition",
        "de-waal-2021-performance-review",
        "pastor-2022-distance-determinants",
        "scheer-2019-threshold-prediction"
      ],
      "statement": "Trail-running performance and exposure are course-specific and multifactorial. Distance alone does not preserve elevation, grade, surface, technicality, altitude, environment, event format, or support."
    },
    {
      "applicable_population": [
        "Adult trained runners in laboratory and short-trail studies"
      ],
      "domain": [
        "Elevation gain and loss",
        "Grade distribution",
        "Downhill exposure"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "trail-ontology.uphill-downhill-demands-differ",
      "limitations": [
        "Studies use small, selected samples and specific grades.",
        "Results do not validate a universal vertical conversion or progression rate."
      ],
      "source_ids": [
        "minetti-2002",
        "bjorklund-2019-short-trail",
        "lemire-2021-downhill-fatigue",
        "lemire-2022-slope-energy-cost"
      ],
      "statement": "Uphill and downhill running impose different metabolic, biomechanical, and neuromuscular demands; total elevation gain cannot stand in for descent exposure or grade distribution."
    },
    {
      "applicable_population": [
        "Adult trail runners in the reviewed field studies"
      ],
      "domain": [
        "Technical terrain",
        "Downhill demand"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "trail-ontology.technicality-and-downhill-vary-performance",
      "limitations": [
        "Technicality measurement is inconsistent across studies.",
        "The evidence does not establish an exact technical-terrain training dose."
      ],
      "source_ids": [
        "bjorklund-2019-short-trail",
        "de-waal-2021-performance-review",
        "genitrini-2024-race-stage"
      ],
      "statement": "Technical terrain and downhill sections can materially change between- runner performance and mechanical exposure, so technicality and descent cannot be inferred safely from distance and gain alone."
    },
    {
      "applicable_population": [
        "Competitive and well-trained adult trail runners in short hilly protocols"
      ],
      "domain": [
        "Intensity interpretation",
        "Slope specificity"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
      "limitations": [
        "Small studies do not invalidate athlete-specific heart-rate or pace context in all settings.",
        "NIRS findings do not authorize a consumer prescription."
      ],
      "source_ids": [
        "born-2017-hilly-intensity",
        "lemire-2022-slope-energy-cost"
      ],
      "statement": "Rapidly changing slope can decouple heart rate and level-running pace from the metabolic and mechanical demands of hilly running; neither is a sufficient sole representation of course demand or training intensity."
    },
    {
      "applicable_population": [
        "Adult novices in one small training trial and trail runners in heterogeneous injury studies"
      ],
      "domain": [
        "Training history",
        "Terrain access",
        "Safety boundary"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose",
      "limitations": [
        "The randomized study found no significant group-by-time interactions.",
        "Observational injury associations do not establish causal prevention rules.",
        "This absence of a validated universal dose does not show that every exposure is equally appropriate."
      ],
      "source_ids": [
        "drum-2023-trail-road-rct",
        "viljoen-2022-risk-factors"
      ],
      "statement": "Direct trail-training evidence is small, and trail-injury evidence is heterogeneous and substantially observational. Neither establishes a universal safe downhill, vertical, technical-terrain, or weekly progression dose, an individualized injury probability, or an injury-prevention guarantee."
    },
    {
      "applicable_population": [
        "Adult endurance athletes represented by the reviewed heat and altitude literature"
      ],
      "domain": [
        "Environmental demand",
        "Maximum altitude",
        "Claim limits"
      ],
      "effect_estimates": [],
      "evidence_strength": "low",
      "id": "trail-ontology.environment-and-altitude-are-distinct-context",
      "limitations": [
        "The evidence is not a direct validation of a trail-course matching schema.",
        "Controlled acute-altitude findings do not establish self-paced trail performance effects.",
        "Heat response varies with metabolic rate, clothing, wind, solar load, acclimation, and individual context."
      ],
      "source_ids": [
        "periard-2021",
        "wehrlin-2006-altitude"
      ],
      "statement": "Heat exposure depends on multiple environmental and athlete factors, while acute altitude can reduce aerobic capacity in controlled endurance protocols. Expected environment and maximum altitude are therefore distinct context dimensions; the evidence does not validate a personal trail pace correction, acclimation schedule, or safety threshold."
    },
    {
      "applicable_population": [
        "Adult endurance athletes represented by the reviewed nutrition literature"
      ],
      "domain": [
        "Expected duration",
        "Fueling-practice experience",
        "Claim limits"
      ],
      "effect_estimates": [],
      "evidence_strength": "moderate",
      "id": "trail-ontology.duration-and-fueling-practice-are-context",
      "limitations": [
        "The evidence is broader endurance evidence rather than a trail-course ontology validation.",
        "Reviewed protocols, carbohydrate forms, event durations, and populations vary.",
        "Practice does not guarantee individual gastrointestinal tolerance or performance."
      ],
      "source_ids": [
        "burke-2011",
        "martinez-2023"
      ],
      "statement": "Endurance carbohydrate strategy varies with expected exercise duration, feeding opportunity, and prior tolerance. Repeated feeding practice may reduce gastrointestinal problems in some protocols, but distance alone does not establish a personal fueling amount, timing rule, tolerance, or performance benefit."
    }
  ],
  "conflicting_findings": [
    "Physiological predictors and their explanatory value differ across trail distances and course contexts.",
    "Similar metabolic demand can coexist with different uphill and downhill mechanical demands.",
    "Trail-versus-road training evidence is too small to establish a universal superior modality."
  ],
  "created_on": "2026-09-01",
  "follow_up_questions": [
    "Which grade bins and technicality rubric can be collected reproducibly without false precision?",
    "Which course fields may be inferred from a verified route file, and what uncertainty must remain visible?",
    "What comparable-history boundary should a non-ultra trail generator require?",
    "How should altitude, heat, support, terrain access, and fueling experience limit only dependent modules?"
  ],
  "id": "evidence-trail-running-goal-ontology-v1",
  "intended_product_purpose": "Define one versioned, provider-neutral trail_course_demand_v1 contract that preserves course specificity and unknowns. It must prevent distance-only routing, silent road-plan fallback, universal distance-to-vertical conversion, and unsupported personal performance or safety claims. This review does not select a plan, dose, user experience, rollout, or provider delivery behavior.",
  "known_gaps": [
    "A validated universal technicality scale or grade-distribution schema",
    "A universal distance-to-vertical or trail-to-road equivalence",
    "Validated safe vertical, downhill, technical-terrain, or weekly progression doses",
    "Prospective validation of trail_course_demand_v1 capability matching",
    "Adequate female-specific and diverse-population training evidence"
  ],
  "method": {
    "exclusion_criteria": [
      "Road-only evidence used to define trail equivalence",
      "Ultra-only findings promoted into non-ultra dose rules",
      "Coaching templates, vendor guidance, blogs, and unverified search snippets",
      "Metadata-only records used for effect estimates or strong conclusions"
    ],
    "inclusion_criteria": [
      "Adult human trail- or hill-running evidence that distinguishes material course demands",
      "Systematic reviews, position statements, controlled studies, and direct field or laboratory studies",
      "Stable DOI or PMID metadata verified against Europe PMC or PubMed"
    ],
    "method_limitations": [
      "Screening and extraction were not independently duplicated by human reviewers.",
      "SPORTDiscus, Scopus, Embase, and Web of Science were not independently searched in this run.",
      "Several systematic reviews and primary studies were available only as indexed abstracts.",
      "Evidence underrepresents women and does not validate sex-specific automatic modifiers.",
      "No reviewed source validates one universal technicality scale, grade-bin schema, or distance-elevation equivalence."
    ],
    "quality_appraisal": "Evidence was appraised for course specificity, directness to adult trail running, study design, sample size, sex representation, terrain realism, and whether it supports an ontology dimension versus an individual prescription. The direct evidence is heterogeneous and often small; it supports keeping course dimensions distinct more strongly than any exact conversion or training dose.",
    "review_type": "rigorous",
    "search_date": "2026-09-01",
    "sources": [
      {
        "name": "Europe PMC and PubMed - exact included records",
        "search_string": "33508776[PMID] OR 35213820[PMID] OR 31114511[PMID] OR 31666898[PMID] OR 12183501[PMID] OR 36901510[PMID] OR 35022162[PMID] OR 32059243[PMID] OR 33191845[PMID] OR 34853187[PMID] OR 27396389[PMID] OR 38979439[PMID] OR 33829868[PMID] OR 16311764[PMID] OR 21660838[PMID] OR 37061651[PMID]"
      },
      {
        "name": "PubMed Central full text",
        "search_string": "PMC6503082 OR PMC6815081 OR PMC10002259 OR PMC11228266 OR PMC10185635"
      },
      {
        "name": "Europe PMC trail demand discovery",
        "search_string": "(trail running OR off-road running) AND (performance OR biomechanics OR injury OR elevation OR slope OR technical terrain) AND adult"
      }
    ]
  },
  "research_question": "For nonclinical adults preparing for a single-day trail-running event, which course, environment, support, access, and prior-exposure dimensions must be represented before Praxys may match a governed plan-generation policy, and what does the literature not justify converting or inferring?",
  "review_notes": [
    "Verification: scheer-2020-off-road-definition - abstract; Europe PMC PMID 32059243 metadata and abstract; 2026-09-01.",
    "Verification: de-waal-2021-performance-review - abstract; Europe PMC PMID 33508776 metadata and abstract; 2026-09-01.",
    "Verification: pastor-2022-distance-determinants - abstract; Europe PMC PMID 35213820 metadata and abstract; 2026-09-01.",
    "Verification: scheer-2019-threshold-prediction - full-text; Europe PMC PMID 31666898 metadata and PubMed Central PMC6815081 full text; 2026-09-01.",
    "Verification: minetti-2002 - abstract; Europe PMC PMID 12183501 metadata and abstract; 2026-09-01.",
    "Verification: bjorklund-2019-short-trail - full-text; Europe PMC PMID 31114511 metadata and PubMed Central PMC6503082 full text; 2026-09-01.",
    "Verification: born-2017-hilly-intensity - abstract; Europe PMC PMID 27396389 metadata and abstract; 2026-09-01.",
    "Verification: lemire-2021-downhill-fatigue - abstract; Europe PMC PMID 33191845 metadata and abstract; 2026-09-01.",
    "Verification: lemire-2022-slope-energy-cost - abstract; Europe PMC PMID 34853187 metadata and abstract; 2026-09-01.",
    "Verification: drum-2023-trail-road-rct - full-text; Europe PMC PMID 36901510 metadata and PubMed Central PMC10002259 full text; 2026-09-01.",
    "Verification: viljoen-2022-risk-factors - abstract; Europe PMC PMID 35022162 metadata and abstract; 2026-09-01.",
    "Verification: genitrini-2024-race-stage - full-text; Europe PMC PMID 38979439 metadata and PubMed Central PMC11228266 full text; 2026-09-01.",
    "Verification: periard-2021 - abstract; Europe PMC PMID 33829868 metadata and abstract; 2026-09-01.",
    "Verification: wehrlin-2006-altitude - abstract; Europe PMC PMID 16311764 metadata and abstract; 2026-09-01.",
    "Verification: burke-2011 - abstract; Europe PMC PMID 21660838 metadata and abstract; 2026-09-01.",
    "Verification: martinez-2023 - full-text; Europe PMC PMID 37061651 metadata and PubMed Central PMC10185635 full text; 2026-09-01."
  ],
  "schema_version": 1,
  "scope": {
    "comparator": [
      "Trail courses with different distance, elevation, grade, technicality, altitude, environment, and support",
      "Uphill versus downhill versus level running",
      "Trail versus road running or distance-only representation"
    ],
    "intervention_or_exposure": [
      "Event distance, elevation gain and loss, grade distribution, technical terrain, altitude, and environment",
      "Expected event duration, aid and external support, terrain access, downhill exposure, and fueling-practice history",
      "Uphill, downhill, and level trail-running demands"
    ],
    "outcomes": [
      "Course-demand description and capability matching",
      "Physiological, biomechanical, neuromuscular, and performance demands",
      "Explicit uncertainty, unknown-field behavior, and generation availability"
    ],
    "population": [
      "Adults aged 18 years or older preparing for a single-day trail-running event",
      "Recreational and trained trail runners represented by the reviewed evidence",
      "Nonclinical planning only"
    ]
  },
  "supersedes": [],
  "title": "Trail-running course-demand ontology and generation boundary",
  "topic": "trail-running-goal-ontology",
  "version": 1
}
```

</details>
