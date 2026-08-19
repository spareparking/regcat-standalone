# Integrated audit — multi-doc completeness

Aggregate evidence across **7 documents**. Re-runnable any time.

## 1. Mechanical proofs (deterministic)

| Doc | Spans | Reqs | Cov | Verbatim fails | Gaps | Overlaps | Unclass | Unreq | Passed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|
| `fda/21-cfr-part-11` | 105 | 153 | 100.00% | 0 | 0 | 0 | 0 | 0 | ✓ |
| **TOTAL** | **105** | **153** | — | **0** | **0** | **0** | **0** | **0** | |

## 2. Modal-verb sniff test (`shall`/`must`/`may`/`should`)

Every modal verb in source should sit inside a span flagged `requirement_bearing` in its primary OR embedded labels. Modal verbs in NEITHER are the highest-value candidate misses (after excluding date abbreviations and similar false positives).

| Doc | shall | must | may | should | in req_bearing | NOT in req_bearing |
|---|---:|---:|---:|---:|---:|---:|
| `fda/21-cfr-part-11` | 25 | 1 | 6 | 1 | 32 | 1 |
| `fda/guidance-electronic-source-data-clinical-investigations` | 0 | 11 | 3 | 35 | 0 | 49 |
| `fda/guidance-patient-reported-outcome-measures` | 0 | 2 | 48 | 78 | 0 | 128 |
| `ich/e6-r3-good-clinical-practice` | 1 | 4 | 138 | 599 | 0 | 742 |
| `ich/e9-statistical-principles` | 0 | 2 | 154 | 281 | 0 | 437 |
| `other/45-cfr-part-160` | 4 | 96 | 131 | 7 | 0 | 238 |
| `other/45-cfr-part-164` | 37 | 200 | 245 | 1 | 0 | 483 |
| **TOTAL** | | | | | **32** | **2078** |

**Aggregate coverage:** 32/2110 (1.52%) of all modal-verb occurrences sit inside a `requirement_bearing` span (primary or embedded).

Spans containing modal verbs NOT in req_bearing (after filtering date abbreviations in source_notes): **1021**.

Top candidates by count of modal verbs (eyeball these — each is a possible miss):

