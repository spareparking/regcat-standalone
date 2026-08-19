"""Stage 8: Relationship Validator (deterministic).

Checks:
  - Every edge's source_req_id and target_req_id exist in requirements.jsonl
  - No self-loops
  - No cycles in `refines` and `composed_of` subgraphs
  - Every `references` edge has matching evidence (we don't deeply check text, but
    flag empty evidence as a warning, not an error)
  - Edge types are valid (Pydantic already enforces this on load)

Halts the pipeline on hard failures.
"""
from __future__ import annotations


def run(ctx) -> None:
    paths = ctx.paths
    rels_path = paths.catalog_dir / "relationships.jsonl"
    if not rels_path.exists():
        ctx.log("    validate_rel: no relationships file, skipping")
        return
    rels = ctx.read_jsonl(rels_path)
    reqs = ctx.read_jsonl(paths.catalog_dir / "requirements.jsonl")
    req_ids = {r["req_id"] for r in reqs}

    failures: list[str] = []
    warnings: list[str] = []

    # 1. existence + self-loop
    for e in rels:
        src, tgt = e["source_req_id"], e["target_req_id"]
        if src not in req_ids:
            failures.append(f"{e['rel_id']}: source {src} not in catalog")
        if tgt not in req_ids:
            failures.append(f"{e['rel_id']}: target {tgt} not in catalog")
        if src == tgt:
            failures.append(f"{e['rel_id']}: self-loop on {src}")
        if not e.get("evidence"):
            warnings.append(f"{e['rel_id']}: empty evidence")

    # 2. acyclic refines / composed_of
    def _find_cycles(edge_type: str) -> list[list[str]]:
        # detect cycles via DFS
        graph: dict[str, list[str]] = {}
        for e in rels:
            if e["type"] == edge_type:
                graph.setdefault(e["source_req_id"], []).append(e["target_req_id"])
        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = {}
        cycles: list[list[str]] = []
        stack: list[str] = []

        def dfs(u: str) -> None:
            color[u] = GREY
            stack.append(u)
            for v in graph.get(u, []):
                c = color.get(v, WHITE)
                if c == GREY:
                    idx = stack.index(v)
                    cycles.append(stack[idx:] + [v])
                elif c == WHITE:
                    dfs(v)
            color[u] = BLACK
            stack.pop()

        for node in list(graph.keys()):
            if color.get(node, WHITE) == WHITE:
                dfs(node)
        return cycles

    # Per design: preserve both, tag as ambiguous. Cycles in refines/composed_of are LLM
    # judgment errors but the right behavior is to mark every edge participating in a
    # cycle as ambiguous so downstream consumers can choose to filter them, rather than
    # silently picking one side. We also record the cycle structure in the validation report.
    cycle_report: list[dict] = []
    for edge_type in ("refines", "composed_of"):
        cycles = _find_cycles(edge_type)
        if not cycles:
            continue
        # Collect every (source, target) pair that participates in any cycle
        cycle_pairs: set[tuple[str, str]] = set()
        for cyc in cycles:
            for i in range(len(cyc) - 1):
                cycle_pairs.add((cyc[i], cyc[i + 1]))
            warnings.append(f"cycle in {edge_type}: " + " -> ".join(cyc))
            cycle_report.append({"type": edge_type, "nodes": cyc})
        # Re-write relationships.jsonl with ambiguity flags on cycle edges
        if cycle_pairs:
            for e in rels:
                if e["type"] == edge_type and (e["source_req_id"], e["target_req_id"]) in cycle_pairs:
                    e["ambiguous"] = True
                    e["evidence"] = (e.get("evidence") or "") + " [cycle: flagged ambiguous by validator]"
            ctx.write_jsonl(paths.catalog_dir / "relationships.jsonl", rels)

    report = {
        "edge_count": len(rels),
        "failures": failures,
        "warnings": warnings,
        "cycles_flagged_ambiguous": cycle_report,
        "passed": not failures,
    }
    ctx.write_json(paths.audit_dir / "relationship_validation.json", report)
    ctx.log(f"    validate_rel: edges={len(rels)} failures={len(failures)} "
            f"warnings={len(warnings)} cycles={len(cycle_report)}")
    if failures:
        raise RuntimeError("relationship validation failed: " + "; ".join(failures[:5]))
