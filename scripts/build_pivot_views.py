"""Build cross-doc pivot views over the registered catalog.

Generates these views under docs/review_site/pivots/:
  by-tag/index.html              -- list every applicability_tag with req counts
  by-tag/<tag>.html              -- every requirement bearing that tag, grouped by doc
  by-subsystem/index.html        -- list each CTMS subsystem
  by-subsystem/<sub>.html        -- every requirement from docs flagged for that subsystem
  glossary/index.html            -- every defined term across all docs
  cross-doc/index.html           -- cross-doc citation graph

Each pivot reads per-doc data (catalog/requirements.jsonl, etc.) and assembles
a global view. Re-run this any time the per-doc data changes — the script is
idempotent and overwrites the pivots directory.
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
from regcat.registry import all_docs, doc_dir as resolve_doc_dir, Subsystem
from regcat.global_ids import global_id

SITE = ROOT / "docs" / "review_site"
PIVOTS = SITE / "pivots"


def loadl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- collect ---------------------------------------------------------------

def collect():
    """Read every registered doc's catalog and return aggregated structures."""
    docs = all_docs(ROOT)
    # Each requirement gets a global_id and carries its doc_id.
    global_reqs: list[dict] = []
    # tag -> list of requirements (with doc context)
    tag_index: dict[str, list[dict]] = defaultdict(list)
    # subsystem -> list of (doc, req)
    subsys_index: dict[str, list[dict]] = defaultdict(list)
    # defined_term -> {doc_id, span_id, citation, definition_text, used_by}
    glossary: dict[str, dict] = {}

    for d in docs:
        base = resolve_doc_dir(ROOT, d.doc_id)
        spans = loadl(base / "source" / "spans.jsonl")
        spans_by_id = {s["span_id"]: s for s in spans}
        reqs = loadl(base / "catalog" / "requirements.jsonl")
        classes = loadl(base / "catalog" / "classifications.jsonl")
        classes_by_span = {c["span_id"]: c for c in classes}

        for r in reqs:
            entry = dict(r)
            entry["doc_id"] = d.doc_id
            entry["doc_title"] = d.title
            entry["global_id"] = global_id(d.doc_id, r["req_id"])
            global_reqs.append(entry)
            for tag in r.get("applicability_tags", []) or []:
                tag_index[tag].append(entry)
            for sub in d.applies_to:
                subsys_index[sub.value].append(entry)

        # Glossary entries: spans classified as `definition`
        for s in spans:
            c = classes_by_span.get(s["span_id"], {})
            if c.get("final_label") != "definition":
                continue
            text = s.get("text", "").strip()
            term = _extract_term(text)
            if not term:
                continue
            key = term.lower()
            glossary.setdefault(key, {
                "term": term,
                "occurrences": [],
            })
            glossary[key]["occurrences"].append({
                "doc_id": d.doc_id,
                "doc_title": d.title,
                "span_id": s["span_id"],
                "citation": s["citation"].get("raw") or s["span_id"],
                "definition": text,
            })

    return {
        "docs": docs,
        "global_reqs": global_reqs,
        "tag_index": tag_index,
        "subsys_index": subsys_index,
        "glossary": glossary,
    }


_TERM_RX = re.compile(r"^(?:\([a-z0-9]+\)\s+)?(?P<term>.+?)\s+means\b", re.DOTALL)


def _extract_term(text: str) -> str | None:
    """Extract the defined term from a CFR-style definition span.

    Handles "(N) TermName means ...", "(a) TermName means ...", and "TermName means ..."
    (no paragraph marker). Term may itself contain spaces ("Clinical investigation"),
    so we lazily match up to the literal " means " marker.
    """
    m = _TERM_RX.match(text.strip())
    if not m:
        return None
    term = m.group("term").strip()
    # Discard if absurdly long (sentence prefix, not a term)
    if len(term) > 80:
        return None
    return term


