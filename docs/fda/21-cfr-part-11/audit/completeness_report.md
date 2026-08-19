# Completeness verification report — fda/21-cfr-part-11

Mechanical checks against the live catalog. Re-runnable any time.

## 1. Source provenance (deterministic)

- PDF: `source.pdf` (73634 bytes)
- PDF sha256: `53cfc4e879e08539a455fc38df1b04bef248e027d4f5caafa7c233406a59cf1b`
- Canonical text: 17510 bytes (after boilerplate strip)
- Canonical sha256: `69bf1669db8758aded8af20593de9e64bae3ae4290b090e8b452833af65b6c5c`
- Coverage report sha matches canonical: **True**

## 2. Boilerplate strip audit

Total stripped lines: **25**.

| Rule | Count |
|---|---:|
| `ECFR_DISCLAIMER` | 1 |
| `PAGE_FOOTER_CITATION_BARE` | 5 |
| `PAGE_FOOTER_COMBINED` | 6 |
| `PAGE_HEADER_DOC_TITLE` | 6 |
| `PAGE_HEADER_PART_DATE` | 6 |
| `PAGE_HEADER_PART_PUBDATE` | 1 |

## 3. Byte coverage (re-verified)

- Spans: **105**  Overlaps: **0**  Gaps: **0**  Coverage: **100.0000%**

## 4. Citation enumeration

- Paragraph markers in canonical: **26** unique  in spans: **26**  missing: **0**
- Section headers in canonical: **10**  in spans: **10**  missing: **0**

## 5. Modal-verb coverage (sniff test, compound-label aware)

| Verb | Total | In requirement_bearing (primary OR embedded) | In neither |
|---|---:|---:|---:|
| `shall` | 25 | 25 | 0 |
| `must` | 1 | 1 | 0 |
| `may` | 6 | 5 | 1 |
| `should` | 1 | 1 | 0 |

### Spans containing modal verbs in NEITHER primary nor embedded `requirement_bearing`

- **`S0039` `amendment_note`** primary=**source_note** — contains: `May`
  - text: _[62 FR 13464, Mar. 20, 1997, as amended at 69 FR 71655, Dec. 9, 2004; 79 FR 71253, 71291, Dec. 1, 2014; 80 FR 56144, 56336, Sept. 17, 2015; 80 FR 74352, 74547, 74667, Nov. 27, 2015; 81 FR 20170, Apr. _

## 6. Requirements-per-span sanity check

| Reqs per span | Spans |
|---:|---:|
| 1 | 19 |
| 2 | 17 |
| 3 | 7 |
| 4 | 7 |
| 5 | 4 |
| 6 | 2 |
| 8 | 1 |
| 11 | 1 |

Most-decomposed span: **§ 11.10(e)** (`S0064`) → 11 requirements.

## 7. Pending downgrades (decomposer/classifier disagreement, awaiting adjudication)

- Spans flagged `downgrade_pending`: **0**
