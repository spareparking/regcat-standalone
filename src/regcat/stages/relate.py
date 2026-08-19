"""Stage 7: Build the relationship graph between atomic requirements.

Unlike Stages 4/5 (per-span), this stage operates on the *full* catalog at once.
Two parallel agents (A, B) are called with the entire requirements list; a
Reconciler merges their edge sets and tags persistent disagreements as ambiguous.

Output: data/catalog/relationships.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

from ..prompts.relate import (
    RELATIONSHIP_A_SYSTEM, RELATIONSHIP_B_SYSTEM, RELATIONSHIP_USER_TEMPLATE,
    RECONCILER_RELATE_SYSTEM, RECONCILER_RELATE_USER_TEMPLATE,
)
from ..schemas import Relationship, RelationshipType

RELATIONSHIP_MAX_TOKENS = 12000
RELATIONSHIP_CHUNK_SIZE = 140
RELATIONSHIP_CHUNK_THRESHOLD = 260


def run(ctx) -> None:
    paths = ctx.paths
    requirements = ctx.read_jsonl(paths.catalog_dir / "requirements.jsonl")
    if not requirements:
        ctx.log("    relate: no requirements yet, skipping")
        return

    if len(requirements) > RELATIONSHIP_CHUNK_THRESHOLD:
        merged, log_entries, agent_counts = _run_chunked(ctx, requirements)
        reconciler_note = f"chunked; chunks={len(agent_counts)}"
        total_a = sum(a for a, _ in agent_counts)
        total_b = sum(b for _, b in agent_counts)
    else:
        catalog_jsonl = "\n".join(json.dumps(_compact_req(r), ensure_ascii=False) for r in requirements)
        merged, log_entry, agent_count = _run_relationship_agents(ctx, catalog_jsonl, "all")
        log_entries = [log_entry] if log_entry else []
        reconciler_note = "reconciled" if log_entry else "agreement"
        total_a, total_b = agent_count

    valid_req_ids = {r["req_id"] for r in requirements}
    relationships = _coerce_relationships(merged, valid_req_ids)
    ctx.write_jsonl(paths.catalog_dir / "relationships.jsonl", relationships)

    if log_entries:
        log_path = paths.audit_dir / "reconciler_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            for entry in log_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    ctx.log(f"    relate: {len(relationships)} edges  "
            f"({reconciler_note}; a={total_a} b={total_b})")


def _run_chunked(ctx, requirements: list[dict]) -> tuple[list[dict], list[dict], list[tuple[int, int]]]:
    """Run relationship extraction in contiguous chunks for large catalogs.

    Most intra-document regulatory relationships are local to nearby sections. Chunking
    prevents large procedural parts from exceeding provider token-per-minute limits.
    Cross-document and part-level references are handled by the separate cross-doc scan.
    """
    all_edges: list[dict] = []
    log_entries: list[dict] = []
    agent_counts: list[tuple[int, int]] = []
    seen: set[tuple[str, str, str]] = set()

    for idx, start in enumerate(range(0, len(requirements), RELATIONSHIP_CHUNK_SIZE), start=1):
        chunk = requirements[start:start + RELATIONSHIP_CHUNK_SIZE]
        key = f"chunk-{idx:03d}"
        catalog_jsonl = "\n".join(json.dumps(_compact_req(r), ensure_ascii=False) for r in chunk)
        merged, log_entry, agent_count = _run_relationship_agents(ctx, catalog_jsonl, key)
        agent_counts.append(agent_count)
        if log_entry:
            log_entries.append(log_entry)
        for edge in merged:
            dedupe_key = (edge.get("source_req_id", ""), edge.get("target_req_id", ""), edge.get("type", ""))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            all_edges.append(edge)
        ctx.log(f"    relate: {key} {len(chunk)} reqs -> {len(merged)} candidate edges")

    return all_edges, log_entries, agent_counts


def _run_relationship_agents(ctx, catalog_jsonl: str, key: str) -> tuple[list[dict], dict | None, tuple[int, int]]:
    user = RELATIONSHIP_USER_TEMPLATE.format(catalog_jsonl=catalog_jsonl)

    out_a = ctx.llm.complete_json(
        "relationship_a",
        key,
        RELATIONSHIP_A_SYSTEM,
        user,
        max_tokens=RELATIONSHIP_MAX_TOKENS,
    )
    out_b = ctx.llm.complete_json(
        "relationship_b",
        key,
        RELATIONSHIP_B_SYSTEM,
        user,
        max_tokens=RELATIONSHIP_MAX_TOKENS,
    )

    rels_a = out_a.get("relationships", []) or []
    rels_b = out_b.get("relationships", []) or []

    if _edges_equal(rels_a, rels_b):
        merged = rels_a
        reconciler_note = "agreement"
        reconciler_log_entry = None
    else:
        recon_user = RECONCILER_RELATE_USER_TEMPLATE.format(
            catalog_jsonl=catalog_jsonl,
            relationships_a_json=json.dumps(rels_a, ensure_ascii=False, indent=2),
            relationships_b_json=json.dumps(rels_b, ensure_ascii=False, indent=2),
        )
        recon = ctx.llm.complete_json(
            "reconciler_relate",
            key,
            RECONCILER_RELATE_SYSTEM,
            recon_user,
            max_tokens=RELATIONSHIP_MAX_TOKENS,
        )
        merged = recon.get("relationships", []) or []
        reconciler_log_entry = {
            "stage": "relate",
            "key": key,
            "count_a": len(rels_a), "count_b": len(rels_b), "count_final": len(merged),
            "ambiguous_items": sum(1 for r in merged if r.get("ambiguous")),
            "status": "ambiguous" if any(r.get("ambiguous") for r in merged) else "resolved",
        }

    return merged, reconciler_log_entry, (len(rels_a), len(rels_b))


def _coerce_relationships(merged: list[dict], valid_req_ids: set[str]) -> list[Relationship]:
    relationships: list[Relationship] = []
    for r in merged:
        if r.get("source_req_id") not in valid_req_ids or r.get("target_req_id") not in valid_req_ids:
            continue
        try:
            rt = RelationshipType(r["type"])
        except (KeyError, ValueError):
            continue
        relationships.append(Relationship(
            rel_id=f"E{len(relationships) + 1:04d}",
            source_req_id=r["source_req_id"],
            target_req_id=r["target_req_id"],
            type=rt,
            evidence=r.get("evidence", ""),
            ambiguous=bool(r.get("ambiguous", False)),
        ))
    return relationships


def _compact_req(r: dict) -> dict:
    return {
        "req_id": r["req_id"],
        "citation": r["citation_raw"],
        "atomic": r["atomic_statement"],
        "subject": r.get("subject", ""),
        "object": r.get("object", ""),
        "applicability_tags": r.get("applicability_tags", []),
    }


def _edges_equal(a: list[dict], b: list[dict]) -> bool:
    if len(a) != len(b):
        return False
    key = lambda r: (r.get("source_req_id"), r.get("target_req_id"), r.get("type"))
    return sorted(a, key=key) == sorted(b, key=key)
