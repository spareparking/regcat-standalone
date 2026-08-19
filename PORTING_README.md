# Porting guide: regcat → drug product label extraction

This package was built to decompose **regulations** (CFR parts, ICH
guidelines) into atomic requirements. The target context of use is now
**drug product labels** (prescribing information) presented as PDFs. This
guide maps what transfers unchanged, what must be replaced, and where the
validation effort should concentrate. It was written by the session that
reviewed the whole system; file references are exact.

---

## 1. What transfers unchanged — do not rewrite these

### The coverage backbone (the reason to reuse this system at all)

| Piece | File(s) | Why it's domain-agnostic |
|---|---|---|
| PDF → text ingest | `stages/ingest.py` | PyMuPDF page extraction, SHA-256 provenance |
| Boilerplate strip framework | `stages/boilerplate.py` | Rule-driven; every removal logged as a `StrippedSpan` with its `rule_id` (provable stripping). Only the *rules* are doc-specific — see §2. |
| Byte-offset, gap-free segmentation contract | `parsers/base.py` | "Every byte falls inside exactly one Span" — parsers record span *starts* only; ends are derived, so gaps are structurally impossible |
| The hard coverage gate | `stages/audit.py` | Pure code, no LLM: 100.0% byte coverage, no overlaps/gaps, every span classified, every extraction's `verbatim_quote` an exact substring of its span. **This is the guarantee being ported.** |
| A/B agents + reconciler pattern | `stages/classify.py`, `stages/decompose.py` | Two personas, cheap-agreement short-circuit, reconciler only on disagreement |
| Ambiguity preservation / `downgrade_pending` | `stages/decompose.py`, `agent_packets.py` | Disagreements are never silently resolved; finalize blocks until adjudicated |
| Agent-packet workflow | `agent_packets.py` | Filesystem work packets, claims with locking, exactly-one-output-per-input validation both directions, atomic backed-up merges |
| LLM client | `llm.py` | Anthropic / OpenAI / claude-code / mock; 3-layer retry (JSON-validity feedback, provider backoff, regex repair); image-input hook (`complete_json_with_images`) — you will want this for label tables/figures |
| Multi-doc registry | `registry.py` | `docs/<jurisdiction>/<short_id>/` layout, per-doc `meta.json` as source of truth |
| Degenerate-span guard | `text_quality.py` | Detects figure/table word-salad before it reaches an LLM. **Labels are table-heavy — keep and expect to tune** |
| Cross-doc IDs | `global_ids.py` | `<doc_id>:<local_id>` |

Also keep the *process* conventions: resumable append-only JSONL outputs,
per-stage artifacts on disk, mock fixtures for offline replay, and the
re-run of `audit` + `validate_rel` after any stage that mutates the catalog.

### The prompt *engineering pattern* (rewrite content, keep structure)

The prompts in `prompts/` are domain-specific text, but their **structure**
was hard-won and should be reproduced in the label domain:

