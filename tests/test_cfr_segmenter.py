"""Regression tests for the CFR segmenter (parsers/cfr.py).

These pin the WS3 HIPAA-extraction fix so the citation-path collapse cannot
silently regress:

  1. Title/part are derived from the doc (45 CFR for HIPAA, not the legacy
     hard-coded 21 CFR 11).
  2. A single-character marker that is also a roman digit (c/d/l/m/v/x/i) is
     resolved by *sequence continuity*, not raw depth — so a level-1 letter
     that follows a numbered sub-list (e.g. § 164.312(d) after (c)(1)(2)) is
     not collapsed into a bogus roman child "(c)(2)(d)".
  3. Genuine deep roman runs (… (iv)(v)(vi) … (x)(xi)) survive intact.

They run the segmenter directly on the committed canonical.txt artifacts (no
LLM, no full pipeline), so they're fast and deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

from regcat.parsers.cfr import (
    CFRSegmenter,
    _int_to_roman,
    _roman_to_int,
)
from regcat.stages.segment import _cfr_title_part, _segmenter_for

ROOT = Path(__file__).resolve().parents[1]
P160 = ROOT / "docs" / "other" / "45-cfr-part-160"
P164 = ROOT / "docs" / "other" / "45-cfr-part-164"
P11 = ROOT / "docs" / "fda" / "21-cfr-part-11"


def _segment(doc_dir: Path):
    meta = json.loads((doc_dir / "meta.json").read_text(encoding="utf-8"))
    title, part = _cfr_title_part(meta)
    canon = (doc_dir / "source" / "canonical.txt").read_text(encoding="utf-8")
    return CFRSegmenter(default_title=title, default_part=part).segment(canon), canon


def _coverage(spans, text):
    n = len(text.encode("utf-8"))
    prev = covered = gaps = overlaps = 0
    for s in sorted(spans, key=lambda x: x.byte_start):
        if s.byte_start < prev:
            overlaps += 1
        if s.byte_start > prev:
            gaps += s.byte_start - prev
        covered += s.byte_end - s.byte_start
        prev = max(prev, s.byte_end)
    if prev < n:
        gaps += n - prev
    return covered, n, gaps, overlaps


# --- roman helpers ----------------------------------------------------------

def test_roman_roundtrip_and_rejects_non_canonical():
    for n, s in [(1, "i"), (4, "iv"), (5, "v"), (9, "ix"), (10, "x"), (14, "xiv")]:
        assert _int_to_roman(n) == s
        assert _roman_to_int(s) == n
    # Single letters that are roman *values* but never sequential list markers:
    assert _roman_to_int("c") == 100
    assert _roman_to_int("d") == 500
    # Non-canonical / non-roman strings do not parse.
    assert _roman_to_int("iiii") is None
    assert _roman_to_int("z") is None
    assert _roman_to_int("") is None


# --- title / part derivation ------------------------------------------------

def test_title_part_derived_from_short_id():
    assert _cfr_title_part({"short_id": "45-cfr-part-160"}) == ("45", "160")
    assert _cfr_title_part({"short_id": "45-cfr-part-164"}) == ("45", "164")
    assert _cfr_title_part({"short_id": "21-cfr-part-11"}) == ("21", "11")
    # Unknown shape falls back to the legacy default.
    assert _cfr_title_part({"short_id": "weird"}) == ("21", "11")
    assert _cfr_title_part({}) == ("21", "11")


def test_hipaa_spans_carry_correct_title_and_part():
    spans, _ = _segment(P160)
    para = [s for s in spans if s.kind.value == "paragraph"]
    assert para, "expected paragraph spans"
    assert all(s.citation.title == "45" for s in para)
    # Part is taken from each section's own prefix.
    assert all(s.citation.part == "160" for s in para if s.citation.section)
    # No span may regress to the legacy 21/11 default.
    assert not any(
        s.citation.title == "21" and s.citation.part == "11"
        for s in spans if s.citation.section
    )


def test_part164_part_derives_from_section_prefix():
    spans, _ = _segment(P164)
    para = [s for s in spans if s.kind.value == "paragraph" and s.citation.section]
    assert all(s.citation.part == "164" for s in para)


# --- the citation-path collapse fix -----------------------------------------

def _paragraphs_for_section(spans, section):
    return {
        s.citation.raw: s.citation.paragraphs
        for s in spans
        if s.citation.section == section and s.kind.value == "paragraph"
    }


def test_164_312_no_path_collapse():
    """§ 164.312 Technical safeguards: (d) is a level-1 letter, NOT (c)(2)(d)."""
    spans, _ = _segment(P164)
    paths = _paragraphs_for_section(spans, "164.312")
    # The standards run a..e at level 1.
    assert "§ 164.312(d)" in paths
    assert paths["§ 164.312(d)"] == ["d"]
    # The collapsed citation must NOT appear.
    assert "§ 164.312(c)(2)(d)" not in paths
    # Implementation specs nest correctly under their numbered parents.
    assert paths.get("§ 164.312(a)(2)(iv)") == ["a", "2", "iv"]
    assert paths.get("§ 164.312(e)(2)(ii)") == ["e", "2", "ii"]


def test_no_cdlm_as_deepest_roman_anywhere():
    """c/d/l/m are never valid sequential roman list markers; if one is the
    deepest paragraph element, that is the collapse bug."""
    for doc in (P160, P164):
        spans, _ = _segment(doc)
        offenders = [
            s.citation.raw
            for s in spans
            if s.kind.value == "paragraph"
            and len(s.citation.paragraphs) >= 3
            and s.citation.paragraphs[-1] in {"c", "d", "l", "m"}
        ]
        assert offenders == [], f"{doc.name}: collapsed roman-letter paths: {offenders}"


def test_genuine_deep_roman_runs_preserved():
    """The safe-harbor identifier list § 164.514(e)(2)(i..xi) is real roman
    nesting and must survive (the fix must not over-correct)."""
    spans, _ = _segment(P164)
    paths = _paragraphs_for_section(spans, "164.514")
    for rom in ("v", "x", "xi"):
        raw = f"§ 164.514(e)(2)({rom})"
        assert raw in paths, f"missing genuine roman {raw}"
        assert paths[raw] == ["e", "2", rom]


# --- coverage invariants (boundaries unchanged by the citation fix) ---------

def test_hipaa_coverage_gap_free():
    for doc in (P160, P164):
        spans, canon = _segment(doc)
        covered, total, gaps, overlaps = _coverage(spans, canon)
        # The committed spans.jsonl prepends a leading source-header span over
        # bytes 0..N; the raw segmenter leaves that as a single leading gap,
        # which the catalog fills. Everything after byte 0 is gap-free.
        assert overlaps == 0
        assert covered + gaps == total


# Part-164 byte range of the §164.512 body (its body header through the start of
# §164.514). The committed spans.jsonl predates the §164.512 soft-wrap fix and
# still carries §164.510 citations across this range; the requirements keyed to
# those frozen span_ids were citation-corrected separately (requirements.jsonl),
# so spans.jsonl is intentionally NOT re-segmented here — re-segmenting would
# renumber span_ids and break the source_span_id→verbatim linkage that
# test_smoke.test_verbatim_quotes_are_substrings pins. See the §164.512 fix note.
_P164_512_BODY_RANGE = (144780, 185800)


def test_committed_spans_match_segmenter_for_hipaa():
    """The committed spans.jsonl citations must equal a fresh re-segmentation.

    Every committed span that starts where a fresh span starts must carry the
    fresh span's citation. A few committed spans have no fresh span at their
    byte_start — the leading source-header (byte 0) and any demoted spurious
    section-header (an inline cross-reference like "§ 160.202 of this
    subchapter." that the fix no longer treats as a header). Those are filled in
    from the containing fresh span and must NOT re-introduce an out-of-part
    section attribution.

    Carve-out: the §164.512 soft-wrap fix corrected the segmenter to emit
    §164.512's body header (canonical.txt ~line 2695, soft-wrapped onto
    "not required.") which the older code missed, mis-filing all of §164.512's
    body under §164.510. The committed part-164 spans.jsonl is intentionally
    frozen (so requirement source_span_id→verbatim linkage stays intact), so
    across the §164.512 body byte range the committed span legitimately still
    reads §164.510 where the fresh span now reads §164.512. That specific
    510→512 relabel within part 164 is allowed; everything else must still match.
    """
    doc_part = {P160: "160", P164: "164"}
    for doc in (P160, P164):
        spans, _ = _segment(doc)
        fresh = {s.byte_start: s for s in spans}
        committed = [
            json.loads(line)
            for line in (doc / "source" / "spans.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        unmatched = 0
        for c in committed:
            f = fresh.get(c["byte_start"])
            if f is None:
                unmatched += 1  # source-header or demoted cross-ref line
                # No committed span may be attributed to a foreign part.
                sec = c["citation"].get("section") or ""
                if sec:
                    assert sec.split(".", 1)[0] == doc_part[doc], (
                        f"{doc.name}: span {c['span_id']} attributed to foreign part {sec}"
                    )
                # A demoted cross-ref must no longer be a section_header.
                assert not (c["kind"] == "section_header" and c["citation"]["raw"].startswith("§ ")
                            and c["citation"].get("section", "").split(".", 1)[0] != doc_part[doc])
                continue
            if c["citation"]["raw"] != f.citation.raw:
                # Allowed iff it's the frozen §164.510→§164.512 relabel inside the
                # §164.512 body range (same part, soft-wrap-fix correction).
                lo, hi = _P164_512_BODY_RANGE
                committed_512_region = (
                    doc is P164
                    and lo <= c["byte_start"] < hi
                    and (c["citation"].get("section") or "").startswith("164.510")
                    and (f.citation.section or "").startswith("164.512")
                )
                assert committed_512_region, (
                    f"{doc.name}: span {c['span_id']} citation "
                    f"{c['citation']['raw']!r} != fresh {f.citation.raw!r}"
                )
                continue
            assert c["citation"]["title"] == f.citation.title
            assert c["citation"]["part"] == f.citation.part
            assert c["citation"]["paragraphs"] == f.citation.paragraphs
        # Source-header (always) plus at most a couple of demoted cross-ref lines.
        assert unmatched <= 3


def test_no_inline_cross_reference_promoted_to_section_header():
    """A soft-wrapped inline citation ("§ 160.202 of this subchapter.") inside a
    Part-164 body must NOT become a § 160.202 section header, and Part-164 atoms
    must never be attributed to Part 160."""
    spans, _ = _segment(P164)
    foreign = [
        s for s in spans
        if (s.citation.section or "").startswith("160")
    ]
    assert foreign == [], f"Part-160 sections leaked into Part-164 segmentation: {[s.citation.raw for s in foreign]}"


# --- dispatch picks the CFR segmenter with derived title/part ---------------

class _FakePaths:
    def __init__(self, meta_path):
        self.meta_path = meta_path


class _FakeCtx:
    def __init__(self, meta_path):
        self.paths = _FakePaths(meta_path)


def test_segment_dispatch_cfr_carries_derived_title_part(tmp_path):
    meta = tmp_path / "meta.json"
    meta.write_text(
        json.dumps({"citation_format": "cfr", "short_id": "45-cfr-part-164"}),
        encoding="utf-8",
    )
    seg = _segmenter_for(_FakeCtx(meta))
    assert isinstance(seg, CFRSegmenter)
    assert seg.default_title == "45"
    assert seg.default_part == "164"


def test_completed_fda_doc_still_21cfr11():
    """Regression guard: the fix must not perturb the already-completed FDA
    21 CFR 11 extraction — its definition spans stay § 11.3(b)(N)."""
    spans, _ = _segment(P11)
    para = [s for s in spans if s.kind.value == "paragraph" and s.citation.section]
    assert all(s.citation.title == "21" for s in para)
    assert all(s.citation.part == "11" for s in para)
