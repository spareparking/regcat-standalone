"""Agent-packet workflow for Codex/Claude-assisted cataloging.

This module does not call a model API. It creates durable work packets that a
subscription-based coding agent can complete directly in the workspace, then
validates and merges only schema-valid, source-grounded output.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Literal, Optional

from .orchestrator import Paths, RunContext, RunMetadata
from .registry import (
    DocStats,
    DocStatus,
    load_meta,
    parse_doc_id,
    save_meta,
    write_registry,
    write_registry_md,
)
from .schemas import (
    AtomicRequirement,
    ClassificationLabel,
    Modality,
    ReconciledClassification,
    Relationship,
    RelationshipType,
)
from .signals import SignalClass, scan as scan_signals
from .stages.decompose import (
    _build_parent_chain,
    _canonicalize_quote,
    mark_downgrade_pending,
    resolve_downgrade_extracted,
)

Stage = Literal["classify", "decompose", "embedded", "relate"]


AGENT_ROOT = "agent_packets"
CLAIM_VERSION = 1
_BATCH_ID_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_STAGES = frozenset({"classify", "decompose", "embedded", "relate"})


def _safe_packet_components(doc_id: str, stage: str, batch_id: str | None = None) -> None:
    parse_doc_id(doc_id)
    if stage not in _STAGES:
        raise ValueError(f"unknown stage: {stage!r}")
    if batch_id is not None and not _BATCH_ID_RX.fullmatch(batch_id):
        raise ValueError(f"batch_id must be a simple identifier, got: {batch_id!r}")


def packet_dir(root: Path, doc_id: str, stage: Stage, batch_id: str) -> Path:
    _safe_packet_components(doc_id, stage, batch_id)
    return Paths.for_doc(root, doc_id).doc_dir / AGENT_ROOT / stage / batch_id


def claim_path(root: Path, doc_id: str) -> Path:
    parse_doc_id(doc_id)
    return Paths.for_doc(root, doc_id).doc_dir / AGENT_ROOT / "claims.json"


def status(root: Path, doc_id: str) -> dict:
    paths = Paths.for_doc(root, doc_id)
    spans = _load_jsonl(paths.source_dir / "spans.jsonl")
    classes = _load_jsonl(paths.catalog_dir / "classifications.jsonl")
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    rels = _load_jsonl(paths.catalog_dir / "relationships.jsonl")
    class_by_span = {c["span_id"]: c for c in classes if "span_id" in c}
    req_bearing = [
        sid for sid, c in class_by_span.items()
        if _is_req_bearing(c)
    ]
    req_source_spans = {r.get("source_span_id") for r in reqs}
    embedded_candidates = _embedded_candidates(spans, classes, paths)
    return {
        "doc_id": doc_id,
        "status": load_meta(root, doc_id).status.value,
        "spans": len(spans),
        "classifications": len(class_by_span),
        "classification_pending": len(spans) - len(class_by_span),
        "req_bearing_spans": len(req_bearing),
        "requirements": len(reqs),
        "decompose_pending": sum(
            1 for sid in req_bearing
            if sid not in req_source_spans and not class_by_span[sid].get("downgrade_pending")
        ),
        "downgrades_pending": sum(
            1 for c in class_by_span.values() if c.get("downgrade_pending")
        ),
        "embedded_candidates_pending": len(embedded_candidates),
        "relationships": len(rels),
        "coverage_report": str(paths.audit_dir / "coverage_report.json"),
        "claims": _claim_summary(root, doc_id),
    }


def export_packet(
    root: Path,
    doc_id: str,
    stage: Stage,
    limit: int,
    batch_id: Optional[str] = None,
    force: bool = False,
) -> Path:
    with _claim_lock(root, doc_id):
        paths = Paths.for_doc(root, doc_id)
        spans = _load_jsonl(paths.source_dir / "spans.jsonl")
        batch_id = batch_id or time.strftime("%Y%m%d-%H%M%S")
        out_dir = packet_dir(root, doc_id, stage, batch_id)
        if out_dir.exists() and any(out_dir.iterdir()) and not force:
            raise RuntimeError(f"packet already exists: {out_dir}; choose a new --batch-id or use --force")
        out_dir.mkdir(parents=True, exist_ok=True)
        claims = _load_claims(root, doc_id)
        claimed = _active_claimed_items(claims, stage)

        if stage == "classify":
            items = _classify_items(paths, spans, limit, claimed)
            instructions = _classify_instructions()
            output_stub = "classification_results.jsonl"
        elif stage == "decompose":
            items = _decompose_items(paths, spans, limit, claimed)
            instructions = _decompose_instructions()
            output_stub = "decomposition_results.jsonl"
        elif stage == "embedded":
            items = _embedded_items(paths, spans, limit, claimed)
            instructions = _embedded_instructions()
            output_stub = "embedded_results.jsonl"
        elif stage == "relate":
            items = [] if _stage_has_active_claim(claims, stage) else _relate_items(paths)
            instructions = _relate_instructions()
            output_stub = "relationship_results.jsonl"
        else:
            raise ValueError(f"unknown stage: {stage}")

        if not items:
            raise RuntimeError(f"no pending items for stage {stage}")
        item_ids = [_item_id(stage, item) for item in items]

        manifest = {
            "doc_id": doc_id,
            "stage": stage,
            "batch_id": batch_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "item_count": len(items),
            "item_ids": item_ids,
            "input_file": "input.jsonl",
            "output_file": output_stub,
            "success_criteria": _success_criteria(stage),
        }
        _record_claim(root, doc_id, stage, batch_id, item_ids)
        _write_json(out_dir / "manifest.json", manifest)
        _write_jsonl(out_dir / "input.jsonl", items)
        (out_dir / "instructions.md").write_text(instructions, encoding="utf-8")
        (out_dir / output_stub).touch(exist_ok=True)
    return out_dir


def validate_packet(root: Path, doc_id: str, stage: Stage, batch_id: str) -> dict:
    paths = Paths.for_doc(root, doc_id)
    pdir = packet_dir(root, doc_id, stage, batch_id)
    manifest = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    input_rows = _load_jsonl(pdir / manifest["input_file"])
    output_path = pdir / manifest["output_file"]
    output_rows = _load_jsonl_strict(output_path)

    if stage == "classify":
        report = _validate_classify(input_rows, output_rows)
    elif stage == "decompose":
        spans_by_id = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
        report = _validate_decompose(input_rows, output_rows, spans_by_id)
    elif stage == "embedded":
        spans_by_id = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
        report = _validate_embedded(input_rows, output_rows, spans_by_id)
    elif stage == "relate":
        req_ids = {r["req_id"] for r in _load_jsonl(paths.catalog_dir / "requirements.jsonl")}
        report = _validate_relate(output_rows, req_ids)
    else:
        raise ValueError(f"unknown stage: {stage}")

    report.update({
        "doc_id": doc_id,
        "stage": stage,
        "batch_id": batch_id,
        "input_count": len(input_rows),
        "output_count": len(output_rows),
        "passed": not report["failures"],
    })
    _write_json(pdir / "validation_report.json", report)
    _update_claim_status(root, doc_id, stage, batch_id, "validated" if report["passed"] else "failed",
                         required=False)
    return report


def merge_packet(root: Path, doc_id: str, stage: Stage, batch_id: str) -> dict:
    with _catalog_lock(root, doc_id):
        report = validate_packet(root, doc_id, stage, batch_id)
        if not report["passed"]:
            raise RuntimeError("packet validation failed; see validation_report.json")

        paths = Paths.for_doc(root, doc_id)
        pdir = packet_dir(root, doc_id, stage, batch_id)
        manifest = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
        rows = _load_jsonl(pdir / manifest["output_file"])

        if stage == "classify":
            merged = _merge_classify(paths, rows)
        elif stage == "decompose":
            merged = _merge_decompose(paths, rows)
        elif stage == "embedded":
            merged = _merge_embedded(paths, rows)
        elif stage == "relate":
            merged = _merge_relate(paths, rows)
        else:
            raise ValueError(f"unknown stage: {stage}")

        _write_json(pdir / "merge_report.json", merged)
        _update_claim_status(root, doc_id, stage, batch_id, "merged", required=False)
        return merged


def list_claims(root: Path, doc_id: str, stage: Optional[Stage] = None) -> dict:
    claims = _load_claims(root, doc_id)
    rows = claims.get("claims", [])
    if stage:
        rows = [r for r in rows if r.get("stage") == stage]
    return {"doc_id": doc_id, "claims": rows}


def release_claim(root: Path, doc_id: str, stage: Stage, batch_id: str) -> dict:
    claims = _load_claims(root, doc_id)
    changed = False
    for row in claims.get("claims", []):
        if row.get("stage") == stage and row.get("batch_id") == batch_id:
            if row.get("status") == "merged":
                raise RuntimeError("cannot release a merged claim")
            row["status"] = "released"
            row["released_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            changed = True
    if not changed:
        raise RuntimeError(f"claim not found for {stage}/{batch_id}")
    _save_claims(root, doc_id, claims)
    return {"released": True, "stage": stage, "batch_id": batch_id}


def finalize(root: Path, doc_id: str) -> None:
    """Run only deterministic validation/render stages after agent merges."""
    paths = Paths.for_doc(root, doc_id)
    paths.ensure()
    ctx = RunContext(
        paths=paths,
        llm=None,  # deterministic stages below do not call ctx.llm
        meta=RunMetadata(
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            pdf_path=str(paths.pdf),
            pdf_sha256="",
            mode="mock",
            model="agent-packet",
        ),
        log_lines=[],
    )
    from .stages import audit, validate_rel
    from .render import markdown

    audit.run(ctx)
    validate_rel.run(ctx)
    _assert_no_unresolved_ambiguity(paths)
    markdown.run(ctx)
    _update_meta_after_finalize(root, doc_id, paths)


def adjudicate_ambiguous_relationships(
    root: Path,
    doc_id: str,
    mode: str = "auto",
    model: Optional[str] = None,
) -> dict:
    """Ask an LLM to resolve ambiguous relationship edges, then apply decisions."""
    paths = Paths.for_doc(root, doc_id)
    rels_path = paths.catalog_dir / "relationships.jsonl"
    if not rels_path.exists():
        return {"doc_id": doc_id, "ambiguous_before": 0, "decisions": [], "changed": False}

    rels = _load_jsonl(rels_path)
    ambiguous = [e for e in rels if e.get("ambiguous")]
    if not ambiguous:
        return {"doc_id": doc_id, "ambiguous_before": 0, "decisions": [], "changed": False}

    reqs = {r["req_id"]: r for r in _load_jsonl(paths.catalog_dir / "requirements.jsonl")}
    payload = []
    for e in ambiguous:
        src = reqs.get(e["source_req_id"], {})
        tgt = reqs.get(e["target_req_id"], {})
        payload.append({
            "rel_id": e["rel_id"],
            "edge": {
                "source_req_id": e["source_req_id"],
                "target_req_id": e["target_req_id"],
                "type": e["type"],
                "evidence": e.get("evidence", ""),
            },
            "source_requirement": _adjudication_req_context(src),
            "target_requirement": _adjudication_req_context(tgt),
        })

    from .llm import LLMClient
    from .prompts.adjudicate import (
        RELATIONSHIP_ADJUDICATOR_SYSTEM,
        RELATIONSHIP_ADJUDICATOR_USER_TEMPLATE,
    )

    edge_types = ", ".join(t.value for t in RelationshipType)
    user = RELATIONSHIP_ADJUDICATOR_USER_TEMPLATE.format(
        doc_id=doc_id,
        edge_types=edge_types,
        edges_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    llm = LLMClient(mode=mode, model=model, env_root=root)
    result = llm.complete_json(
        "relationship_adjudicator",
        "ambiguous",
        RELATIONSHIP_ADJUDICATOR_SYSTEM,
        user,
        max_tokens=6000,
    )

    decisions = result.get("decisions", []) or []
    report = _apply_relationship_adjudication(paths, rels, decisions)
    report.update({
        "doc_id": doc_id,
        "ambiguous_before": len(ambiguous),
        "decisions": decisions,
    })
    _write_json(paths.audit_dir / "relationship_adjudication.json", report)
    return report


def adjudicate_ambiguous_catalog(
    root: Path,
    doc_id: str,
    mode: str = "auto",
    model: Optional[str] = None,
) -> dict:
    """Resolve all catalog ambiguity classes that should not survive completion."""
    class_report = adjudicate_ambiguous_classifications(root, doc_id, mode=mode, model=model)
    downgrade_report = adjudicate_pending_downgrades(root, doc_id, mode=mode, model=model)
    completion_report = complete_unrequirementized_spans(root, doc_id, mode=mode, model=model)
    req_report = adjudicate_ambiguous_requirements(root, doc_id, mode=mode, model=model)
    rel_report = adjudicate_ambiguous_relationships(root, doc_id, mode=mode, model=model)
    changed = any(r.get("changed") for r in (
        class_report, downgrade_report, completion_report, req_report, rel_report,
    ))
    return {
        "doc_id": doc_id,
        "changed": changed,
        "classifications": class_report,
        "downgrades": downgrade_report,
        "missing_requirements": completion_report,
        "requirements": req_report,
        "relationships": rel_report,
    }


def complete_unrequirementized_spans(
    root: Path,
    doc_id: str,
    mode: str = "auto",
    model: Optional[str] = None,
) -> dict:
    """Generate requirements for req-bearing spans left empty after adjudication."""
    paths = Paths.for_doc(root, doc_id)
    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
    classes = _load_jsonl(paths.catalog_dir / "classifications.jsonl")
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    req_source_spans = {r["source_span_id"] for r in reqs}
    pending = [
        c for c in classes
        if _is_req_bearing(c)
        and c.get("span_id") not in req_source_spans
        # Spans already flagged downgrade_pending belong to the downgrade
        # adjudicator (adjudicate_pending_downgrades), not the completion pass.
        and not c.get("downgrade_pending")
    ]
    if not pending:
        return {"doc_id": doc_id, "pending_before": 0, "changed": False}

    from .llm import LLMClient
    from .prompts.decompose import (
        DECOMPOSER_A_SYSTEM,
        DECOMPOSER_B_SYSTEM,
        DECOMPOSER_USER_TEMPLATE,
        RECONCILER_DECOMPOSE_SYSTEM,
        RECONCILER_DECOMPOSE_USER_TEMPLATE,
    )

    llm = LLMClient(mode=mode, model=model, env_root=root)
    next_idx = max((int(r["req_id"][1:]) for r in reqs), default=0)
    added = 0
    downgraded: list[str] = []
    completed: list[dict] = []
    spans_by_id = spans
    classes_by_id = {c["span_id"]: c for c in classes}

    for cls in pending:
        sid = cls["span_id"]
        span = spans[sid]
        user = DECOMPOSER_USER_TEMPLATE.format(
            citation=span["citation"].get("raw") or sid,
            kind=span["kind"],
            parent_chain=_build_parent_chain(span, spans_by_id),
            text=span["text"],
        )
        out_a = llm.complete_json("decomposer_a", f"complete_{sid}", DECOMPOSER_A_SYSTEM, user, max_tokens=4000)
        out_b = llm.complete_json("decomposer_b", f"complete_{sid}", DECOMPOSER_B_SYSTEM, user, max_tokens=4000)
        reconcile_user = RECONCILER_DECOMPOSE_USER_TEMPLATE.format(
            citation=span["citation"].get("raw") or sid,
            kind=span["kind"],
            text=span["text"],
            requirements_a_json=json.dumps(out_a.get("requirements", []), ensure_ascii=False, indent=2),
            requirements_b_json=json.dumps(out_b.get("requirements", []), ensure_ascii=False, indent=2),
        )
        merged = llm.complete_json(
            "reconciler_decompose",
            f"complete_{sid}",
            RECONCILER_DECOMPOSE_SYSTEM,
            reconcile_user,
            max_tokens=5000,
        ).get("requirements", []) or []
        if not merged:
            # Preserve the disagreement: flag for downgrade adjudication instead
            # of silently clearing requirement_bearing.
            mark_downgrade_pending(
                classes_by_id[sid],
                reason="completion decomposers found no supported requirements",
                source="adjudication_completion",
            )
            downgraded.append(sid)
            continue
        before = len(reqs)
        for row in merged:
            next_idx += 1
            reqs.append(_make_requirement(f"R{next_idx:05d}", sid, span, row).model_dump(mode="json"))
        added += len(reqs) - before
        completed.append({"span_id": sid, "requirements_added": len(reqs) - before})

    _atomic_write_jsonl(paths.catalog_dir / "requirements.jsonl", reqs)
    _atomic_write_jsonl(paths.catalog_dir / "classifications.jsonl", classes_by_id.values())
    report = {
        "doc_id": doc_id,
        "pending_before": len(pending),
        "requirements_added": added,
        # Legacy key name kept for report consumers; semantics are now "flagged
        # downgrade_pending for adjudication", not "labels silently changed".
        "classifications_downgraded": downgraded,
        "downgrades_pending": downgraded,
        "completed": completed,
        "changed": bool(added or downgraded),
    }
    _write_json(paths.audit_dir / "missing_requirement_completion.json", report)
    return report


def adjudicate_pending_downgrades(
    root: Path,
    doc_id: str,
    mode: str = "auto",
    model: Optional[str] = None,
    batch_size: int = 25,
) -> dict:
    """Adjudicate classifications flagged `downgrade_pending`.

    These are spans the classifier marked requirement_bearing but for which the
    decomposers returned zero requirements. Instead of silently flipping the
    label, the pipeline preserved the disagreement; this adjudicator resolves it:

      - confirm_downgrade: apply the recorded (or an overridden) non-requirement
        label, marked as adjudicated with reasoning.
      - extract: the supplied requirements are added (verbatim-quote validated)
        and the span keeps its requirement_bearing classification.

    Works in mock mode: fixtures are read from the doc's `fixtures/` directory
    (`fixtures/downgrade_adjudicator/pending_<n>.json`), matching the pipeline's
    mock-replay convention.
    """
    paths = Paths.for_doc(root, doc_id)
    classes_path = paths.catalog_dir / "classifications.jsonl"
    if not classes_path.exists():
        return {"doc_id": doc_id, "pending_before": 0, "decisions": [], "changed": False}

    classes = _load_jsonl(classes_path)
    pending = [c for c in classes if c.get("downgrade_pending")]
    if not pending:
        return {"doc_id": doc_id, "pending_before": 0, "decisions": [], "changed": False}

    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}

    from .llm import LLMClient
    from .prompts.adjudicate import (
        DOWNGRADE_ADJUDICATOR_SYSTEM,
        DOWNGRADE_ADJUDICATOR_USER_TEMPLATE,
    )

    llm = LLMClient(mode=mode, model=model, fixtures_root=paths.fixtures_dir, env_root=root)
    labels = ", ".join(l.value for l in ClassificationLabel)
    decisions: list[dict] = []
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        payload = []
        for c in batch:
            span = spans.get(c["span_id"], {})
            payload.append({
                "span_id": c["span_id"],
                "citation": (span.get("citation") or {}).get("raw") or c["span_id"],
                "kind": span.get("kind"),
                "text": span.get("text", ""),
                "classification": {
                    "final_label": c.get("final_label"),
                    "final_embedded": c.get("final_embedded", []),
                    "reconciler_note": c.get("reconciler_note", ""),
                },
                "downgrade_proposal": c.get("downgrade_proposal") or {},
            })
        user = DOWNGRADE_ADJUDICATOR_USER_TEMPLATE.format(
            doc_id=doc_id,
            labels=labels,
            items_json=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        result = llm.complete_json(
            "downgrade_adjudicator",
            f"pending_{start // batch_size + 1}",
            DOWNGRADE_ADJUDICATOR_SYSTEM,
            user,
            max_tokens=6000,
        )
        decisions.extend(result.get("decisions", []) or [])

    report = _apply_downgrade_adjudication(paths, classes, decisions)
    report.update({
        "doc_id": doc_id,
        "pending_before": len(pending),
        "decisions": decisions,
    })
    _write_json(paths.audit_dir / "downgrade_adjudication.json", report)
    return report


def _apply_downgrade_adjudication(paths: Paths, classes: list[dict], decisions: list[dict]) -> dict:
    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    by_id = {c["span_id"]: c for c in classes}
    next_idx = max((int(r["req_id"][1:]) for r in reqs), default=0)
    confirmed: list[str] = []
    extracted: list[str] = []
    ignored: list[dict] = []
    requirements_added = 0

    for d in decisions:
        sid = d.get("span_id")
        cls = by_id.get(sid)
        decision = (d.get("decision") or "").strip().lower()
        if not cls:
            ignored.append({"span_id": sid, "reason": "not found"})
            continue
        if not cls.get("downgrade_pending"):
            ignored.append({"span_id": sid, "reason": "no pending downgrade"})
            continue
        proposal = dict(cls.get("downgrade_proposal") or {})
        rationale = d.get("rationale") or ""

        if decision == "confirm_downgrade":
            embedded = [e for e in cls.get("final_embedded", []) if e != "requirement_bearing"]
            if cls.get("final_label") == "requirement_bearing":
                label_value = d.get("final_label") or proposal.get("proposed_label") or "administrative"
                try:
                    final_label = ClassificationLabel(label_value)
                except Exception:
                    ignored.append({"span_id": sid, "reason": f"invalid final_label {label_value!r}"})
                    continue
                if final_label is ClassificationLabel.REQUIREMENT_BEARING:
                    ignored.append({
                        "span_id": sid,
                        "reason": "confirm_downgrade cannot keep requirement_bearing",
                    })
                    continue
                cls["final_label"] = final_label.value
                embedded = [e for e in embedded if e != final_label.value]
            cls["final_embedded"] = embedded
            cls["ambiguous"] = False
            cls["downgrade_pending"] = False
            proposal["resolution"] = {
                "decision": "confirm_downgrade",
                "rationale": rationale,
                "adjudicated": True,
            }
            cls["downgrade_proposal"] = proposal
            cls["reconciler_note"] = (
                (cls.get("reconciler_note", "") + " | ").lstrip(" |")
                + f"downgrade adjudicator confirmed downgrade (final_label={cls['final_label']})"
                + (f": {rationale}" if rationale else "")
            )
            confirmed.append(sid)

        elif decision == "extract":
            rows = d.get("requirements") or []
            if not rows:
                ignored.append({"span_id": sid, "reason": "extract decision without requirements"})
                continue
            span = spans.get(sid)
            if not span:
                ignored.append({"span_id": sid, "reason": "source span not found"})
                continue
            bad: Optional[str] = None
            for i, row in enumerate(rows):
                quote = _canonicalize_quote((row.get("verbatim_quote") or "").strip(), span["text"])
                if not quote or quote not in span["text"]:
                    bad = f"requirements[{i}]: verbatim_quote not found in source span"
                    break
            if bad:
                ignored.append({"span_id": sid, "reason": bad})
                continue
            try:
                new_rows = []
                for row in rows:
                    new_rows.append(
                        _make_requirement(f"R{next_idx + len(new_rows) + 1:05d}", sid, span, row)
                        .model_dump(mode="json")
                    )
            except Exception as e:
                ignored.append({"span_id": sid, "reason": f"extracted requirement invalid: {e}"})
                continue
            next_idx += len(new_rows)
            reqs.extend(new_rows)
            requirements_added += len(new_rows)
            cls["downgrade_pending"] = False
            proposal["resolution"] = {
                "decision": "extract",
                "rationale": rationale,
                "adjudicated": True,
                "requirements_added": len(new_rows),
            }
            cls["downgrade_proposal"] = proposal
            cls["reconciler_note"] = (
                (cls.get("reconciler_note", "") + " | ").lstrip(" |")
                + f"downgrade adjudicator extracted {len(new_rows)} requirement(s); "
                  "span stays requirement_bearing"
                + (f": {rationale}" if rationale else "")
            )
            extracted.append(sid)

        else:
            ignored.append({"span_id": sid, "reason": f"invalid decision {decision!r}"})

    validated = [
        ReconciledClassification.model_validate(c).model_dump(mode="json")
        for c in classes
    ]
    _atomic_write_jsonl(paths.catalog_dir / "classifications.jsonl", validated)
    if requirements_added:
        validated_reqs = [AtomicRequirement.model_validate(r).model_dump(mode="json") for r in reqs]
        _atomic_write_jsonl(paths.catalog_dir / "requirements.jsonl", validated_reqs)
    return {
        "changed": bool(confirmed or extracted),
        "confirmed_downgrades": confirmed,
        "extracted": extracted,
        "ignored": ignored,
        "requirements_added": requirements_added,
        "pending_after": sum(1 for c in validated if c.get("downgrade_pending")),
    }


def adjudicate_ambiguous_classifications(
    root: Path,
    doc_id: str,
    mode: str = "auto",
    model: Optional[str] = None,
    batch_size: int = 25,
) -> dict:
    """Ask an LLM to clear ambiguous classification records."""
    paths = Paths.for_doc(root, doc_id)
    classes_path = paths.catalog_dir / "classifications.jsonl"
    if not classes_path.exists():
        return {"doc_id": doc_id, "ambiguous_before": 0, "decisions": [], "changed": False}

    classes = _load_jsonl(classes_path)
    ambiguous = [c for c in classes if c.get("ambiguous")]
    if not ambiguous:
        return {"doc_id": doc_id, "ambiguous_before": 0, "decisions": [], "changed": False}

    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
    reqs_by_span: dict[str, list[dict]] = {}
    for req in _load_jsonl(paths.catalog_dir / "requirements.jsonl"):
        reqs_by_span.setdefault(req.get("source_span_id"), []).append(req)

    from .llm import LLMClient
    from .prompts.adjudicate import (
        CLASSIFICATION_ADJUDICATOR_SYSTEM,
        CLASSIFICATION_ADJUDICATOR_USER_TEMPLATE,
    )

    llm = LLMClient(mode=mode, model=model, env_root=root)
    labels = ", ".join(l.value for l in ClassificationLabel)
    decisions: list[dict] = []
    for start in range(0, len(ambiguous), batch_size):
        batch = ambiguous[start:start + batch_size]
        payload = []
        for c in batch:
            span = spans.get(c["span_id"], {})
            payload.append({
                "span_id": c["span_id"],
                "citation": (span.get("citation") or {}).get("raw") or c["span_id"],
                "kind": span.get("kind"),
                "text": span.get("text", ""),
                "current": {
                    "label_a": c.get("label_a"),
                    "label_b": c.get("label_b"),
                    "reason_a": c.get("reason_a", ""),
                    "reason_b": c.get("reason_b", ""),
                    "final_label": c.get("final_label"),
                    "final_embedded": c.get("final_embedded", []),
                    "embedded_a": c.get("embedded_a", []),
                    "embedded_b": c.get("embedded_b", []),
                    "reconciler_note": c.get("reconciler_note", ""),
                },
                "existing_requirements": [
                    _adjudication_req_context(req) for req in reqs_by_span.get(c["span_id"], [])
                ],
            })
        user = CLASSIFICATION_ADJUDICATOR_USER_TEMPLATE.format(
            doc_id=doc_id,
            labels=labels,
            items_json=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        result = llm.complete_json(
            "classification_adjudicator",
            f"ambiguous_{start // batch_size + 1}",
            CLASSIFICATION_ADJUDICATOR_SYSTEM,
            user,
            max_tokens=6000,
        )
        decisions.extend(result.get("decisions", []) or [])

    report = _apply_classification_adjudication(paths, classes, decisions)
    report.update({
        "doc_id": doc_id,
        "ambiguous_before": len(ambiguous),
        "decisions": decisions,
    })
    _write_json(paths.audit_dir / "classification_adjudication.json", report)
    return report


def adjudicate_ambiguous_requirements(
    root: Path,
    doc_id: str,
    mode: str = "auto",
    model: Optional[str] = None,
    batch_size: int = 25,
) -> dict:
    """Ask an LLM to clear ambiguous atomic requirements."""
    paths = Paths.for_doc(root, doc_id)
    reqs_path = paths.catalog_dir / "requirements.jsonl"
    if not reqs_path.exists():
        return {"doc_id": doc_id, "ambiguous_before": 0, "decisions": [], "changed": False}

    reqs = _load_jsonl(reqs_path)
    ambiguous = [r for r in reqs if r.get("ambiguous")]
    if not ambiguous:
        return {"doc_id": doc_id, "ambiguous_before": 0, "decisions": [], "changed": False}

    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}

    from .llm import LLMClient
    from .prompts.adjudicate import (
        REQUIREMENT_ADJUDICATOR_SYSTEM,
        REQUIREMENT_ADJUDICATOR_USER_TEMPLATE,
    )

    llm = LLMClient(mode=mode, model=model, env_root=root)
    decisions: list[dict] = []
    for start in range(0, len(ambiguous), batch_size):
        batch = ambiguous[start:start + batch_size]
        payload = []
        for req in batch:
            span = spans.get(req["source_span_id"], {})
            payload.append({
                "requirement": _adjudication_req_context(req) | {
                    "modality": req.get("modality"),
                    "ambiguous": req.get("ambiguous"),
                    "alternates": req.get("alternates", []),
                },
                "source_span": {
                    "span_id": span.get("span_id"),
                    "citation": (span.get("citation") or {}).get("raw") or req.get("citation_raw"),
                    "kind": span.get("kind"),
                    "text": span.get("text", ""),
                },
            })
        user = REQUIREMENT_ADJUDICATOR_USER_TEMPLATE.format(
            doc_id=doc_id,
            items_json=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        result = llm.complete_json(
            "requirement_adjudicator",
            f"ambiguous_{start // batch_size + 1}",
            REQUIREMENT_ADJUDICATOR_SYSTEM,
            user,
            max_tokens=6000,
        )
        decisions.extend(result.get("decisions", []) or [])

    report = _apply_requirement_adjudication(paths, reqs, decisions)
    report.update({
        "doc_id": doc_id,
        "ambiguous_before": len(ambiguous),
        "decisions": decisions,
    })
    _write_json(paths.audit_dir / "requirement_adjudication.json", report)
    return report


def _adjudication_req_context(req: dict) -> dict:
    return {
        "req_id": req.get("req_id"),
        "citation": req.get("citation_raw"),
        "atomic_statement": req.get("atomic_statement"),
        "verbatim_quote": req.get("verbatim_quote"),
        "subject": req.get("subject", ""),
        "object": req.get("object", ""),
        "conditions": req.get("conditions", []),
        "applicability_tags": req.get("applicability_tags", []),
    }


def _apply_relationship_adjudication(paths: Paths, rels: list[dict], decisions: list[dict]) -> dict:
    by_id = {e["rel_id"]: e for e in rels}
    dropped: list[str] = []
    kept: list[str] = []
    edited: list[str] = []
    ignored: list[dict] = []

    for d in decisions:
        rel_id = d.get("rel_id")
        rel = by_id.get(rel_id)
        decision = (d.get("decision") or "").strip().lower()
        if not rel:
            ignored.append({"rel_id": rel_id, "reason": "not found"})
            continue
        if decision == "drop":
            dropped.append(rel_id)
            continue
        if decision not in {"keep", "edit"}:
            ignored.append({"rel_id": rel_id, "reason": f"invalid decision {decision!r}"})
            continue
        try:
            rel_type = RelationshipType(d.get("type") or rel.get("type"))
        except Exception:
            ignored.append({"rel_id": rel_id, "reason": f"invalid type {d.get('type')!r}"})
            continue
        rel["type"] = rel_type.value
        rel["evidence"] = d.get("evidence") or rel.get("evidence", "")
        rel["ambiguous"] = False
        if decision == "edit":
            edited.append(rel_id)
        else:
            kept.append(rel_id)

    remaining = [e for e in rels if e["rel_id"] not in set(dropped)]
    validated: list[dict] = []
    for i, e in enumerate(remaining, start=1):
        validated.append(Relationship(
            rel_id=f"E{i:04d}",
            source_req_id=e["source_req_id"],
            target_req_id=e["target_req_id"],
            type=RelationshipType(e["type"]),
            evidence=e.get("evidence", ""),
            ambiguous=bool(e.get("ambiguous", False)),
        ).model_dump(mode="json"))
    _atomic_write_jsonl(paths.catalog_dir / "relationships.jsonl", validated)
    return {
        "changed": bool(dropped or kept or edited),
        "dropped": dropped,
        "kept": kept,
        "edited": edited,
        "ignored": ignored,
        "relationships_after": len(validated),
        "ambiguous_after_apply": sum(1 for e in validated if e.get("ambiguous")),
    }


def _apply_classification_adjudication(paths: Paths, classes: list[dict], decisions: list[dict]) -> dict:
    by_id = {c["span_id"]: c for c in classes}
    updated: list[str] = []
    ignored: list[dict] = []

    for d in decisions:
        span_id = d.get("span_id")
        cls = by_id.get(span_id)
        if not cls:
            ignored.append({"span_id": span_id, "reason": "not found"})
            continue
        try:
            final_label = ClassificationLabel(d.get("final_label"))
            final_embedded = [
                ClassificationLabel(label).value
                for label in (d.get("final_embedded") or [])
                if label != final_label.value
            ]
        except Exception as e:
            ignored.append({"span_id": span_id, "reason": f"invalid label: {e}"})
            continue
        cls["final_label"] = final_label.value
        cls["final_embedded"] = sorted(set(final_embedded))
        cls["ambiguous"] = False
        cls["reconciler_note"] = d.get("reconciler_note") or d.get("rationale") or cls.get("reconciler_note", "")
        updated.append(span_id)

    validated = [
        ReconciledClassification.model_validate(c).model_dump(mode="json")
        for c in classes
    ]
    _atomic_write_jsonl(paths.catalog_dir / "classifications.jsonl", validated)
    return {
        "changed": bool(updated),
        "updated": updated,
        "ignored": ignored,
        "ambiguous_after_apply": sum(1 for c in validated if c.get("ambiguous")),
    }


def _apply_requirement_adjudication(paths: Paths, reqs: list[dict], decisions: list[dict]) -> dict:
    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
    by_id = {r["req_id"]: r for r in reqs}
    dropped: list[str] = []
    kept: list[str] = []
    edited: list[str] = []
    ignored: list[dict] = []

    for d in decisions:
        req_id = d.get("req_id")
        req = by_id.get(req_id)
        decision = (d.get("decision") or "").strip().lower()
        if not req:
            ignored.append({"req_id": req_id, "reason": "not found"})
            continue
        if decision == "drop":
            dropped.append(req_id)
            continue
        if decision not in {"keep", "edit"}:
            ignored.append({"req_id": req_id, "reason": f"invalid decision {decision!r}"})
            continue
        if decision == "edit":
            span = spans.get(req["source_span_id"], {})
            quote = _canonicalize_quote((d.get("verbatim_quote") or "").strip(), span.get("text", ""))
            if not quote or quote not in span.get("text", ""):
                ignored.append({"req_id": req_id, "reason": "edited verbatim_quote not found in source span"})
                continue
            try:
                updated = AtomicRequirement(
                    req_id=req["req_id"],
                    source_span_id=req["source_span_id"],
                    citation_raw=req["citation_raw"],
                    verbatim_quote=quote,
                    atomic_statement=(d.get("atomic_statement") or "").strip(),
                    modality=_coerce_modality(d.get("modality")),
                    subject=(d.get("subject") or "").strip(),
                    object=(d.get("object") or "").strip(),
                    applicability_tags=[t.strip().lower() for t in d.get("applicability_tags", []) if t],
                    conditions=[c.strip() for c in d.get("conditions", []) if c],
                    ambiguous=False,
                    alternates=[],
                ).model_dump(mode="json")
            except Exception as e:
                ignored.append({"req_id": req_id, "reason": f"edited requirement invalid: {e}"})
                continue
            req.clear()
            req.update(updated)
            edited.append(req_id)
        else:
            req["ambiguous"] = False
            req["alternates"] = []
            kept.append(req_id)

    dropped_set = set(dropped)
    remaining = [r for r in reqs if r["req_id"] not in dropped_set]
    validated = [AtomicRequirement.model_validate(r).model_dump(mode="json") for r in remaining]
    _atomic_write_jsonl(paths.catalog_dir / "requirements.jsonl", validated)
    # Preserve the adjudicator's drop rationale per source span so the pending
    # downgrade record carries the *why* into downgrade adjudication.
    drop_rationales: dict[str, str] = {}
    for d in decisions:
        if (d.get("decision") or "").strip().lower() != "drop":
            continue
        req = by_id.get(d.get("req_id"))
        if not req or req["req_id"] not in dropped_set:
            continue
        sid = req["source_span_id"]
        rationale = (d.get("rationale") or "").strip()
        if rationale:
            drop_rationales[sid] = (
                f"{drop_rationales[sid]}; {rationale}" if sid in drop_rationales else rationale
            )
    adjusted_classes = _flag_orphan_requirement_bearing_for_downgrade(
        paths,
        {r["source_span_id"] for r in reqs if r["req_id"] in dropped_set},
        {r["source_span_id"] for r in validated},
        drop_rationales,
    )
    removed_edges = _drop_relationships_for_missing_requirements(paths, {r["req_id"] for r in validated})
    return {
        "changed": bool(dropped or kept or edited),
        "dropped": dropped,
        "kept": kept,
        "edited": edited,
        "ignored": ignored,
        "requirements_after": len(validated),
        "classifications_adjusted_after_drops": adjusted_classes,
        "relationships_removed_for_dropped_requirements": removed_edges,
        "ambiguous_after_apply": sum(1 for r in validated if r.get("ambiguous")),
    }


def _flag_orphan_requirement_bearing_for_downgrade(
    paths: Paths,
    dropped_source_spans: set[str],
    source_spans_with_requirements: set[str],
    drop_rationales: dict[str, str],
) -> list[str]:
    """Flag spans whose LAST requirement was dropped by the requirement
    adjudicator as `downgrade_pending`.

    Previously this path silently cleared requirement_bearing (the same bug
    class fixed in the decompose/merge/completion paths) — the obligation could
    vanish with coverage passing and the doc reaching `completed`. Per the
    locked philosophy (never silently pick), the label is preserved and the
    downgrade adjudicator must explicitly confirm the downgrade or extract
    replacement requirements before finalize unblocks.
    """
    orphan_spans = dropped_source_spans - source_spans_with_requirements
    if not orphan_spans:
        return []
    classes_path = paths.catalog_dir / "classifications.jsonl"
    classes = _load_jsonl(classes_path)
    changed: list[str] = []
    for cls in classes:
        sid = cls.get("span_id")
        if sid not in orphan_spans or not _is_req_bearing(cls):
            continue
        if cls.get("downgrade_pending"):
            continue  # already awaiting downgrade adjudication
        reason = "requirement adjudicator dropped the span's last requirement"
        rationale = drop_rationales.get(sid, "")
        if rationale:
            reason += f": {rationale}"
        mark_downgrade_pending(cls, reason=reason, source="requirement_adjudication")
        changed.append(sid)
    if changed:
        validated = [
            ReconciledClassification.model_validate(c).model_dump(mode="json")
            for c in classes
        ]
        _atomic_write_jsonl(classes_path, validated)
    return changed


def _drop_relationships_for_missing_requirements(paths: Paths, req_ids: set[str]) -> int:
    rels_path = paths.catalog_dir / "relationships.jsonl"
    if not rels_path.exists():
        return 0
    rels = _load_jsonl(rels_path)
    kept = [
        e for e in rels
        if e.get("source_req_id") in req_ids and e.get("target_req_id") in req_ids
    ]
    removed = len(rels) - len(kept)
    if removed:
        validated = []
        for i, e in enumerate(kept, start=1):
            validated.append(Relationship(
                rel_id=f"E{i:04d}",
                source_req_id=e["source_req_id"],
                target_req_id=e["target_req_id"],
                type=RelationshipType(e["type"]),
                evidence=e.get("evidence", ""),
                ambiguous=bool(e.get("ambiguous", False)),
            ).model_dump(mode="json"))
        _atomic_write_jsonl(rels_path, validated)
    return removed


def _update_meta_after_finalize(root: Path, doc_id: str, paths: Paths) -> None:
    cov_path = paths.audit_dir / "coverage_report.json"
    if not cov_path.exists():
        return
    cov = json.loads(cov_path.read_text(encoding="utf-8"))
    rels_path = paths.catalog_dir / "relationships.jsonl"
    rel_report_path = paths.audit_dir / "relationship_validation.json"
    rels_exist = rels_path.exists()
    rel_report = json.loads(rel_report_path.read_text(encoding="utf-8")) if rel_report_path.exists() else {}
    rels = _load_jsonl(rels_path)
    classes = _load_jsonl(paths.catalog_dir / "classifications.jsonl")
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")

    meta = load_meta(root, doc_id)
    meta.stats = DocStats(
        spans=cov.get("span_count", 0),
        requirements=cov.get("requirements_extracted", 0),
        relationships=len(rels),
        coverage_pct=cov.get("coverage_pct", 0.0),
        ambiguous_classifications=sum(1 for row in classes if row.get("ambiguous")),
        ambiguous_requirements=sum(1 for row in reqs if row.get("ambiguous")),
        ambiguous_relationships=sum(1 for row in rels if row.get("ambiguous")),
        cycles_flagged=len(rel_report.get("cycles_flagged_ambiguous", [])),
    )
    meta.canonical_sha256 = cov.get("canonical_source_sha256", meta.canonical_sha256)
    if cov.get("passed") and rels_exist and rel_report.get("passed", False):
        meta.status = DocStatus.COMPLETED
        meta.completed_at = time.strftime("%Y-%m-%d")
    elif not cov.get("passed"):
        meta.status = DocStatus.NEEDS_REVIEW
    save_meta(root, meta)
    write_registry(root)
    write_registry_md(root)


def _assert_no_unresolved_ambiguity(paths: Paths) -> None:
    counts = unresolved_catalog_counts(paths)
    unresolved = {k: v for k, v in counts.items() if v}
    if unresolved:
        detail = "; ".join(f"{k}={v}" for k, v in unresolved.items())
        raise RuntimeError(
            "finalize refused unresolved catalog ambiguity: "
            f"{detail}. Run `regcat agent adjudicate-ambiguities --doc {paths.doc_id} --mode openai`."
        )


def unresolved_catalog_counts(paths: Paths) -> dict[str, int]:
    classes = _load_jsonl(paths.catalog_dir / "classifications.jsonl")
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    rels = _load_jsonl(paths.catalog_dir / "relationships.jsonl")
    rel_report_path = paths.audit_dir / "relationship_validation.json"
    rel_report = json.loads(rel_report_path.read_text(encoding="utf-8")) if rel_report_path.exists() else {}
    return {
        "ambiguous classifications": sum(1 for row in classes if row.get("ambiguous")),
        # Spans flagged for downgrade adjudication block finalize exactly like
        # unresolved ambiguity. Absent field (all pre-existing catalogs) counts 0.
        "pending downgrades": sum(1 for row in classes if row.get("downgrade_pending")),
        "ambiguous requirements": sum(1 for row in reqs if row.get("ambiguous")),
        "ambiguous relationships": sum(1 for row in rels if row.get("ambiguous")),
        "relationship cycles": len(rel_report.get("cycles_flagged_ambiguous", [])),
    }


def _classify_items(paths: Paths, spans: list[dict], limit: int, claimed: set[str]) -> list[dict]:
    done = {c["span_id"] for c in _load_jsonl(paths.catalog_dir / "classifications.jsonl")}
    out = []
    for s in spans:
        if s["span_id"] in done or s["span_id"] in claimed:
            continue
        out.append({
            "span_id": s["span_id"],
            "citation": s["citation"].get("raw") or s["span_id"],
            "kind": s["kind"],
            "text": s["text"],
        })
        if len(out) >= limit:
            break
    return out


def _decompose_items(paths: Paths, spans: list[dict], limit: int, claimed: set[str]) -> list[dict]:
    spans_by_id = {s["span_id"]: s for s in spans}
    classes = {c["span_id"]: c for c in _load_jsonl(paths.catalog_dir / "classifications.jsonl")}
    done = {r["source_span_id"] for r in _load_jsonl(paths.catalog_dir / "requirements.jsonl")}
    out = []
    for sid, c in classes.items():
        if sid in done or sid in claimed or not _is_req_bearing(c):
            continue
        if c.get("downgrade_pending"):
            # Zero-requirement disagreement already recorded; resolution goes
            # through the downgrade adjudicator, not another decompose packet.
            continue
        s = spans_by_id[sid]
        out.append({
            "span_id": sid,
            "citation": s["citation"].get("raw") or sid,
            "kind": s["kind"],
            "parent_chain": _build_parent_chain(s, spans_by_id),
            "classification": c,
            "text": s["text"],
        })
        if len(out) >= limit:
            break
    return out


def _embedded_items(paths: Paths, spans: list[dict], limit: int, claimed: set[str]) -> list[dict]:
    classes = _load_jsonl(paths.catalog_dir / "classifications.jsonl")
    candidates = _embedded_candidates(spans, classes, paths)
    candidates = [c for c in candidates if c["span_id"] not in claimed]
    return candidates[:limit]


def _embedded_candidates(spans: list[dict], classes: list[dict], paths: Paths) -> list[dict]:
    classes_by_span = {c["span_id"]: c for c in classes}
    audited = {
        e.get("span_id")
        for e in _load_jsonl(paths.audit_dir / "embedded_audit_log.jsonl")
    }
    out = []
    for s in spans:
        sid = s["span_id"]
        if sid in audited:
            continue
        c = classes_by_span.get(sid)
        if not c or _is_req_bearing(c):
            continue
        sigs = scan_signals(s["text"])
        if c["final_label"] == "source_note":
            sigs = [g for g in sigs if g.sig_class != SignalClass.MODAL_PERMISSIVE]
        if not sigs:
            continue
        out.append({
            "span_id": sid,
            "citation": s["citation"].get("raw") or sid,
            "classification": c["final_label"],
            "signals": sorted({f"{g.sig_class.value}({g.pattern_id})" for g in sigs}),
            "text": s["text"],
        })
    return out


def _relate_items(paths: Paths) -> list[dict]:
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    if not reqs:
        return []
    return [{
        "requirements": [
            {
                "req_id": r["req_id"],
                "citation": r["citation_raw"],
                "atomic": r["atomic_statement"],
                "subject": r.get("subject", ""),
                "object": r.get("object", ""),
                "applicability_tags": r.get("applicability_tags", []),
                "conditions": r.get("conditions", []),
            }
            for r in reqs
        ]
    }]


def _validate_classify(inputs: list[dict], outputs: list[dict]) -> dict:
    expected = {r["span_id"] for r in inputs}
    seen = set()
    failures = []
    for row in outputs:
        sid = row.get("span_id")
        if sid not in expected:
            failures.append(f"{sid}: not in packet input")
            continue
        if sid in seen:
            failures.append(f"{sid}: duplicate output")
        seen.add(sid)
        try:
            ReconciledClassification.model_validate(row)
        except Exception as e:
            failures.append(f"{sid}: schema invalid: {e}")
    missing = expected - seen
    failures.extend(f"{sid}: missing output" for sid in sorted(missing))
    return {"failures": failures}


def _validate_decompose(inputs: list[dict], outputs: list[dict], spans_by_id: dict[str, dict]) -> dict:
    return _validate_requirements_packet(inputs, outputs, spans_by_id, require_decision=False)


def _validate_embedded(inputs: list[dict], outputs: list[dict], spans_by_id: dict[str, dict]) -> dict:
    return _validate_requirements_packet(inputs, outputs, spans_by_id, require_decision=True)


def _validate_requirements_packet(
    inputs: list[dict],
    outputs: list[dict],
    spans_by_id: dict[str, dict],
    require_decision: bool,
) -> dict:
    expected = {r["span_id"] for r in inputs}
    seen = set()
    failures = []
    for row in outputs:
        sid = row.get("span_id")
        if sid not in expected:
            failures.append(f"{sid}: not in packet input")
            continue
        if sid in seen:
            failures.append(f"{sid}: duplicate output")
        seen.add(sid)
        if require_decision and "has_embedded_obligation" not in row:
            failures.append(f"{sid}: missing has_embedded_obligation")
        reqs = row.get("requirements")
        if not isinstance(reqs, list):
            failures.append(f"{sid}: requirements must be a list")
            continue
        span_text = spans_by_id[sid]["text"]
        for i, req in enumerate(reqs):
            quote = (req.get("verbatim_quote") or "").strip()
            canonical = _canonicalize_quote(quote, span_text)
            if not quote or canonical not in span_text:
                failures.append(f"{sid}[{i}]: verbatim_quote not found in span")
            try:
                AtomicRequirement(
                    req_id="R00000",
                    source_span_id=sid,
                    citation_raw=spans_by_id[sid]["citation"].get("raw") or sid,
                    verbatim_quote=canonical or quote,
                    atomic_statement=(req.get("atomic_statement") or "").strip(),
                    modality=_coerce_modality(req.get("modality")),
                    subject=(req.get("subject") or "").strip(),
                    object=(req.get("object") or "").strip(),
                    applicability_tags=req.get("applicability_tags", []) or [],
                    conditions=req.get("conditions", []) or [],
                )
            except Exception as e:
                failures.append(f"{sid}[{i}]: requirement schema invalid: {e}")
    missing = expected - seen
    failures.extend(f"{sid}: missing output" for sid in sorted(missing))
    return {"failures": failures}


def _validate_relate(outputs: list[dict], req_ids: set[str]) -> dict:
    failures = []
    for i, row in enumerate(outputs):
        relationships = row.get("relationships", outputs if isinstance(outputs, list) else [])
        if isinstance(row, dict) and "relationships" in row:
            iterable = relationships
        else:
            iterable = [row]
        for rel in iterable:
            src = rel.get("source_req_id")
            tgt = rel.get("target_req_id")
            if src not in req_ids:
                failures.append(f"relationship {i}: source {src} not in requirements")
            if tgt not in req_ids:
                failures.append(f"relationship {i}: target {tgt} not in requirements")
            if src == tgt:
                failures.append(f"relationship {i}: self-loop {src}")
            try:
                RelationshipType(rel.get("type"))
            except Exception:
                failures.append(f"relationship {i}: invalid type {rel.get('type')}")
    return {"failures": failures}


def _merge_classify(paths: Paths, rows: list[dict]) -> dict:
    existing = _dedupe_by_key(_load_jsonl(paths.catalog_dir / "classifications.jsonl"), "span_id")
    added = 0
    for row in rows:
        if row["span_id"] in existing:
            continue
        existing[row["span_id"]] = ReconciledClassification.model_validate(row).model_dump(mode="json")
        added += 1
    _atomic_write_jsonl(paths.catalog_dir / "classifications.jsonl", existing.values())
    return {"added": added, "total": len(existing)}


def _merge_decompose(paths: Paths, rows: list[dict]) -> dict:
    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
    classes = _dedupe_by_key(_load_jsonl(paths.catalog_dir / "classifications.jsonl"), "span_id")
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    # `done` tracks every span that has requirements — from the catalog AND from
    # rows merged earlier in THIS packet — so a duplicate/malformed packet with a
    # second zero-requirement row for a span that already supplied requirements
    # cannot re-flag it downgrade_pending (and duplicate requirement rows cannot
    # double-add).
    done = {r["source_span_id"] for r in reqs}
    next_idx = max((int(r["req_id"][1:]) for r in reqs), default=0)
    added = 0
    downgraded = 0
    skipped_rows_for_spans_with_requirements = 0
    for row in rows:
        sid = row["span_id"]
        new_reqs = row.get("requirements") or []
        if sid in done:
            skipped_rows_for_spans_with_requirements += 1
            continue
        if not new_reqs:
            if sid in classes and not classes[sid].get("downgrade_pending"):
                # Preserve the disagreement: flag for downgrade adjudication
                # instead of silently flipping/dropping requirement_bearing.
                mark_downgrade_pending(
                    classes[sid],
                    reason="agent decompose packet returned 0 requirements",
                    source="agent_merge",
                )
                downgraded += 1
            continue
        span = spans[sid]
        for r in new_reqs:
            next_idx += 1
            reqs.append(_make_requirement(f"R{next_idx:05d}", sid, span, r).model_dump(mode="json"))
            added += 1
        done.add(sid)
        if sid in classes and classes[sid].get("downgrade_pending"):
            # A packet exported before the span was flagged supplied requirements
            # after all — the disagreement is resolved by extraction.
            resolve_downgrade_extracted(classes[sid], "agent packet merge supplied requirements")
    _atomic_write_jsonl(paths.catalog_dir / "requirements.jsonl", reqs)
    _atomic_write_jsonl(paths.catalog_dir / "classifications.jsonl", classes.values())
    return {
        "requirements_added": added,
        # Legacy key name kept for report consumers; semantics are now "flagged
        # downgrade_pending for adjudication", not "labels silently changed".
        "classifications_downgraded": downgraded,
        "downgrades_pending": downgraded,
        "skipped_rows_for_spans_with_requirements": skipped_rows_for_spans_with_requirements,
        "total": len(reqs),
    }


def _merge_embedded(paths: Paths, rows: list[dict]) -> dict:
    spans = {s["span_id"]: s for s in _load_jsonl(paths.source_dir / "spans.jsonl")}
    classes = _dedupe_by_key(_load_jsonl(paths.catalog_dir / "classifications.jsonl"), "span_id")
    reqs = _load_jsonl(paths.catalog_dir / "requirements.jsonl")
    log = _load_jsonl(paths.audit_dir / "embedded_audit_log.jsonl")
    next_idx = max((int(r["req_id"][1:]) for r in reqs), default=0)
    added = promoted = 0
    for row in rows:
        sid = row["span_id"]
        has_obligation = bool(row.get("has_embedded_obligation"))
        new_reqs = row.get("requirements") or []
        log.append({
            "stage": "embedded_audit",
            "span_id": sid,
            "citation": spans[sid]["citation"].get("raw") or sid,
            "primary": classes.get(sid, {}).get("final_label"),
            "signals": row.get("signals", []),
            "decision": "embedded_obligation_added" if has_obligation and new_reqs else "false_positive",
            "rationale": row.get("rationale", ""),
            "count": len(new_reqs),
        })
        if not (has_obligation and new_reqs):
            continue
        cls = classes[sid]
        embedded = set(cls.get("final_embedded", []))
        embedded.add("requirement_bearing")
        cls["final_embedded"] = sorted(embedded)
        cls["ambiguous"] = True
        cls["reconciler_note"] = (
            (cls.get("reconciler_note", "") + " | ").lstrip(" |")
            + "agent embedded audit added requirement_bearing"
        )
        promoted += 1
        for r in new_reqs:
            next_idx += 1
            reqs.append(_make_requirement(f"R{next_idx:05d}", sid, spans[sid], r).model_dump(mode="json"))
            added += 1
    _atomic_write_jsonl(paths.catalog_dir / "requirements.jsonl", reqs)
    _atomic_write_jsonl(paths.catalog_dir / "classifications.jsonl", classes.values())
    _atomic_write_jsonl(paths.audit_dir / "embedded_audit_log.jsonl", log)
    return {"spans_promoted": promoted, "requirements_added": added, "total_requirements": len(reqs)}


def _merge_relate(paths: Paths, rows: list[dict]) -> dict:
    flat = []
    for row in rows:
        if isinstance(row, dict) and "relationships" in row:
            flat.extend(row.get("relationships") or [])
        else:
            flat.append(row)
    relationships = []
    seen = set()
    for rel in flat:
        key = (rel["source_req_id"], rel["target_req_id"], rel["type"])
        if key in seen:
            continue
        seen.add(key)
        relationships.append(Relationship(
            rel_id=f"E{len(relationships) + 1:04d}",
            source_req_id=rel["source_req_id"],
            target_req_id=rel["target_req_id"],
            type=RelationshipType(rel["type"]),
            evidence=rel.get("evidence", ""),
            ambiguous=bool(rel.get("ambiguous", False)),
        ).model_dump(mode="json"))
    _atomic_write_jsonl(paths.catalog_dir / "relationships.jsonl", relationships)
    return {"relationships": len(relationships)}


def _make_requirement(req_id: str, sid: str, span: dict, row: dict) -> AtomicRequirement:
    quote = _canonicalize_quote((row.get("verbatim_quote") or "").strip(), span["text"])
    return AtomicRequirement(
        req_id=req_id,
        source_span_id=sid,
        citation_raw=span["citation"].get("raw") or sid,
        verbatim_quote=quote,
        atomic_statement=(row.get("atomic_statement") or "").strip(),
        modality=_coerce_modality(row.get("modality")),
        subject=(row.get("subject") or "").strip(),
        object=(row.get("object") or "").strip(),
        applicability_tags=[t.strip().lower() for t in row.get("applicability_tags", []) if t],
        conditions=[c.strip() for c in row.get("conditions", []) if c],
        ambiguous=bool(row.get("ambiguous", False)),
        alternates=row.get("alternates", []) or [],
    )


def _is_req_bearing(c: dict) -> bool:
    return "requirement_bearing" in ({c.get("final_label")} | set(c.get("final_embedded", [])))


def _coerce_modality(s) -> Modality:
    try:
        return Modality((s or "unspecified").strip().lower())
    except ValueError:
        return Modality.UNSPECIFIED


def _dedupe_by_key(rows: Iterable[dict], key: str) -> dict[str, dict]:
    out = {}
    for row in rows:
        if key in row and row[key] not in out:
            out[row[key]] = row
    return out


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_jsonl_strict(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as e:
            raise RuntimeError(f"{path}:{i}: invalid JSON: {e}") from e
    return rows


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(obj, indent=2, ensure_ascii=False)
    last_exc: Optional[Exception] = None
    for _ in range(20):
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
            return
        except PermissionError as e:
            last_exc = e
            time.sleep(0.1)
    raise last_exc or RuntimeError(f"failed to write {path}")


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _atomic_write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_suffix(path.suffix + f".bak-{time.strftime('%Y%m%d%H%M%S')}")
    if path.exists():
        shutil.copy2(path, backup)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)


def _load_claims(root: Path, doc_id: str) -> dict:
    path = claim_path(root, doc_id)
    if not path.exists():
        return {"version": CLAIM_VERSION, "claims": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", CLAIM_VERSION)
    data.setdefault("claims", [])
    return data


@contextmanager
def _claim_lock(root: Path, doc_id: str, timeout_seconds: float = 30.0):
    with _file_lock(claim_path(root, doc_id).with_suffix(".json.lock"), timeout_seconds):
        yield


@contextmanager
def _catalog_lock(root: Path, doc_id: str, timeout_seconds: float = 120.0):
    with _file_lock(Paths.for_doc(root, doc_id).doc_dir / AGENT_ROOT / "catalog.lock", timeout_seconds):
        yield


@contextmanager
def _file_lock(lock: Path, timeout_seconds: float):
    lock.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    fd = None
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}\n".encode("utf-8"))
            break
        except FileExistsError:
            if time.time() - start > timeout_seconds:
                raise RuntimeError(f"timed out waiting for lock: {lock}")
            time.sleep(0.1)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _save_claims(root: Path, doc_id: str, claims: dict) -> None:
    _write_json(claim_path(root, doc_id), claims)


def _record_claim(root: Path, doc_id: str, stage: Stage, batch_id: str, item_ids: list[str]) -> None:
    claims = _load_claims(root, doc_id)
    active = _active_claimed_items(claims, stage)
    overlap = sorted(set(item_ids) & active)
    if overlap:
        raise RuntimeError(f"packet claim overlap for {stage}: {overlap[:10]}")
    for row in claims["claims"]:
        if row.get("stage") == stage and row.get("batch_id") == batch_id and row.get("status") != "released":
            raise RuntimeError(f"active claim already exists for {stage}/{batch_id}")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    claims["claims"].append({
        "stage": stage,
        "batch_id": batch_id,
        "status": "claimed",
        "claimed_at": now,
        "updated_at": now,
        "item_count": len(item_ids),
        "item_ids": item_ids,
    })
    _save_claims(root, doc_id, claims)


def _update_claim_status(
    root: Path,
    doc_id: str,
    stage: Stage,
    batch_id: str,
    status: str,
    required: bool = True,
) -> None:
    with _claim_lock(root, doc_id):
        claims = _load_claims(root, doc_id)
        for row in claims.get("claims", []):
            if row.get("stage") == stage and row.get("batch_id") == batch_id:
                row["status"] = status
                row["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                _save_claims(root, doc_id, claims)
                return
        if required:
            raise RuntimeError(f"claim not found for {stage}/{batch_id}")


def _active_claimed_items(claims: dict, stage: Stage) -> set[str]:
    active_statuses = {"claimed", "validated", "failed"}
    out: set[str] = set()
    for row in claims.get("claims", []):
        if row.get("stage") != stage or row.get("status") not in active_statuses:
            continue
        out.update(row.get("item_ids", []))
    return out


def _stage_has_active_claim(claims: dict, stage: Stage) -> bool:
    return any(
        row.get("stage") == stage and row.get("status") in {"claimed", "validated", "failed"}
        for row in claims.get("claims", [])
    )


def _claim_summary(root: Path, doc_id: str) -> dict:
    claims = _load_claims(root, doc_id)
    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    active_items: dict[str, int] = {}
    for row in claims.get("claims", []):
        status = row.get("status", "unknown")
        stage = row.get("stage", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_stage[stage] = by_stage.get(stage, 0) + 1
        if status in {"claimed", "validated", "failed"}:
            active_items[stage] = active_items.get(stage, 0) + int(row.get("item_count", 0))
    return {
        "claim_file": str(claim_path(root, doc_id)),
        "packets_by_status": by_status,
        "packets_by_stage": by_stage,
        "active_items_by_stage": active_items,
    }


def _item_id(stage: Stage, item: dict) -> str:
    if stage == "relate":
        return "all"
    return item["span_id"]


def _success_criteria(stage: Stage) -> list[str]:
    base = [
        "Every input item has exactly one output row.",
        "Output is strict JSONL with no prose and no code fences.",
        "Validation must pass before merge.",
        "No final success is allowed until deterministic audit/finalize passes.",
    ]
    if stage in {"decompose", "embedded"}:
        base.append("Every verbatim_quote must be an exact substring of its source span.")
    if stage == "relate":
        base.append("Every relationship endpoint must resolve to an existing requirement id.")
    return base


def _classify_instructions() -> str:
    labels = ", ".join(l.value for l in ClassificationLabel)
    return f"""# Agent Classification Packet

