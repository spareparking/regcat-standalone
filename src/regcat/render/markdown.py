"""Markdown renderer for the catalog.

Organizes output by Subpart > Section, with separate sections for definitions,
scope inclusions/exclusions, and a tag index. Designed to be readable by someone
auditing the catalog against the source regulation.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def run(ctx) -> None:
    paths = ctx.paths
    spans = ctx.read_jsonl(paths.source_dir / "spans.jsonl")
    spans_by_id = {s["span_id"]: s for s in spans}

    classifications: list[dict] = []
    cl_path = paths.catalog_dir / "classifications.jsonl"
    if cl_path.exists():
        classifications = ctx.read_jsonl(cl_path)
    class_by_span = {c["span_id"]: c for c in classifications}

    requirements: list[dict] = []
    req_path = paths.catalog_dir / "requirements.jsonl"
    if req_path.exists():
        requirements = ctx.read_jsonl(req_path)
    reqs_by_span: dict[str, list[dict]] = defaultdict(list)
    reqs_by_id: dict[str, dict] = {}
    for r in requirements:
        reqs_by_span[r["source_span_id"]].append(r)
        reqs_by_id[r["req_id"]] = r

    relationships: list[dict] = []
    rel_path = paths.catalog_dir / "relationships.jsonl"
    if rel_path.exists():
        relationships = ctx.read_jsonl(rel_path)
    rels_out: dict[str, list[dict]] = defaultdict(list)
    rels_in: dict[str, list[dict]] = defaultdict(list)
    for e in relationships:
        rels_out[e["source_req_id"]].append(e)
        rels_in[e["target_req_id"]].append(e)

    coverage = {}
    cov_path = paths.audit_dir / "coverage_report.json"
    if cov_path.exists():
        coverage = json.loads(cov_path.read_text(encoding="utf-8"))

    recon_log: list[dict] = []
    log_path = paths.audit_dir / "reconciler_log.jsonl"
    if log_path.exists():
        recon_log = ctx.read_jsonl(log_path)

    # ---- group spans by section ----
    by_section: dict[str, list[dict]] = defaultdict(list)
    subpart_of_section: dict[str, str] = {}
    for s in spans:
        sec = s["citation"].get("section") or ""
        subpart = s["citation"].get("subpart") or ""
        if sec:
            by_section[sec].append(s)
            if subpart and sec not in subpart_of_section:
                subpart_of_section[sec] = subpart

    # ---- build output ----
    lines: list[str] = []
    lines.append("# Catalog — 21 CFR Part 11 (Electronic Records; Electronic Signatures)")
    lines.append("")
    _coverage_summary(lines, coverage, ctx)
    _definitions(lines, spans, class_by_span)
    _scope(lines, spans, class_by_span, reqs_by_span)
    _requirements_by_section(lines, by_section, subpart_of_section, class_by_span,
                             reqs_by_span, rels_out, rels_in, reqs_by_id)
    _tag_index(lines, requirements)
    _reconciler_log(lines, recon_log)
    _ambiguous_index(lines, classifications, requirements, relationships)
    _appendix_spans(lines, spans, class_by_span)

    out_path = paths.catalog_dir / "catalog.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    ctx.log(f"    render: wrote {out_path}")


# ---------------------------------------------------------------------------

def _coverage_summary(lines, coverage, ctx) -> None:
    lines.append("## Coverage")
    lines.append("")
    if not coverage:
        lines.append("_No coverage report — run the audit stage first._")
        lines.append("")
        return
    lines.append(f"- Source PDF sha256: `{ctx.meta.pdf_sha256}`")
    lines.append(f"- Canonical sha256: `{coverage.get('canonical_source_sha256', '')}`")
    lines.append(f"- Mode: `{ctx.meta.mode}`  Model: `{ctx.meta.model}`")
    lines.append(f"- Coverage: **{coverage.get('coverage_pct', 0):.4f}%** "
                 f"({coverage.get('covered_bytes', 0)}/{coverage.get('total_bytes', 0)} bytes)")
    lines.append(f"- Spans: **{coverage.get('span_count', 0)}**  "
                 f"Requirements: **{coverage.get('requirements_extracted', 0)}**")
    lines.append(f"- Verbatim quote failures: **{len(coverage.get('verbatim_quote_failures', []))}**  "
                 f"Unclassified: **{len(coverage.get('unclassified_spans', []))}**  "
                 f"Unrequirementized: **{len(coverage.get('unrequirementized_spans', []))}**  "
                 f"Passed: **{coverage.get('passed', False)}**")
    lines.append("")
    lines.append("**Spans by classification:**")
    lines.append("")
    lines.append("| Classification | Count |")
    lines.append("|---|---:|")
    for label, count in sorted(coverage.get("spans_by_classification", {}).items()):
        lines.append(f"| {label} | {count} |")
    lines.append("")


def _definitions(lines, spans, class_by_span) -> None:
    defs = [s for s in spans if class_by_span.get(s["span_id"], {}).get("final_label") == "definition"]
    if not defs:
        return
    lines.append("## Definitions (§ 11.3)")
    lines.append("")
    for s in defs:
        cit = s["citation"].get("raw") or s["span_id"]
        text = s["text"].strip()
        # Extract the term (first word(s) before "means")
        term = ""
        body = text
        if " means " in text:
            head, body = text.split(" means ", 1)
            # head looks like "(1)  Act"
            term = head.split(")", 1)[-1].strip()
            body = "means " + body
        else:
            body = text
        if term:
            lines.append(f"- **{term}** ({cit}): {body.strip()}")
        else:
            lines.append(f"- ({cit}): {text}")
    lines.append("")


def _scope(lines, spans, class_by_span, reqs_by_span) -> None:
    inc = [s for s in spans if class_by_span.get(s["span_id"], {}).get("final_label") == "scope_inclusion"]
    exc = [s for s in spans if class_by_span.get(s["span_id"], {}).get("final_label") == "scope_exclusion"]
    if not inc and not exc:
        return
    lines.append("## Scope")
    lines.append("")
    if inc:
        lines.append("### Inclusions")
        lines.append("")
        for s in inc:
            cit = s["citation"].get("raw") or s["span_id"]
            text = _clean_paragraph(s["text"])
            lines.append(f"- **{cit}**: {text}")
        lines.append("")
    if exc:
        lines.append("### Exclusions")
        lines.append("")
        lines.append("Records or signatures to which this part does NOT apply:")
        lines.append("")
        for s in exc:
            cit = s["citation"].get("raw") or s["span_id"]
            text = _clean_paragraph(s["text"])
            lines.append(f"- **{cit}**: {text}")
        lines.append("")


def _requirements_by_section(lines, by_section, subpart_of_section, class_by_span,
                              reqs_by_span, rels_out, rels_in, reqs_by_id) -> None:
    lines.append("## Requirements")
    lines.append("")
    # Order: by section number sorted numerically
    sections = sorted(by_section.keys(), key=lambda s: tuple(int(x) for x in s.split(".")))
    for sec in sections:
        sec_spans = []
        for s in by_section[sec]:
            c = class_by_span.get(s["span_id"], {})
            labels = {c.get("final_label")} | set(c.get("final_embedded", []))
            if "requirement_bearing" in labels:
                sec_spans.append(s)
        if not sec_spans:
            continue
        # Section header line — find the section header span for its title
        header_span = next((s for s in by_section[sec] if s["kind"] == "section_header"), None)
        title = header_span["text"].strip() if header_span else f"§ {sec}"
        subpart = subpart_of_section.get(sec, "")
        sp_label = f"Subpart {subpart} — " if subpart else ""
        lines.append(f"### {sp_label}{title}")
        lines.append("")

        # Within a section, sort by source-byte order
        sec_spans.sort(key=lambda s: s["byte_start"])
        for s in sec_spans:
            cit = s["citation"].get("raw") or s["span_id"]
            text = _clean_paragraph(s["text"])
            cls = class_by_span.get(s["span_id"], {})
            amb_marker = "  **[ambiguous]**" if cls.get("ambiguous") else ""
            embedded = cls.get("final_embedded") or []
            emb_marker = (f"  _[primary: {cls.get('final_label', '?')}; "
                          f"also: {', '.join(embedded)}]_") if embedded else ""

            lines.append(f"#### {cit}{amb_marker}{emb_marker}")
            lines.append("")
            lines.append(f"> {text}")
            lines.append("")

            reqs = reqs_by_span.get(s["span_id"], [])
            for r in reqs:
                amb_r = "  ⚠ ambiguous" if r.get("ambiguous") else ""
                lines.append(f"- **`{r['req_id']}`** [{r['modality']}]{amb_r} {r['atomic_statement']}")
                if r.get("subject"):
                    lines.append(f"  - subject: {r['subject']}")
                if r.get("object"):
                    lines.append(f"  - object: {r['object']}")
                if r.get("applicability_tags"):
                    lines.append(f"  - tags: `{', '.join(r['applicability_tags'])}`")
                if r.get("conditions"):
                    lines.append(f"  - conditions: {'; '.join(r['conditions'])}")
                if r.get("verbatim_quote"):
                    short_q = r["verbatim_quote"].replace("\n", " ").strip()
                    if len(short_q) > 200:
                        short_q = short_q[:197] + "..."
                    lines.append(f"  - quote: \"{short_q}\"")

                # outgoing edges
                out_edges = rels_out.get(r["req_id"], [])
                for e in out_edges:
                    tgt = reqs_by_id.get(e["target_req_id"])
                    tgt_cit = tgt["citation_raw"] if tgt else "?"
                    amb_e = " ⚠" if e.get("ambiguous") else ""
                    lines.append(f"  - **{e['type']}**{amb_e} → `{e['target_req_id']}` ({tgt_cit})")
                    if e.get("evidence"):
                        lines.append(f"    - evidence: _{e['evidence']}_")

                # incoming refines/references count
                in_edges = rels_in.get(r["req_id"], [])
                if in_edges:
                    by_type: dict[str, int] = defaultdict(int)
                    for ie in in_edges:
                        by_type[ie["type"]] += 1
                    parts = ", ".join(f"{n} {t}" for t, n in sorted(by_type.items()))
                    lines.append(f"  - referenced by: {parts}")
            lines.append("")


def _tag_index(lines, requirements) -> None:
    if not requirements:
        return
    tag_to_reqs: dict[str, list[str]] = defaultdict(list)
    for r in requirements:
        for t in r.get("applicability_tags", []):
            tag_to_reqs[t].append(r["req_id"])
    if not tag_to_reqs:
        return
    lines.append("## Index by applicability tag")
    lines.append("")
    for tag in sorted(tag_to_reqs.keys()):
        ids = ", ".join(f"`{rid}`" for rid in tag_to_reqs[tag])
        lines.append(f"- **`{tag}`** ({len(tag_to_reqs[tag])}): {ids}")
    lines.append("")


def _reconciler_log(lines, log) -> None:
    if not log:
        return
    lines.append("## Reconciler activity")
    lines.append("")
    for e in log:
        stage = e.get("stage", "?")
        key = e.get("span_id") or e.get("key") or "?"
        status = e.get("status", "?")
        line = f"- **{stage}** `{key}` — status: **{status}**"
        if stage == "classify":
            line += (f"  (A={e.get('label_a')} → B={e.get('label_b')} "
                     f"→ final={e.get('final_label')})")
        elif stage == "decompose":
            line += (f"  (A={e.get('count_a')} reqs, B={e.get('count_b')} reqs, "
                     f"final={e.get('count_final')}, ambiguous_items={e.get('ambiguous_items', 0)})")
        elif stage == "relate":
            line += (f"  (A={e.get('count_a')} edges, B={e.get('count_b')} edges, "
                     f"final={e.get('count_final')}, ambiguous_items={e.get('ambiguous_items', 0)})")
        lines.append(line)
    lines.append("")


def _ambiguous_index(lines, classifications, requirements, relationships) -> None:
    amb_class = [c for c in classifications if c.get("ambiguous")]
    amb_req = [r for r in requirements if r.get("ambiguous")]
    amb_rel = [e for e in relationships if e.get("ambiguous")]
    pending_downgrades = [c for c in classifications if c.get("downgrade_pending")]
    if not (amb_class or amb_req or amb_rel or pending_downgrades):
        return
    lines.append("## Ambiguous items (preserved by reconciler)")
    lines.append("")
    if pending_downgrades:
        lines.append("### Pending downgrades (decomposers returned zero requirements; "
                     "adjudication required before finalize)")
        lines.append("")
        for c in pending_downgrades:
            prop = c.get("downgrade_proposal") or {}
            lines.append(f"- `{c['span_id']}` — final: **{c.get('final_label')}**  "
                         f"proposed: **{prop.get('proposed_label')}** "
                         f"(kind: {prop.get('kind')}, source: {prop.get('source')})")
            if prop.get("reason"):
                lines.append(f"  - _{prop['reason']}_")
        lines.append("")
    if amb_class:
        lines.append("### Classifications")
        lines.append("")
        for c in amb_class:
            lines.append(f"- `{c['span_id']}` — A: **{c['label_a']}**  B: **{c['label_b']}**  → final: **{c['final_label']}**")
            if c.get("reconciler_note"):
                lines.append(f"  - _{c['reconciler_note']}_")
        lines.append("")
    if amb_req:
        lines.append("### Requirements")
        lines.append("")
        for r in amb_req:
            lines.append(f"- `{r['req_id']}` ({r['citation_raw']}): {r['atomic_statement']}")
        lines.append("")
    if amb_rel:
        lines.append("### Relationships")
        lines.append("")
        for e in amb_rel:
            lines.append(f"- `{e['source_req_id']}` --**{e['type']}**--> `{e['target_req_id']}`")
            if e.get("evidence"):
                lines.append(f"  - _{e['evidence']}_")
        lines.append("")


def _appendix_spans(lines, spans, class_by_span) -> None:
    lines.append("## Appendix: full span listing")
    lines.append("")
    lines.append("Every span produced by the segmenter, in source-byte order. "
                 "This is the verbatim ground-truth view of the source.")
    lines.append("")
    lines.append("| Span | Citation | Kind | Classification | Bytes |")
    lines.append("|---|---|---|---|---:|")
    for s in spans:
        sid = s["span_id"]
        cit = (s["citation"].get("raw") or "")
        kind = s["kind"]
        cls = class_by_span.get(sid, {}).get("final_label", "—")
        amb = " ⚠" if class_by_span.get(sid, {}).get("ambiguous") else ""
        byte_len = s["byte_end"] - s["byte_start"]
        lines.append(f"| `{sid}` | {cit} | `{kind}` | {cls}{amb} | {byte_len} |")
    lines.append("")


def _clean_paragraph(text: str) -> str:
    """Strip the leading (a)/(1)/(i) marker for cleaner inline display, and join wrapped lines."""
    t = text.strip()
    # Join wrapped lines: replace \n + non-empty-non-marker with space
    import re
    t = re.sub(r"\n(?!\s*\()", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t
