"""Regression tests for the ICH segmenter (parsers/ich.py).

The original ICH segmenter that produced E6(R3)'s catalog was lost (no git
history). It turned every page-number footer into a fake `section_header`
(78 artifacts in E6). The rebuilt segmenter drops that noise while recovering
the real structure. These tests pin that behavior so it can't silently regress.

They run the segmenter directly on the committed canonical.txt artifacts (no
LLM, no full pipeline), so they're fast and deterministic.
"""
from __future__ import annotations

import re
from pathlib import Path

from regcat.parsers.ich import ICHSegmenter
from regcat.stages.segment import _segmenter_for

ROOT = Path(__file__).resolve().parents[1]
E6_CANON = ROOT / "docs" / "ich" / "e6-r3-good-clinical-practice" / "source" / "canonical.txt"
E9_CANON = ROOT / "docs" / "ich" / "e9-statistical-principles" / "source" / "canonical.txt"


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


# --- E6(R3): scratch regression guard (E6's frozen spans are NOT touched) ---

def test_e6_full_coverage_no_gaps():
    text = E6_CANON.read_text(encoding="utf-8")
    spans = ICHSegmenter().segment(text)
    covered, total, gaps, overlaps = _coverage(spans, text)
    assert covered == total
    assert gaps == 0
    assert overlaps == 0


def test_e6_recovers_262_decimal_sections():
    # The real structural backbone the original segmenter also found.
    text = E6_CANON.read_text(encoding="utf-8")
    spans = ICHSegmenter().segment(text)
    decimals = [s for s in spans if s.kind.value == "paragraph"]
    assert len(decimals) == 262


def test_e6_drops_page_number_artifacts():
    # No section_header may be a bare integer (those were the 78 page footers).
    text = E6_CANON.read_text(encoding="utf-8")
    spans = ICHSegmenter().segment(text)
    headers = [s for s in spans if s.kind.value == "section_header"]
    bare_int = [h for h in headers if re.fullmatch(r"\d+", (h.citation.raw or "").strip())]
    assert bare_int == [], f"page-number artifacts leaked back in: {[h.citation.raw for h in bare_int]}"
    # The real roman/named headers are present.
    raws = {(h.citation.raw or "").strip() for h in headers}
    assert {"I", "II", "III", "GLOSSARY"} <= raws


# --- E9: the new doc the segmenter was built to handle ----------------------

def test_e9_full_coverage_no_gaps():
    text = E9_CANON.read_text(encoding="utf-8")
    spans = ICHSegmenter().segment(text)
    covered, total, gaps, overlaps = _coverage(spans, text)
    assert covered == total
    assert gaps == 0
    assert overlaps == 0


def test_e9_roman_parts_present():
    text = E9_CANON.read_text(encoding="utf-8")
    spans = ICHSegmenter().segment(text)
    raws = {(s.citation.raw or "").strip() for s in spans if s.kind.value == "section_header"}
    assert {"I", "II", "III", "IV", "V", "VI", "VII"} <= raws


def test_e9_rtsm_critical_sections_present():
    # Blinding and Randomisation are the IWRS/RTSM-relevant sections; they must
    # survive segmentation as their own decimal spans.
    text = E9_CANON.read_text(encoding="utf-8")
    spans = ICHSegmenter().segment(text)
    sections = {s.citation.section for s in spans if s.kind.value == "paragraph"}
    assert "2.3.1" in sections  # Blinding
    assert "2.3.2" in sections  # Randomisation


# --- dispatch ---------------------------------------------------------------

class _FakeMeta:
    pass


class _FakePaths:
    def __init__(self, meta_path):
        self.meta_path = meta_path


class _FakeCtx:
    def __init__(self, meta_path):
        self.paths = _FakePaths(meta_path)


def test_segment_dispatch_picks_ich(tmp_path):
    meta = tmp_path / "meta.json"
    meta.write_text('{"citation_format": "ich"}', encoding="utf-8")
    assert isinstance(_segmenter_for(_FakeCtx(meta)), ICHSegmenter)


def test_segment_dispatch_defaults_to_cfr(tmp_path):
    from regcat.parsers.cfr import CFRSegmenter
    meta = tmp_path / "meta.json"
    meta.write_text('{"citation_format": "cfr"}', encoding="utf-8")
    assert isinstance(_segmenter_for(_FakeCtx(meta)), CFRSegmenter)
