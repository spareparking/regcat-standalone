"""Build the multi-doc review website.

Usage:
    # Build everything (landing page + every doc's review page)
    python scripts/build_review_site.py

    # Build one doc's page and refresh the landing index
    python scripts/build_review_site.py --doc fda/21-cfr-part-11

Output:
    docs/review_site/index.html                       <- landing page (filterable list)
    docs/review_site/<doc_id>/index.html              <- per-doc review page
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from regcat.registry import (
    DocMeta, all_docs, doc_dir as resolve_doc_dir,
)

SITE_ROOT = ROOT / "docs" / "review_site"


def loadl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Per-doc review page
# ---------------------------------------------------------------------------

def build_doc_page(doc_id: str) -> Path:
    base = resolve_doc_dir(ROOT, doc_id)
    canonical = (base / "source" / "canonical.txt").read_text(encoding="utf-8")
    spans = loadl(base / "source" / "spans.jsonl")
    classifications = {c["span_id"]: c for c in loadl(base / "catalog" / "classifications.jsonl")}
    requirements = loadl(base / "catalog" / "requirements.jsonl")
    relationships = loadl(base / "catalog" / "relationships.jsonl") if (base / "catalog" / "relationships.jsonl").exists() else []
    coverage = json.loads((base / "audit" / "coverage_report.json").read_text(encoding="utf-8"))

    # Load meta for the header
    from regcat.registry import load_meta
    meta = load_meta(ROOT, doc_id)

    # byte → char offsets
    canonical_bytes = canonical.encode("utf-8")
    def byte_to_char(byte_pos: int) -> int:
        return len(canonical_bytes[:byte_pos].decode("utf-8", errors="replace"))
    for s in spans:
        s["char_start"] = byte_to_char(s["byte_start"])
        s["char_end"] = byte_to_char(s["byte_end"])

    reqs_by_span: dict[str, list[dict]] = defaultdict(list)
    for r in requirements:
        s = next((x for x in spans if x["span_id"] == r["source_span_id"]), None)
        if not s:
            continue
        span_text = canonical[s["char_start"]:s["char_end"]]
        pos = span_text.find(r["verbatim_quote"])
        if pos < 0:
            continue
        r["char_start"] = s["char_start"] + pos
        r["char_end"] = r["char_start"] + len(r["verbatim_quote"])
        reqs_by_span[r["source_span_id"]].append(r)

    rels_out: dict[str, list[dict]] = defaultdict(list)
    for e in relationships:
        rels_out[e["source_req_id"]].append(e)

    spans_sorted = sorted(spans, key=lambda s: s["char_start"])
    span_blocks: list[str] = []
    for s in spans_sorted:
        sid = s["span_id"]
        kind = s["kind"]
        cls = classifications.get(sid, {})
        label = cls.get("final_label", "unclassified")
        embedded = cls.get("final_embedded", []) or []
        ambiguous_cls = cls.get("ambiguous", False)
        cit = html.escape(s["citation"].get("raw") or sid)
        span_reqs = reqs_by_span.get(sid, [])
        span_html = _render_span_text(canonical[s["char_start"]:s["char_end"]],
                                       span_offset=s["char_start"], reqs=span_reqs)
        amb_tag = ' <span class="amb-tag">ambiguous</span>' if ambiguous_cls else ""
        embedded_tag = "".join(
            f'<span class="span-class span-class-{html.escape(e)} embedded-tag">+ {html.escape(e)}</span>'
            for e in embedded
        )
        span_blocks.append(
            f'<div class="span span-{html.escape(label)}" data-span-id="{sid}" data-kind="{kind}">\n'
            f'  <div class="span-meta">\n'
            f'    <span class="span-cit">{cit}</span>'
            f'    <span class="span-kind">{kind}</span>'
            f'    <span class="span-class span-class-{html.escape(label)}">{label}</span>'
            f'    {embedded_tag}'
            f'    <span class="span-reqs">{len(span_reqs)} req{"s" if len(span_reqs) != 1 else ""}</span>'
            f'{amb_tag}'
            f'  </div>\n'
            f'  <div class="span-text">{span_html}</div>\n'
            f'</div>'
        )

    js_reqs = {r["req_id"]: {
        "req_id": r["req_id"], "citation": r["citation_raw"],
        "verbatim_quote": r["verbatim_quote"], "atomic_statement": r["atomic_statement"],
        "modality": r["modality"], "subject": r.get("subject", ""), "object": r.get("object", ""),
        "applicability_tags": r.get("applicability_tags", []), "conditions": r.get("conditions", []),
        "ambiguous": r.get("ambiguous", False), "source_span_id": r["source_span_id"],
    } for r in requirements}
    js_rels = {req_id: [{
        "target": e["target_req_id"], "type": e["type"],
        "evidence": e.get("evidence", ""), "ambiguous": e.get("ambiguous", False),
    } for e in edges] for req_id, edges in rels_out.items()}

    stats_html = (
        f'<div><b>{coverage.get("span_count", 0)}</b> spans</div>'
        f'<div><b>{coverage.get("requirements_extracted", 0)}</b> requirements</div>'
        f'<div>coverage <b>{coverage.get("coverage_pct", 0):.4f}%</b></div>'
        f'<div class="passed">audit {"passed" if coverage.get("passed") else "FAILED"}</div>'
    )

    title = f"{meta.title} ({meta.doc_id})"
    html_out = DOC_PAGE_TEMPLATE.format(
        title=html.escape(title),
        doc_id=html.escape(meta.doc_id),
        stats_html=stats_html,
        document_body="\n".join(span_blocks),
        reqs_json=json.dumps(js_reqs, ensure_ascii=False),
        rels_json=json.dumps(js_rels, ensure_ascii=False),
    )

    out = SITE_ROOT / doc_id / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")
    build_relationship_graph_page(doc_id, meta, requirements, relationships)
    return out


def build_relationship_graph_page(
    doc_id: str,
    meta: DocMeta,
    requirements: list[dict],
    relationships: list[dict],
) -> Path:
    reqs = {
        r["req_id"]: {
            "id": r["req_id"],
            "citation": r.get("citation_raw", ""),
            "statement": r.get("atomic_statement", ""),
            "modality": r.get("modality", ""),
            "subject": r.get("subject", ""),
            "object": r.get("object", ""),
            "tags": r.get("applicability_tags", []),
            "conditions": r.get("conditions", []),
            "source_span_id": r.get("source_span_id", ""),
        }
        for r in requirements
    }
    links = [
        {
            "id": e.get("rel_id", ""),
            "source": e.get("source_req_id", ""),
            "target": e.get("target_req_id", ""),
            "type": e.get("type", ""),
            "evidence": e.get("evidence", ""),
            "ambiguous": bool(e.get("ambiguous", False)),
        }
        for e in relationships
        if e.get("source_req_id") in reqs and e.get("target_req_id") in reqs
    ]
    type_counts: dict[str, int] = defaultdict(int)
    for e in links:
        type_counts[e["type"]] += 1
    type_buttons = "\n".join(
        f'<label class="type-toggle type-{html.escape(t)}">'
        f'<input type="checkbox" value="{html.escape(t)}" checked> '
        f'{html.escape(t)} <span>{n}</span></label>'
        for t, n in sorted(type_counts.items())
    )
    out = SITE_ROOT / doc_id / "relationships.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        RELATIONSHIP_GRAPH_TEMPLATE.format(
            title=html.escape(f"{meta.title} ({meta.doc_id})"),
            doc_id=html.escape(meta.doc_id),
            node_count=len(reqs),
            edge_count=len(links),
            type_buttons=type_buttons,
            nodes_json=json.dumps(list(reqs.values()), ensure_ascii=False),
            links_json=json.dumps(links, ensure_ascii=False),
        ),
        encoding="utf-8",
    )
    return out


def _render_span_text(text: str, span_offset: int, reqs: list[dict]) -> str:
    if not reqs:
        return _escape_with_breaks(text)
    events = []
    for r in reqs:
        rs = r["char_start"] - span_offset
        re_ = r["char_end"] - span_offset
        events.append((rs, 0, r["req_id"]))
        events.append((re_, 1, r["req_id"]))
    events.sort(key=lambda e: (e[0], e[1]))
    active: set[str] = set()
    cursor = 0
    parts: list[str] = []
    for pos, kind, rid in events:
        if pos > cursor:
            segment = text[cursor:pos]
            if active:
                rids = ",".join(sorted(active))
                anchor = sorted(active)[0]
                parts.append(f'<mark id="{html.escape(anchor)}" class="req-mark" data-reqs="{rids}">{_escape_with_breaks(segment)}</mark>')
            else:
                parts.append(_escape_with_breaks(segment))
            cursor = pos
        if kind == 0:
            active.add(rid)
        else:
            active.discard(rid)
    if cursor < len(text):
        segment = text[cursor:]
        if active:
            rids = ",".join(sorted(active))
            anchor = sorted(active)[0]
            parts.append(f'<mark id="{html.escape(anchor)}" class="req-mark" data-reqs="{rids}">{_escape_with_breaks(segment)}</mark>')
        else:
            parts.append(_escape_with_breaks(segment))
    return "".join(parts)


def _escape_with_breaks(text: str) -> str:
    return html.escape(text).replace("\n", "<br>\n")


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------

def build_landing(docs: list[DocMeta]) -> Path:
    rows: list[str] = []
    for d in sorted(docs, key=lambda x: x.doc_id):
        tags_html = " ".join(f'<span class="tag tag-{html.escape(t.value)}">{html.escape(t.value)}</span>'
                              for t in d.applies_to)
        status_class = f"status-{d.status.value}"
        coverage_pct = f"{d.stats.coverage_pct:.2f}%"
        rows.append(
            f'<tr class="doc-row" data-jurisdiction="{d.jurisdiction.value}" '
            f'data-status="{d.status.value}" '
            f'data-tags="{",".join(t.value for t in d.applies_to)}" '
            f'data-search="{html.escape((d.doc_id + " " + d.title).lower())}">'
            f'  <td><a href="{html.escape(d.doc_id)}/index.html">{html.escape(d.doc_id)}</a></td>'
            f'  <td>{html.escape(d.title)}</td>'
            f'  <td><span class="jur jur-{d.jurisdiction.value}">{d.jurisdiction.value}</span></td>'
            f'  <td>{d.document_type.value}</td>'
            f'  <td><span class="status {status_class}">{d.status.value}</span></td>'
            f'  <td class="num">{d.stats.requirements}</td>'
            f'  <td class="num">{coverage_pct}</td>'
            f'  <td>{tags_html}</td>'
            f'  <td><a href="{html.escape(d.doc_id)}/relationships.html">graph</a></td>'
            f'</tr>'
        )

    jurisdictions = sorted({d.jurisdiction.value for d in docs})
    statuses = sorted({d.status.value for d in docs})
    all_tags = sorted({t.value for d in docs for t in d.applies_to})

    jur_options = "".join(f'<option value="{j}">{j}</option>' for j in jurisdictions)
    status_options = "".join(f'<option value="{s}">{s}</option>' for s in statuses)
    tag_options = "".join(f'<option value="{t}">{t}</option>' for t in all_tags)

    total_reqs = sum(d.stats.requirements for d in docs)
    total_completed = sum(1 for d in docs if d.status.value == "completed")

    html_out = LANDING_TEMPLATE.format(
        doc_count=len(docs),
        jur_count=len(jurisdictions),
        total_reqs=total_reqs,
        total_completed=total_completed,
        rows="\n".join(rows),
        jur_options=jur_options,
        status_options=status_options,
        tag_options=tag_options,
    )
    out = SITE_ROOT / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

DOC_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>regcat: {title}</title>
<style>
  :root {{
    --bg:#f6f7f9; --fg:#1a1d23; --muted:#6b7280; --border:#d9dce1; --card:#ffffff;
    --req:#d4f4dd; --req-h:#79d894;
    --def:#dceaff; --def-h:#7fa6e6;
    --excl:#ffe0c2; --excl-h:#e89a4e;
    --incl:#fff4b8; --incl-h:#e2c54b;
    --admin:#ececec; --admin-h:#b3b3b3;
    --src:#ece2f7; --src-h:#a685cf;
    --struct:#f5f5f5; --struct-h:#c8c8c8;
    --cr:#f7e0e0; --cr-h:#d99393;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--fg); background:var(--bg); font-size:14px; line-height:1.5; }}
  .sticky-top {{ position:sticky; top:0; z-index:10; background:var(--card);
                 box-shadow:0 1px 3px rgba(0,0,0,0.05); }}
  header {{ background:var(--card); border-bottom:1px solid var(--border);
            padding:0.6rem 1.2rem; display:flex; flex-wrap:wrap; gap:1rem; align-items:center; }}
  header h1 {{ font-size:1rem; margin:0; font-weight:600; }}
  header a.back {{ color:var(--muted); text-decoration:none; }}
  header a.back:hover {{ color:var(--fg); }}
  .stats {{ margin-left:auto; color:var(--muted); display:flex; gap:0.8rem; }}
  .stats b {{ color:var(--fg); }}
  .stats .passed {{ color:#207340; font-weight:600; }}
  .legend {{ background:var(--card); border-bottom:1px solid var(--border);
             padding:0.5rem 1.2rem; display:flex; flex-wrap:wrap; gap:0.5rem;
             font-size:0.85rem; color:var(--muted); }}
  .legend .badge {{ padding:0.15rem 0.5rem; border-radius:3px; }}
  .badge-requirement_bearing {{ background:var(--req); }}
  .badge-definition          {{ background:var(--def); }}
  .badge-scope_exclusion     {{ background:var(--excl); }}
  .badge-scope_inclusion     {{ background:var(--incl); }}
  .badge-administrative      {{ background:var(--admin); }}
  .badge-source_note         {{ background:var(--src); }}
  .badge-structural          {{ background:var(--struct); }}
  .badge-cross_reference     {{ background:var(--cr); }}
  .badge-highlight {{ background:white; border:1px solid var(--req-h);
                       box-shadow:inset 0 -3px 0 var(--req-h); }}
  main {{ max-width:980px; margin:0 auto; padding:1.2rem; }}
  .span {{ margin-bottom:0.5rem; border-radius:4px; padding:0.5rem 0.8rem;
           background:var(--struct); border-left:3px solid var(--struct-h); }}
  .span-requirement_bearing {{ background:var(--req); border-left-color:var(--req-h); }}
  .span-definition {{ background:var(--def); border-left-color:var(--def-h); }}
  .span-scope_exclusion {{ background:var(--excl); border-left-color:var(--excl-h); }}
  .span-scope_inclusion {{ background:var(--incl); border-left-color:var(--incl-h); }}
  .span-administrative {{ background:var(--admin); border-left-color:var(--admin-h); }}
  .span-source_note {{ background:var(--src); border-left-color:var(--src-h); }}
  .span-structural {{ background:var(--struct); border-left-color:var(--struct-h); }}
  .span-cross_reference {{ background:var(--cr); border-left-color:var(--cr-h); }}
  .span-meta {{ display:flex; flex-wrap:wrap; gap:0.5rem; font-size:0.75rem;
                color:var(--muted); margin-bottom:0.4rem; }}
  .span-cit {{ font-weight:600; color:var(--fg); }}
  .span-kind {{ font-family:ui-monospace,"SF Mono",monospace; opacity:0.7; }}
  .span-class {{ padding:0.05rem 0.4rem; border-radius:3px; background:rgba(255,255,255,0.6); }}
  .embedded-tag {{ border:1px dashed currentColor; background:rgba(255,255,255,0.4); margin-left:0.25rem; }}
  .span-reqs {{ margin-left:auto; opacity:0.7; }}
  .amb-tag {{ color:#a14f00; background:#fff4d4; padding:0.05rem 0.4rem;
              border-radius:3px; border:1px solid #d8b878; }}
  .span-text {{ font-size:0.95rem; }}
  mark.req-mark {{ background:rgba(255,255,255,0.85); border-bottom:2px solid #2e7d3e;
                    cursor:help; border-radius:1px; padding:0 1px; }}
  mark.req-mark:hover {{ background:#fff; box-shadow:0 0 0 2px rgba(46,125,62,0.25); }}
  mark.req-mark.pinned {{ background:#fff8c0; box-shadow:0 0 0 2px #e2c54b; }}
  #tooltip {{ position:fixed; background:var(--card); border:1px solid var(--border);
              border-radius:6px; padding:0.7rem 0.9rem; box-shadow:0 8px 24px rgba(0,0,0,0.15);
              max-width:440px; max-height:80vh; overflow-y:auto; font-size:0.85rem;
              line-height:1.45; z-index:100; display:none; }}
  #tooltip.visible {{ display:block; }}
  #tooltip .tt-cit {{ font-weight:600; font-size:0.95rem; margin-bottom:0.3rem; }}
  #tooltip .tt-req {{ border-top:1px solid var(--border); padding-top:0.5rem; margin-top:0.5rem; }}
  #tooltip .tt-req:first-of-type {{ border-top:none; padding-top:0; margin-top:0; }}
  #tooltip .tt-modality {{ display:inline-block; background:#2e7d3e; color:white;
                            padding:0.05rem 0.4rem; border-radius:3px; font-size:0.75rem;
                            text-transform:uppercase; margin-right:0.3rem; }}
  #tooltip .tt-modality.may {{ background:#6c757d; }}
  #tooltip .tt-modality.should {{ background:#b08938; }}
  #tooltip .tt-quote {{ margin-top:0.4rem; border-left:3px solid var(--def-h);
                        padding-left:0.5rem; color:var(--muted); font-style:italic;
                        font-family:ui-monospace,monospace; font-size:0.78rem; }}
  #tooltip .tt-fields {{ margin-top:0.4rem; font-size:0.78rem; color:var(--muted); }}
  #tooltip .tt-tags span {{ display:inline-block; background:var(--struct);
                             padding:0.05rem 0.4rem; margin-right:0.2rem; margin-top:0.2rem;
                             border-radius:3px; font-size:0.72rem; }}
  #tooltip .tt-rel {{ margin-top:0.15rem; color:var(--muted); font-size:0.78rem; }}
  #tooltip .tt-rel a {{ color:#2563cf; text-decoration:none; }}
  #tooltip .tt-amb {{ color:#a14f00; font-weight:600; }}
  #tooltip .tt-pin-hint {{ margin-top:0.5rem; font-size:0.7rem; color:var(--muted);
                            border-top:1px solid var(--border); padding-top:0.3rem; }}
</style>
</head>
<body>
<div class="sticky-top">
  <header>
    <a class="back" href="../../index.html">&larr; all documents</a>
    <a class="back" href="relationships.html">relationship graph</a>
    <h1>{title}</h1>
    <div class="stats">{stats_html}</div>
  </header>
  <div class="legend">
    <span>Classifications:</span>
    <span class="badge badge-requirement_bearing">requirement_bearing</span>
    <span class="badge badge-definition">definition</span>
    <span class="badge badge-scope_inclusion">scope_inclusion</span>
    <span class="badge badge-scope_exclusion">scope_exclusion</span>
    <span class="badge badge-administrative">administrative</span>
    <span class="badge badge-source_note">source_note</span>
    <span class="badge badge-cross_reference">cross_reference</span>
    <span class="badge badge-structural">structural</span>
    <span class="badge badge-highlight">verbatim quote &rarr; hover</span>
  </div>
</div>
<main>
{document_body}
</main>
<div id="tooltip"></div>
<script>
const REQS = {reqs_json};
const RELS = {rels_json};
const tooltip = document.getElementById("tooltip");
let pinnedMark = null;

function escapeHtml(s) {{
  if (s == null) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}}

function renderTooltip(reqIds) {{
  if (!reqIds || reqIds.length === 0) return "";
  const first = REQS[reqIds[0]]; if (!first) return "";
  const blocks = reqIds.map(rid => {{
    const r = REQS[rid]; if (!r) return "";
    const tags = (r.applicability_tags || []).map(t => `<span>${{t}}</span>`).join("");
    const conds = (r.conditions || []).join("; ");
    const rels = (RELS[rid] || []).map(e => {{
      const target = REQS[e.target];
      const tgtCit = target ? target.citation : e.target;
      const amb = e.ambiguous ? ' <span class="tt-amb">ambiguous</span>' : "";
      const evid = e.evidence ? `<div style="margin-left:0.5rem;font-size:0.72rem;opacity:0.8;">${{escapeHtml(e.evidence)}}</div>` : "";
      return `<div class="tt-rel"><b>${{e.type}}</b>${{amb}} &rarr; <a href="#" data-jump="${{e.target}}">${{rid}} &rarr; ${{escapeHtml(tgtCit)}} (${{e.target}})</a>${{evid}}</div>`;
    }}).join("");
    const ambReq = r.ambiguous ? ' <span class="tt-amb">ambiguous</span>' : "";
    return `<div class="tt-req"><div><span class="tt-modality ${{r.modality}}">${{r.modality}}</span><span class="tt-statement">${{escapeHtml(r.atomic_statement)}}</span>${{ambReq}}</div><div class="tt-quote">${{escapeHtml(r.verbatim_quote)}}</div><div class="tt-fields">${{r.subject ? `<div><b>subject:</b> ${{escapeHtml(r.subject)}}</div>` : ""}}${{r.object ? `<div><b>object:</b> ${{escapeHtml(r.object)}}</div>` : ""}}${{conds ? `<div><b>conditions:</b> ${{escapeHtml(conds)}}</div>` : ""}}${{tags ? `<div class="tt-tags"><b>tags:</b> ${{tags}}</div>` : ""}}</div>${{rels}}<div style="margin-top:0.3rem;font-size:0.72rem;opacity:0.7;"><code>${{rid}}</code></div></div>`;
  }}).join("");
  return `<div class="tt-cit">${{escapeHtml(first.citation)}}</div>${{blocks}}<div class="tt-pin-hint">click to pin · click elsewhere to dismiss</div>`;
}}
function positionTooltip(rect) {{
  const tw = tooltip.offsetWidth, th = tooltip.offsetHeight;
  const vw = window.innerWidth, vh = window.innerHeight;
  let left = rect.right + 8, top = rect.top;
  if (left + tw + 8 > vw) left = Math.max(8, rect.left - tw - 8);
  if (top + th + 8 > vh) top = Math.max(8, vh - th - 8);
  tooltip.style.left = left + "px"; tooltip.style.top = top + "px";
}}
function showTooltipFor(m) {{
  const ids = (m.dataset.reqs || "").split(",").filter(Boolean);
  if (!ids.length) return;
  tooltip.innerHTML = renderTooltip(ids);
  tooltip.classList.add("visible");
  positionTooltip(m.getBoundingClientRect());
}}
function hideTooltip() {{ if (pinnedMark) return; tooltip.classList.remove("visible"); }}
function pin(m) {{ pinnedMark = m; m.classList.add("pinned"); }}
function unpin() {{ if (pinnedMark) pinnedMark.classList.remove("pinned"); pinnedMark = null; }}
document.addEventListener("mouseover", (e) => {{ if (pinnedMark) return;
  const m = e.target.closest("mark.req-mark"); if (m) showTooltipFor(m); }});
document.addEventListener("mouseout", (e) => {{ if (pinnedMark) return;
  const m = e.target.closest("mark.req-mark");
  if (m && !tooltip.contains(e.relatedTarget)) hideTooltip(); }});
document.addEventListener("click", (e) => {{
  const m = e.target.closest("mark.req-mark");
  if (tooltip.contains(e.target)) {{
    const a = e.target.closest("a[data-jump]");
    if (a) {{ e.preventDefault();
      const mark = document.querySelector(`mark.req-mark[data-reqs*="${{a.dataset.jump}}"]`);
      if (mark) {{ mark.scrollIntoView({{behavior:"smooth", block:"center"}}); unpin();
        setTimeout(() => {{ pin(mark); showTooltipFor(mark); }}, 280); }}
    }} return;
  }}
  if (m) {{ if (pinnedMark === m) {{ unpin(); hideTooltip(); }}
    else {{ unpin(); pin(m); showTooltipFor(m); }}
  }} else {{ unpin(); hideTooltip(); }}
}});
</script>
</body></html>
"""


