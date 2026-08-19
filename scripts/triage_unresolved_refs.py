"""Classify unresolved cross-document CFR references for processing scope.

The scanner records every unresolved reference. This script converts that raw
surface into a durable queue so unresolved references cannot silently disappear:
each referenced part is marked process, defer, or exclude with counts and a
plain rationale.
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from regcat.registry import all_docs

OUT_JSON = ROOT / "docs" / "scope_triage.json"
OUT_MD = ROOT / "docs" / "scope_triage.md"
OUT_HTML = ROOT / "docs" / "review_site" / "pivots" / "scope-triage" / "index.html"

RX_PARTS = [
    re.compile(r"\b21\s+CFR\s+(\d+)(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\b[Pp]art\s+(\d+)\b"),
    re.compile(r"(\d+)\.\d+"),
]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def part_from_citation(citation: str) -> str | None:
    for rx in RX_PARTS:
        match = rx.search(citation or "")
        if match:
            return match.group(1)
    return None


def part_from_doc(doc_id: str) -> str | None:
    match = re.search(r"21-cfr-part-(\d+)$", doc_id)
    return match.group(1) if match else None


def decision_for(part: str, refs: int, citing_docs: set[str], cfg: dict, processed: set[str]) -> tuple[str, str]:
    if part in processed:
        return "already_processed", "Referenced part is already in the processed corpus."

    known = cfg.get("known_parts", {}).get(part, {})
    domain = known.get("domain", "unknown")
    domains = cfg.get("domains", {})
    thresholds = cfg.get("thresholds", {})

    if domain in domains.get("exclude", []):
        return "exclude", f"Domain `{domain}` is outside the project scope."

    if domain in domains.get("core", []):
        return "process", f"Domain `{domain}` is core to the project scope."

    if domain in domains.get("defer", []):
        return "defer", f"Domain `{domain}` is peripheral; keep as deferred unless project scope expands."

    min_docs = int(thresholds.get("process_if_unique_core_citing_docs_at_least", 2))
    min_refs = int(thresholds.get("process_if_total_references_at_least", 5))
    if len(citing_docs) >= min_docs and refs >= min_refs:
        return "defer", (
            f"Unknown domain but cited {refs} times across {len(citing_docs)} documents; "
            "defer pending targeted review."
        )
    return "defer", "Unknown or low-context reference; defer rather than process automatically."


def build_report() -> dict:
    cfg = load_json(ROOT / "config" / "regulatory_scope.json")
    edges = load_jsonl(ROOT / "docs" / "cross_doc_relationships.jsonl")
    docs = all_docs(ROOT)
    processed_parts = {part for d in docs if (part := part_from_doc(d.doc_id))}

    counts: dict[str, int] = defaultdict(int)
    citing_docs: dict[str, set[str]] = defaultdict(set)
    examples: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        if edge.get("auto_resolved"):
            continue
        part = part_from_citation(edge.get("citation_in_source") or "")
        if not part:
            continue
        counts[part] += 1
        citing_docs[part].add(edge.get("source_doc") or "")
        if len(examples[part]) < 5:
            examples[part].append(edge.get("citation_in_source") or "")

    rows = []
    for part, refs in sorted(counts.items(), key=lambda item: (-item[1], int(item[0]))):
        known = cfg.get("known_parts", {}).get(part, {})
        decision, rationale = decision_for(part, refs, citing_docs[part], cfg, processed_parts)
        rows.append({
            "part": part,
            "title": known.get("title", "(unknown)"),
            "domain": known.get("domain", "unknown"),
            "decision": decision,
            "rationale": rationale,
            "references": refs,
            "citing_doc_count": len(citing_docs[part]),
            "citing_docs": sorted(d for d in citing_docs[part] if d),
            "examples": examples[part],
        })

    summary: dict[str, int] = defaultdict(int)
    for row in rows:
        summary[row["decision"]] += 1

    return {
        "generated_from": "docs/cross_doc_relationships.jsonl",
        "processed_part_count": len(processed_parts),
        "unresolved_part_count": len(rows),
        "summary": dict(sorted(summary.items())),
        "items": rows,
    }


def write_markdown(report: dict) -> None:
    lines = [
        "# Regulatory Scope Triage",
        "",
        "Every unresolved cross-document reference is classified so it is either queued, deferred, or excluded.",
        "",
        f"Processed parts: **{report['processed_part_count']}**",
        f"Unresolved referenced parts: **{report['unresolved_part_count']}**",
        "",
        "| part | decision | refs | docs | domain | title | rationale |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for row in report["items"]:
        lines.append(
            f"| Part {row['part']} | `{row['decision']}` | {row['references']} | "
            f"{row['citing_doc_count']} | {row['domain']} | {row['title']} | {row['rationale']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(report: dict) -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in report["items"]:
        examples = "<br>".join(html.escape(e) for e in row["examples"])
        rows.append(
            "<tr>"
            f"<td>Part {html.escape(row['part'])}</td>"
            f"<td><code>{html.escape(row['decision'])}</code></td>"
            f"<td class=\"num\">{row['references']}</td>"
            f"<td class=\"num\">{row['citing_doc_count']}</td>"
            f"<td>{html.escape(row['domain'])}</td>"
            f"<td>{html.escape(row['title'])}</td>"
            f"<td>{html.escape(row['rationale'])}<br><small>{examples}</small></td>"
            "</tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan=\"7\">No unresolved external references.</td></tr>"
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Scope Triage</title>
<style>
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f6f7f9; color:#1a1d23; font-size:14px; }}
header {{ background:#fff; border-bottom:1px solid #d9dce1; padding:0.8rem 1.5rem; position:sticky; top:0; }}
main {{ max-width:1200px; margin:0 auto; padding:1.2rem; }}
table {{ width:100%; border-collapse:collapse; background:#fff; }}
th,td {{ padding:0.5rem 0.7rem; border-bottom:1px solid #d9dce1; text-align:left; vertical-align:top; }}
th {{ background:#f6f7f9; color:#6b7280; text-transform:uppercase; font-size:0.8rem; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
small {{ color:#6b7280; }}
a {{ color:#2563cf; text-decoration:none; }}
</style></head>
<body><header><a href="../index.html">&larr; back</a><h1>Scope Triage</h1></header>
<main><p>Unresolved external references classified as process, defer, exclude, or already processed.</p>
<table><thead><tr><th>part</th><th>decision</th><th>refs</th><th>docs</th><th>domain</th><th>title</th><th>rationale / examples</th></tr></thead>
<tbody>{body}</tbody></table></main></body></html>
"""
    OUT_HTML.write_text(page, encoding="utf-8")


def main() -> None:
    report = build_report()
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report)
    write_html(report)
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_HTML}")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