You are classifying regulatory spans for `regcat`.

Read `input.jsonl` and write `classification_results.jsonl`.
Write exactly one JSON object per input row, with this shape:

```json
{{"span_id":"S0001","label_a":"requirement_bearing","label_b":"requirement_bearing","reason_a":"...","reason_b":"...","final_label":"requirement_bearing","final_embedded":[],"embedded_a":[],"embedded_b":[],"ambiguous":false,"reconciler_note":"..."}}
```

Allowed labels: {labels}

Success criteria:
- One output row for every input span_id.
- No extra span_ids.
- Use `requirement_bearing` for obligations, prohibitions, permissions, or constructive scope.
- Use embedded `requirement_bearing` when a definition/admin/scope span hides an obligation.
- Do not declare the packet complete until `regcat agent validate` passes.
"""


def _decompose_instructions() -> str:
    return """# Agent Decomposition Packet

Read `input.jsonl` and write `decomposition_results.jsonl`.
Write exactly one JSON object per input span:

```json
{"span_id":"S0001","requirements":[{"verbatim_quote":"exact source substring","atomic_statement":"one testable obligation","modality":"shall","subject":"who is bound","object":"what is acted on","applicability_tags":["tag"],"conditions":[]}]}
```

Rules:
- Split compound requirements into atomic requirements.
- `verbatim_quote` must be copied exactly from the span text.
- If the span truly has no standalone requirement, return an empty requirements list.
- Do not assign req_id values; merge assigns stable IDs.
- Do not declare the packet complete until `regcat agent validate` passes.
"""


def _embedded_instructions() -> str:
    return """# Agent Embedded-Obligation Packet

Read `input.jsonl` and write `embedded_results.jsonl`.
Each input is a non-requirement span with deterministic obligation signals.
Write exactly one row per span:

```json
{"span_id":"S0001","has_embedded_obligation":true,"rationale":"...","requirements":[{"verbatim_quote":"exact source substring","atomic_statement":"...","modality":"must","subject":"...","object":"...","applicability_tags":[],"conditions":[]}]}
```

If the signal is a false positive, set `has_embedded_obligation` false and use an empty requirements list.
Do not declare the packet complete until `regcat agent validate` passes.
"""


def _relate_instructions() -> str:
    rels = ", ".join(r.value for r in RelationshipType)
    return f"""# Agent Relationship Packet

Read `input.jsonl` and write `relationship_results.jsonl`.
The packet contains the current requirement catalog. Emit justified relationships:

```json
{{"relationships":[{{"source_req_id":"R00001","target_req_id":"R00002","type":"references","evidence":"short textual reason"}}]}}
```

Allowed relationship types: {rels}

Rules:
- Only emit edges justified by the catalog text.
- Do not invent requirement IDs.
- Skip weak/trivial edges.
- Do not declare the packet complete until `regcat agent validate` and `regcat agent finalize` pass.
"""