- Two deliberately different personas per stage (legal analyst vs. software
  architect), one biased toward recall ("missing X is far worse than
  over-flagging").
- Numbered **fidelity rules** encoding real observed failure modes — e.g.
  list-polarity propagation (a bullet under "avoid the following:" is a
  prohibition), enumeration completeness ("emit an atom for EVERY member,
  INCLUDING THE LAST ONE"), no hallucinated clauses, "verbatim_quote must
  appear character-for-character — the pipeline rejects it otherwise".
- Reconciler rules that are unionist on flags, prefer the finer split, and
  emit `ambiguous` + `alternates` on unresolvable disagreement.
- Every system prompt ends with a literal JSON output schema; every user
  template ends with "Output JSON only."

---

## 2. What must be replaced for drug labels

Replace these in roughly this order; each is independently testable.

### 2.1 Segmenter — the main build

Drug labels in **PLR format (21 CFR 201.56 / 201.57)** have strong, stable
structure that deserves its own segmenter, exactly the way ICH got one:

- **Highlights of Prescribing Information** (its own mini-sections: boxed
  warning summary, indications, dosage, dosage forms, contraindications,
  warnings, adverse reactions, drug interactions, use in specific
  populations, revision date)
- **Full Prescribing Information: Contents** (a TOC — map to `TOC_ENTRY`)
- **Boxed warning** (all-caps, box-delimited)
- **Numbered sections 1–17** with decimal subsections (`6.1 Clinical Trials
  Experience`, `8.1 Pregnancy`) — structurally close to `ICHSegmenter`'s
  `RX_DECIMAL` + `decimal_parent()` prefix-walk tree building; start from a
  copy of `parsers/ich.py`, not `parsers/cfr.py` (the CFR paragraph-letter
  machinery is irrelevant here)

Concrete steps:

1. Add `plr` (or `spl`) to `CitationFormat` in `registry.py`.
2. Write `parsers/plr.py` following the ICH template: line scan, byte
   offsets, start-only span records, `emitted[0].byte_start = 0` pinned,
   furniture regexes for the manufacturer's running headers/footers.
3. Wire it in `stages/segment.py`'s `_segmenter_for()`.
4. Citation scheme: section-number paths (`"6.1"`, `"BOXED WARNING"`,
   `"HIGHLIGHTS/DOSAGE"`) in `Citation.section`/`Citation.raw`. The CFR
   title/part fields can stay `None` — nothing downstream requires them.
5. **`GenericSegmenter` is your day-one fallback.** It runs on any prose PDF
   (blank-line blocking) and passes the coverage gate. Get the pipeline
   running end-to-end with `--citation-format generic` first, then swap in
   the PLR segmenter and diff span quality.

Older labels not in PLR format (pre-2006 generic labels are common) will not
match PLR structure — keep `generic` as the registered format for those.

### 2.2 Classification taxonomy

`ClassificationLabel` in `schemas.py` is regulatory: `requirement_bearing`,
`scope_exclusion`, `cross_reference`, … A label wants **content classes**,
e.g.: `indication`, `dosage_administration`, `contraindication`,
`boxed_warning`, `warning_precaution`, `adverse_reaction`,
`drug_interaction`, `specific_population`, `clinical_pharmacology`,
`clinical_studies`, `how_supplied_storage`, `patient_counseling`,
`structural`, plus whatever your downstream consumer needs.

Keep the **compound primary + embedded** model — it maps well (e.g. a
dosage section that embeds a contraindication note). Keep the rule that the
extraction stage runs on any span where an extraction-worthy label appears
in primary *or* embedded.

Grep for the string `requirement_bearing` across `stages/`,
`agent_packets.py`, and `render/markdown.py` — it is the pivot label that
gates decomposition, the downgrade machinery, and rendering. Decide your
equivalent pivot (e.g. "clinically actionable statement") and rename
consistently.

### 2.3 Extraction schema (`AtomicRequirement`)

`modality` (shall/should/may), `subject` ("persons using closed systems"),
`object` — these are obligation concepts. A label atom probably wants:
statement type (indication / dose instruction / warning / interaction /
monitoring requirement…), population/condition qualifiers, dose + route +
frequency fields where applicable, and severity/box status. Keep:
`verbatim_quote` (non-negotiable — the audit depends on it),
`atomic_statement`, `applicability_tags`, `conditions`, `ambiguous` +
`alternates`.

### 2.4 Prompts

All five families (`prompts/classify.py`, `decompose.py`, `embedded.py`,
`relate.py`, `adjudicate.py`) need rewriting for label semantics, preserving
the structure described in §1. Label-domain fidelity rules to encode (the
analogues of the CFR negation/polarity rules):

- Never drop a population qualifier ("in patients with renal impairment").
- Never merge distinct dose regimens (starting vs. maintenance vs.
  max dose; adult vs. pediatric) into one atom.
- Table rows are co-equal enumerations — every row becomes an atom,
  including the last one.
- "Not recommended" vs. "contraindicated" vs. "avoid" are different
  strengths — never upgrade or downgrade between them.
- Frequencies/percentages in adverse-reaction text must be copied exactly,
  never rounded or summarized.

### 2.5 `signals.py`

The obligation detectors (shall/must, nominalized imperatives,
`remain_subject_to`) are meaningless for labels. The embedded-audit stage is
still valuable — its label analogue hunts clinically significant statements
hiding in "wrong" sections (a contraindication mentioned inside Clinical
Studies, a dose adjustment inside Drug Interactions). Replace the pattern
groups with label signals: `contraindicat\w+`, `do not`, `avoid`,
`discontinue`, `fatal|death|serious`, `dose (reduction|adjustment)`,
`monitor\w*`, `pregnan\w+`, `renal|hepatic impairment`, boxed-warning
keywords. Keep the recall-over-precision bias and the downstream LLM triage.
Note the date-false-positive guard on `may` — labels have revision dates
too; keep it.

### 2.6 Relationship types

`RelationshipType` (refines, exception_to, conditional_on, defined_by,
composed_of, references) partially transfers. Label-relevant candidates:
dose-adjustment-modifies-base-dose, contraindication-limits-indication,
interaction-triggers-dose-change, warning-references-adverse-reaction.
Decide whether the relate stage earns its cost in v1 at all — it is cleanly
skippable (`--stages` flag) and the validator tolerates an absent
relationships file.

### 2.7 Boilerplate rules

`_BASE_RULES` strip eCFR page furniture. Labels need: manufacturer running
headers/footers, "Reference ID: <n>" lines (FDA submission stamps), page
`X of Y` footers, and the `FULL PRESCRIBING INFORMATION: CONTENTS` dot
leaders if you choose to strip rather than span them. Follow the existing
pattern: every rule gets a `rule_id`, every removal is logged.

### 2.8 Renderer

`render/markdown.py` hardcodes the H1 "Catalog — 21 CFR Part 11 …" and a
"Definitions (§ 11.3)" header (known deficiency, pre-existing). Rebuild the
section grouping around label sections 1–17; the span appendix, ambiguity
index, and coverage summary transfer as-is.

---

## 3. Known weak points to test hardest (from the pre-port review)

1. **Tables.** Labels are dense with adverse-reaction and dosage tables and
   multi-column layouts. PyMuPDF `get_text("text", sort=True)` will produce
   scrambled word-order there. Mitigations already in the codebase: the
   degenerate-span guard (`text_quality.py` — expect to *lower* its
   thresholds: label tables are smaller than CFR figure salad, so tune
   `DEGENERATE_MIN_CHARS`/`DEGENERATE_WS_RATIO` against real spans) and the
   image-input path (`llm.complete_json_with_images`) for a vision pass over
   table/figure pages. Plan a dedicated table-extraction validation set
   early; this is where the port will succeed or fail.
2. **Multi-column Highlights layout.** The Highlights section is typically
   two-column; verify reading order on real PDFs before trusting the
   segmenter. If order is scrambled, consider a per-page column split at
   ingest (PyMuPDF gives block coordinates) *before* canonicalization —
   never after, or byte offsets desync.
3. **`live`-mode Anthropic retries.** `complete_json` retries JSON-decode
   failures but a provider exception in `live` mode is immediately fatal
   (transient-retry wrappers exist only for claude-code and OpenAI). If you
   use `--mode live` for long runs, add a retry wrapper mirroring
   `_call_claude_code_with_provider_retries`.
4. **Coverage ≠ correctness.** The audit proves every byte was *attributed*,
   not that classification/extraction is *right*. Build a labeled validation
   corpus (a handful of diverse labels — new PLR biologic, old-format
   generic, table-heavy oncology drug) and score classification/extraction
   against human annotation before trusting throughput runs.
5. **Default model names** in `llm.py` (`DEFAULT_ANTHROPIC_MODEL`,
   `DEFAULT_OPENAI_MODEL`) reflect this repo's era — check them against
   current model availability; override via `ANTHROPIC_MODEL`/`OPENAI_MODEL`
   env vars without code changes.

---

## 4. Suggested porting sequence

1. `pip install -e ".[dev]"` → `pytest` green (offline).
2. `regcat run --doc fda/21-cfr-part-11 --mode mock --root .` → replay the
   reference doc end-to-end; read the artifacts it produces so you know what
   "done" looks like (`docs/fda/21-cfr-part-11/{source,catalog,audit}/`).
3. Ingest one real label with `--citation-format generic`; run only
   `--stages ingest,boilerplate,segment,audit` (deterministic, no LLM) and
   inspect `spans.jsonl` + the coverage log. Iterate boilerplate rules here.
4. Build the PLR segmenter (§2.1) against 3–5 real labels; port the
   segmenter test style from `tests/test_ich_segmenter.py` (the tests assert
   the gap-free invariant and specific structural fixes — do the same for
   Highlights/boxed-warning/section-tree cases).
5. Replace taxonomy + schemas + prompts (§2.2–2.4); create mock fixtures for
   one label so the full pipeline replays offline in CI.
6. Replace signals (§2.5); decide on relate (§2.6); rebuild the renderer
   (§2.8).
7. Only then run live-LLM validation against the annotated corpus (§3.4).

Everything in `stages/audit.py` and `parsers/base.py` should survive the
port byte-for-byte. If you find yourself editing the audit gate to make a
run pass, stop — that is the system telling you the port has a real defect
upstream.
