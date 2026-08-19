"""Build a unified atomic-requirement relationship map across all documents.

Outputs:
  docs/atomic_relationship_map.json
  docs/review_site/relationships.html

The map contains:
  - all intra-document relationships from each doc's catalog/relationships.jsonl
  - cross-document atomic references when a cross-doc citation resolves to a
    target span that contains atomic requirements

Part-level cross-doc references are counted as unresolved-to-atomic because
linking one citing requirement to every requirement in another part would create
noise rather than knowledge.
"""
from __future__ import annotations

import html
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from regcat.global_ids import global_id
from regcat.registry import all_docs, doc_dir as resolve_doc_dir

SITE = ROOT / "docs" / "review_site"


def loadl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect() -> dict:
    docs = all_docs(ROOT)
    nodes: dict[str, dict] = {}
    reqs_by_doc: dict[str, dict[str, dict]] = {}
    reqs_by_span: dict[tuple[str, str], list[dict]] = defaultdict(list)
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str, str]] = set()

    for d in docs:
        base = resolve_doc_dir(ROOT, d.doc_id)
        reqs = loadl(base / "catalog" / "requirements.jsonl")
        rels = loadl(base / "catalog" / "relationships.jsonl")
        reqs_by_doc[d.doc_id] = {}
        for r in reqs:
            gid = global_id(d.doc_id, r["req_id"])
            node = {
                "id": gid,
                "doc_id": d.doc_id,
                "doc_title": d.title,
                "req_id": r["req_id"],
                "citation": r.get("citation_raw", ""),
                "statement": r.get("atomic_statement", ""),
                "modality": r.get("modality", ""),
                "subject": r.get("subject", ""),
                "object": r.get("object", ""),
                "tags": r.get("applicability_tags", []),
                "conditions": r.get("conditions", []),
                "source_span_id": r.get("source_span_id", ""),
            }
            nodes[gid] = node
            reqs_by_doc[d.doc_id][r["req_id"]] = node
            reqs_by_span[(d.doc_id, r.get("source_span_id", ""))].append(node)

        for rel in rels:
            src = reqs_by_doc[d.doc_id].get(rel.get("source_req_id"))
            tgt = reqs_by_doc[d.doc_id].get(rel.get("target_req_id"))
            if not src or not tgt:
                continue
            edge = {
                "id": global_id(d.doc_id, rel.get("rel_id", "")),
                "source": src["id"],
                "target": tgt["id"],
                "source_doc": d.doc_id,
                "target_doc": d.doc_id,
                "type": rel.get("type", ""),
                "scope": "intra_doc",
                "evidence": rel.get("evidence", ""),
                "citation": "",
            }
            key = (edge["source"], edge["target"], edge["type"], edge["scope"])
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(edge)

    cross_edges = loadl(ROOT / "docs" / "cross_doc_relationships.jsonl")
    cross_resolved = 0
    cross_unresolved_to_atomic = 0
    for ref in cross_edges:
        if not ref.get("auto_resolved"):
            continue
        src_doc = ref.get("source_doc")
        tgt_doc = ref.get("target_doc")
        src_span = ref.get("source_span_id")
        tgt_span = ref.get("target_span_id")
        source_reqs = reqs_by_span.get((src_doc, src_span), [])
        if not source_reqs or not tgt_span:
            cross_unresolved_to_atomic += 1
            continue
        target_reqs = reqs_by_span.get((tgt_doc, tgt_span), [])
        if not target_reqs:
            cross_unresolved_to_atomic += 1
            continue
        for src in source_reqs:
            for tgt in target_reqs:
                edge = {
                    "id": f"cross:{src['id']}->{tgt['id']}:{ref.get('citation_in_source', '')}",
                    "source": src["id"],
                    "target": tgt["id"],
                    "source_doc": src_doc,
                    "target_doc": tgt_doc,
                    "type": "cross_doc_reference",
                    "scope": "cross_doc",
                    "evidence": f"source cites {ref.get('citation_in_source', '')}",
                    "citation": ref.get("citation_in_source", ""),
                    "source_span_id": src_span,
                    "target_span_id": tgt_span,
                }
                key = (edge["source"], edge["target"], edge["type"], edge["scope"])
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append(edge)
                    cross_resolved += 1

    by_scope = defaultdict(int)
    by_type = defaultdict(int)
    by_doc_pair = defaultdict(int)
    for e in edges:
        by_scope[e["scope"]] += 1
        by_type[e["type"]] += 1
        by_doc_pair[f"{e['source_doc']} -> {e['target_doc']}"] += 1

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "documents": len(docs),
            "nodes": len(nodes),
            "edges": len(edges),
            "edges_by_scope": dict(sorted(by_scope.items())),
            "edges_by_type": dict(sorted(by_type.items())),
            "edges_by_doc_pair": dict(sorted(by_doc_pair.items())),
            "cross_doc_atomic_edges": cross_resolved,
            "cross_doc_refs_unresolved_to_atomic": cross_unresolved_to_atomic,
        },
    }


