"""Stage: LLM adjudication of residual catalog ambiguity."""
from __future__ import annotations


def run(ctx) -> None:
    if ctx.llm.mode == "mock":
        ctx.log("    adjudicate: mock mode, no ambiguity adjudication fixtures loaded")
        return

    from ..agent_packets import adjudicate_ambiguous_catalog

    report = adjudicate_ambiguous_catalog(
        ctx.paths.root,
        ctx.paths.doc_id,
        mode=ctx.llm.mode,
        model=ctx.llm.model,
    )
    ctx.write_json(ctx.paths.audit_dir / "catalog_adjudication.json", report)
    ctx.log(
        "    adjudicate: "
        f"classifications={report['classifications'].get('ambiguous_before', 0)} "
        f"requirements={report['requirements'].get('ambiguous_before', 0)} "
        f"relationships={report['relationships'].get('ambiguous_before', 0)} "
        f"changed={report.get('changed', False)}"
    )
