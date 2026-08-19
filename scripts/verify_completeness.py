"""Hard, deterministic completeness checks on a doc's live catalog.

Re-runnable any time:

    python scripts/verify_completeness.py --doc fda/21-cfr-part-11

Writes docs/<doc_id>/audit/completeness_report.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from regcat.registry import doc_dir as resolve_doc_dir


def loadl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True, help="doc_id, e.g. fda/21-cfr-part-11")
    args = ap.parse_args()

    base = resolve_doc_dir(ROOT, args.doc)
    PDF        = base / "source.pdf"
    CANON_TXT  = base / "source" / "canonical.txt"
    CANON_JSON = base / "source" / "canonical.json"
    SPANS      = base / "source" / "spans.jsonl"
    CLASSES    = base / "catalog" / "classifications.jsonl"
    REQS       = base / "catalog" / "requirements.jsonl"
    RELS       = base / "catalog" / "relationships.jsonl"
    RECON      = base / "audit" / "reconciler_log.jsonl"
    COV        = base / "audit" / "coverage_report.json"
    OUT        = base / "audit" / "completeness_report.md"

    lines = []
    def w(s=""):
        lines.append(s)

    pdf_bytes = PDF.read_bytes()
    pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()
    canonical = CANON_TXT.read_text(encoding="utf-8")
    canon_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    cov = json.loads(COV.read_text(encoding="utf-8"))
    canon_json = json.loads(CANON_JSON.read_text(encoding="utf-8"))
    spans = loadl(SPANS)
    spans_by_id = {s["span_id"]: s for s in spans}
    classifications = {c["span_id"]: c for c in loadl(CLASSES)}
    reqs = loadl(REQS)
    rels = loadl(RELS)
    recon = loadl(RECON) if RECON.exists() else []

    w(f"# Completeness verification report — {args.doc}")
    w("")
    w("Mechanical checks against the live catalog. Re-runnable any time.")
    w("")

    w("## 1. Source provenance (deterministic)")
    w("")
    w(f"- PDF: `{PDF.name}` ({len(pdf_bytes)} bytes)")
    w(f"- PDF sha256: `{pdf_sha}`")
    w(f"- Canonical text: {len(canonical.encode('utf-8'))} bytes (after boilerplate strip)")
    w(f"- Canonical sha256: `{canon_sha}`")
    w(f"- Coverage report sha matches canonical: **{cov['canonical_source_sha256'] == canon_sha}**")
    w("")

    w("## 2. Boilerplate strip audit")
    w("")
    stripped = canon_json["stripped"]
    rule_counts: dict[str, int] = {}
    for s in stripped:
        rule_counts[s["rule_id"]] = rule_counts.get(s["rule_id"], 0) + 1
    w(f"Total stripped lines: **{len(stripped)}**.")
    w("")
    w("| Rule | Count |")
    w("|---|---:|")
    for r, c in sorted(rule_counts.items()):
        w(f"| `{r}` | {c} |")
    w("")

    w("## 3. Byte coverage (re-verified)")
    w("")
    by_start = sorted(spans, key=lambda s: s["byte_start"])
    prev_end = 0
    overlap = 0
    gaps = []
    for s in by_start:
        if s["byte_start"] < prev_end:
            overlap += 1
        if s["byte_start"] > prev_end:
            gaps.append((prev_end, s["byte_start"]))
        prev_end = max(prev_end, s["byte_end"])
    canonical_bytes = len(canonical.encode("utf-8"))
    if prev_end < canonical_bytes:
        gaps.append((prev_end, canonical_bytes))
    w(f"- Spans: **{len(spans)}**  Overlaps: **{overlap}**  Gaps: **{len(gaps)}**  "
      f"Coverage: **{(prev_end / canonical_bytes * 100):.4f}%**")
    w("")

    w("## 4. Citation enumeration")
    w("")
    para_pattern = re.compile(r"^\(([a-z0-9ivxlcdm]{1,5})\)", re.MULTILINE)
    found_markers = [(m.group(1), m.start()) for m in para_pattern.finditer(canonical)]
    span_markers = set()
    for s in spans:
        cit = s.get("citation", {})
        if cit.get("paragraphs"):
            span_markers.add(cit["paragraphs"][-1])
    found_marker_set = {m for m, _ in found_markers}
    missing = found_marker_set - span_markers
    w(f"- Paragraph markers in canonical: **{len(found_marker_set)}** unique  "
      f"in spans: **{len(span_markers & found_marker_set)}**  missing: **{len(missing)}**")
    section_pattern = re.compile(r"^§\s*(\d+\.\d+)\s", re.MULTILINE)
    found_sections = {m.group(1) for m in section_pattern.finditer(canonical)}
    span_sections = {s["citation"]["section"] for s in spans if s["kind"] == "section_header" and s["citation"].get("section")}
    missing_sections = found_sections - span_sections
    w(f"- Section headers in canonical: **{len(found_sections)}**  in spans: "
      f"**{len(span_sections)}**  missing: **{len(missing_sections)}**")
    w("")

    w("## 5. Modal-verb coverage (sniff test, compound-label aware)")
    w("")
    canonical_bytes_b = canonical.encode("utf-8")
    def find_span_for_byte(byte_off: int):
        for s in spans:
            if s["byte_start"] <= byte_off < s["byte_end"]:
                return s
        return None
    modal_findings = {"shall": [], "must": [], "may": [], "should": []}
    for verb in modal_findings:
        for m in re.finditer(rf"\b{verb}\b", canonical, re.IGNORECASE):
            byte_off = len(canonical[:m.start()].encode("utf-8"))
            span = find_span_for_byte(byte_off)
            if not span:
                modal_findings[verb].append((byte_off, "(no span)", "(unclassified)", [], False, m.group(0)))
                continue
            c_rec = classifications.get(span["span_id"], {})
            primary = c_rec.get("final_label", "(unclassified)")
            embedded = c_rec.get("final_embedded", []) or []
            labels = {primary} | set(embedded)
            in_req = "requirement_bearing" in labels
            modal_findings[verb].append((byte_off, span["span_id"], primary, embedded, in_req, m.group(0)))
    w("| Verb | Total | In requirement_bearing (primary OR embedded) | In neither |")
    w("|---|---:|---:|---:|")
    suspect = []
    for verb in ("shall", "must", "may", "should"):
        hits = modal_findings[verb]
        in_req = sum(1 for _, _, _, _, ir, _ in hits if ir)
        other = len(hits) - in_req
        w(f"| `{verb}` | {len(hits)} | {in_req} | {other} |")
        for _, sid, primary, embedded, ir, hit in hits:
            if not ir and sid != "(no span)":
                cit = spans_by_id[sid]["citation"].get("raw") or sid
                suspect.append((sid, cit, hit, primary, embedded))
    w("")
    if suspect:
        w("### Spans containing modal verbs in NEITHER primary nor embedded `requirement_bearing`")
        w("")
        from collections import defaultdict
        grouped = defaultdict(list)
        for sid, cit, hit, primary, embedded in suspect:
            grouped[sid].append((cit, hit, primary, embedded))
        for sid, items in grouped.items():
            span = spans_by_id[sid]
            verbs_here = sorted({hit for _, hit, _, _ in items})
            primary = items[0][2]
            embedded = items[0][3]
            cit = items[0][0]
            preview = span["text"].strip().replace("\n", " ")[:200]
            emb_str = f" (also embedded: {embedded})" if embedded else ""
            w(f"- **`{sid}` `{cit}`** primary=**{primary}**{emb_str} — contains: "
              f"{', '.join(f'`{v}`' for v in verbs_here)}")
            w(f"  - text: _{preview}_")
        w("")

    w("## 6. Requirements-per-span sanity check")
    w("")
    from collections import Counter
    per_span = Counter(r["source_span_id"] for r in reqs)
    by_count = {}
    for sid, n in per_span.items():
        by_count.setdefault(n, []).append(sid)
    w("| Reqs per span | Spans |")
    w("|---:|---:|")
    for n in sorted(by_count.keys()):
        w(f"| {n} | {len(by_count[n])} |")
    if per_span:
        biggest = max(per_span.items(), key=lambda x: x[1])
        bsid, bn = biggest
        bcit = spans_by_id[bsid]["citation"].get("raw") or bsid
        w("")
        w(f"Most-decomposed span: **{bcit}** (`{bsid}`) → {bn} requirements.")
    w("")

    w("## 7. Pending downgrades (decomposer/classifier disagreement, awaiting adjudication)")
    w("")
    pending_dg = [c for c in classifications.values() if c.get("downgrade_pending")]
    w(f"- Spans flagged `downgrade_pending`: **{len(pending_dg)}**")
    for c in pending_dg:
        sid = c["span_id"]
        cit = spans_by_id[sid]["citation"].get("raw") or sid
        prop = c.get("downgrade_proposal") or {}
        w(f"  - `{sid}` **{cit}** — final=`{c.get('final_label')}`; proposed="
          f"`{prop.get('proposed_label')}` (kind={prop.get('kind')}, source={prop.get('source')})")
    w("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
