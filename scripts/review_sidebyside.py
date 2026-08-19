"""Side-by-side review tool: verbatim_quote next to atomic_statement for eyeballing.

Usage:
    python scripts/review_sidebyside.py --doc fda/21-cfr-part-11

Writes docs/<doc_id>/audit/review_sidebyside.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
    spans = loadl(base / "source" / "spans.jsonl")
    spans_by_id = {s["span_id"]: s for s in spans}
    reqs = loadl(base / "catalog" / "requirements.jsonl")
    classes = {c["span_id"]: c for c in loadl(base / "catalog" / "classifications.jsonl")}
    reqs_by_span: dict[str, list[dict]] = defaultdict(list)
    for r in reqs:
        reqs_by_span[r["source_span_id"]].append(r)

    lines: list[str] = []
    lines.append(f"# Side-by-side review — {args.doc}")
    lines.append("")
    lines.append("For each requirement:")
    lines.append("")
    lines.append("1. **VERBATIM_QUOTE** — exact source substring. Confirm it's in the paragraph below.")
    lines.append("2. **ATOMIC_STATEMENT** — LLM paraphrase. Confirm fidelity.")
    lines.append("3. **SOURCE PARAGRAPH** — full span text, for context.")
    lines.append("")
    lines.append(f"Total requirements: **{len(reqs)}** over **{len([s for s in spans if s['span_id'] in reqs_by_span])}** spans.")
    lines.append("")
    lines.append("---")
    lines.append("")

    spans_with_reqs = [s for s in spans if s["span_id"] in reqs_by_span]
    spans_with_reqs.sort(key=lambda s: s["byte_start"])

    for s in spans_with_reqs:
        sid = s["span_id"]
        cit = s["citation"].get("raw") or sid
        cls = classes.get(sid, {})
        amb = " ⚠ AMBIGUOUS" if cls.get("ambiguous") else ""
        embedded = cls.get("final_embedded", []) or []
        emb_str = f"  (+ embedded: {', '.join(embedded)})" if embedded else ""
        lines.append(f"## {cit} [{cls.get('final_label', '?')}{emb_str}{amb}] — {len(reqs_by_span[sid])} requirements")
        lines.append("")
        lines.append("**Source paragraph (verbatim):**")
        lines.append("")
        for tline in s["text"].strip().splitlines():
            lines.append(f"> {tline}" if tline else ">")
        lines.append("")

        for r in reqs_by_span[sid]:
            amb_r = " ⚠" if r.get("ambiguous") else ""
            lines.append(f"### {r['req_id']}{amb_r}  [{r['modality']}]")
            lines.append("")
            lines.append("**VERBATIM_QUOTE:**")
            lines.append("")
            for qline in r["verbatim_quote"].splitlines():
                lines.append(f"> {qline}")
            lines.append("")
            lines.append("**ATOMIC_STATEMENT:**")
            lines.append("")
            lines.append(f"> {r['atomic_statement']}")
            lines.append("")
            if r.get("subject") or r.get("object") or r.get("conditions") or r.get("applicability_tags"):
                fields = []
                if r.get("subject"): fields.append(f"subject={r['subject']}")
                if r.get("object"): fields.append(f"object={r['object']}")
                if r.get("conditions"): fields.append("conditions=" + "; ".join(r["conditions"]))
                if r.get("applicability_tags"): fields.append("tags=" + ", ".join(r["applicability_tags"]))
                lines.append("`" + "  |  ".join(fields) + "`")
                lines.append("")
        lines.append("---")
        lines.append("")

    OUT = base / "audit" / "review_sidebyside.md"
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}  ({len(reqs)} reqs over {len(spans_with_reqs)} spans)")


if __name__ == "__main__":
    main()
