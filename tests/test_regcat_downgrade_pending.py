"""Workstream C phase 1: downgrade_pending semantics.

Old behavior (the one hole in coverage accounting): when the decomposer agents
returned zero requirements for a span classified requirement_bearing, the span's
primary label was silently flipped to a non-requirement label and the obligation
could vanish with the coverage audit still passing.

New behavior under test:
  - the label is preserved and the record is flagged `downgrade_pending` with the
    would-have-been label recorded in `downgrade_proposal`;
  - the coverage audit treats a pending span as attributed (NOT a failure) but
    reports it distinctly in `downgrade_pending_spans`;
  - `agent_packets.finalize` blocks on pending downgrades exactly like unresolved
    ambiguity;
  - the downgrade adjudicator resolves each span with `confirm_downgrade` (apply
    the recorded non-requirement label) or `extract` (requirements supplied, span
    stays requirement-bearing);
  - catalogs produced before this change (no downgrade fields anywhere) parse and
    finalize exactly as before.

All tests are mock-mode and self-contained in tmp_path. No LLM APIs, no docs/.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from regcat import agent_packets
from regcat.llm import LLMClient
from regcat.orchestrator import Paths, RunContext
from regcat.registry import DocMeta, Jurisdiction, save_meta
from regcat.schemas import ReconciledClassification, RunMetadata
from regcat.stages import audit, decompose

DOC_ID = "fda/test-dg"


# ---------------------------------------------------------------------------
# fixture builders (self-contained temp-dir doc)
# ---------------------------------------------------------------------------

def _cls(span_id: str, label: str, embedded: list[str] | None = None, **extra) -> dict:
    row = {
        "span_id": span_id,
        "label_a": label,
        "label_b": label,
        "reason_a": "r",
        "reason_b": "r",
        "final_label": label,
        "final_embedded": list(embedded or []),
        "embedded_a": [],
        "embedded_b": [],
        "ambiguous": False,
        "reconciler_note": "",
    }
    row.update(extra)
    return row


def _req(req_id: str, sid: str, quote: str, citation: str = "§ 1.1") -> dict:
    return {
        "req_id": req_id,
        "source_span_id": sid,
        "citation_raw": citation,
        "verbatim_quote": quote,
        "atomic_statement": "a testable obligation",
        "modality": "shall",
        "subject": "the sponsor",
        "object": "records",
        "applicability_tags": [],
        "conditions": [],
        "ambiguous": False,
        "alternates": [],
    }


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def _build_doc(root: Path, span_texts: list[tuple[str, str]],
               classifications: list[dict], requirements: list[dict]) -> Paths:
    """Create a complete minimal doc under root/docs/fda/test-dg/.

    span_texts: ordered (span_id, text) pairs; canonical.txt is their exact
    concatenation, so byte coverage is 100% by construction.
    """
    paths = Paths.for_doc(root, DOC_ID)
    paths.ensure()
    canonical = "".join(text for _, text in span_texts)
    (paths.source_dir / "canonical.txt").write_text(canonical, encoding="utf-8")

    spans = []
    offset = 0
    for i, (sid, text) in enumerate(span_texts, start=1):
        n = len(text.encode("utf-8"))
        spans.append({
            "span_id": sid,
            "kind": "paragraph",
            "citation": {"title": "21", "part": "1", "section": "1.1",
                         "paragraphs": [], "subpart": None, "raw": f"§ 1.{i}"},
            "parent_span_id": None,
            "byte_start": offset,
            "byte_end": offset + n,
            "text": text,
            "page_number": 1,
        })
        offset += n
    _write_jsonl(paths.source_dir / "spans.jsonl", spans)
    _write_jsonl(paths.catalog_dir / "classifications.jsonl", classifications)
    _write_jsonl(paths.catalog_dir / "requirements.jsonl", requirements)

    save_meta(root, DocMeta(
        doc_id=DOC_ID, jurisdiction=Jurisdiction.FDA, short_id="test-dg",
        title="Downgrade-pending test doc",
    ))
    return paths


def _ctx(paths: Paths) -> RunContext:
    return RunContext(
        paths=paths,
        llm=LLMClient(mode="mock", fixtures_root=paths.fixtures_dir),
        meta=RunMetadata(started_at="t", pdf_path="", pdf_sha256="", mode="mock", model="mock"),
        log_lines=[],
    )


def _mock_decomposers_return_zero(paths: Paths, sid: str) -> None:
    for agent in ("decomposer_a", "decomposer_b"):
        fdir = paths.fixtures_dir / agent
        fdir.mkdir(parents=True, exist_ok=True)
        (fdir / f"{sid}.json").write_text(json.dumps({"requirements": []}), encoding="utf-8")


def _adjudicator_fixture(paths: Paths, decisions: list[dict]) -> None:
    fdir = paths.fixtures_dir / "downgrade_adjudicator"
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "pending_1.json").write_text(
        json.dumps({"decisions": decisions}), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _classes_by_id(paths: Paths) -> dict[str, dict]:
    return {c["span_id"]: c for c in _read_jsonl(paths.catalog_dir / "classifications.jsonl")}


GOOD_SPAN = ("S0001", "The sponsor shall maintain adequate records.\n")
GOOD_QUOTE = "The sponsor shall maintain adequate records."


# ---------------------------------------------------------------------------
# golden case (a): genuinely administrative fragment
# ---------------------------------------------------------------------------

def test_admin_fragment_flagged_then_confirm_downgrade_then_finalizes(tmp_path):
    frag = ("S0002", "(ii) Telephone number;\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, frag],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    _mock_decomposers_return_zero(paths, "S0002")

    decompose.run(_ctx(paths))

    cls = _classes_by_id(paths)["S0002"]
    # Label is NOT flipped; the disagreement is preserved.
    assert cls["final_label"] == "requirement_bearing"
    assert cls["downgrade_pending"] is True
    assert cls["downgrade_proposal"]["kind"] == "primary"
    assert cls["downgrade_proposal"]["proposed_label"] == "administrative"
    assert "0 requirements" in cls["reconciler_note"]

    # Coverage audit: attributed, not a failure — but reported distinctly.
    audit.run(_ctx(paths))
    cov = json.loads((paths.audit_dir / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["passed"] is True
    assert cov["unrequirementized_spans"] == []
    assert cov["downgrade_pending_spans"] == ["S0002"]

    # Finalize blocks while the downgrade is unresolved.
    with pytest.raises(RuntimeError, match="pending downgrades=1"):
        agent_packets.finalize(tmp_path, DOC_ID)

    # Adjudicate: confirm the downgrade (mock mode).
    _adjudicator_fixture(paths, [
        {"span_id": "S0002", "decision": "confirm_downgrade",
         "rationale": "list fragment, no standalone obligation"},
    ])
    report = agent_packets.adjudicate_pending_downgrades(tmp_path, DOC_ID, mode="mock")
    assert report["changed"] is True
    assert report["confirmed_downgrades"] == ["S0002"]
    assert report["pending_after"] == 0

    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "administrative"
    assert cls["downgrade_pending"] is False
    assert cls["downgrade_proposal"]["resolution"]["decision"] == "confirm_downgrade"
    assert "downgrade adjudicator confirmed" in cls["reconciler_note"]

    # Now finalize passes and renders the catalog.
    agent_packets.finalize(tmp_path, DOC_ID)
    assert (paths.catalog_dir / "catalog.md").exists()


# ---------------------------------------------------------------------------
# golden case (b): buried obligation — finalize BLOCKS until `extract`
# ---------------------------------------------------------------------------

def test_buried_obligation_blocks_until_extract(tmp_path):
    buried_text = ("For purposes of this part, the sponsor must retain all "
                   "records for five years.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, ("S0002", buried_text)],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    _mock_decomposers_return_zero(paths, "S0002")

    decompose.run(_ctx(paths))
    cls = _classes_by_id(paths)["S0002"]
    assert cls["downgrade_pending"] is True
    assert cls["final_label"] == "requirement_bearing"  # obligation NOT vanished

    audit.run(_ctx(paths))  # passes — attributed
    with pytest.raises(RuntimeError, match="pending downgrades"):
        agent_packets.finalize(tmp_path, DOC_ID)

    # An extract decision with a bad quote is ignored and the span STAYS pending.
    _adjudicator_fixture(paths, [
        {"span_id": "S0002", "decision": "extract", "rationale": "buried obligation",
         "requirements": [{"verbatim_quote": "not in the span text",
                           "atomic_statement": "x", "modality": "must",
                           "subject": "sponsor", "object": "records"}]},
    ])
    report = agent_packets.adjudicate_pending_downgrades(tmp_path, DOC_ID, mode="mock")
    assert report["changed"] is False
    assert report["pending_after"] == 1
    with pytest.raises(RuntimeError, match="pending downgrades"):
        agent_packets.finalize(tmp_path, DOC_ID)

    # A valid extract resolves it: requirements added, span stays req-bearing.
    quote = "the sponsor must retain all records for five years"
    _adjudicator_fixture(paths, [
        {"span_id": "S0002", "decision": "extract", "rationale": "buried obligation",
         "requirements": [{"verbatim_quote": quote,
                           "atomic_statement": "Sponsor retains records 5 years",
                           "modality": "must", "subject": "the sponsor",
                           "object": "records", "applicability_tags": ["records"],
                           "conditions": []}]},
    ])
    report = agent_packets.adjudicate_pending_downgrades(tmp_path, DOC_ID, mode="mock")
    assert report["changed"] is True
    assert report["extracted"] == ["S0002"]
    assert report["requirements_added"] == 1

    reqs = _read_jsonl(paths.catalog_dir / "requirements.jsonl")
    new = [r for r in reqs if r["source_span_id"] == "S0002"]
    assert len(new) == 1
    assert new[0]["req_id"] == "R00002"
    assert new[0]["verbatim_quote"] == quote

    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "requirement_bearing"
    assert cls["downgrade_pending"] is False
    assert cls["downgrade_proposal"]["resolution"]["decision"] == "extract"

    agent_packets.finalize(tmp_path, DOC_ID)
    cov = json.loads((paths.audit_dir / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["passed"] is True
    assert cov["requirements_extracted"] == 2
    assert cov["downgrade_pending_spans"] == []


# ---------------------------------------------------------------------------
# golden case (c): backwards compatibility — old catalogs unchanged
# ---------------------------------------------------------------------------

def test_old_catalog_without_downgrade_fields_finalizes_unchanged(tmp_path):
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, ("S0002", "Scope. This part applies to electronic records.\n")],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "scope_inclusion")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    # No downgrade fields anywhere → no pending downgrades.
    counts = agent_packets.unresolved_catalog_counts(paths)
    assert counts["pending downgrades"] == 0

    agent_packets.finalize(tmp_path, DOC_ID)
    cov = json.loads((paths.audit_dir / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["passed"] is True
    assert cov["downgrade_pending_spans"] == []

    # Old records parse with defaults through the schema.
    model = ReconciledClassification.model_validate(_cls("S0009", "administrative"))
    assert model.downgrade_pending is False
    assert model.downgrade_proposal is None


def test_truly_missing_requirements_still_fail_audit(tmp_path):
    """The hard gate is preserved: a req-bearing span with no requirements and
    no downgrade_pending flag is still a coverage failure (nothing got looser)."""
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, ("S0002", "The investigator shall sign the form.\n")],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    with pytest.raises(RuntimeError, match="requirement-bearing spans without requirements"):
        audit.run(_ctx(paths))


# ---------------------------------------------------------------------------
# embedded-flag case + agent-packet merge path + resume idempotency
# ---------------------------------------------------------------------------

def test_embedded_requirement_bearing_flag_is_preserved_not_dropped(tmp_path):
    definition = ("S0002", "Electronic record means any digital information kept "
                  "by the sponsor.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, definition],
        [_cls("S0001", "requirement_bearing"),
         _cls("S0002", "definition", embedded=["requirement_bearing"])],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    _mock_decomposers_return_zero(paths, "S0002")
    decompose.run(_ctx(paths))

    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "definition"
    assert "requirement_bearing" in cls["final_embedded"]  # NOT silently dropped
    assert cls["downgrade_pending"] is True
    assert cls["downgrade_proposal"]["kind"] == "embedded"

    _adjudicator_fixture(paths, [
        {"span_id": "S0002", "decision": "confirm_downgrade",
         "rationale": "pure definition, no embedded obligation"},
    ])
    report = agent_packets.adjudicate_pending_downgrades(tmp_path, DOC_ID, mode="mock")
    assert report["confirmed_downgrades"] == ["S0002"]
    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "definition"
    assert "requirement_bearing" not in cls["final_embedded"]
    assert cls["downgrade_pending"] is False

    agent_packets.finalize(tmp_path, DOC_ID)


def test_agent_merge_zero_requirements_marks_pending(tmp_path):
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, ("S0002", "(a) Reserved.\n")],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    report = agent_packets._merge_decompose(paths, [{"span_id": "S0002", "requirements": []}])
    assert report["downgrades_pending"] == 1

    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "requirement_bearing"  # not flipped
    assert cls["downgrade_pending"] is True
    assert cls["downgrade_proposal"]["source"] == "agent_merge"

    # The agent-packet status surface reports it distinctly, and decompose
    # packets no longer re-export the span.
    st = agent_packets.status(tmp_path, DOC_ID)
    assert st["downgrades_pending"] == 1
    assert st["decompose_pending"] == 0


# ---------------------------------------------------------------------------
# red-team finding 1: requirement adjudicator's drop path must not silently
# downgrade when it removes a span's last requirement
# ---------------------------------------------------------------------------

def test_adjudicator_drop_of_last_requirement_flags_pending_primary(tmp_path):
    span2 = ("S0002", "The IRB shall review all research activities.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, span2],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE),
         _req("R00002", "S0002", "The IRB shall review all research activities.")],
    )
    reqs = _read_jsonl(paths.catalog_dir / "requirements.jsonl")
    report = agent_packets._apply_requirement_adjudication(paths, reqs, [
        {"req_id": "R00002", "decision": "drop",
         "rationale": "duplicate of a parent obligation"},
    ])
    assert report["dropped"] == ["R00002"]
    assert report["classifications_adjusted_after_drops"] == ["S0002"]

    # The requirement is gone, but the obligation has NOT silently vanished:
    remaining = _read_jsonl(paths.catalog_dir / "requirements.jsonl")
    assert [r["req_id"] for r in remaining] == ["R00001"]
    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "requirement_bearing"  # NOT flipped to administrative
    assert cls["downgrade_pending"] is True
    assert cls["downgrade_proposal"]["kind"] == "primary"
    assert cls["downgrade_proposal"]["source"] == "requirement_adjudication"
    # The adjudicator's drop rationale is preserved on the pending record.
    assert "duplicate of a parent obligation" in cls["downgrade_proposal"]["reason"]

    # Coverage audit attributes it; finalize blocks until adjudicated.
    audit.run(_ctx(paths))
    cov = json.loads((paths.audit_dir / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["passed"] is True
    assert cov["downgrade_pending_spans"] == ["S0002"]
    assert agent_packets.unresolved_catalog_counts(paths)["pending downgrades"] == 1
    with pytest.raises(RuntimeError, match="pending downgrades=1"):
        agent_packets.finalize(tmp_path, DOC_ID)

    # confirm_downgrade unblocks finalize.
    _adjudicator_fixture(paths, [
        {"span_id": "S0002", "decision": "confirm_downgrade",
         "rationale": "covered by the parent requirement"},
    ])
    report = agent_packets.adjudicate_pending_downgrades(tmp_path, DOC_ID, mode="mock")
    assert report["confirmed_downgrades"] == ["S0002"]
    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "administrative"
    assert cls["downgrade_pending"] is False
    agent_packets.finalize(tmp_path, DOC_ID)


def test_adjudicator_drop_of_last_requirement_flags_pending_embedded(tmp_path):
    definition = ("S0002", "Sponsor means the person who initiates the "
                  "investigation and must notify FDA.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, definition],
        [_cls("S0001", "requirement_bearing"),
         _cls("S0002", "definition", embedded=["requirement_bearing"])],
        [_req("R00001", "S0001", GOOD_QUOTE),
         _req("R00002", "S0002", "must notify FDA")],
    )
    reqs = _read_jsonl(paths.catalog_dir / "requirements.jsonl")
    agent_packets._apply_requirement_adjudication(paths, reqs, [
        {"req_id": "R00002", "decision": "drop", "rationale": "not standalone"},
    ])

    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "definition"
    assert "requirement_bearing" in cls["final_embedded"]  # NOT silently stripped
    assert cls["downgrade_pending"] is True
    assert cls["downgrade_proposal"]["kind"] == "embedded"
    assert cls["downgrade_proposal"]["source"] == "requirement_adjudication"
    with pytest.raises(RuntimeError, match="pending downgrades"):
        agent_packets.finalize(tmp_path, DOC_ID)

    _adjudicator_fixture(paths, [
        {"span_id": "S0002", "decision": "confirm_downgrade",
         "rationale": "definition only; obligation lives in the operative section"},
    ])
    agent_packets.adjudicate_pending_downgrades(tmp_path, DOC_ID, mode="mock")
    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "definition"
    assert "requirement_bearing" not in cls["final_embedded"]
    assert cls["downgrade_pending"] is False
    agent_packets.finalize(tmp_path, DOC_ID)


def test_adjudicator_drop_with_surviving_requirement_does_not_flag(tmp_path):
    """Dropping one of TWO requirements on a span must not flag anything."""
    span2 = ("S0002", "The IRB shall review and shall approve all research.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, span2],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE),
         _req("R00002", "S0002", "The IRB shall review"),
         _req("R00003", "S0002", "shall approve all research")],
    )
    reqs = _read_jsonl(paths.catalog_dir / "requirements.jsonl")
    report = agent_packets._apply_requirement_adjudication(paths, reqs, [
        {"req_id": "R00003", "decision": "drop", "rationale": "duplicate"},
    ])
    assert report["classifications_adjusted_after_drops"] == []
    cls = _classes_by_id(paths)["S0002"]
    assert cls["final_label"] == "requirement_bearing"
    assert not cls.get("downgrade_pending")
    agent_packets.finalize(tmp_path, DOC_ID)


# ---------------------------------------------------------------------------
# red-team finding 2: duplicate zero-requirement row in one merge must not
# re-flag a span that already has requirements
# ---------------------------------------------------------------------------

def test_merge_duplicate_zero_row_after_requirements_row_does_not_flag(tmp_path):
    span2 = ("S0002", "The sponsor must submit annual reports.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, span2],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    req_row = {"verbatim_quote": "The sponsor must submit annual reports.",
               "atomic_statement": "Sponsor submits annual reports",
               "modality": "must", "subject": "the sponsor", "object": "annual reports"}
    report = agent_packets._merge_decompose(paths, [
        {"span_id": "S0002", "requirements": [req_row]},
        {"span_id": "S0002", "requirements": []},  # duplicate/malformed zero row
    ])
    assert report["requirements_added"] == 1
    assert report["downgrades_pending"] == 0
    assert report["skipped_rows_for_spans_with_requirements"] == 1

    reqs = _read_jsonl(paths.catalog_dir / "requirements.jsonl")
    assert [r["req_id"] for r in reqs if r["source_span_id"] == "S0002"] == ["R00002"]
    cls = _classes_by_id(paths)["S0002"]
    assert not cls.get("downgrade_pending")
    assert agent_packets.unresolved_catalog_counts(paths)["pending downgrades"] == 0
    agent_packets.finalize(tmp_path, DOC_ID)


def test_merge_zero_row_before_requirements_row_resolves_pending(tmp_path):
    """Reversed ordering: the zero row flags, the later requirements row in the
    same merge resolves the flag by extraction — never left wedged."""
    span2 = ("S0002", "The sponsor must submit annual reports.\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, span2],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    req_row = {"verbatim_quote": "The sponsor must submit annual reports.",
               "atomic_statement": "Sponsor submits annual reports",
               "modality": "must", "subject": "the sponsor", "object": "annual reports"}
    report = agent_packets._merge_decompose(paths, [
        {"span_id": "S0002", "requirements": []},
        {"span_id": "S0002", "requirements": [req_row]},
    ])
    assert report["requirements_added"] == 1
    cls = _classes_by_id(paths)["S0002"]
    assert cls["downgrade_pending"] is False
    assert cls["downgrade_proposal"]["resolution"]["decision"] == "extract"
    agent_packets.finalize(tmp_path, DOC_ID)


def test_merge_duplicate_zero_row_for_span_already_in_catalog_does_not_flag(tmp_path):
    """Zero-req row for a span whose requirements are already IN THE CATALOG."""
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN],
        [_cls("S0001", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    report = agent_packets._merge_decompose(paths, [
        {"span_id": "S0001", "requirements": []},
    ])
    assert report["downgrades_pending"] == 0
    assert report["skipped_rows_for_spans_with_requirements"] == 1
    assert not _classes_by_id(paths)["S0001"].get("downgrade_pending")


def test_decompose_rerun_is_idempotent_and_skips_pending_spans(tmp_path):
    frag = ("S0002", "(ii) Telephone number;\n")
    paths = _build_doc(
        tmp_path,
        [GOOD_SPAN, frag],
        [_cls("S0001", "requirement_bearing"), _cls("S0002", "requirement_bearing")],
        [_req("R00001", "S0001", GOOD_QUOTE)],
    )
    _mock_decomposers_return_zero(paths, "S0002")
    decompose.run(_ctx(paths))
    note_after_first = _classes_by_id(paths)["S0002"]["reconciler_note"]

    # Remove the fixtures: a re-run must NOT need the decomposers again for the
    # pending span (mock mode would raise on a missing fixture).
    for agent in ("decomposer_a", "decomposer_b"):
        (paths.fixtures_dir / agent / "S0002.json").unlink()
    decompose.run(_ctx(paths))

    cls = _classes_by_id(paths)["S0002"]
    assert cls["downgrade_pending"] is True
    assert cls["reconciler_note"] == note_after_first  # no duplicate annotations
