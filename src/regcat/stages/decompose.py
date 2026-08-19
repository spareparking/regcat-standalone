"""Stage 5: Decompose each requirement-bearing span into atomic requirements.

Two parallel agents (Decomposer-A, Decomposer-B) + Reconciler. On disagreement that
the Reconciler can't merge, the requirement is emitted with `ambiguous: true` and the
alternate reading is preserved in `alternates`.

Output: data/catalog/requirements.jsonl
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..prompts.decompose import (
    DECOMPOSER_A_SYSTEM, DECOMPOSER_B_SYSTEM, DECOMPOSER_USER_TEMPLATE,
    RECONCILER_DECOMPOSE_SYSTEM, RECONCILER_DECOMPOSE_USER_TEMPLATE,
)
from ..schemas import AtomicRequirement, Modality


def run(ctx) -> None:
    paths = ctx.paths
    spans = {s["span_id"]: s for s in ctx.read_jsonl(paths.source_dir / "spans.jsonl")}
    classifications = {c["span_id"]: c for c in ctx.read_jsonl(paths.catalog_dir / "classifications.jsonl")}

    out_path = paths.catalog_dir / "requirements.jsonl"
    existing_reqs: list[dict] = []
    already_done_spans: set[str] = set()
    if out_path.exists():
        existing_reqs = ctx.read_jsonl(out_path)
        already_done_spans = {r["source_span_id"] for r in existing_reqs}
        if already_done_spans:
            ctx.log(f"    decompose: resuming — {len(already_done_spans)} source spans already decomposed, skipping")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fout = out_path.open("a", encoding="utf-8")

    requirements: list[AtomicRequirement] = []
    reconciler_log: list[dict] = []
    next_req_idx = max((int(r["req_id"][1:]) for r in existing_reqs), default=0)

    def next_req_id() -> str:
        nonlocal next_req_idx
        next_req_idx += 1
        return f"R{next_req_idx:05d}"

    def persist(req: AtomicRequirement) -> None:
        fout.write(json.dumps(req.model_dump(mode="json"), ensure_ascii=False) + "\n")
        fout.flush()

    for sid, span in spans.items():
        c = classifications.get(sid)
        if not c:
            continue
        # Run decompose if requirement_bearing is the primary OR an embedded label.
        labels = {c.get("final_label")} | set(c.get("final_embedded", []))
        if "requirement_bearing" not in labels:
            continue
        if sid in already_done_spans:
            continue
        if c.get("downgrade_pending"):
            # Already flagged on a previous run: the decomposers returned zero
            # requirements. Resolution belongs to the downgrade adjudicator, not
            # to a re-run of the decomposers (keeps resume cheap + deterministic).
            continue

        citation = span["citation"].get("raw") or "(no citation)"
        parent_chain = _build_parent_chain(span, spans)
        user = DECOMPOSER_USER_TEMPLATE.format(
            citation=citation, kind=span["kind"], parent_chain=parent_chain, text=span["text"],
        )

        out_a = ctx.llm.complete_json("decomposer_a", sid, DECOMPOSER_A_SYSTEM, user)
        out_b = ctx.llm.complete_json("decomposer_b", sid, DECOMPOSER_B_SYSTEM, user)

        reqs_a = out_a.get("requirements", []) or []
        reqs_b = out_b.get("requirements", []) or []

        if _equivalent(reqs_a, reqs_b):
            merged = reqs_a
            ambiguous = False
            reconciler_note = "agreement"
        else:
            recon_user = RECONCILER_DECOMPOSE_USER_TEMPLATE.format(
                citation=citation, kind=span["kind"], text=span["text"],
                requirements_a_json=json.dumps(reqs_a, ensure_ascii=False, indent=2),
                requirements_b_json=json.dumps(reqs_b, ensure_ascii=False, indent=2),
            )
            recon = ctx.llm.complete_json("reconciler_decompose", sid, RECONCILER_DECOMPOSE_SYSTEM, recon_user)
            merged = recon.get("requirements", []) or []
            # Per the prompt, the reconciler MAY tag individual items as ambiguous;
            # ambiguous-at-span-level is true if any item is ambiguous.
            ambiguous = any(bool(r.get("ambiguous")) for r in merged)
            reconciler_note = "reconciled"

            reconciler_log.append({
                "stage": "decompose",
                "span_id": sid,
                "count_a": len(reqs_a), "count_b": len(reqs_b), "count_final": len(merged),
                "ambiguous_items": sum(1 for r in merged if r.get("ambiguous")),
                "status": "ambiguous" if ambiguous else "resolved",
            })

        for r in merged:
            raw_quote = r.get("verbatim_quote", "").strip()
            canonical_quote = _canonicalize_quote(raw_quote, span["text"])
            req = AtomicRequirement(
                req_id=next_req_id(),
                source_span_id=sid,
                citation_raw=citation,
                verbatim_quote=canonical_quote,
                atomic_statement=r.get("atomic_statement", "").strip(),
                modality=_coerce_modality(r.get("modality")),
                subject=r.get("subject", "").strip(),
                object=r.get("object", "").strip(),
                applicability_tags=[t.strip().lower() for t in r.get("applicability_tags", []) if t],
                conditions=[c2.strip() for c2 in r.get("conditions", []) if c2],
                ambiguous=bool(r.get("ambiguous", False)),
                alternates=r.get("alternates", []) or [],
            )
            requirements.append(req)
            persist(req)

    fout.close()
    _append_jsonl(paths.audit_dir / "reconciler_log.jsonl", reconciler_log)
    all_reqs = ctx.read_jsonl(out_path)

    # Decomposer/classifier disagreement: the decomposers produced zero requirements
    # for a span whose labels include requirement_bearing (primary or embedded).
    # Per the project's locked philosophy — on persistent disagreement, preserve
    # both interpretations; never silently pick — we do NOT change any label here.
    # The classification record is flagged `downgrade_pending`, the would-have-been
    # downgrade is preserved in `downgrade_proposal`, and finalization blocks until
    # the downgrade adjudicator resolves it (`confirm_downgrade` or `extract`).
    spans_with_reqs = {r["source_span_id"] for r in all_reqs}
    newly_pending: list[str] = []
    cleared_pending: list[str] = []
    classification_list = list(classifications.values())
    for c in classification_list:
        sid = c["span_id"]
        labels = {c.get("final_label")} | set(c.get("final_embedded", []))
        if "requirement_bearing" not in labels:
            continue
        if sid in spans_with_reqs:
            if c.get("downgrade_pending"):
                # Requirements now exist for a previously-pending span (e.g. a
                # later merge or re-run extracted them): the disagreement is gone.
                resolve_downgrade_extracted(c, "requirements present after re-run")
                cleared_pending.append(sid)
            continue
        if c.get("downgrade_pending"):
            continue  # already flagged; idempotent on resume
        if c.get("final_label") == "requirement_bearing":
            reason = "span likely a fragment or non-substantive"
        else:
            reason = "embedded requirement_bearing flag unsupported by decomposition"
        mark_downgrade_pending(c, reason=reason, source="pipeline_decompose")
        newly_pending.append(sid)
    if newly_pending or cleared_pending:
        ctx.write_jsonl(paths.catalog_dir / "classifications.jsonl", classification_list)
        if newly_pending:
            ctx.log(f"    decompose: {len(newly_pending)} requirement-bearing spans with 0 "
                    f"requirements flagged downgrade_pending (labels preserved; "
                    f"adjudication required): {newly_pending}")
        if cleared_pending:
            ctx.log(f"    decompose: cleared downgrade_pending on {len(cleared_pending)} "
                    f"spans that now have requirements: {cleared_pending}")

    req_bearing_spans = sum(
        1 for c in classifications.values()
        if "requirement_bearing" in ({c.get("final_label")} | set(c.get("final_embedded", [])))
    )
    ctx.log(f"    decompose: {len(all_reqs)} requirements total "
            f"({len(requirements)} this run) from {req_bearing_spans} req-bearing spans")


def mark_downgrade_pending(c: dict, reason: str, source: str) -> None:
    """Flag a requirement-bearing classification whose decomposers returned zero
    requirements.

    Labels are NOT changed. The would-have-been downgrade (the label the old
    behavior would have silently applied) is recorded in `downgrade_proposal` and
    finalization blocks until the downgrade adjudicator decides:
      - confirm_downgrade: apply the recorded non-requirement label, or
      - extract: requirements are supplied and the span stays requirement-bearing.
    Idempotent: a record already pending is left untouched.
    """
    if c.get("downgrade_pending"):
        return
    primary = c.get("final_label")
    embedded = list(c.get("final_embedded", []))
    if primary == "requirement_bearing":
        kind = "primary"
        proposed_label = next((e for e in embedded if e != "requirement_bearing"), "administrative")
        proposed_embedded = [e for e in embedded if e not in (proposed_label, "requirement_bearing")]
    else:
        kind = "embedded"
        proposed_label = primary
        proposed_embedded = [e for e in embedded if e != "requirement_bearing"]
    c["downgrade_pending"] = True
    c["downgrade_proposal"] = {
        "kind": kind,
        "proposed_label": proposed_label,
        "proposed_embedded": proposed_embedded,
        "reason": reason,
        "source": source,
    }
    note = c.get("reconciler_note", "") or ""
    if kind == "primary":
        detail = f"downgrade of primary to {proposed_label} pending adjudication"
    else:
        detail = "removal of embedded requirement_bearing flag pending adjudication"
    c["reconciler_note"] = (
        note + f" | decomposers returned 0 requirements; {detail} ({reason})"
    ).lstrip(" |")


def resolve_downgrade_extracted(c: dict, rationale: str) -> None:
    """Clear a pending downgrade because requirements now exist for the span."""
    proposal = dict(c.get("downgrade_proposal") or {})
    proposal["resolution"] = {"decision": "extract", "rationale": rationale}
    c["downgrade_pending"] = False
    c["downgrade_proposal"] = proposal
    c["reconciler_note"] = (
        (c.get("reconciler_note", "") + " | ").lstrip(" |")
        + f"downgrade_pending cleared: {rationale}"
    )


def _build_parent_chain(span: dict, all_spans: dict[str, dict]) -> str:
    chain = []
    pid = span.get("parent_span_id")
    while pid:
        p = all_spans.get(pid)
        if not p:
            break
        chain.insert(0, p["citation"].get("raw") or p["span_id"])
        pid = p.get("parent_span_id")
    return " > ".join(chain) if chain else "(top-level)"


def _canonicalize_quote(quote: str, span_text: str) -> str:
    """Return the true verbatim form of `quote` as it appears in `span_text`.

    The LLM often normalizes PDF line-wrap whitespace (turning "\\n" into " ").
    To preserve byte-true verbatim quotes in the catalog, we look for the source
    substring that matches the LLM's quote up to whitespace runs, and substitute
    it. If no such substring exists, we return the original quote unchanged —
    the audit will then flag it as a real failure.
    """
    if not quote or quote in span_text:
        return quote
    # Normalize the LLM's quote: collapse whitespace, drop commas/semicolons (LLMs sometimes
    # add or remove a serial comma); then build a regex that:
    #   - allows any whitespace run AND optional commas/semicolons between tokens
    #   - allows soft-hyphen wraps ("FDA-\nregulated" vs "FDA-regulated") inside tokens
    needle_norm = re.sub(r"\s+", " ", quote).strip()
    needle_clean = re.sub(r"\s+", " ", re.sub(r"[,;]", "", needle_norm)).strip()
    if not needle_clean:
        return quote
    tokens = [re.escape(p).replace("-", r"-\s*") for p in needle_clean.split(" ")]
    # Inter-token: any mix of whitespace + commas/semicolons (at least one whitespace char).
    pattern = r"[,;]?\s+[,;]?\s*".join(tokens)
    m = re.search(pattern, span_text)
    return m.group(0) if m else quote


def _coerce_modality(s) -> Modality:
    if isinstance(s, Modality):
        return s
    try:
        return Modality((s or "unspecified").strip().lower())
    except ValueError:
        return Modality.UNSPECIFIED


def _equivalent(a: list[dict], b: list[dict]) -> bool:
    """Cheap shape-equality check: same count, same verbatim_quote multiset."""
    if len(a) != len(b):
        return False
    qa = sorted((r.get("verbatim_quote") or "").strip() for r in a)
    qb = sorted((r.get("verbatim_quote") or "").strip() for r in b)
    return qa == qb


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")