def write_map(data: dict) -> Path:
    out = ROOT / "docs" / "atomic_relationship_map.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def write_graph(data: dict) -> Path:
    docs = sorted({n["doc_id"] for n in data["nodes"]})
    type_counts = data["stats"]["edges_by_type"]
    scope_counts = data["stats"]["edges_by_scope"]
    doc_options = "\n".join(f'<option value="{html.escape(d)}">{html.escape(d)}</option>' for d in docs)
    type_toggles = "\n".join(
        f'<label><input type="checkbox" value="{html.escape(t)}" checked> {html.escape(t)} <span>{n}</span></label>'
        for t, n in sorted(type_counts.items())
    )
    scope_toggles = "\n".join(
        f'<label><input type="checkbox" value="{html.escape(s)}" checked> {html.escape(s)} <span>{n}</span></label>'
        for s, n in sorted(scope_counts.items())
    )
    out = SITE / "relationships.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(GLOBAL_GRAPH_TEMPLATE.format(
        node_count=data["stats"]["nodes"],
        edge_count=data["stats"]["edges"],
        doc_count=data["stats"]["documents"],
        cross_count=data["stats"]["cross_doc_atomic_edges"],
        unresolved_count=data["stats"]["cross_doc_refs_unresolved_to_atomic"],
        doc_options=doc_options,
        type_toggles=type_toggles,
        scope_toggles=scope_toggles,
        nodes_json=json.dumps(data["nodes"], ensure_ascii=False),
        edges_json=json.dumps(data["edges"], ensure_ascii=False),
    ), encoding="utf-8")
    return out


