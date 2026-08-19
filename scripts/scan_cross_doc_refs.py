"""Deterministic cross-doc citation scanner.

For every span in every registered doc, scan the text for explicit CFR citation
patterns and try to resolve each one to a span (or requirement) in another doc
the system knows about.

Output: docs/cross_doc_relationships.jsonl with one edge per resolved reference.

Patterns we recognize today (US CFR-specific; extend per-jurisdiction later):
  §  X.Y                  full section reference within same chapter
  §§ X.A through X.B      range of sections
  21 CFR X.Y              fully qualified
  21 CFR Part N           full-part reference
  part N                  part reference (lowercase 'part')
  Part N                  part reference (Title-case)
  subpart X of part N     subpart within a different part
  subpart X of this part  internal — not a cross-doc reference

If we can resolve to a specific span (matching section + paragraphs), we record
both source and target as spans. If only the part is identified, we record the
edge at the part-level (target_span_id is null but target_doc resolves).

False-positive guardrails:
  - References inside scope_exclusion or amendment_note spans still count
    (they're real citations to specific other parts)
  - Self-references (e.g., "this part" or "§ 11.30" appearing within Part 11)
    are excluded — they belong to the intra-doc relationship graph.
  - Statutory cites (21 U.S.C. 321) are out of scope; not in our catalog.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from regcat.global_ids import global_id
from regcat.registry import all_docs, doc_dir as resolve_doc_dir


def loadl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- citation regexes -------------------------------------------------------

# Section citation with optional paragraph chain: § 11.10(k)(2)
RX_SECTION = re.compile(
    r"§§?\s*(?P<part>\d+)\.(?P<sec>\d+)(?P<paras>(?:\([a-z0-9ivxlcdm]+\))*)"
)

# "Part NN" — both capitalizations. We accept it only if preceded by a word
# boundary (not "subpart" matching "part" as a substring).
RX_PART = re.compile(r"\b(?:[Pp]art|PART)\s+(?P<part>\d+)\b")

# "21 CFR \d+\.\d+" — fully qualified
RX_CFR_FULL = re.compile(r"\b21\s+CFR\s+(?P<part>\d+)\.(?P<sec>\d+)")

# Range like "§§ 1.326 through 1.368"
RX_SECTION_RANGE = re.compile(
    r"§§\s*(?P<part>\d+)\.(?P<sec_a>\d+)\s+through\s+\d+\.(?P<sec_b>\d+)"
)

# Phrases that indicate self-reference (do NOT count as cross-doc cite)
SELF_REF_HINTS = re.compile(
    r"\bthis (?:part|chapter|subpart|section)\b", re.IGNORECASE
)


# --- resolution -------------------------------------------------------------

def build_doc_index() -> dict[str, dict]:
    """Map CFR part number -> {doc_id, spans_by_section}.

    For each known doc, we read its spans.jsonl and bucket section_headers
    (and their children) by section number, so we can resolve a cited section
    to a target span_id.
    """
    docs = all_docs(ROOT)
    out: dict[str, dict] = {}
    for d in docs:
        # CFR-only for V1; other jurisdictions can register similarly via meta.
        if d.jurisdiction.value != "fda":
            continue
        # Extract part number from short_id like "21-cfr-part-11"
        m = re.match(r"21-cfr-part-(\d+)", d.short_id)
        if not m:
            continue
        part_num = m.group(1)
        spans_path = resolve_doc_dir(ROOT, d.doc_id) / "source" / "spans.jsonl"
        if not spans_path.exists():
            continue
        spans = loadl(spans_path)
        # Build section -> top span_id map (the section_header span)
        spans_by_section: dict[str, str] = {}
        spans_by_section_paragraph: dict[tuple[str, tuple[str, ...]], str] = {}
        for s in spans:
            cit = s.get("citation") or {}
            sec = cit.get("section")
            paras = tuple(cit.get("paragraphs") or [])
            if not sec:
                continue
            if not paras and s.get("kind") == "section_header":
                spans_by_section[sec] = s["span_id"]
            spans_by_section_paragraph[(sec, paras)] = s["span_id"]
        out[part_num] = {
            "doc_id": d.doc_id,
            "spans_by_section": spans_by_section,
            "spans_by_section_paragraph": spans_by_section_paragraph,
        }
    return out


def resolve_section(idx: dict[str, dict], part: str, sec: str,
                     paragraphs: tuple[str, ...]) -> Optional[tuple[str, str]]:
    """Return (target_doc_id, target_span_id) or None."""
    info = idx.get(part)
    if not info:
        return None
    # Try most-specific first: section + exact paragraph chain
    if paragraphs:
        # Walk down: try full chain, then shorter, until we find a match
        for k in range(len(paragraphs), -1, -1):
            sub = tuple(paragraphs[:k])
            sid = info["spans_by_section_paragraph"].get((sec, sub))
            if sid:
                return info["doc_id"], sid
    # Fall back to section_header
    sid = info["spans_by_section"].get(sec)
    if sid:
        return info["doc_id"], sid
    return None


def resolve_part(idx: dict[str, dict], part: str) -> Optional[str]:
    info = idx.get(part)
    return info["doc_id"] if info else None


# --- main scan --------------------------------------------------------------

def scan_doc(doc_id: str, idx: dict[str, dict], src_part: str) -> list[dict]:
    base = resolve_doc_dir(ROOT, doc_id)
    spans_path = base / "source" / "spans.jsonl"
    if not spans_path.exists():
        return []
    spans = loadl(spans_path)
    edges: list[dict] = []
    seen_edges: set[tuple] = set()  # dedupe by (source_span, target_doc, target_span, ref_type)

    for s in spans:
        sid = s["span_id"]
        text = s.get("text") or ""
        self_referential_block = SELF_REF_HINTS.search(text) is not None

        # 1. Section citations
        for m in RX_SECTION.finditer(text):
            part = m.group("part")
            sec = m.group("sec")
            full_sec = f"{part}.{sec}"
            paras_str = m.group("paras") or ""
            paragraphs = tuple(re.findall(r"\(([a-z0-9ivxlcdm]+)\)", paras_str))
            # Self-reference: same part
            if part == src_part:
                continue
            target = resolve_section(idx, part, full_sec, paragraphs)
            if not target:
                # We see the citation but don't have that doc in our catalog
                # (yet). Record as unresolved.
                edges.append({
                    "source_doc": doc_id,
                    "source_span_id": sid,
                    "source_global": global_id(doc_id, sid),
                    "target_doc": None,
                    "target_span_id": None,
                    "target_global": None,
                    "ref_type": "references_external",
                    "citation_in_source": m.group(0).strip(),
                    "auto_resolved": False,
                })
                continue
            t_doc, t_span = target
            key = (sid, t_doc, t_span, "references_external")
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({
                "source_doc": doc_id,
                "source_span_id": sid,
                "source_global": global_id(doc_id, sid),
                "target_doc": t_doc,
                "target_span_id": t_span,
                "target_global": global_id(t_doc, t_span),
                "ref_type": "references_external",
                "citation_in_source": m.group(0).strip(),
                "auto_resolved": True,
            })

        # 2. Section ranges
        for m in RX_SECTION_RANGE.finditer(text):
            part = m.group("part")
            if part == src_part:
                continue
            t_doc = resolve_part(idx, part)
            if t_doc:
                key = (sid, t_doc, None, "references_part_range")
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({
                        "source_doc": doc_id,
                        "source_span_id": sid,
                        "source_global": global_id(doc_id, sid),
                        "target_doc": t_doc,
                        "target_span_id": None,
                        "target_global": t_doc,
                        "ref_type": "references_part_range",
                        "citation_in_source": m.group(0).strip(),
                        "auto_resolved": True,
                    })

        # 3. Part references
        for m in RX_PART.finditer(text):
            part = m.group("part")
            if part == src_part:
                continue
            # Avoid matching "subpart N" — the regex uses [Pp]art word-boundary
            # so "subpart" wouldn't match. But "Part 1" inside a "subpart X of part 1"
            # phrase is a real part reference. We accept it.
            t_doc = resolve_part(idx, part)
            if t_doc:
                key = (sid, t_doc, None, "references_part")
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({
                        "source_doc": doc_id,
                        "source_span_id": sid,
                        "source_global": global_id(doc_id, sid),
                        "target_doc": t_doc,
                        "target_span_id": None,
                        "target_global": t_doc,
                        "ref_type": "references_part",
                        "citation_in_source": m.group(0).strip(),
                        "auto_resolved": True,
                    })
            else:
                edges.append({
                    "source_doc": doc_id,
                    "source_span_id": sid,
                    "source_global": global_id(doc_id, sid),
                    "target_doc": None,
                    "target_span_id": None,
                    "target_global": None,
                    "ref_type": "references_part",
                    "citation_in_source": m.group(0).strip(),
                    "auto_resolved": False,
                })

        # 4. 21 CFR \d+\.\d+ — fully qualified
        for m in RX_CFR_FULL.finditer(text):
            part = m.group("part")
            sec = m.group("sec")
            full_sec = f"{part}.{sec}"
            if part == src_part:
                continue
            target = resolve_section(idx, part, full_sec, ())
            if not target:
                continue
            t_doc, t_span = target
            key = (sid, t_doc, t_span, "references_external")
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({
                    "source_doc": doc_id,
                    "source_span_id": sid,
                    "source_global": global_id(doc_id, sid),
                    "target_doc": t_doc,
                    "target_span_id": t_span,
                    "target_global": global_id(t_doc, t_span),
                    "ref_type": "references_external",
                    "citation_in_source": m.group(0).strip(),
                    "auto_resolved": True,
                })

    return edges


def main():
    idx = build_doc_index()
    if not idx:
        print("No FDA docs found in registry.")
        return

    print(f"Indexed {len(idx)} FDA part(s): {sorted(idx.keys())}")
    all_edges: list[dict] = []
    for part, info in idx.items():
        edges = scan_doc(info["doc_id"], idx, part)
        resolved = sum(1 for e in edges if e["auto_resolved"])
        unresolved = sum(1 for e in edges if not e["auto_resolved"])
        print(f"  {info['doc_id']}: {len(edges)} citations  (resolved={resolved} unresolved={unresolved})")
        all_edges.extend(edges)

    out = ROOT / "docs" / "cross_doc_relationships.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in all_edges:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"\nwrote {out} ({len(all_edges)} edges)")

    # Summary by source doc -> target doc
    pairs: dict[tuple[str, str], int] = defaultdict(int)
    for e in all_edges:
        if e["auto_resolved"]:
            pairs[(e["source_doc"], e["target_doc"])] += 1
    if pairs:
        print("\nResolved edges by doc pair:")
        for (src, tgt), n in sorted(pairs.items()):
            print(f"  {src}  -> {tgt}: {n}")


if __name__ == "__main__":
    main()
