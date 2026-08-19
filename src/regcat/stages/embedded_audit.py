"""Stage 5.5: Embedded-Obligation Auditor.

Runs between decompose (5) and audit (6). For every span whose classification does
NOT include `requirement_bearing` (in primary or embedded), scan the span text with
the deterministic signal library. If any obligation-bearing signal is detected,
route the span through the embedded-obligation decomposer:

  - It asks the LLM whether the signal is a real embedded obligation
  - If yes, the LLM emits one or more atomic requirements
  - We canonicalize the verbatim quote, add the requirements to requirements.jsonl,
    and patch the classification to add `requirement_bearing` to its embedded labels

The audit stage downstream then validates the catalog as usual; if any
non-requirement span still has unattributed signal hits AFTER this stage, the audit
gate fails (configurable).

This stage exists as a safety net: even if the upstream classifier misses an
embedded obligation, the signal-based scan catches it and the LLM triages it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..llm import LLMError
from ..prompts.embedded import EMBEDDED_AUDIT_SYSTEM, EMBEDDED_AUDIT_USER_TEMPLATE
from ..schemas import AtomicRequirement, ClassificationLabel, Modality
from ..signals import scan as scan_signals, SignalClass
from ..text_quality import is_degenerate_span


def run(ctx) -> None:
    paths = ctx.paths
    spans = ctx.read_jsonl(paths.source_dir / "spans.jsonl")
    spans_by_id = {s["span_id"]: s for s in spans}
    classifications = ctx.read_jsonl(paths.catalog_dir / "classifications.jsonl")
    classes_by_span = {c["span_id"]: c for c in classifications}
    requirements = ctx.read_jsonl(paths.catalog_dir / "requirements.jsonl")

    # Spans to inspect: every span whose existing labels do NOT include requirement_bearing
    candidates: list[tuple[dict, dict, list]] = []  # (span, class, signals)
    for s in spans:
        sid = s["span_id"]
        c = classes_by_span.get(sid)
        if not c:
            continue
        labels = {c["final_label"]} | set(c.get("final_embedded", []))
        if "requirement_bearing" in labels:
            continue
        # Degenerate figure/table extraction artifacts (auto-classified STRUCTURAL by
        # classify) carry scattered modal words that the signal scan flags, but sending
        # the garbled "word salad" to the embedded-obligation auditor trips the backend
        # content filter (this halted the PRO pilot at S0110 even after the classify
        # guard). Skip them here too; their real content is recovered via figure-vision.
        if is_degenerate_span(s["text"]):
            continue
        # We DON'T skip structural/disclaimer by primary label — if a structural-classified
        # span actually contains obligation-bearing language, the signal scan will catch
        # it (most structural spans have no signals and produce empty results below).
        # This was tightened after integrated_audit found 3 Part 314 spans where the
        # classifier picked `structural` despite the text containing `must`/`may`.
        sigs = scan_signals(s["text"])
        # Filter: drop signals that are ONLY weak modal-permissive ("may") in source_notes
        if c["final_label"] == "source_note":
            sigs = [g for g in sigs if g.sig_class != SignalClass.MODAL_PERMISSIVE]
        if sigs:
            candidates.append((s, c, sigs))

    ctx.log(f"    embedded_audit: {len(candidates)} non-requirement spans with detected signals")

    if not candidates:
        ctx.log("    embedded_audit: no candidates to audit")
        return

    # Numbering: continue from the highest existing req_id
    next_idx = max((int(r["req_id"][1:]) for r in requirements), default=0)

    appended_reqs: list[AtomicRequirement] = []
    patched_spans: list[str] = []
    auditor_log: list[dict] = []

    for span, cls, sigs in candidates:
        sid = span["span_id"]
        citation = span["citation"].get("raw") or sid
        signal_summary = ", ".join(sorted({f"{s.sig_class.value}({s.pattern_id})" for s in sigs}))
        user = EMBEDDED_AUDIT_USER_TEMPLATE.format(
            citation=citation,
            classification=cls["final_label"],
            signals=signal_summary,
            text=span["text"],
        )
        try:
            result = ctx.llm.complete_json("embedded_auditor", sid, EMBEDDED_AUDIT_SYSTEM, user)
        except LLMError as e:
            # Mock mode without a fixture for this span — treat as "no embedded obligation"
            # and log. Live / claude-code mode would never hit this.
            if ctx.llm.mode == "mock":
                auditor_log.append({
                    "stage": "embedded_audit",
                    "span_id": sid,
                    "citation": citation,
                    "primary": cls["final_label"],
                    "signals": signal_summary,
                    "decision": "skipped_no_mock_fixture",
                    "rationale": "no fixture in mock mode; no embedded promotion attempted",
                })
                continue
            raise

        has_obligation = bool(result.get("has_embedded_obligation"))
        new_reqs = result.get("requirements") or []
        log_entry = {
            "stage": "embedded_audit",
            "span_id": sid,
            "citation": citation,
            "primary": cls["final_label"],
            "signals": signal_summary,
            "decision": "embedded_obligation_added" if (has_obligation and new_reqs) else "false_positive",
            "rationale": result.get("rationale", ""),
            "count": len(new_reqs),
        }
        auditor_log.append(log_entry)

        if not (has_obligation and new_reqs):
            continue

        # Patch classification — add requirement_bearing to embedded labels (idempotent)
        embedded = list(cls.get("final_embedded", []))
        if "requirement_bearing" not in embedded:
            embedded.append("requirement_bearing")
        cls["final_embedded"] = sorted(set(embedded))
        cls["ambiguous"] = True
        cls["reconciler_note"] = (
            (cls.get("reconciler_note", "") + " | ").lstrip(" |")
            + f"embedded_audit added requirement_bearing (signals: {signal_summary})"
        )
        patched_spans.append(sid)

        # Add the new requirements
        for r in new_reqs:
            raw_quote = (r.get("verbatim_quote") or "").strip()
            canonical_quote = _canonicalize_quote(raw_quote, span["text"])
            if canonical_quote not in span["text"]:
                # Don't add a malformed requirement; the audit would reject it anyway.
                log_entry.setdefault("warnings", []).append(
                    f"verbatim_quote not in span text after canonicalization: {raw_quote!r}"
                )
                continue
            next_idx += 1
            appended_reqs.append(AtomicRequirement(
                req_id=f"R{next_idx:05d}",
                source_span_id=sid,
                citation_raw=citation,
                verbatim_quote=canonical_quote,
                atomic_statement=(r.get("atomic_statement") or "").strip(),
                modality=_coerce_modality(r.get("modality")),
                subject=(r.get("subject") or "").strip(),
                object=(r.get("object") or "").strip(),
                applicability_tags=[t.strip().lower() for t in r.get("applicability_tags", []) if t],
                conditions=[c.strip() for c in r.get("conditions", []) if c],
                ambiguous=False,
                alternates=[],
            ))

    # Write back patched classifications + appended requirements
    if patched_spans:
        ctx.write_jsonl(paths.catalog_dir / "classifications.jsonl", classifications)
    if appended_reqs:
        with (paths.catalog_dir / "requirements.jsonl").open("a", encoding="utf-8") as f:
            for r in appended_reqs:
                f.write(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) + "\n")

    # Append audit log
    log_path = paths.audit_dir / "embedded_audit_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        for entry in auditor_log:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    ctx.log(f"    embedded_audit: promoted {len(patched_spans)} spans, "
            f"added {len(appended_reqs)} requirements, "
            f"{sum(1 for e in auditor_log if e['decision'] == 'false_positive')} false positives filtered")


def _canonicalize_quote(quote: str, span_text: str) -> str:
    if not quote or quote in span_text:
        return quote
    n = re.sub(r"\s+", " ", quote).strip()
    n_clean = re.sub(r"\s+", " ", re.sub(r"[,;]", "", n)).strip()
    if not n_clean:
        return quote
    tokens = [re.escape(p).replace("-", r"-\s*") for p in n_clean.split(" ")]
    pat = r"[,;]?\s+[,;]?\s*".join(tokens)
    m = re.search(pat, span_text)
    return m.group(0) if m else quote


def _coerce_modality(s) -> Modality:
    if isinstance(s, Modality):
        return s
    try:
        return Modality((s or "unspecified").strip().lower())
    except ValueError:
        return Modality.UNSPECIFIED