RELATIONSHIP_GRAPH_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>regcat relationships: {title}</title>
<style>
  :root {{
    --bg:#f6f7f9; --fg:#1a1d23; --muted:#6b7280; --border:#d9dce1; --card:#ffffff;
    --refines:#2563cf; --references:#7c3aed; --exception_to:#d97706;
    --conditional_on:#0f766e; --defined_by:#be123c; --composed_of:#4b5563;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; height:100vh; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--fg); background:var(--bg); font-size:14px; }}
  header {{ height:48px; display:flex; align-items:center; gap:1rem; padding:0 1rem;
            background:var(--card); border-bottom:1px solid var(--border); }}
  header a {{ color:#2563cf; text-decoration:none; }}
  header h1 {{ margin:0; font-size:0.98rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  header .stats {{ margin-left:auto; display:flex; gap:0.7rem; color:var(--muted); font-size:0.82rem; }}
  .app {{ height:calc(100vh - 48px); display:grid; grid-template-columns:300px 1fr 360px; }}
  aside, section.detail {{ background:var(--card); border-right:1px solid var(--border); overflow:auto; }}
  section.detail {{ border-right:none; border-left:1px solid var(--border); }}
  .panel {{ padding:0.9rem; border-bottom:1px solid var(--border); }}
  .panel h2 {{ margin:0 0 0.5rem; font-size:0.78rem; text-transform:uppercase; color:var(--muted); letter-spacing:0.04em; }}
  input, select, button {{ font:inherit; }}
  input[type="search"], select {{ width:100%; border:1px solid var(--border); border-radius:4px; padding:0.38rem 0.5rem; background:white; }}
  button {{ border:1px solid var(--border); background:var(--bg); border-radius:4px; padding:0.35rem 0.55rem; cursor:pointer; }}
  .button-row {{ display:flex; gap:0.35rem; flex-wrap:wrap; margin-top:0.5rem; }}
  .type-toggle {{ display:block; margin:0.35rem 0; padding:0.25rem 0.35rem; border-radius:4px; border-left:4px solid var(--border); }}
  .type-toggle span {{ color:var(--muted); float:right; }}
  .type-refines {{ border-left-color:var(--refines); }}
  .type-references {{ border-left-color:var(--references); }}
  .type-exception_to {{ border-left-color:var(--exception_to); }}
  .type-conditional_on {{ border-left-color:var(--conditional_on); }}
  .type-defined_by {{ border-left-color:var(--defined_by); }}
  .type-composed_of {{ border-left-color:var(--composed_of); }}
  .hint {{ color:var(--muted); font-size:0.78rem; line-height:1.35; }}
  .graph-wrap {{ position:relative; min-width:0; min-height:0; }}
  canvas {{ display:block; width:100%; height:100%; background:#fbfbfc; }}
  .hud {{ position:absolute; left:12px; bottom:12px; background:rgba(255,255,255,0.92);
          border:1px solid var(--border); border-radius:4px; padding:0.4rem 0.55rem;
          color:var(--muted); font-size:0.78rem; pointer-events:none; }}
  .detail .empty {{ color:var(--muted); padding:0.9rem; }}
  .req-card {{ padding:0.9rem; }}
  .req-id {{ font-family:ui-monospace,"SF Mono",monospace; color:var(--muted); font-size:0.78rem; }}
  .citation {{ font-weight:600; margin:0.25rem 0 0.5rem; }}
  .statement {{ line-height:1.45; }}
  .modality {{ display:inline-block; background:#14532d; color:white; border-radius:3px; padding:0.05rem 0.35rem; font-size:0.72rem; text-transform:uppercase; margin-right:0.35rem; }}
  .modality.may {{ background:#6b7280; }}
  .modality.should {{ background:#a16207; }}
  .kv {{ margin-top:0.55rem; color:var(--muted); font-size:0.82rem; }}
  .tags span {{ display:inline-block; background:#eef2ff; border-radius:3px; padding:0.08rem 0.35rem; margin:0.15rem 0.15rem 0 0; color:#3730a3; }}
  .edge-list {{ border-top:1px solid var(--border); }}
  .edge {{ padding:0.55rem 0.9rem; border-bottom:1px solid var(--border); font-size:0.83rem; }}
  .edge b {{ color:var(--fg); }}
  .edge small {{ display:block; color:var(--muted); margin-top:0.2rem; line-height:1.35; }}
  .edge button {{ margin-top:0.35rem; font-size:0.75rem; }}
  .focus-note {{ margin-top:0.45rem; color:var(--muted); font-size:0.78rem; }}
</style>
</head>
<body>
<header>
  <a href="../../index.html">&larr; all docs</a>
  <a href="index.html">source view</a>
  <h1>{title}</h1>
  <div class="stats"><span><b>{node_count}</b> atomic elements</span><span><b>{edge_count}</b> relationships</span></div>
</header>
<div class="app">
  <aside>
    <div class="panel">
      <h2>Find Element</h2>
      <input id="search" type="search" list="req-options" placeholder="Search ID, citation, statement">
      <datalist id="req-options"></datalist>
      <div class="button-row">
        <button id="fit">Fit</button>
        <button id="reset">Reset</button>
        <button id="neighbors">Neighbors</button>
        <button id="all">All</button>
      </div>
      <div class="focus-note" id="focus-note">Showing all connected atomic elements.</div>
    </div>
    <div class="panel">
      <h2>Relationship Types</h2>
      {type_buttons}
    </div>
    <div class="panel hint">
      Drag to pan. Scroll to zoom. Click an atomic element to inspect its statement and its incoming/outgoing relationships. Use Neighbors to isolate the selected element's immediate graph.
    </div>
  </aside>
  <div class="graph-wrap">
    <canvas id="graph"></canvas>
    <div class="hud" id="hud"></div>
  </div>
  <section class="detail" id="detail"><div class="empty">Select an atomic element.</div></section>
</div>
<script>
const NODES_RAW = {nodes_json};
const LINKS_RAW = {links_json};
const TYPE_COLORS = {{
  refines:"#2563cf", references:"#7c3aed", exception_to:"#d97706",
  conditional_on:"#0f766e", defined_by:"#be123c", composed_of:"#4b5563"
}};
const nodesById = new Map(NODES_RAW.map(n => [n.id, n]));
const linksRaw = LINKS_RAW.filter(e => nodesById.has(e.source) && nodesById.has(e.target));
let activeTypes = new Set(Object.keys(TYPE_COLORS));
let neighborMode = false;
let selected = null;
let hover = null;
let scale = 1, tx = 0, ty = 0;
let dragging = false, dragNode = null, last = null;
let nodes = [], links = [];

const canvas = document.getElementById("graph");
const ctx = canvas.getContext("2d");
const detail = document.getElementById("detail");
const hud = document.getElementById("hud");
const search = document.getElementById("search");
const options = document.getElementById("req-options");
const focusNote = document.getElementById("focus-note");

for (const n of NODES_RAW) {{
  const opt = document.createElement("option");
  opt.value = `${{n.id}} ${{n.citation}}`;
  options.appendChild(opt);
}}

function escapeHtml(s) {{
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}}

function resize() {{
  const r = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(r.width * devicePixelRatio));
  canvas.height = Math.max(1, Math.floor(r.height * devicePixelRatio));
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  draw();
}}
window.addEventListener("resize", resize);

function buildGraph() {{
  const typeLinks = linksRaw.filter(e => activeTypes.has(e.type));
  let ids = new Set();
  for (const e of typeLinks) {{ ids.add(e.source); ids.add(e.target); }}
  if (neighborMode && selected) {{
    ids = new Set([selected.id]);
    for (const e of typeLinks) {{
      if (e.source === selected.id) ids.add(e.target);
      if (e.target === selected.id) ids.add(e.source);
    }}
  }}
  nodes = Array.from(ids, id => {{
    const base = nodesById.get(id);
    return Object.assign({{}}, base, {{
      x: base.x ?? (Math.random() - 0.5) * 900,
      y: base.y ?? (Math.random() - 0.5) * 650,
      vx: base.vx ?? 0,
      vy: base.vy ?? 0
    }});
  }});
  const visible = new Set(nodes.map(n => n.id));
  links = typeLinks.filter(e => visible.has(e.source) && visible.has(e.target));
  for (const n of nodes) {{
    const old = nodesById.get(n.id);
    Object.assign(old, n);
  }}
  focusNote.textContent = neighborMode && selected
    ? `Showing immediate neighbors for ${{selected.id}}.`
    : "Showing all connected atomic elements.";
}}

function step() {{
  const byId = new Map(nodes.map(n => [n.id, n]));
  for (const n of nodes) {{ n.vx *= 0.86; n.vy *= 0.86; }}
  for (let i = 0; i < nodes.length; i++) {{
    for (let j = i + 1; j < nodes.length; j++) {{
      const a = nodes[i], b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let d2 = dx*dx + dy*dy + 0.01;
      if (d2 > 160000) continue;
      const f = Math.min(1800 / d2, 0.08);
      a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
    }}
  }}
  for (const e of links) {{
    const a = byId.get(e.source), b = byId.get(e.target);
    if (!a || !b) continue;
    const dx = b.x - a.x, dy = b.y - a.y;
    const d = Math.hypot(dx, dy) || 1;
    const target = 115;
    const f = (d - target) * 0.008;
    const fx = dx / d * f, fy = dy / d * f;
    a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
  }}
  for (const n of nodes) {{
    n.vx += -n.x * 0.0015; n.vy += -n.y * 0.0015;
    if (!n.fixed) {{ n.x += Math.max(-8, Math.min(8, n.vx)); n.y += Math.max(-8, Math.min(8, n.vy)); }}
    Object.assign(nodesById.get(n.id), {{x:n.x,y:n.y,vx:n.vx,vy:n.vy}});
  }}
}}

function world(pt) {{ return {{x:(pt.x - tx) / scale, y:(pt.y - ty) / scale}}; }}
function screen(n) {{ return {{x:n.x * scale + tx, y:n.y * scale + ty}}; }}
function nodeRadius(n) {{
  let degree = 0;
  for (const e of links) if (e.source === n.id || e.target === n.id) degree++;
  return Math.min(12, 4.5 + Math.sqrt(degree) * 1.25);
}}
function drawArrow(a, b, color, alpha) {{
  const r = nodeRadius(b) + 2;
  const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 1;
  const sx = a.x + dx / d * (nodeRadius(a) + 2), sy = a.y + dy / d * (nodeRadius(a) + 2);
  const tx2 = b.x - dx / d * r, ty2 = b.y - dy / d * r;
  ctx.strokeStyle = color; ctx.globalAlpha = alpha; ctx.lineWidth = 1.2 / scale;
  ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(tx2, ty2); ctx.stroke();
  const size = 6 / scale, ang = Math.atan2(dy, dx);
  ctx.beginPath();
  ctx.moveTo(tx2, ty2);
  ctx.lineTo(tx2 - Math.cos(ang - 0.45) * size, ty2 - Math.sin(ang - 0.45) * size);
  ctx.lineTo(tx2 - Math.cos(ang + 0.45) * size, ty2 - Math.sin(ang + 0.45) * size);
  ctx.closePath(); ctx.fillStyle = color; ctx.fill();
  ctx.globalAlpha = 1;
}}
function draw() {{
  const w = canvas.clientWidth, h = canvas.clientHeight;
  ctx.clearRect(0, 0, w, h);
  ctx.save();
  ctx.translate(tx, ty); ctx.scale(scale, scale);
  const byId = new Map(nodes.map(n => [n.id, n]));
  for (const e of links) {{
    const a = byId.get(e.source), b = byId.get(e.target);
    if (!a || !b) continue;
    const active = selected && (e.source === selected.id || e.target === selected.id);
    drawArrow(a, b, TYPE_COLORS[e.type] || "#6b7280", selected && !active ? 0.13 : 0.62);
  }}
  for (const n of nodes) {{
    const isSel = selected && selected.id === n.id;
    const isHover = hover && hover.id === n.id;
    const related = !selected || isSel || links.some(e => (e.source === selected.id && e.target === n.id) || (e.target === selected.id && e.source === n.id));
    ctx.globalAlpha = selected && !related ? 0.25 : 1;
    const r = nodeRadius(n);
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = isSel ? "#111827" : isHover ? "#f59e0b" : "#ffffff";
    ctx.fill();
    ctx.lineWidth = (isSel || isHover ? 2.4 : 1.2) / scale;
    ctx.strokeStyle = isSel ? "#111827" : "#64748b";
    ctx.stroke();
    if (scale > 0.85 || isSel || isHover) {{
      ctx.font = `${{11 / scale}}px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif`;
      ctx.fillStyle = isSel ? "#111827" : "#374151";
      ctx.fillText(n.id, n.x + r + 3 / scale, n.y + 4 / scale);
    }}
    ctx.globalAlpha = 1;
  }}
  ctx.restore();
  hud.textContent = `${{nodes.length}} nodes · ${{links.length}} edges · zoom ${{Math.round(scale * 100)}}%`;
}}
function animate() {{
  for (let i = 0; i < 2; i++) step();
  draw();
  requestAnimationFrame(animate);
}}
function fit() {{
  if (!nodes.length) return;
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  for (const n of nodes) {{ minX=Math.min(minX,n.x); minY=Math.min(minY,n.y); maxX=Math.max(maxX,n.x); maxY=Math.max(maxY,n.y); }}
  const w = canvas.clientWidth, h = canvas.clientHeight, pad = 70;
  scale = Math.max(0.08, Math.min(2.8, Math.min((w-pad*2)/(maxX-minX || 1), (h-pad*2)/(maxY-minY || 1))));
  tx = w/2 - (minX+maxX)/2 * scale; ty = h/2 - (minY+maxY)/2 * scale;
  draw();
}}
function pick(x, y) {{
  const p = world({{x,y}});
  let best = null, bestD = Infinity;
  for (const n of nodes) {{
    const d = Math.hypot(n.x - p.x, n.y - p.y);
    if (d < nodeRadius(n) + 5 / scale && d < bestD) {{ best = n; bestD = d; }}
  }}
  return best;
}}
function selectNode(n, doFit=false) {{
  selected = n ? nodesById.get(n.id) : null;
  renderDetail();
  if (neighborMode) {{ buildGraph(); if (doFit) fit(); }}
  draw();
}}
function renderDetail() {{
  if (!selected) {{ detail.innerHTML = '<div class="empty">Select an atomic element.</div>'; return; }}
  const out = linksRaw.filter(e => e.source === selected.id && activeTypes.has(e.type));
  const inc = linksRaw.filter(e => e.target === selected.id && activeTypes.has(e.type));
  const edgeHtml = [...out.map(e => edgeHtmlBlock(e, "out")), ...inc.map(e => edgeHtmlBlock(e, "in"))].join("") || '<div class="empty">No visible relationships for current filters.</div>';
  const tags = (selected.tags || []).map(t => `<span>${{escapeHtml(t)}}</span>`).join("");
  const conds = (selected.conditions || []).map(escapeHtml).join("; ");
  detail.innerHTML = `<div class="req-card">
    <div class="req-id">${{escapeHtml(selected.id)}} · span ${{escapeHtml(selected.source_span_id)}}</div>
    <div class="citation">${{escapeHtml(selected.citation)}}</div>
    <div class="statement"><span class="modality ${{escapeHtml(selected.modality)}}">${{escapeHtml(selected.modality)}}</span>${{escapeHtml(selected.statement)}}</div>
    ${{selected.subject ? `<div class="kv"><b>Subject:</b> ${{escapeHtml(selected.subject)}}</div>` : ""}}
    ${{selected.object ? `<div class="kv"><b>Object:</b> ${{escapeHtml(selected.object)}}</div>` : ""}}
    ${{conds ? `<div class="kv"><b>Conditions:</b> ${{conds}}</div>` : ""}}
    ${{tags ? `<div class="kv tags"><b>Tags:</b><br>${{tags}}</div>` : ""}}
    <div class="button-row"><button onclick="openSource('${{selected.id}}')">Open in source view</button></div>
  </div><div class="edge-list">${{edgeHtml}}</div>`;
}}
function edgeHtmlBlock(e, dir) {{
  const otherId = dir === "out" ? e.target : e.source;
  const other = nodesById.get(otherId);
  const arrow = dir === "out" ? "→" : "←";
  return `<div class="edge"><b style="color:${{TYPE_COLORS[e.type] || "#6b7280"}}">${{escapeHtml(e.type)}}</b> ${{arrow}} ${{escapeHtml(otherId)}}<br>
    <span>${{escapeHtml(other ? other.citation : "")}}</span>
    <small>${{escapeHtml(other ? other.statement : "")}}</small>
    ${{e.evidence ? `<small><b>Evidence:</b> ${{escapeHtml(e.evidence)}}</small>` : ""}}
    <button onclick="jumpToNode('${{otherId}}')">Select</button></div>`;
}}
function jumpToNode(id) {{
  const n = nodesById.get(id); if (!n) return;
  selected = n;
  if (neighborMode) buildGraph();
  tx = canvas.clientWidth / 2 - n.x * scale; ty = canvas.clientHeight / 2 - n.y * scale;
  renderDetail(); draw();
}}
function openSource(id) {{ window.location.href = `index.html#${{encodeURIComponent(id)}}`; }}

canvas.addEventListener("mousedown", e => {{
  const n = pick(e.offsetX, e.offsetY);
  dragging = true; last = {{x:e.offsetX, y:e.offsetY}};
  if (n) {{ dragNode = n; n.fixed = true; selectNode(n); }}
}});
canvas.addEventListener("mousemove", e => {{
  hover = pick(e.offsetX, e.offsetY);
  if (!dragging) {{ draw(); return; }}
  if (dragNode) {{ const p = world({{x:e.offsetX, y:e.offsetY}}); dragNode.x = p.x; dragNode.y = p.y; Object.assign(nodesById.get(dragNode.id), {{x:p.x,y:p.y}}); }}
  else {{ tx += e.offsetX - last.x; ty += e.offsetY - last.y; last = {{x:e.offsetX, y:e.offsetY}}; }}
  draw();
}});
window.addEventListener("mouseup", () => {{ dragging = false; if (dragNode) dragNode.fixed = false; dragNode = null; }});
canvas.addEventListener("wheel", e => {{
  e.preventDefault();
  const old = scale;
  const factor = Math.exp(-e.deltaY * 0.001);
  scale = Math.max(0.08, Math.min(4, scale * factor));
  const mx = e.offsetX, my = e.offsetY;
  tx = mx - (mx - tx) * (scale / old); ty = my - (my - ty) * (scale / old);
  draw();
}}, {{passive:false}});

document.querySelectorAll('.type-toggle input').forEach(cb => cb.addEventListener('change', () => {{
  activeTypes = new Set(Array.from(document.querySelectorAll('.type-toggle input:checked')).map(x => x.value));
  buildGraph(); renderDetail(); draw();
}}));
search.addEventListener("change", () => {{
  const q = search.value.trim().toLowerCase();
  if (!q) return;
  const idMatch = q.match(/r\\d{{5}}/i);
  let n = idMatch ? nodesById.get(idMatch[0].toUpperCase()) : null;
  if (!n) n = NODES_RAW.find(x => (`${{x.id}} ${{x.citation}} ${{x.statement}}`).toLowerCase().includes(q));
  if (n) jumpToNode(n.id);
}});
document.getElementById("fit").onclick = fit;
document.getElementById("reset").onclick = () => {{ selected = null; neighborMode = false; buildGraph(); renderDetail(); fit(); }};
document.getElementById("neighbors").onclick = () => {{ if (selected) {{ neighborMode = true; buildGraph(); fit(); renderDetail(); }} }};
document.getElementById("all").onclick = () => {{ neighborMode = false; buildGraph(); fit(); renderDetail(); }};

buildGraph();
resize();
setTimeout(fit, 50);
animate();
</script>
</body>
</html>
"""


LANDING_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>regcat — document catalog</title>
<style>
  :root {{ --bg:#f6f7f9; --fg:#1a1d23; --muted:#6b7280; --border:#d9dce1; --card:#ffffff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--fg); background:var(--bg); font-size:14px; line-height:1.5; }}
  header {{ background:var(--card); border-bottom:1px solid var(--border); padding:1rem 1.5rem; }}
  header h1 {{ margin:0 0 0.3rem; font-size:1.3rem; }}
  header .stats {{ color:var(--muted); display:flex; gap:1rem; }}
  header .stats b {{ color:var(--fg); }}
  .filters {{ background:var(--card); border-bottom:1px solid var(--border);
              padding:0.7rem 1.5rem; display:flex; flex-wrap:wrap; gap:0.6rem; align-items:center; }}
  .filters label {{ color:var(--muted); margin-right:0.2rem; font-size:0.85rem; }}
  .filters select, .filters input {{ font-size:0.9rem; padding:0.3rem 0.5rem;
                                       border:1px solid var(--border); border-radius:4px; background:white; }}
  .filters input {{ flex:1; min-width:200px; max-width:400px; }}
  .filters button {{ font-size:0.85rem; padding:0.3rem 0.7rem; border:1px solid var(--border);
                      background:var(--bg); border-radius:4px; cursor:pointer; color:var(--muted); }}
  .filters .visible-count {{ margin-left:auto; color:var(--muted); }}
  main {{ padding:1rem 1.5rem; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card);
           box-shadow:0 1px 3px rgba(0,0,0,0.05); border-radius:4px; overflow:hidden; }}
  th, td {{ padding:0.5rem 0.7rem; text-align:left; border-bottom:1px solid var(--border); }}
  th {{ background:var(--bg); font-size:0.8rem; color:var(--muted); text-transform:uppercase;
         letter-spacing:0.5px; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  tr.doc-row.hidden {{ display:none; }}
  td a {{ color:#2563cf; text-decoration:none; font-weight:500; }}
  td a:hover {{ text-decoration:underline; }}
  .jur {{ display:inline-block; padding:0.1rem 0.4rem; border-radius:3px;
          font-size:0.75rem; background:#e8e8e8; }}
  .jur-fda {{ background:#dbeafe; color:#1e3a8a; }}
  .jur-ema {{ background:#fce7f3; color:#831843; }}
  .jur-ich {{ background:#d1fae5; color:#064e3b; }}
  .jur-iso, .jur-iec {{ background:#fef3c7; color:#78350f; }}
  .status {{ display:inline-block; padding:0.1rem 0.4rem; border-radius:3px;
             font-size:0.75rem; background:#e8e8e8; }}
  .status-completed {{ background:#dcfce7; color:#14532d; }}
  .status-needs_review {{ background:#fed7aa; color:#7c2d12; }}
  .status-in_progress {{ background:#dbeafe; color:#1e3a8a; }}
  .status-registered {{ background:#f3f4f6; color:#374151; }}
  .status-archived, .status-superseded {{ background:#e5e7eb; color:#6b7280; }}
  .tag {{ display:inline-block; padding:0.05rem 0.3rem; margin:1px;
          border-radius:3px; font-size:0.7rem; background:#f3f4f6; }}
  .tag-edc {{ background:#e0e7ff; }}
  .tag-iwrs {{ background:#fce7f3; }}
  .tag-ecoa {{ background:#d1fae5; }}
  .tag-etmf {{ background:#fef3c7; }}
  .tag-ctms_general {{ background:#e5e7eb; }}
</style>
</head>
<body>
<header>
  <h1>regcat — regulatory catalog</h1>
  <div class="stats">
    <div><b>{doc_count}</b> documents</div>
    <div><b>{jur_count}</b> jurisdictions</div>
    <div><b>{total_completed}</b> completed</div>
    <div><b>{total_reqs}</b> requirements across all docs</div>
  </div>
  <nav style="margin-top:0.5rem;">
    <a href="pivots/index.html" style="color:#2563cf; text-decoration:none; margin-right:1rem;">→ pivot views (by tag · by subsystem · glossary · cross-doc references)</a>
    <a href="relationships.html" style="color:#2563cf; text-decoration:none;">→ unified atomic relationship map</a>
  </nav>
</header>
<div class="filters">
  <label for="f-jur">jurisdiction</label>
  <select id="f-jur"><option value="">all</option>{jur_options}</select>
  <label for="f-status">status</label>
  <select id="f-status"><option value="">all</option>{status_options}</select>
  <label for="f-tag">applies to</label>
  <select id="f-tag"><option value="">any</option>{tag_options}</select>
  <input type="search" id="f-search" placeholder="search doc_id or title">
  <button id="f-reset">reset</button>
  <span class="visible-count" id="visible-count"></span>
</div>
<main>
  <table>
    <thead>
      <tr>
        <th>doc_id</th><th>title</th><th>jurisdiction</th><th>type</th>
        <th>status</th><th>reqs</th><th>coverage</th><th>applies to</th><th>relationships</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</main>
<script>
const rows = Array.from(document.querySelectorAll("tr.doc-row"));
const fJur = document.getElementById("f-jur");
const fStatus = document.getElementById("f-status");
const fTag = document.getElementById("f-tag");
const fSearch = document.getElementById("f-search");
const vCount = document.getElementById("visible-count");
function apply() {{
  const j = fJur.value, s = fStatus.value, t = fTag.value;
  const q = fSearch.value.trim().toLowerCase();
  let visible = 0;
  for (const r of rows) {{
    let show = true;
    if (j && r.dataset.jurisdiction !== j) show = false;
    if (s && r.dataset.status !== s) show = false;
    if (t && !r.dataset.tags.split(",").includes(t)) show = false;
    if (q && !r.dataset.search.includes(q)) show = false;
    r.classList.toggle("hidden", !show);
    if (show) visible++;
  }}
  vCount.textContent = visible + " of " + rows.length + " shown";
}}
[fJur, fStatus, fTag, fSearch].forEach(el => el.addEventListener("input", apply));
document.getElementById("f-reset").addEventListener("click", () => {{
  fJur.value = ""; fStatus.value = ""; fTag.value = ""; fSearch.value = ""; apply();
}});
apply();
</script>
</body></html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--doc",
        default=None,
        help="Build this doc's page and refresh the landing index (default: build all docs + landing).",
    )
    args = ap.parse_args()

    docs = all_docs(ROOT)
    if args.doc:
        out = build_doc_page(args.doc)
        print(f"wrote {out}")
        out = build_landing(docs)
        print(f"wrote {out}")
    else:
        for d in docs:
            try:
                out = build_doc_page(d.doc_id)
                print(f"wrote {out}")
            except Exception as e:
                print(f"  skipped {d.doc_id}: {e}")
        out = build_landing(docs)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