# --- render helpers --------------------------------------------------------

PAGE_CSS = """
  :root { --bg:#f6f7f9; --fg:#1a1d23; --muted:#6b7280; --border:#d9dce1; --card:#ffffff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         color:var(--fg); background:var(--bg); font-size:14px; line-height:1.5; }
  header { background:var(--card); border-bottom:1px solid var(--border); padding:0.8rem 1.5rem;
           position:sticky; top:0; z-index:10; box-shadow:0 1px 3px rgba(0,0,0,0.05); }
  header h1 { margin:0; font-size:1.1rem; }
  header a.back { color:var(--muted); text-decoration:none; margin-right:1rem; }
  header a.back:hover { color:var(--fg); }
  main { max-width:1100px; margin:0 auto; padding:1.2rem; }
  .req { background:var(--card); border-radius:4px; padding:0.6rem 0.9rem;
         margin-bottom:0.5rem; border-left:3px solid #79d894; }
  .req .head { font-size:0.8rem; color:var(--muted); margin-bottom:0.3rem;
               display:flex; flex-wrap:wrap; gap:0.5rem; align-items:baseline; }
  .req .head .gid { font-family:ui-monospace,monospace; color:#2563cf; }
  .req .head .cit { font-weight:600; color:var(--fg); }
  .req .head .doc { color:var(--muted); font-size:0.75rem; }
  .req .head .modality { padding:0.05rem 0.4rem; border-radius:3px; background:#2e7d3e;
                          color:white; font-size:0.7rem; text-transform:uppercase; }
  .req .head .modality.may { background:#6c757d; }
  .req .head .modality.should { background:#b08938; }
  .req .stmt { font-size:0.92rem; }
  .req .quote { margin-top:0.3rem; font-style:italic; color:var(--muted); font-size:0.78rem;
                border-left:2px solid var(--border); padding-left:0.5rem; }
  .req .tags span { display:inline-block; background:#f3f4f6; padding:0.05rem 0.4rem;
                     margin:1px; border-radius:3px; font-size:0.7rem; }
  table { width:100%; border-collapse:collapse; background:var(--card); margin-top:1rem;
          box-shadow:0 1px 3px rgba(0,0,0,0.05); border-radius:4px; }
  th, td { padding:0.5rem 0.7rem; text-align:left; border-bottom:1px solid var(--border); }
  th { background:var(--bg); font-size:0.8rem; color:var(--muted); text-transform:uppercase;
       letter-spacing:0.5px; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; }
  td a { color:#2563cf; text-decoration:none; }
  td a:hover { text-decoration:underline; }
  .group { background:var(--card); border-radius:4px; padding:0.5rem 1rem;
           margin-bottom:0.7rem; }
  .group h3 { margin:0.3rem 0; font-size:1rem; }
  .group h3 a { text-decoration:none; color:var(--fg); }
  .group h3 a:hover { color:#2563cf; }
"""


