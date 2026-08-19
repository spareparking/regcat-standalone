"""Regression tests for the generic/prose segmenter (parsers/generic.py).

The original generic segmenter that produced the FDA *guidance* catalogs
(eSource, the electronic-systems Q&A) was lost — like the ICH segmenter before
it (see test_ich_segmenter.py). Its loss was silent: `citation_format=generic`
fell through to the CFR segmenter, which emits ZERO spans on prose (no § tree),
so a fresh `regcat run` on any guidance doc produced 0 requirements at 0%
coverage. The rebuilt GenericSegmenter restores blank-line-block segmentation.

The eSource doc's committed `source/spans.jsonl` is the ground-truth fixture:
the rebuilt segmenter reproduces its 99 spans' byte boundaries exactly. These
tests pin that so the segmenter (and the generic dispatch) can't silently
regress again. They run the segmenter directly on committed canonical.txt
artifacts — no LLM, no pipeline — so they're fast and deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

from regcat.parsers.generic import GenericSegmenter
from regcat.stages.segment import _segmenter_for

ROOT = Path(__file__).resolve().parents[1]
ESOURCE = ROOT / "docs" / "fda" / "guidance-electronic-source-data-clinical-investigations" / "source"
PRO = ROOT / "docs" / "fda" / "guidance-patient-reported-outcome-measures" / "source"


def _coverage(spans, text):
    n = len(text.encode("utf-8"))
    prev = covered = gaps = overlaps = 0
    for s in spans:
        if s.byte_start < prev:
            overlaps += 1
        if s.byte_start > prev:
            gaps += s.byte_start - prev
        covered += s.byte_end - s.byte_start
        prev = max(prev, s.byte_end)
    if prev < n:
        gaps += n - prev
    return covered, n, gaps, overlaps


def test_generic_full_coverage_no_gaps_esource():
    text = (ESOURCE / "canonical.txt").read_text(encoding="utf-8")
    spans = GenericSegmenter().segment(text)
    covered, total, gaps, overlaps = _coverage(spans, text)
    assert covered == total
    assert gaps == 0
    assert overlaps == 0
    assert spans[0].byte_start == 0


def test_generic_reproduces_esource_fixture_boundaries():
    """The strong regression guard: exact byte boundaries of the lost
    segmenter's stored output (99 spans)."""
    text = (ESOURCE / "canonical.txt").read_text(encoding="utf-8")
    fixture = [json.loads(line) for line in (ESOURCE / "spans.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    got = GenericSegmenter().segment(text)
    assert len(got) == len(fixture) == 99
    assert [(s.byte_start, s.byte_end) for s in got] == [(f["byte_start"], f["byte_end"]) for f in fixture]


def test_generic_full_coverage_no_gaps_pro():
    # The PRO guidance is the eCOA/ePRO pilot doc; a 45-page prose guidance.
    text = (PRO / "canonical.txt").read_text(encoding="utf-8")
    spans = GenericSegmenter().segment(text)
    covered, total, gaps, overlaps = _coverage(spans, text)
    assert covered == total
    assert gaps == 0
    assert overlaps == 0
    # Prose blocks, not zero (the CFR-fallback bug produced 0 here).
    assert len(spans) > 100


def test_generic_dispatch_for_generic_format(tmp_path, monkeypatch):
    """`citation_format=generic` must route to GenericSegmenter, not the CFR
    fallback that silently yielded 0 spans on prose."""
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"citation_format": "generic"}), encoding="utf-8")

    class _Paths:
        meta_path = meta

    class _Ctx:
        paths = _Paths()

    assert isinstance(_segmenter_for(_Ctx()), GenericSegmenter)