GLOBAL_GRAPH_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>regcat unified atomic relationship map</title>
<style>
  :root {{ --bg:#f6f7f9; --fg:#1a1d23; --muted:#6b7280; --border:#d9dce1; --card:#ffffff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; height:100vh; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; color:var(--fg); background:var(--bg); font-size:14px; }}
  header {{ height:50px; display:flex; align-items:center; gap:1rem; padding:0 1rem; background:var(--card); border-bottom:1px solid var(--border); }}
  header h1 {{ margin:0; font-size:1rem; }}
  header a {{ color:#2563cf; text-decoration:none; }}
  header .stats {{ margin-left:auto; display:flex; gap:0.75rem; color:var(--muted); font-size:0.82rem; }}
  .app {{ height:calc(100vh - 50px); display:grid; grid-template-columns:320px 1fr 390px; }}
  aside, .detail {{ background:var(--card); overflow:auto; }}
  aside {{ border-right:1px solid var(--border); }}
  .detail {{ border-left:1px solid var(--border); }}
  .panel {{ padding:0.85rem; border-bottom:1px solid var(--border); }}
  .panel h2 {{ margin:0 0 0.5rem; font-size:0.78rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; }}
  select, input, button {{ font:inherit; }}
  select, input[type=search] {{ width:100%; padding:0.38rem 0.5rem; border:1px solid var(--border); border-radius:4px; background:white; }}
  button {{ border:1px solid var(--border); border-radius:4px; background:var(--bg); padding:0.35rem 0.55rem; cursor:pointer; }}
  .row {{ display:grid; grid-template-columns:1fr 1fr; gap:0.45rem; }}
  .buttons {{ display:flex; flex-wrap:wrap; gap:0.35rem; margin-top:0.5rem; }}
  label {{ display:block; padding:0.18rem 0; }}
  label span {{ float:right; color:var(--muted); }}
  .hint {{ color:var(--muted); font-size:0.78rem; line-height:1.35; }}
  .graph {{ position:relative; min-width:0; min-height:0; }}
  canvas {{ display:block; width:100%; height:100%; background:#fbfbfc; }}
  .hud {{ position:absolute; left:12px; bottom:12px; background:rgba(255,255,255,0.94); border:1px solid var(--border); border-radius:4px; padding:0.4rem 0.55rem; color:var(--muted); font-size:0.78rem; pointer-events:none; }}
  .empty {{ color:var(--muted); padding:0.9rem; }}
  .card {{ padding:0.85rem; border-bottom:1px solid var(--border); }}
  .gid {{ font-family:ui-monospace,"SF Mono",monospace; color:#2563cf; font-size:0.78rem; word-break:break-all; }}
  .doc {{ color:var(--muted); font-size:0.78rem; }}
  .citation {{ font-weight:600; margin:0.3rem 0; }}
  .statement {{ line-height:1.42; }}
  .modality {{ display:inline-block; background:#14532d; color:white; border-radius:3px; padding:0.05rem 0.35rem; font-size:0.7rem; text-transform:uppercase; margin-right:0.3rem; }}
  .modality.may {{ background:#6b7280; }}
  .modality.should {{ background:#a16207; }}
  .kv {{ color:var(--muted); margin-top:0.45rem; font-size:0.82rem; }}
  .tags span {{ display:inline-block; background:#eef2ff; color:#3730a3; border-radius:3px; padding:0.08rem 0.35rem; margin:0.12rem; }}
  .edge {{ padding:0.55rem 0.85rem; border-bottom:1px solid var(--border); font-size:0.82rem; }}
  .edge small {{ display:block; color:var(--muted); margin-top:0.2rem; line-height:1.35; }}
  .edge button {{ margin-top:0.32rem; font-size:0.75rem; }}
</style>
</head>
<body>
<header>
  <a href="index.html">&larr; review index</a>
  <h1>Unified Atomic Relationship Map</h1>
  <div class="stats"><span><b>{doc_count}</b> docs</span><span><b>{node_count}</b> atomic requirements</span><span><b>{edge_count}</b> edges</span><span><b>{cross_count}</b> cross-doc atomic</span></div>
</header>
<div class="app">
  <aside>
    <div class="panel">
      <h2>Scope</h2>
      <div class="row">
        <div><select id="source-doc"><option value="">any source</option>{doc_options}</select></div>
        <div><select id="target-doc"><option value="">any target</option>{doc_options}</select></div>
      </div>
      <div class="buttons">
        <button id="fit">Fit</button>
        <button id="reset">Reset</button>
        <button id="neighbors">Neighbors</button>
        <button id="all">All</button>
      </div>
    </div>
    <div class="panel">
      <h2>Search</h2>
      <input id="search" type="search" list="node-options" placeholder="Req ID, doc, citation, statement">
      <datalist id="node-options"></datalist>
    </div>
    <div class="panel">
      <h2>Edge Scope</h2>
      <div id="scope-filters">{scope_toggles}</div>
    </div>
    <div class="panel">
      <h2>Relationship Types</h2>
      <div id="type-filters">{type_toggles}</div>
    </div>
    <div class="panel hint">
      Filters redraw the visible subgraph. To keep the graph readable, only the first 1,500 edges matching the filters are drawn at once; search or document filters narrow the map. Cross-doc part-level citations not resolved to atomic requirements: <b>{unresolved_count}</b>.
    </div>
  </aside>
  <main class="graph"><canvas id="graph"></canvas><div class="hud" id="hud"></div></main>
  <section class="detail" id="detail"><div class="empty">Select an atomic requirement.</div></section>
</div>
<script>
const NODES_RAW = {nodes_json};
const EDGES_RAW = {edges_json};
const MAX_EDGES = 1500;
const TYPE_COLORS = {{
  refines:"#2563cf", references:"#7c3aed", exception_to:"#d97706",
  conditional_on:"#0f766e", defined_by:"#be123c", composed_of:"#4b5563",
  cross_doc_reference:"#dc2626"
}};
const nodesById = new Map(NODES_RAW.map(n => [n.id, n]));
let nodes = [], edges = [], selected = null, hover = null;
let activeTypes = new Set([...new Set(EDGES_RAW.map(e => e.type))]);
let activeScopes = new Set([...new Set(EDGES_RAW.map(e => e.scope))]);
let neighborMode = false, scale = 1, tx = 0, ty = 0, dragging = false, dragNode = null, last = null;
const canvas = document.getElementById("graph"), ctx = canvas.getContext("2d"), hud = document.getElementById("hud"), detail = document.getElementById("detail");
const sourceDoc = document.getElementById("source-doc"), targetDoc = document.getElementById("target-doc"), search = document.getElementById("search");
const options = document.getElementById("node-options");
for (const n of NODES_RAW.slice(0, 5000)) {{ const o=document.createElement("option"); o.value=`${{n.id}} ${{n.citation}}`; options.appendChild(o); }}
function esc(s) {{ return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }}
function resize() {{ const r=canvas.getBoundingClientRect(); canvas.width=Math.max(1,Math.floor(r.width*devicePixelRatio)); canvas.height=Math.max(1,Math.floor(r.height*devicePixelRatio)); ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0); draw(); }}
window.addEventListener("resize", resize);
function filteredEdges() {{
  const s=sourceDoc.value, t=targetDoc.value;
  let out = EDGES_RAW.filter(e => activeTypes.has(e.type) && activeScopes.has(e.scope) && (!s || e.source_doc===s) && (!t || e.target_doc===t));
  if (neighborMode && selected) out = out.filter(e => e.source===selected.id || e.target===selected.id);
  return out.slice(0, MAX_EDGES);
}}
function buildGraph() {{
  edges = filteredEdges();
  const ids = new Set();
  for (const e of edges) {{ ids.add(e.source); ids.add(e.target); }}
  if (neighborMode && selected) ids.add(selected.id);
  nodes = [...ids].map(id => Object.assign({{}}, nodesById.get(id), {{x:nodesById.get(id).x ?? (Math.random()-0.5)*1200, y:nodesById.get(id).y ?? (Math.random()-0.5)*800, vx:nodesById.get(id).vx ?? 0, vy:nodesById.get(id).vy ?? 0}}));
}}
function step() {{
  const by = new Map(nodes.map(n=>[n.id,n]));
  for (const n of nodes) {{ n.vx*=0.86; n.vy*=0.86; }}
  for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++) {{
    const a=nodes[i],b=nodes[j]; let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+0.1; if(d2>120000) continue;
    const f=Math.min(1200/d2,0.05); a.vx+=dx*f; a.vy+=dy*f; b.vx-=dx*f; b.vy-=dy*f;
  }}
  for (const e of edges) {{ const a=by.get(e.source), b=by.get(e.target); if(!a||!b) continue; const dx=b.x-a.x, dy=b.y-a.y, d=Math.hypot(dx,dy)||1, f=(d-130)*0.006; a.vx+=dx/d*f; a.vy+=dy/d*f; b.vx-=dx/d*f; b.vy-=dy/d*f; }}
  for (const n of nodes) {{ n.vx += -n.x*0.001; n.vy += -n.y*0.001; if(!n.fixed) {{ n.x+=Math.max(-7,Math.min(7,n.vx)); n.y+=Math.max(-7,Math.min(7,n.vy)); }} Object.assign(nodesById.get(n.id), {{x:n.x,y:n.y,vx:n.vx,vy:n.vy}}); }}
}}
function radius(n) {{ let d=0; for(const e of edges) if(e.source===n.id||e.target===n.id)d++; return Math.min(11,4+Math.sqrt(d)*1.2); }}
function drawArrow(a,b,e,alpha) {{ const color=TYPE_COLORS[e.type]||"#64748b", dx=b.x-a.x, dy=b.y-a.y, d=Math.hypot(dx,dy)||1, ra=radius(a)+2, rb=radius(b)+2; const sx=a.x+dx/d*ra, sy=a.y+dy/d*ra, ex=b.x-dx/d*rb, ey=b.y-dy/d*rb; ctx.globalAlpha=alpha; ctx.strokeStyle=color; ctx.lineWidth=1.1/scale; ctx.beginPath(); ctx.moveTo(sx,sy); ctx.lineTo(ex,ey); ctx.stroke(); const ang=Math.atan2(dy,dx), size=5.5/scale; ctx.beginPath(); ctx.moveTo(ex,ey); ctx.lineTo(ex-Math.cos(ang-.45)*size,ey-Math.sin(ang-.45)*size); ctx.lineTo(ex-Math.cos(ang+.45)*size,ey-Math.sin(ang+.45)*size); ctx.closePath(); ctx.fillStyle=color; ctx.fill(); ctx.globalAlpha=1; }}
function draw() {{ const w=canvas.clientWidth,h=canvas.clientHeight; ctx.clearRect(0,0,w,h); ctx.save(); ctx.translate(tx,ty); ctx.scale(scale,scale); const by=new Map(nodes.map(n=>[n.id,n])); for(const e of edges) {{ const a=by.get(e.source), b=by.get(e.target); if(a&&b) drawArrow(a,b,e,selected && e.source!==selected.id && e.target!==selected.id ? .12 : .6); }} for(const n of nodes) {{ const r=radius(n), sel=selected&&selected.id===n.id, hov=hover&&hover.id===n.id; ctx.beginPath(); ctx.arc(n.x,n.y,r,0,Math.PI*2); ctx.fillStyle=sel?"#111827":hov?"#f59e0b":"#fff"; ctx.fill(); ctx.lineWidth=(sel||hov?2.3:1.1)/scale; ctx.strokeStyle=sel?"#111827":"#64748b"; ctx.stroke(); if(scale>.9||sel||hov) {{ ctx.font=`${{10.5/scale}}px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif`; ctx.fillStyle="#374151"; ctx.fillText(n.req_id,n.x+r+3/scale,n.y+4/scale); }} }} ctx.restore(); hud.textContent=`${{nodes.length}} nodes · ${{edges.length}}/${{filteredEdges().length}} edges drawn · zoom ${{Math.round(scale*100)}}%`; }}
function animate() {{ for(let i=0;i<2;i++) step(); draw(); requestAnimationFrame(animate); }}
function fit() {{ if(!nodes.length)return; let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity; for(const n of nodes){{minX=Math.min(minX,n.x);minY=Math.min(minY,n.y);maxX=Math.max(maxX,n.x);maxY=Math.max(maxY,n.y);}} const w=canvas.clientWidth,h=canvas.clientHeight,p=80; scale=Math.max(.05,Math.min(2.5,Math.min((w-p*2)/(maxX-minX||1),(h-p*2)/(maxY-minY||1)))); tx=w/2-(minX+maxX)/2*scale; ty=h/2-(minY+maxY)/2*scale; draw(); }}
function world(x,y) {{ return {{x:(x-tx)/scale,y:(y-ty)/scale}}; }}
function pick(x,y) {{ const p=world(x,y); let best=null,bd=Infinity; for(const n of nodes){{const d=Math.hypot(n.x-p.x,n.y-p.y); if(d<radius(n)+5/scale&&d<bd){{best=n;bd=d;}}}} return best; }}
function select(n) {{ selected=n?nodesById.get(n.id):null; renderDetail(); if(neighborMode){{buildGraph(); fit();}} draw(); }}
function renderDetail() {{ if(!selected) {{ detail.innerHTML='<div class="empty">Select an atomic requirement.</div>'; return; }} const out=EDGES_RAW.filter(e=>e.source===selected.id&&activeTypes.has(e.type)&&activeScopes.has(e.scope)); const inc=EDGES_RAW.filter(e=>e.target===selected.id&&activeTypes.has(e.type)&&activeScopes.has(e.scope)); const tags=(selected.tags||[]).map(t=>`<span>${{esc(t)}}</span>`).join(""); const edgeHtml=[...out.map(e=>edgeBlock(e,"out")),...inc.map(e=>edgeBlock(e,"in"))].join("")||'<div class="empty">No visible relationships.</div>'; detail.innerHTML=`<div class="card"><div class="gid">${{esc(selected.id)}}</div><div class="doc">${{esc(selected.doc_title)}} · ${{esc(selected.doc_id)}} · span ${{esc(selected.source_span_id)}}</div><div class="citation">${{esc(selected.citation)}}</div><div class="statement"><span class="modality ${{esc(selected.modality)}}">${{esc(selected.modality)}}</span>${{esc(selected.statement)}}</div>${{selected.subject?`<div class="kv"><b>Subject:</b> ${{esc(selected.subject)}}</div>`:""}}${{selected.object?`<div class="kv"><b>Object:</b> ${{esc(selected.object)}}</div>`:""}}${{tags?`<div class="kv tags"><b>Tags:</b><br>${{tags}}</div>`:""}}<div class="buttons"><button onclick="openSource('${{selected.id}}')">Open source view</button></div></div><div>${{edgeHtml}}</div>`; }}
function edgeBlock(e,dir) {{ const oid=dir==="out"?e.target:e.source, other=nodesById.get(oid), arrow=dir==="out"?"→":"←"; return `<div class="edge"><b style="color:${{TYPE_COLORS[e.type]||"#64748b"}}">${{esc(e.type)}}</b> <span>${{esc(e.scope)}}</span> ${{arrow}} <code>${{esc(oid)}}</code><small>${{esc(other?other.citation:"")}} · ${{esc(other?other.doc_id:"")}}</small><small>${{esc(other?other.statement:"")}}</small>${{e.evidence?`<small><b>Evidence:</b> ${{esc(e.evidence)}}</small>`:""}}<button onclick="jump('${{oid}}')">Select</button></div>`; }}
function jump(id) {{ const n=nodesById.get(id); if(!n)return; selected=n; if(!nodes.some(x=>x.id===id)) {{ sourceDoc.value=""; targetDoc.value=""; neighborMode=true; buildGraph(); }} tx=canvas.clientWidth/2-n.x*scale; ty=canvas.clientHeight/2-n.y*scale; renderDetail(); draw(); }}
function openSource(id) {{ const n=nodesById.get(id); if(!n)return; window.location.href=`${{n.doc_id}}/index.html#${{encodeURIComponent(n.req_id)}}`; }}
canvas.addEventListener("mousedown",e=>{{const n=pick(e.offsetX,e.offsetY); dragging=true; last={{x:e.offsetX,y:e.offsetY}}; if(n){{dragNode=n;n.fixed=true;select(n);}}}});
canvas.addEventListener("mousemove",e=>{{hover=pick(e.offsetX,e.offsetY); if(!dragging){{draw();return;}} if(dragNode){{const p=world(e.offsetX,e.offsetY); dragNode.x=p.x; dragNode.y=p.y; Object.assign(nodesById.get(dragNode.id),{{x:p.x,y:p.y}});}} else {{tx+=e.offsetX-last.x; ty+=e.offsetY-last.y; last={{x:e.offsetX,y:e.offsetY}};}} draw();}});
window.addEventListener("mouseup",()=>{{dragging=false;if(dragNode)dragNode.fixed=false;dragNode=null;}});
canvas.addEventListener("wheel",e=>{{e.preventDefault(); const old=scale, f=Math.exp(-e.deltaY*.001); scale=Math.max(.05,Math.min(4,scale*f)); tx=e.offsetX-(e.offsetX-tx)*(scale/old); ty=e.offsetY-(e.offsetY-ty)*(scale/old); draw();}},{{passive:false}});
function refresh() {{ buildGraph(); renderDetail(); fit(); }}
sourceDoc.onchange=refresh; targetDoc.onchange=refresh;
document.querySelectorAll("#type-filters input").forEach(cb=>cb.onchange=()=>{{activeTypes=new Set([...document.querySelectorAll("#type-filters input:checked")].map(x=>x.value)); refresh();}});
document.querySelectorAll("#scope-filters input").forEach(cb=>cb.onchange=()=>{{activeScopes=new Set([...document.querySelectorAll("#scope-filters input:checked")].map(x=>x.value)); refresh();}});
search.onchange=()=>{{const q=search.value.trim().toLowerCase(); if(!q)return; let n=NODES_RAW.find(x=>x.id.toLowerCase()===q||x.req_id.toLowerCase()===q)||NODES_RAW.find(x=>`${{x.id}} ${{x.doc_id}} ${{x.citation}} ${{x.statement}}`.toLowerCase().includes(q)); if(n)jump(n.id);}};
document.getElementById("fit").onclick=fit; document.getElementById("reset").onclick=()=>{{selected=null;neighborMode=false;sourceDoc.value="";targetDoc.value="";refresh();}}; document.getElementById("neighbors").onclick=()=>{{if(selected){{neighborMode=true;refresh();}}}}; document.getElementById("all").onclick=()=>{{neighborMode=false;refresh();}};
buildGraph(); resize(); setTimeout(fit,50); animate();
</script>
</body>
</html>
"""


def main() -> None:
    data = collect()
    map_path = write_map(data)
    graph_path = write_graph(data)
    print(f"wrote {map_path} ({data['stats']['nodes']} nodes, {data['stats']['edges']} edges)")
    print(f"wrote {graph_path}")


if __name__ == "__main__":
    main()