- `ich/e6-r3-good-clinical-practice` `S0002` **GUIDELINE FOR GOOD CLINICAL PRACTICE** primary=`?` — verbs: May, may, must, shall
- `ich/e6-r3-good-clinical-practice` `S0281` **3.16.2** primary=`?` — verbs: may, must, should
- `ich/e9-statistical-principles` `S0085` **chapeau** primary=`?` — verbs: may, must, should
- `ich/e9-statistical-principles` `S0118` **chapeau** primary=`?` — verbs: may, must, should
- `other/45-cfr-part-160` `S0468` **§ 160.504(c)** primary=`?` — verbs: may, must, shall
- `fda/guidance-electronic-source-data-clinical-investigations` `S0032` **Source data includes all information in original records and certified copies of original records of** primary=`?` — verbs: must, should
- `fda/guidance-electronic-source-data-clinical-investigations` `S0069` **The eCRF should include the capability to record who entered or generated the data and when it** primary=`?` — verbs: must, should
- `fda/guidance-electronic-source-data-clinical-investigations` `S0076` **Only a clinical investigator(s) or delegated clinical study staff should perform modifications or** primary=`?` — verbs: must, should
- `fda/guidance-electronic-source-data-clinical-investigations` `S0084` **To comply with the requirement to maintain accurate case histories14 clinical investigator(s)** primary=`?` — verbs: must, should
- `fda/guidance-electronic-source-data-clinical-investigations` `S0092` **When data elements are transcribed from paper sources into an eCRF, the clinical investigator(s)** primary=`?` — verbs: may, must
- `fda/guidance-electronic-source-data-clinical-investigations` `S0094` **7** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0080` **Claims representing general concepts often are not supported** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0098` **The conceptual framework of a PRO instrument may be straight** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0116` **Item generation should include input from the target patient** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0122` **If items are not generated in all language groups included i** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0157` **A scoring algorithm creates a single score from multiple ite** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0174` **The degree of respondent burden that is tolerable for instru** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0194` **When patient experience of a concept is predicted to change,** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0197` **The adequacy of an instrument’s development and testing is s** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0219` **Open-label clinical trials, where patients and investigators** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0220` **In blinded clinical trials, patients should be blinded to tr** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0232` **Sometimes patients fail to report for visits, fail to comple** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0237` **The frequency of PRO assessment should correspond with the s** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0239` **The duration of PRO assessment depends on the PRO research q** primary=`?` — verbs: may, should
- `fda/guidance-patient-reported-outcome-measures` `S0243` **Regardless of whether the primary endpoint for the clinical ** primary=`?` — verbs: may, should

## 3. Dropped requirements (verbatim quote couldn't be canonicalized)

Requirements where the LLM's quoted text didn't match its source span even with whitespace/punctuation/hyphen-wrap tolerance. Dropped from the catalog with full context preserved in `docs/<doc>/audit/dropped_quotes.jsonl`.

**Total dropped across all docs: 0**.

## 4. Decomposer-overruled-classifier downgrades

Spans where the classifier said `requirement_bearing` (primary or embedded) but the decomposer found 0 atomic obligations. These are usually fragment list items or purely descriptive content. The classification was downgraded; the requirement count is unaffected (there were no reqs to lose).

### fda/21-cfr-part-11 — 1 downgrades

- `S0053` **§ 11.3(b)(6)** → `definition` — _(6)  Electronic record means any combination of text, graphics, data, audio, pictorial, or other information representation in digital form _

**Total downgrades: 1**.

## 5. Embedded-audit safety net (the Tier-1 catch-mechanism)

Spans the deterministic signal scanner flagged + LLM triaged. Activity here is a quality signal — the system caught buried obligations the classifier didn't.


**Total: 0 spans rescued; 0 false positives filtered.**

## 6. Reconciler-preserved ambiguity

Cases where two parallel agents (A and B) disagreed and the reconciler couldn't merge cleanly. Both interpretations preserved with `ambiguous=true`.

| Doc | Classifications | Requirements | Relationships | Cycles |
|---|---:|---:|---:|---:|
| `fda/21-cfr-part-11` | 0 | 0 | 2 | 0 |
| `fda/guidance-electronic-source-data-clinical-investigations` | 0 | 0 | 0 | 0 |
| `fda/guidance-patient-reported-outcome-measures` | 0 | 0 | 0 | 0 |
| `ich/e6-r3-good-clinical-practice` | 0 | 0 | 0 | 0 |
| `ich/e9-statistical-principles` | 0 | 0 | 0 | 0 |
| `other/45-cfr-part-160` | 0 | 0 | 0 | 0 |
| `other/45-cfr-part-164` | 0 | 0 | 0 | 0 |

## 7. Cross-doc unresolved citations (what to ingest next)

**20** citations in our docs reference parts we have NOT ingested. Top targets (priority ingest list):

| CFR Part | Times referenced |
|---|---:|
| Part 1 | 9 |
| Part 117 | 2 |
| Part 507 | 2 |
| Part 112 | 2 |
| Part 121 | 2 |

## 8. Where to look manually (prioritized)

1. **Dropped quotes (Section 3)** — 2 reqs were dropped. The atomic statements may still be salvageable by hand-fixing the verbatim_quote.
2. **Modal-verb suspects (Section 2)** — eyeball the listed spans to confirm they're legitimate non-obligations (e.g., source notes, scope exclusions). Anything not expected is a candidate miss.
3. **Decomposer-overruled downgrades (Section 4)** — these were spans where the classifier and decomposer disagreed. Most are fragment list items, but rare cases could be real obligations the LLM didn't parse.
4. **Reconciler-preserved ambiguity (Section 6)** — high-ambiguity docs (Part 50, Part 314 in this run) have items worth examining individually. Side-by-side view in `docs/<doc>/audit/review_sidebyside.md` is the fastest path.
5. **Unresolved cross-doc citations (Section 7)** — Part 1 is the most-referenced absent part. Ingesting it would resolve many of those edges.
