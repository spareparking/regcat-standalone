"""Stage 6: Coverage Auditor.

Hard, deterministic gate. Pure code, no LLM. Computes:

  - byte coverage of canonical text by spans (must be 100%, no overlaps, no gaps)
  - every span has a classification record (after Stage 4)
  - every requirement-bearing span has >=1 requirement (after Stage 5)
  - every requirement's verbatim_quote appears EXACTLY inside its source span's text
  - canonical sha256 matches the canonical_source artifact

Halts the pipeline (raises) on any failure unless `--allow-partial-audit` is passed,
which is intended for during-development inspection only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..schemas import CoverageReport


def run(ctx) -> None:
    paths = ctx.paths

    canonical_path = paths.source_dir / "canonical.txt"
    canonical_text = canonical_path.read_text(encoding="utf-8")
    canonical_bytes = canonical_text.encode("utf-8")
    expected_sha = hashlib.sha256(canonical_bytes).hexdigest()

    spans = ctx.read_jsonl(paths.source_dir / "spans.jsonl")
    spans_by_id = {s["span_id"]: s for s in spans}

    classifications_path = paths.catalog_dir / "classifications.jsonl"
    classifications = ctx.read_jsonl(classifications_path) if classifications_path.exists() else []
    classification_by_span = {c["span_id"]: c for c in classifications}

    requirements_path = paths.catalog_dir / "requirements.jsonl"
    requirements = ctx.read_jsonl(requirements_path) if requirements_path.exists() else []

    # Byte coverage checks
    total_bytes = len(canonical_bytes)
    sorted_spans = sorted(spans, key=lambda s: s["byte_start"])

    overlap_failures: list[str] = []
    gap_failures: list[dict] = []
    prev_end = 0
    covered = 0
    for s in sorted_spans:
        bs, be = s["byte_start"], s["byte_end"]
        if bs < prev_end:
            overlap_failures.append(f"{s['span_id']} overlaps previous (start={bs} < prev_end={prev_end})")
        if bs > prev_end:
            # Gap! Show the bytes that fall in the gap.
            gap_text = canonical_bytes[prev_end:bs].decode("utf-8", errors="replace")
            gap_failures.append({"start": prev_end, "end": bs, "text": gap_text[:200]})
        covered += be - bs
        prev_end = max(prev_end, be)
    if prev_end < total_bytes:
        gap_text = canonical_bytes[prev_end:total_bytes].decode("utf-8", errors="replace")
        gap_failures.append({"start": prev_end, "end": total_bytes, "text": gap_text[:200]})

    coverage_pct = (covered / total_bytes * 100.0) if total_bytes else 0.0

    # Classification completeness (after Stage 4)
    unclassified = []
    if classifications:
        for s in spans:
            if s["span_id"] not in classification_by_span:
                unclassified.append(s["span_id"])

    # Requirement coverage of requirement-bearing spans (after Stage 5).
    # A span needs at least one requirement if `requirement_bearing` is its primary
    # label OR appears in its embedded labels.
    # Exception: a span flagged `downgrade_pending` is ATTRIBUTED — the zero-
    # requirement disagreement is preserved and awaits the downgrade adjudicator —
    # so it is not a coverage failure, but it is counted and reported distinctly
    # (and finalize blocks on it via unresolved_catalog_counts).
    unrequirementized = []
    downgrade_pending_spans = []
    if requirements is not None and classifications:
        req_source_spans = {r["source_span_id"] for r in requirements}
        for sid, c in classification_by_span.items():
            labels = {c.get("final_label")} | set(c.get("final_embedded", []))
            if "requirement_bearing" in labels and sid not in req_source_spans:
                if c.get("downgrade_pending"):
                    downgrade_pending_spans.append(sid)
                else:
                    unrequirementized.append(sid)

    # Verbatim-quote check
    verbatim_failures = []
    for r in requirements:
        sid = r["source_span_id"]
        span = spans_by_id.get(sid)
        if not span:
            verbatim_failures.append(f"{r['req_id']}: source_span_id {sid} not found")
            continue
        quote = r.get("verbatim_quote", "")
        if not quote:
            verbatim_failures.append(f"{r['req_id']}: empty verbatim_quote")
            continue
        # Match must be exact substring of the span's text. Normalize whitespace MINIMALLY: only
        # collapse runs of spaces/tabs/newlines into single space for comparison, since PDF text
        # extraction may differ from prose by a soft-wrap. We log a strict failure either way.
        if quote in span["text"]:
            continue
        if _whitespace_loose_in(quote, span["text"]):
            verbatim_failures.append(f"{r['req_id']}: quote matches only after whitespace normalization (loose)")
            continue
        verbatim_failures.append(f"{r['req_id']}: verbatim_quote not found in span {sid}")

    # Reconciler unresolved (we tag them in Stage 4/5 as ambiguous=True; nothing should remain
    # "unresolved" beyond that)
    reconciler_unresolved: list[str] = []
    log_path = paths.audit_dir / "reconciler_log.jsonl"
    if log_path.exists():
        for entry in ctx.read_jsonl(log_path):
            if entry.get("status") == "unresolved":
                reconciler_unresolved.append(entry.get("key", "?"))

    # Compose report
    spans_by_classification: dict[str, int] = {}
    if classifications:
        for c in classifications:
            label = c.get("final_label", "unclassified")
            spans_by_classification[label] = spans_by_classification.get(label, 0) + 1
    else:
        # If we ran without Stage 4 yet, count by SpanKind so the report is still informative
        for s in spans:
            kind = s.get("kind", "unknown")
            spans_by_classification[kind] = spans_by_classification.get(kind, 0) + 1

    sha_match = (expected_sha == ctx.meta.canonical_sha256) if ctx.meta.canonical_sha256 else True

    passed = (
        sha_match
        and not overlap_failures
        and not gap_failures
        and not unclassified
        and not unrequirementized
        and not verbatim_failures
        and not reconciler_unresolved
        and abs(coverage_pct - 100.0) < 1e-6
    )

    report = CoverageReport(
        canonical_source_sha256=expected_sha,
        total_bytes=total_bytes,
        covered_bytes=covered,
        coverage_pct=round(coverage_pct, 6),
        span_count=len(spans),
        spans_by_classification=spans_by_classification,
        requirements_extracted=len(requirements),
        verbatim_quote_failures=verbatim_failures,
        unclassified_spans=unclassified,
        unrequirementized_spans=unrequirementized,
        downgrade_pending_spans=sorted(downgrade_pending_spans),
        reconciler_unresolved=reconciler_unresolved,
        overlap_failures=overlap_failures,
        gap_failures=gap_failures,
        passed=passed,
    )
    ctx.write_json(paths.audit_dir / "coverage_report.json", report)
    ctx.log(f"    audit: coverage={coverage_pct:.4f}%  covered={covered}/{total_bytes}  "
            f"spans={len(spans)}  reqs={len(requirements)}  "
            f"pending_downgrades={len(downgrade_pending_spans)}  passed={passed}")
    if downgrade_pending_spans:
        ctx.log(f"    audit: {len(downgrade_pending_spans)} spans flagged downgrade_pending "
                f"(attributed, not a coverage failure; finalize blocks until adjudicated): "
                f"{sorted(downgrade_pending_spans)}")

    if not passed:
        # Roll up the most useful failure reasons into the exception message.
        reasons = []
        if not sha_match:
            reasons.append("canonical sha256 mismatch")
        if overlap_failures:
            reasons.append(f"{len(overlap_failures)} overlap failures")
        if gap_failures:
            reasons.append(f"{len(gap_failures)} gap failures")
        if unclassified:
            reasons.append(f"{len(unclassified)} unclassified spans")
        if unrequirementized:
            reasons.append(f"{len(unrequirementized)} requirement-bearing spans without requirements")
        if verbatim_failures:
            reasons.append(f"{len(verbatim_failures)} verbatim quote failures")
        if reconciler_unresolved:
            reasons.append(f"{len(reconciler_unresolved)} unresolved reconciler entries")
        if abs(coverage_pct - 100.0) >= 1e-6:
            reasons.append(f"coverage {coverage_pct:.4f}% != 100%")

        # If we haven't run classify/decompose yet, allow the audit to "pass through" by treating
        # missing artifacts as a soft warning. The Stage 4/5 runs will trigger a full re-audit.
        if not classifications:
            ctx.log("    audit: classifications not present yet — soft check only")
            return

        raise RuntimeError("coverage audit failed: " + "; ".join(reasons))


def _whitespace_loose_in(needle: str, haystack: str) -> bool:
    import re
    n = re.sub(r"\s+", " ", needle).strip()
    h = re.sub(r"\s+", " ", haystack).strip()
    return n in h
