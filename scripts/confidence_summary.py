"""Summarize mechanical proofs + explicitly-flagged uncertainties for one doc.

Usage:
    python scripts/confidence_summary.py --doc fda/21-cfr-part-11

Writes docs/<doc_id>/audit/confidence_summary.md.
"""
from __future__ import annotations

import argparse
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
    ap.add_argument("--doc", required=True)
    args = ap.parse_args()

    base = resolve_doc_dir(ROOT, args.doc)
    cov = json.loads((base / "audit" / "coverage_report.json").read_text(encoding="utf-8"))
    rel_val = json.loads((base / "audit" / "relationship_validation.json").read_text(encoding="utf-8"))
    classes = loadl(base / "catalog" / "classifications.jsonl")
    reqs = loadl(base / "catalog" / "requirements.jsonl")
    rels = loadl(base / "catalog" / "relationships.jsonl")
    recon = loadl(base / "audit" / "reconciler_log.jsonl") if (base / "audit" / "reconciler_log.jsonl").exists() else []
    emb_log = loadl(base / "audit" / "embedded_audit_log.jsonl") if (base / "audit" / "embedded_audit_log.jsonl").exists() else []
    spans_by_id = {s["span_id"]: s for s in loadl(base / "source" / "spans.jsonl")}

    out = []
    def w(s=""):
        out.append(s)

    w(f"# Confidence summary — {args.doc}")
    w("")
    w("## Mechanical proofs (deterministic)")
    w("")
    w(f"- Byte coverage: **{cov['coverage_pct']:.4f}%** ({cov['covered_bytes']}/{cov['total_bytes']})")
    w(f"- Gap failures: **{len(cov['gap_failures'])}**  |  Overlap failures: **{len(cov['overlap_failures'])}**")
    w(f"- Unclassified spans: **{len(cov['unclassified_spans'])}**")
    w(f"- Unrequirementized req-bearing spans: **{len(cov['unrequirementized_spans'])}**")
    pending_dg = [c for c in classes if c.get("downgrade_pending")]
    w(f"- Pending downgrades (zero-requirement spans preserved for adjudication): **{len(pending_dg)}**")
    w(f"- Verbatim-quote failures: **{len(cov['verbatim_quote_failures'])}**")
    w(f"- Relationship target failures: **{len(rel_val['failures'])}**")
    w(f"- Overall audit passed: **{cov['passed']}**")
    w("")

    amb_cls = [c for c in classes if c.get("ambiguous")]
    w("## Ambiguities flagged for human review")
    w("")
    w(f"### Classifications: {len(amb_cls)}")
    w("")
    for c in amb_cls:
        sid = c["span_id"]
        cit = spans_by_id[sid]["citation"].get("raw") or sid
        w(f"- **`{sid}`  {cit}** — A=`{c.get('label_a')}` B=`{c.get('label_b')}` → "
          f"final=`{c.get('final_label')}` + embedded `{c.get('final_embedded', [])}`")
        if c.get("reconciler_note"):
            w(f"  - _{c['reconciler_note']}_")
    if not amb_cls:
        w("(none)")
    w("")

    w(f"### Pending downgrades: {len(pending_dg)}")
    w("")
    for c in pending_dg:
        sid = c["span_id"]
        cit = spans_by_id[sid]["citation"].get("raw") or sid
        prop = c.get("downgrade_proposal") or {}
        w(f"- **`{sid}`  {cit}** — final=`{c.get('final_label')}` → proposed "
          f"`{prop.get('proposed_label')}` (kind={prop.get('kind')}, source={prop.get('source')})")
        if prop.get("reason"):
            w(f"  - _{prop['reason']}_")
    if not pending_dg:
        w("(none)")
    w("")

    amb_req = [r for r in reqs if r.get("ambiguous")]
    w(f"### Requirements: {len(amb_req)}")
    w("")
    for r in amb_req:
        w(f"- **`{r['req_id']}` {r['citation_raw']}**: {r['atomic_statement']}")
    if not amb_req:
        w("(none)")
    w("")

    amb_rel = [e for e in rels if e.get("ambiguous")]
    w(f"### Relationships: {len(amb_rel)} ambiguous edges  |  "
      f"{len(rel_val.get('cycles_flagged_ambiguous', []))} cycles")
    w("")

    emb_added = [e for e in emb_log if e.get("decision") == "embedded_obligation_added"]
    emb_filtered = [e for e in emb_log if e.get("decision") == "false_positive"]
    w("## Embedded-audit safety-net activity")
    w("")
    w(f"- Rescued (classifier missed → auditor added): **{len(emb_added)}**")
    for e in emb_added:
        w(f"  - `{e['span_id']}` {e['citation']} (was `{e['primary']}`)")
        w(f"    - _{e.get('rationale', '')}_")
    w(f"- Filtered as false positives: **{len(emb_filtered)}**")
    for e in emb_filtered:
        w(f"  - `{e['span_id']}` {e['citation']} — _{e.get('rationale', '')[:140]}_")
    w("")

    decompose_reconciles = [e for e in recon if e.get("stage") == "decompose"]
    classify_reconciles = [e for e in recon if e.get("stage") == "classify"]
    relate_reconciles = [e for e in recon if e.get("stage") == "relate"]
    w("## Reconciler activity")
    w("")
    w(f"- Classify reconciles: **{len(classify_reconciles)}**")
    w(f"- Decompose reconciles: **{len(decompose_reconciles)}**")
    w(f"- Relate reconciles: **{len(relate_reconciles)}**")
    big_diff = [e for e in decompose_reconciles if abs(e.get("count_a", 0) - e.get("count_b", 0)) > 3]
    big_diff.sort(key=lambda e: -abs(e["count_a"] - e["count_b"]))
    if big_diff:
        w("")
        w("Most-divergent decompose disagreements (A vs B differ by >3 reqs):")
        for e in big_diff[:10]:
            sid = e["span_id"]
            cit = spans_by_id[sid]["citation"].get("raw") or sid
            w(f"- **`{sid}` {cit}**: A={e['count_a']}, B={e['count_b']}, final={e['count_final']}")
    w("")

    w("## Modal-verb sniff test residual")
    w("")
    canonical = (base / "source" / "canonical.txt").read_text(encoding="utf-8")
    classes_by_id = {c["span_id"]: c for c in classes}
    found = []
    for verb in ("shall", "must", "may", "should"):
        rx = re.compile(rf"\b{verb}\b", re.IGNORECASE)
        for m in rx.finditer(canonical):
            byte_off = len(canonical[:m.start()].encode("utf-8"))
            for s in spans_by_id.values():
                if s["byte_start"] <= byte_off < s["byte_end"]:
                    c = classes_by_id.get(s["span_id"], {})
                    labels = {c.get("final_label")} | set(c.get("final_embedded", []))
                    if "requirement_bearing" not in labels:
                        found.append((s["span_id"], s["citation"].get("raw") or s["span_id"],
                                      m.group(0), c.get("final_label")))
                    break
    if found:
        for sid, cit, hit, label in found:
            w(f"- `{sid}` **{cit}** [{label}]: `{hit}`")
    else:
        w("(clean — every modal verb is in a span flagged requirement_bearing somewhere)")
    w("")

    OUT = base / "audit" / "confidence_summary.md"
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