def _page(title: str, back_href: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{PAGE_CSS}</style></head>
<body><header><a class="back" href="{back_href}">&larr; back</a>
<h1>{html.escape(title)}</h1></header>
<main>{body}</main></body></html>
"""


def _req_block(r: dict, link_to_doc: bool = True) -> str:
    mod = r.get("modality", "shall")
    tags_html = "".join(f"<span>{html.escape(t)}</span>"
                         for t in r.get("applicability_tags", []) or [])
    quote = r.get("verbatim_quote", "").replace("\n", " ").strip()
    if len(quote) > 220:
        quote = quote[:217] + "..."
    doc_anchor = ""
    if link_to_doc:
        doc_anchor = (f' <a class="doc" href="../../{html.escape(r["doc_id"])}/index.html">'
                       f'{html.escape(r["doc_title"])}</a>')
    return (f'<div class="req">'
            f'<div class="head">'
            f'<span class="gid">{html.escape(r["global_id"])}</span>'
            f'<span class="cit">{html.escape(r.get("citation_raw", ""))}</span>'
            f'{doc_anchor}'
            f'<span class="modality {mod}">{mod}</span>'
            f'</div>'
            f'<div class="stmt">{html.escape(r.get("atomic_statement", ""))}</div>'
            f'<div class="quote">{html.escape(quote)}</div>'
            f'<div class="tags">{tags_html}</div>'
            f'</div>')


# --- pivot renderers -------------------------------------------------------

def build_by_tag(data):
    PIVOTS.mkdir(parents=True, exist_ok=True)
    tags = data["tag_index"]
    out_dir = PIVOTS / "by-tag"
    out_dir.mkdir(parents=True, exist_ok=True)

    # index page
    rows = []
    for tag in sorted(tags.keys()):
        reqs = tags[tag]
        docs_for_tag = sorted({r["doc_id"] for r in reqs})
        rows.append(f'<tr><td><a href="{html.escape(tag)}.html">{html.escape(tag)}</a></td>'
                    f'<td class="num">{len(reqs)}</td>'
                    f'<td>{", ".join(html.escape(d) for d in docs_for_tag)}</td></tr>')
    body = ('<p>Browse atomic requirements by applicability tag. Tags are assigned per-requirement '
            'by the decomposer (e.g. <code>audit_trail</code>, <code>signature_manifestation</code>, '
            '<code>id_password</code>).</p>'
            f'<table><thead><tr><th>tag</th><th>requirements</th><th>docs</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')
    (out_dir / "index.html").write_text(_page("By applicability tag", "../../index.html", body), encoding="utf-8")

    # per-tag pages
    for tag, reqs in tags.items():
        by_doc: dict[str, list[dict]] = defaultdict(list)
        for r in reqs:
            by_doc[r["doc_id"]].append(r)
        sections = []
        for doc_id in sorted(by_doc.keys()):
            sections.append(f'<div class="group">'
                            f'<h3><a href="../../{html.escape(doc_id)}/index.html">{html.escape(doc_id)}</a> '
                            f'<small>({len(by_doc[doc_id])} reqs)</small></h3>'
                            f'{"".join(_req_block(r) for r in by_doc[doc_id])}'
                            f'</div>')
        body = (f'<p><b>{len(reqs)}</b> requirements bearing tag <code>{html.escape(tag)}</code> '
                f'across <b>{len(by_doc)}</b> doc(s).</p>'
                f'{"".join(sections)}')
        (out_dir / f"{tag}.html").write_text(
            _page(f"Tag: {tag}", "index.html", body), encoding="utf-8"
        )


def build_by_subsystem(data):
    out_dir = PIVOTS / "by-subsystem"
    out_dir.mkdir(parents=True, exist_ok=True)
    subsys = data["subsys_index"]

    rows = []
    for sub in sorted(subsys.keys()):
        reqs = subsys[sub]
        docs_for_sub = sorted({r["doc_id"] for r in reqs})
        rows.append(f'<tr><td><a href="{html.escape(sub)}.html">{html.escape(sub)}</a></td>'
                    f'<td class="num">{len(reqs)}</td>'
                    f'<td class="num">{len(docs_for_sub)}</td></tr>')
    body = ('<p>Browse requirements by CTMS subsystem (per-doc <code>applies_to</code> tags). '
            'A requirement appears under every subsystem that its source doc applies to.</p>'
            f'<table><thead><tr><th>subsystem</th><th>requirements</th><th>docs</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')
    (out_dir / "index.html").write_text(_page("By CTMS subsystem", "../../index.html", body), encoding="utf-8")

    for sub, reqs in subsys.items():
        by_doc: dict[str, list[dict]] = defaultdict(list)
        for r in reqs:
            by_doc[r["doc_id"]].append(r)
        sections = []
        for doc_id in sorted(by_doc.keys()):
            sections.append(f'<div class="group">'
                            f'<h3><a href="../../{html.escape(doc_id)}/index.html">{html.escape(doc_id)}</a> '
                            f'<small>({len(by_doc[doc_id])} reqs)</small></h3>'
                            f'{"".join(_req_block(r) for r in by_doc[doc_id])}'
                            f'</div>')
        body = (f'<p><b>{len(reqs)}</b> requirements apply to subsystem <code>{html.escape(sub)}</code> '
                f'(from <b>{len(by_doc)}</b> doc(s)).</p>'
                f'{"".join(sections)}')
        (out_dir / f"{sub}.html").write_text(
            _page(f"Subsystem: {sub}", "index.html", body), encoding="utf-8"
        )


def build_glossary(data):
    out_dir = PIVOTS / "glossary"
    out_dir.mkdir(parents=True, exist_ok=True)
    glossary = data["glossary"]

    entries = []
    for term in sorted(glossary.keys()):
        info = glossary[term]
        occurrences = "".join(
            f'<li><a href="../../{html.escape(o["doc_id"])}/index.html">{html.escape(o["doc_id"])}</a> '
            f'<code>{html.escape(o["citation"])}</code>: '
            f'<span style="color:#6b7280">{html.escape((o["definition"] or "")[:300])}</span></li>'
            for o in info["occurrences"]
        )
        entries.append(f'<div class="group">'
                       f'<h3>{html.escape(info["term"])}</h3>'
                       f'<ul>{occurrences}</ul>'
                       f'</div>')
    body = (f'<p><b>{len(glossary)}</b> defined terms across all docs. '
            'A term that appears in multiple docs has multiple entries here, one per definition source.</p>'
            f'{"".join(entries)}')
    (out_dir / "index.html").write_text(_page("Glossary", "../../index.html", body), encoding="utf-8")


def build_cross_doc(data):
    out_dir = PIVOTS / "cross-doc"
    out_dir.mkdir(parents=True, exist_ok=True)

    edges = loadl(ROOT / "docs" / "cross_doc_relationships.jsonl")
    resolved = [e for e in edges if e["auto_resolved"]]
    unresolved = [e for e in edges if not e["auto_resolved"]]

    # Resolved: pair count
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for e in resolved:
        pair_counts[(e["source_doc"], e["target_doc"])] += 1

    pair_rows = "".join(
        f'<tr><td><code>{html.escape(s)}</code></td>'
        f'<td><code>{html.escape(t)}</code></td>'
        f'<td class="num">{n}</td></tr>'
        for (s, t), n in sorted(pair_counts.items())
    )

    # Sample of resolved edges
    sample = "".join(
        f'<tr><td><code>{html.escape(e["source_doc"])}</code> <small>{html.escape(e["source_span_id"])}</small></td>'
        f'<td><code>{html.escape(e["citation_in_source"])}</code></td>'
        f'<td><code>{html.escape(e["target_doc"])}</code> <small>{html.escape(e["target_span_id"] or "")}</small></td>'
        f'<td>{html.escape(e["ref_type"])}</td></tr>'
        for e in resolved[:50]
    )

    # Unresolved: what other parts are referenced that we DON'T have. The
    # section symbol can be mojibake in PDF-derived text, so also accept bare
    # CFR section patterns like "101.7(f)".
    unresolved_parts: dict[str, int] = defaultdict(int)
    unresolved_rxes = [
        re.compile(r"\b21\s+CFR\s+(\d+)(?:\.\d+)?", re.IGNORECASE),
        re.compile(r"\b[Pp]art\s+(\d+)\b"),
        re.compile(r"(\d+)\.\d+"),
    ]
    for e in unresolved:
        cit = e["citation_in_source"] or ""
        part = None
        for rx in unresolved_rxes:
            m = rx.search(cit)
            if m:
                part = m.group(1)
                break
        if part:
            unresolved_parts[part] += 1
    unresolved_rows = "".join(
        f'<tr><td>Part {html.escape(p)}</td><td class="num">{n}</td></tr>'
        for p, n in sorted(unresolved_parts.items(), key=lambda x: -x[1])[:30]
    )

    body = (
        f'<p><b>{len(resolved)}</b> resolved cross-doc references, <b>{len(unresolved)}</b> unresolved '
        '(referenced parts/sections we have not ingested yet).</p>'
        f'<h2>Resolved references by doc pair</h2>'
        f'<table><thead><tr><th>source doc</th><th>target doc</th><th>edges</th></tr></thead>'
        f'<tbody>{pair_rows or "<tr><td colspan=3>(none yet)</td></tr>"}</tbody></table>'
        f'<h2>Sample of resolved edges</h2>'
        f'<table><thead><tr><th>source</th><th>citation in source</th><th>target</th><th>type</th></tr></thead>'
        f'<tbody>{sample or "<tr><td colspan=4>(none yet)</td></tr>"}</tbody></table>'
        f'<h2>Most-referenced unresolved parts (candidates for next ingest)</h2>'
        f'<table><thead><tr><th>part</th><th>references</th></tr></thead>'
        f'<tbody>{unresolved_rows or "<tr><td colspan=2>(none)</td></tr>"}</tbody></table>'
    )
    (out_dir / "index.html").write_text(_page("Cross-doc references", "../../index.html", body), encoding="utf-8")


def build_pivot_index(data):
    body = (
        '<p>Cross-cutting views across every registered doc.</p>'
        '<table><thead><tr><th>view</th><th>what it shows</th></tr></thead><tbody>'
        '<tr><td><a href="by-tag/index.html">By applicability tag</a></td>'
        '<td>Requirements grouped by per-requirement tags (audit_trail, signature, etc.).</td></tr>'
        '<tr><td><a href="by-subsystem/index.html">By CTMS subsystem</a></td>'
        '<td>Requirements grouped by per-doc applies_to subsystem (edc, iwrs, ecoa, etmf, ctms_general).</td></tr>'
        '<tr><td><a href="glossary/index.html">Glossary</a></td>'
        '<td>Every defined term across every doc, with all definition sources.</td></tr>'
        '<tr><td><a href="cross-doc/index.html">Cross-doc references</a></td>'
        '<td>Explicit citations from one doc to another, plus referenced parts we have not yet ingested.</td></tr>'
        '<tr><td><a href="scope-triage/index.html">Scope triage</a></td>'
        '<td>Unresolved referenced parts classified as process, defer, exclude, or already processed.</td></tr>'
        '<tr><td><a href="../relationships.html">Unified atomic relationship map</a></td>'
        '<td>Atomic requirement graph spanning all documents, including resolved cross-document atomic references.</td></tr>'
        '</tbody></table>'
        f'<p style="color:#6b7280; margin-top:1rem;">Stats: '
        f'<b>{len(data["global_reqs"])}</b> requirements across <b>{len(data["docs"])}</b> docs · '
        f'<b>{len(data["tag_index"])}</b> tags · '
        f'<b>{len(data["subsys_index"])}</b> subsystems · '
        f'<b>{len(data["glossary"])}</b> defined terms.</p>'
    )
    PIVOTS.mkdir(parents=True, exist_ok=True)
    (PIVOTS / "index.html").write_text(_page("Pivot views", "../index.html", body), encoding="utf-8")


def main():
    data = collect()
    build_pivot_index(data)
    build_by_tag(data)
    build_by_subsystem(data)
    build_glossary(data)
    build_cross_doc(data)
    print(f"Built pivots: {len(data['global_reqs'])} reqs, "
          f"{len(data['tag_index'])} tags, {len(data['subsys_index'])} subsystems, "
          f"{len(data['glossary'])} glossary terms.")
    print(f"Pivot landing: {PIVOTS / 'index.html'}")


if __name__ == "__main__":
    main()
