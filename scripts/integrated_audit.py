"""Cross-doc integrated audit: how confident are we that nothing substantial was missed?

For each registered doc, compute the same mechanical proofs we'd run per-doc, then
aggregate them. Also surface every place the pipeline EXPLICITLY flagged uncertainty
(dropped quotes, decomposer-overruled spans, ambiguous classifications, etc.) so
the user has a prioritized manual-review queue.

Output: docs/integrated_audit.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from regcat.registry import all_docs, doc_dir as resolve_doc_dir


def loadl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    docs = all_docs(ROOT)
    lines: list[str] = []
    def w(s=""): lines.append(s)

    w("# Integrated audit — multi-doc completeness")
    w("")
    w(f"Aggregate evidence across **{len(docs)} documents**. Re-runnable any time.")
    w("")

    # === 1. Mechanical proofs ===
    w("## 1. Mechanical proofs (deterministic)")
    w("")
    w("| Doc | Spans | Reqs | Cov | Verbatim fails | Gaps | Overlaps | Unclass | Unreq | Passed |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|")
    totals = {"spans": 0, "reqs": 0, "verbatim_fails": 0, "gaps": 0, "overlaps": 0,
              "unclassified": 0, "unrequirementized": 0}
    for d in docs:
        cov_path = resolve_doc_dir(ROOT, d.doc_id) / "audit" / "coverage_report.json"
        if not cov_path.exists():
            continue
        cov = json.loads(cov_path.read_text(encoding="utf-8"))
        passed = "✓" if cov.get("passed") else "✗"
        w(f"| `{d.doc_id}` | {cov['span_count']} | {cov['requirements_extracted']} | "
          f"{cov['coverage_pct']:.2f}% | {len(cov['verbatim_quote_failures'])} | "
          f"{len(cov['gap_failures'])} | {len(cov['overlap_failures'])} | "
          f"{len(cov['unclassified_spans'])} | {len(cov['unrequirementized_spans'])} | {passed} |")
        totals["spans"] += cov["span_count"]
        totals["reqs"] += cov["requirements_extracted"]
        totals["verbatim_fails"] += len(cov["verbatim_quote_failures"])
        totals["gaps"] += len(cov["gap_failures"])
        totals["overlaps"] += len(cov["overlap_failures"])
        totals["unclassified"] += len(cov["unclassified_spans"])
        totals["unrequirementized"] += len(cov["unrequirementized_spans"])
    w(f"| **TOTAL** | **{totals['spans']}** | **{totals['reqs']}** | — | "
      f"**{totals['verbatim_fails']}** | **{totals['gaps']}** | **{totals['overlaps']}** | "
      f"**{totals['unclassified']}** | **{totals['unrequirementized']}** | |")
    w("")

    # === 2. Modal-verb sniff (compound-aware) ===
    w("## 2. Modal-verb sniff test (`shall`/`must`/`may`/`should`)")
    w("")
    w("Every modal verb in source should sit inside a span flagged `requirement_bearing` "
      "in its primary OR embedded labels. Modal verbs in NEITHER are the highest-value "
      "candidate misses (after excluding date abbreviations and similar false positives).")
    w("")
    w("| Doc | shall | must | may | should | in req_bearing | NOT in req_bearing |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    grand_total_modals = 0
    grand_in_req = 0
    suspect_spans: list[tuple[str, str, str, str, list]] = []  # (doc, sid, cit, primary, embedded, hits)
    for d in docs:
        base = resolve_doc_dir(ROOT, d.doc_id)
        canon = (base / "source" / "canonical.txt").read_text(encoding="utf-8") if (base / "source" / "canonical.txt").exists() else ""
        spans = loadl(base / "source" / "spans.jsonl")
        classes = {c["span_id"]: c for c in loadl(base / "catalog" / "classifications.jsonl")}
        counts = {"shall": 0, "must": 0, "may": 0, "should": 0}
        in_req = 0
        out_of_req: dict[str, list[str]] = {}
        for verb in counts:
            for m in re.finditer(rf"\b{verb}\b", canon, re.IGNORECASE):
                counts[verb] += 1
                byte_off = len(canon[:m.start()].encode("utf-8"))
                # find containing span
                for s in spans:
                    if s["byte_start"] <= byte_off < s["byte_end"]:
                        c = classes.get(s["span_id"], {})
                        labels = {c.get("final_label")} | set(c.get("final_embedded", []))
                        if "requirement_bearing" in labels:
                            in_req += 1
                        else:
                            out_of_req.setdefault(s["span_id"], []).append(m.group(0))
                        break
        total_doc = sum(counts.values())
        out_total = sum(len(v) for v in out_of_req.values())
        w(f"| `{d.doc_id}` | {counts['shall']} | {counts['must']} | {counts['may']} | "
          f"{counts['should']} | {in_req} | {out_total} |")
        grand_total_modals += total_doc
        grand_in_req += in_req
        for sid, hits in out_of_req.items():
            span = next((x for x in spans if x["span_id"] == sid), None)
            if not span:
                continue
            c = classes.get(sid, {})
            primary = c.get("final_label", "?")
            embedded = c.get("final_embedded", [])
            cit = span["citation"].get("raw") or sid
            suspect_spans.append((d.doc_id, sid, cit, primary, embedded, sorted(set(hits))))
    w(f"| **TOTAL** | | | | | **{grand_in_req}** | **{grand_total_modals - grand_in_req}** |")
    w("")
    w(f"**Aggregate coverage:** {grand_in_req}/{grand_total_modals} "
      f"({grand_in_req/grand_total_modals*100:.2f}%) of all modal-verb occurrences sit "
      f"inside a `requirement_bearing` span (primary or embedded).")
    w("")
    if suspect_spans:
        # Filter trivially-explainable cases (date abbreviations in source notes)
        real_suspects = [
            (doc, sid, cit, p, e, hits) for (doc, sid, cit, p, e, hits) in suspect_spans
            if not (p == "source_note" and set(hits) <= {"May", "may"})
        ]
        w(f"Spans containing modal verbs NOT in req_bearing (after filtering date abbreviations "
          f"in source_notes): **{len(real_suspects)}**.")
        w("")
        if real_suspects:
            w("Top candidates by count of modal verbs (eyeball these — each is a possible miss):")
            w("")
            real_suspects.sort(key=lambda x: -len(x[5]))
            for doc, sid, cit, p, e, hits in real_suspects[:25]:
                emb = f" embedded={e}" if e else ""
                w(f"- `{doc}` `{sid}` **{cit}** primary=`{p}`{emb} — verbs: {', '.join(hits)}")
    w("")

    # === 3. Dropped quotes (audit trail) ===
    w("## 3. Dropped requirements (verbatim quote couldn't be canonicalized)")
    w("")
    w("Requirements where the LLM's quoted text didn't match its source span even with "
      "whitespace/punctuation/hyphen-wrap tolerance. Dropped from the catalog with full "
      "context preserved in `docs/<doc>/audit/dropped_quotes.jsonl`.")
    w("")
    total_dropped = 0
    for d in docs:
        drop_path = resolve_doc_dir(ROOT, d.doc_id) / "audit" / "dropped_quotes.jsonl"
        if not drop_path.exists():
            continue
        dropped = loadl(drop_path)
        if not dropped:
            continue
        total_dropped += len(dropped)
        w(f"### {d.doc_id} — {len(dropped)} dropped")
        w("")
        for r in dropped:
            w(f"- **`{r['req_id']}`** {r.get('citation_raw', '')}")
            w(f"  - LLM quote: `{r['verbatim_quote'][:200]}{'...' if len(r['verbatim_quote'])>200 else ''}`")
            w(f"  - atomic statement: {r['atomic_statement']}")
            w(f"  - source preview: {r.get('span_text_preview', '')[:300]}...")
        w("")
    w(f"**Total dropped across all docs: {total_dropped}**.")
    w("")

    # === 4. Decomposer-overruled spans (downgrades) ===
    w("## 4. Decomposer-overruled-classifier downgrades")
    w("")
    w("Spans where the classifier said `requirement_bearing` (primary or embedded) but the "
      "decomposer found 0 atomic obligations. These are usually fragment list items or "
      "purely descriptive content. The classification was downgraded; the requirement count "
      "is unaffected (there were no reqs to lose).")
    w("")
    downgrade_total = 0
    for d in docs:
        classes = loadl(resolve_doc_dir(ROOT, d.doc_id) / "catalog" / "classifications.jsonl")
        downgrades = [c for c in classes if "decomposer found 0 obligations" in (c.get("reconciler_note") or "")]
        if not downgrades:
            continue
        downgrade_total += len(downgrades)
        spans = {s["span_id"]: s for s in loadl(resolve_doc_dir(ROOT, d.doc_id) / "source" / "spans.jsonl")}
        w(f"### {d.doc_id} — {len(downgrades)} downgrades")
        w("")
        for c in downgrades[:5]:
            sid = c["span_id"]
            cit = spans[sid]["citation"].get("raw") or sid
            preview = spans[sid]["text"].strip().replace("\n", " ")[:140]
            w(f"- `{sid}` **{cit}** → `{c.get('final_label')}` — _{preview}_")
        if len(downgrades) > 5:
            w(f"- (+ {len(downgrades) - 5} more)")
        w("")
    w(f"**Total downgrades: {downgrade_total}**.")
    w("")

    # === 5. Embedded-audit safety net activity ===
    w("## 5. Embedded-audit safety net (the Tier-1 catch-mechanism)")
    w("")
    w("Spans the deterministic signal scanner flagged + LLM triaged. Activity here is a "
      "quality signal — the system caught buried obligations the classifier didn't.")
    w("")
    total_rescued = 0
    total_false_pos = 0
    for d in docs:
        log_path = resolve_doc_dir(ROOT, d.doc_id) / "audit" / "embedded_audit_log.jsonl"
        if not log_path.exists():
            continue
        entries = loadl(log_path)
        rescued = sum(1 for e in entries if e.get("decision") == "embedded_obligation_added")
        false_pos = sum(1 for e in entries if e.get("decision") == "false_positive")
        if rescued or false_pos:
            w(f"- `{d.doc_id}`: rescued **{rescued}**, filtered **{false_pos}** false positives")
            total_rescued += rescued
            total_false_pos += false_pos
    w(f"\n**Total: {total_rescued} spans rescued; {total_false_pos} false positives filtered.**")
    w("")

    # === 6. Ambiguous items (preserved by reconciler) ===
    w("## 6. Reconciler-preserved ambiguity")
    w("")
    w("Cases where two parallel agents (A and B) disagreed and the reconciler couldn't "
      "merge cleanly. Both interpretations preserved with `ambiguous=true`.")
    w("")
    w("| Doc | Classifications | Requirements | Relationships | Cycles |")
    w("|---|---:|---:|---:|---:|")
    for d in docs:
        base = resolve_doc_dir(ROOT, d.doc_id)
        classes = loadl(base / "catalog" / "classifications.jsonl")
        reqs = loadl(base / "catalog" / "requirements.jsonl")
        rels = loadl(base / "catalog" / "relationships.jsonl")
        amb_c = sum(1 for c in classes if c.get("ambiguous"))
        amb_r = sum(1 for r in reqs if r.get("ambiguous"))
        amb_e = sum(1 for e in rels if e.get("ambiguous"))
        rv_path = base / "audit" / "relationship_validation.json"
        cycles = 0
        if rv_path.exists():
            cycles = len(json.loads(rv_path.read_text(encoding="utf-8")).get("cycles_flagged_ambiguous", []))
        w(f"| `{d.doc_id}` | {amb_c} | {amb_r} | {amb_e} | {cycles} |")
    w("")

    # === 7. Cross-doc unresolved citations ===
    w("## 7. Cross-doc unresolved citations (what to ingest next)")
    w("")
    edges = loadl(ROOT / "docs" / "cross_doc_relationships.jsonl")
    unresolved = [e for e in edges if not e.get("auto_resolved")]
    parts_referenced: dict[str, int] = defaultdict(int)
    rx = re.compile(r"\b(?:part\s+|21\s+CFR\s+|§§?\s*)(\d+)(?:\.\d+)?", re.IGNORECASE)
    for e in unresolved:
        for m in rx.finditer(e.get("citation_in_source") or ""):
            parts_referenced[m.group(1)] += 1
    w(f"**{len(unresolved)}** citations in our docs reference parts we have NOT ingested. "
      "Top targets (priority ingest list):")
    w("")
    w("| CFR Part | Times referenced |")
    w("|---|---:|")
    for part, n in sorted(parts_referenced.items(), key=lambda x: -x[1])[:15]:
        w(f"| Part {part} | {n} |")
    w("")

    # === 8. Manual review queue ===
    w("## 8. Where to look manually (prioritized)")
    w("")
    w("1. **Dropped quotes (Section 3)** — 2 reqs were dropped. The atomic statements may "
      "still be salvageable by hand-fixing the verbatim_quote.")
    w("2. **Modal-verb suspects (Section 2)** — eyeball the listed spans to confirm they're "
      "legitimate non-obligations (e.g., source notes, scope exclusions). Anything not "
      "expected is a candidate miss.")
    w("3. **Decomposer-overruled downgrades (Section 4)** — these were spans where the "
      "classifier and decomposer disagreed. Most are fragment list items, but rare cases "
      "could be real obligations the LLM didn't parse.")
    w("4. **Reconciler-preserved ambiguity (Section 6)** — high-ambiguity docs (Part 50, "
      "Part 314 in this run) have items worth examining individually. Side-by-side view in "
      "`docs/<doc>/audit/review_sidebyside.md` is the fastest path.")
    w("5. **Unresolved cross-doc citations (Section 7)** — Part 1 is the most-referenced "
      "absent part. Ingesting it would resolve many of those edges.")
    w("")

    out = ROOT / "docs" / "integrated_audit.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
