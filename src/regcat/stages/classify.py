"""Stage 4: Classify each span using two parallel agents + a reconciler.

V2: compound classification — each span gets a primary label PLUS zero or more
embedded labels (substantive content the primary label may hide). The decomposer
runs on any span where `requirement_bearing` is the primary OR an embedded label.

Mock mode reads pre-recorded JSON responses from data/fixtures/<agent>/<span_id>.json.
Existing fixtures without an `embedded` field load with embedded=[] for
backward compatibility.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..prompts.classify import (
    CLASSIFIER_A_SYSTEM, CLASSIFIER_B_SYSTEM, CLASSIFIER_USER_TEMPLATE,
    RECONCILER_CLASSIFY_SYSTEM, RECONCILER_CLASSIFY_USER_TEMPLATE,
)
from ..schemas import ClassificationLabel, ReconciledClassification
from ..text_quality import is_degenerate_span as _is_degenerate_span


def run(ctx) -> None:
    paths = ctx.paths
    spans = ctx.read_jsonl(paths.source_dir / "spans.jsonl")

    # Incremental save / resume: classifications.jsonl is written line-by-line as we go.
    # On resume, skip span_ids already present (the previous run got to those).
    out_path = paths.catalog_dir / "classifications.jsonl"
    already_done: set[str] = set()
    existing_classifications: list[dict] = []
    if out_path.exists():
        existing_classifications = ctx.read_jsonl(out_path)
        already_done = {c["span_id"] for c in existing_classifications}
        if already_done:
            ctx.log(f"    classify: resuming — {len(already_done)} spans already classified, skipping")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fout = out_path.open("a", encoding="utf-8")

    classifications: list[ReconciledClassification] = []
    reconciler_log: list[dict] = []
    disagree_count = 0
    ambiguous_count = 0
    embedded_count = 0

    def persist(rc: ReconciledClassification) -> None:
        fout.write(json.dumps(rc.model_dump(mode="json"), ensure_ascii=False) + "\n")
        fout.flush()

    degenerate_count = 0

    for s in spans:
        sid = s["span_id"]
        if sid in already_done:
            continue

        # Degenerate-span guard: PDF figure/table extraction artifacts are
        # auto-classified STRUCTURAL without an LLM call. They hold no atomic
        # requirements and sending the garbled "word salad" to the backend trips
        # its content filter (the failure that halted the PRO pilot at S0109).
        # Coverage is unaffected — the span still exists, it just isn't sent out.
        if _is_degenerate_span(s["text"]):
            degenerate_count += 1
            ws_ratio = round(sum(1 for c in s["text"] if c.isspace()) / len(s["text"]), 3)
            final = ReconciledClassification(
                span_id=sid,
                label_a=ClassificationLabel.STRUCTURAL,
                label_b=ClassificationLabel.STRUCTURAL,
                reason_a="auto: degenerate extraction artifact",
                reason_b="auto: degenerate extraction artifact",
                embedded_a=[], embedded_b=[],
                final_label=ClassificationLabel.STRUCTURAL,
                final_embedded=[],
                ambiguous=False,
                reconciler_note=(
                    "auto-classified STRUCTURAL: degenerate PDF figure/table extraction "
                    f"artifact (whitespace_ratio={ws_ratio}); LLM skipped"
                ),
            )
            classifications.append(final)
            persist(final)
            reconciler_log.append({
                "stage": "classify",
                "span_id": sid,
                "kind": "degenerate_skip",
                "whitespace_ratio": ws_ratio,
                "chars": len(s["text"]),
            })
            continue

        citation = s["citation"].get("raw") or "(no citation)"
        kind = s["kind"]
        user = CLASSIFIER_USER_TEMPLATE.format(citation=citation, kind=kind, text=s["text"])

        out_a = ctx.llm.complete_json("classifier_a", sid, CLASSIFIER_A_SYSTEM, user)
        out_b = ctx.llm.complete_json("classifier_b", sid, CLASSIFIER_B_SYSTEM, user)

        label_a = _coerce_label(out_a.get("label"))
        label_b = _coerce_label(out_b.get("label"))
        embedded_a = _coerce_labels(out_a.get("embedded", []))
        embedded_b = _coerce_labels(out_b.get("embedded", []))
        reason_a = out_a.get("reason", "")
        reason_b = out_b.get("reason", "")
        conf_a = out_a.get("confidence", "medium")
        conf_b = out_b.get("confidence", "medium")

        primary_agreement = (label_a == label_b)
        embedded_agreement = (set(embedded_a) == set(embedded_b))

        if primary_agreement and embedded_agreement:
            final = ReconciledClassification(
                span_id=sid,
                label_a=label_a, label_b=label_b,
                reason_a=reason_a, reason_b=reason_b,
                embedded_a=embedded_a, embedded_b=embedded_b,
                final_label=label_a,
                final_embedded=sorted(set(embedded_a), key=lambda x: x.value),
                ambiguous=False,
                reconciler_note="agreement",
            )
        elif primary_agreement and not embedded_agreement:
            # Local union — embedded labels are unionist by design.
            union = sorted(set(embedded_a) | set(embedded_b), key=lambda x: x.value)
            final = ReconciledClassification(
                span_id=sid,
                label_a=label_a, label_b=label_b,
                reason_a=reason_a, reason_b=reason_b,
                embedded_a=embedded_a, embedded_b=embedded_b,
                final_label=label_a,
                final_embedded=union,
                ambiguous=False,
                reconciler_note=f"primary agreement; embedded unionized: {[l.value for l in union]}",
            )
            reconciler_log.append({
                "stage": "classify",
                "span_id": sid,
                "kind": "embedded_union",
                "embedded_a": [l.value for l in embedded_a],
                "embedded_b": [l.value for l in embedded_b],
                "final_embedded": [l.value for l in union],
                "status": "resolved",
            })
            embedded_count += 1
        else:
            disagree_count += 1
            recon_user = RECONCILER_CLASSIFY_USER_TEMPLATE.format(
                citation=citation, kind=kind, text=s["text"],
                label_a=label_a.value, conf_a=conf_a, reason_a=reason_a, embedded_a=[l.value for l in embedded_a],
                label_b=label_b.value, conf_b=conf_b, reason_b=reason_b, embedded_b=[l.value for l in embedded_b],
            )
            recon = ctx.llm.complete_json("reconciler_classify", sid, RECONCILER_CLASSIFY_SYSTEM, recon_user)
            final = ReconciledClassification(
                span_id=sid,
                label_a=label_a, label_b=label_b,
                reason_a=reason_a, reason_b=reason_b,
                embedded_a=embedded_a, embedded_b=embedded_b,
                final_label=_coerce_label(recon.get("final_label")),
                final_embedded=_coerce_labels(recon.get("final_embedded", [])),
                ambiguous=bool(recon.get("ambiguous", False)),
                reconciler_note=recon.get("reconciler_note", ""),
            )
            reconciler_log.append({
                "stage": "classify",
                "span_id": sid,
                "label_a": label_a.value, "label_b": label_b.value,
                "embedded_a": [l.value for l in embedded_a],
                "embedded_b": [l.value for l in embedded_b],
                "final_label": final.final_label.value,
                "final_embedded": [l.value for l in final.final_embedded],
                "ambiguous": final.ambiguous,
                "status": "ambiguous" if final.ambiguous else "resolved",
            })
            if final.ambiguous:
                ambiguous_count += 1

        classifications.append(final)
        persist(final)

    fout.close()
    # Reconciler log is truncate-overwrite by classify but appended-to by later stages.
    # On resume, the truncate would wipe valid prior log entries — only truncate if we
    # processed the FIRST span this run (i.e. there were no prior classifications).
    truncate_log = not already_done
    _append_jsonl(paths.audit_dir / "reconciler_log.jsonl", reconciler_log, truncate_first=truncate_log)

    # Compute cumulative counts (resume-aware) by re-reading what's on disk
    all_classifications = ctx.read_jsonl(out_path)
    embedded_with_req = sum(
        1 for c in all_classifications
        if c.get("final_label") != "requirement_bearing"
        and "requirement_bearing" in c.get("final_embedded", [])
    )
    ctx.log(f"    classify: {len(all_classifications)} spans total "
            f"({len(classifications)} this run), primary-disagree={disagree_count}, "
            f"ambiguous={ambiguous_count}, embedded-only-unions={embedded_count}, "
            f"degenerate-skipped={degenerate_count}, "
            f"non-req spans with embedded requirement_bearing={embedded_with_req}")


def _coerce_label(s) -> ClassificationLabel:
    if isinstance(s, ClassificationLabel):
        return s
    try:
        return ClassificationLabel(s)
    except ValueError:
        s_norm = (s or "").strip().lower().replace("-", "_").replace(" ", "_")
        synonyms = {
            "requirement": "requirement_bearing",
            "obligation": "requirement_bearing",
            "exclusion": "scope_exclusion",
            "inclusion": "scope_inclusion",
            "definitional": "definition",
            "header": "structural",
            "toc": "structural",
            "title": "structural",
        }
        s_norm = synonyms.get(s_norm, s_norm)
        return ClassificationLabel(s_norm)


def _coerce_labels(items) -> list[ClassificationLabel]:
    if not items:
        return []
    out: list[ClassificationLabel] = []
    for x in items:
        try:
            out.append(_coerce_label(x))
        except ValueError:
            continue
    # Preserve order, dedupe
    seen: set[ClassificationLabel] = set()
    deduped: list[ClassificationLabel] = []
    for l in out:
        if l in seen:
            continue
        seen.add(l)
        deduped.append(l)
    return deduped


def _append_jsonl(path: Path, rows: list[dict], truncate_first: bool = False) -> None:
    if truncate_first and path.exists():
        path.unlink()
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")
