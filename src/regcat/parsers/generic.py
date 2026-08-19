"""Citation-agnostic segmenter for prose documents (FDA guidance, white papers).

Many source documents are not structured as a CFR paragraph tree or an ICH
roman/decimal hierarchy — they are prose with section headings, a dot-leader
table of contents, and free-flowing paragraphs. The CFR and ICH segmenters emit
zero spans on such text because they key on citation structure that prose lacks.

This segmenter chunks prose into **blank-line-delimited blocks**: each maximal
run of non-blank lines is one span, and the intervening blank lines fold into
the preceding block. A block's ``kind`` is a light, advisory heuristic — short
heading / dot-leader lines and leading front matter are ``document_title``;
everything else is ``paragraph`` (the requirement-bearing candidate). The kind
is context for the LLM classifier only; classify.py runs on every span
regardless of kind, so block *boundaries* matter and kind labels do not gate
extraction. It is the segmenter the registry's ``generic`` ``citation_format``
maps to (see ``stages/segment.py``).

Splitting on blank lines (rather than on heading patterns) is deliberate: a
heading-based split mis-fires on body lines that merely begin with a number
("21 CFR 312...", "2009", list items), shredding prose into hundreds of
fragments. Blank-line blocking reproduces the ~1-span-per-paragraph granularity
of the original generic segmenter.

Coverage is gap-free and non-overlapping by construction: each emitted span's
byte_end is the next emitted span's byte_start, non-emitting lines fold into the
preceding span, and the first span is pinned to byte 0.

This restores the segmentation contract of the (since-lost) generic segmenter
that originally extracted the FDA guidance documents already in the catalog
(e.g. ``fda/guidance-electronic-source-data-clinical-investigations``). That
doc's stored ``source/spans.jsonl`` is the coverage regression fixture — see
``tests``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import Citation, Span, SpanKind
from .base import SegmenterBase


RX_BLANK = re.compile(r"^\s*$")

# Table-of-contents line: title text followed by dot leaders ending in a page
# number ("A.  Data Capture ......... 3").
RX_TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$")

# Numbered/lettered heading marker at line start: a roman numeral, a single
# capital letter, or a (possibly dotted) decimal, then separator + title text.
# Only consulted for short lines (see _block_kind), so body sentences that begin
# with a number are not mistaken for headings.
_ROMAN = r"[IVXLC]+"
RX_HEADING = re.compile(rf"^(?:{_ROMAN}\.|[A-Z]\.|\d+(?:\.\d+)*\.?)\s+\S")

# A heading line is short.
_HEADING_MAX_LEN = 80


def _is_caps_heading(stripped: str) -> bool:
    """True for a short ALL-CAPS line (e.g. 'INTRODUCTION', 'BACKGROUND')."""
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and len(stripped) <= _HEADING_MAX_LEN and all(c.isupper() for c in letters)


def _block_kind(stripped: str, seen_body: bool) -> SpanKind:
    """Advisory kind for a block, from its first line. Boundaries (not kind)
    drive extraction; this only gives the LLM classifier helpful context."""
    if RX_TOC_LINE.search(stripped):
        return SpanKind.TOC_ENTRY
    if len(stripped) <= _HEADING_MAX_LEN and (_is_caps_heading(stripped) or RX_HEADING.match(stripped)):
        return SpanKind.SECTION_HEADER
    return SpanKind.PARAGRAPH if seen_body else SpanKind.DOCUMENT_TITLE


@dataclass
class _Open:
    kind: SpanKind
    citation: Citation
    byte_start: int
    span_id: str


class _IdGen:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> str:
        self.n += 1
        return f"S{self.n:04d}"


class GenericSegmenter(SegmenterBase):
    name = "generic"

    def segment(self, canonical_text: str) -> list[Span]:
        canonical_byte_count = len(canonical_text.encode("utf-8"))

        raw_split = canonical_text.split("\n")
        if raw_split and raw_split[-1] == "":
            raw_split = raw_split[:-1]

        lines: list[tuple[int, str]] = []
        offset = 0
        for line in raw_split:
            lines.append((offset, line))
            offset += len(line.encode("utf-8")) + 1  # +1 for the stripped \n

        ids = _IdGen()
        emitted: list[_Open] = []
        prev_blank = True   # so the first non-blank line opens a block
        seen_body = False   # flips at the first body section header (post-TOC)

        for byte_off, line in lines:
            if RX_BLANK.match(line):
                prev_blank = True
                continue

            if prev_blank:
                # First non-blank line of a new block opens a span; the rest of
                # the block's lines fold in via byte_end chaining.
                stripped = line.strip()
                kind = _block_kind(stripped, seen_body)
                if kind is SpanKind.SECTION_HEADER:
                    seen_body = True
                emitted.append(_Open(kind, Citation(raw=stripped[:60]), byte_off, ids.next()))
                prev_blank = False
                continue

            # Continuation line of the current block — absorbed.
            prev_blank = False

        # Pin the first span to byte 0 so any leading blank lines are covered,
        # then chain byte_end = next span's byte_start for gap-free coverage.
        if emitted:
            emitted[0].byte_start = 0
            emitted[0].kind = SpanKind.DOCUMENT_TITLE

        spans: list[Span] = []
        data = canonical_text.encode("utf-8")
        for idx, o in enumerate(emitted):
            byte_end = emitted[idx + 1].byte_start if idx + 1 < len(emitted) else canonical_byte_count
            text = data[o.byte_start:byte_end].decode("utf-8", errors="replace")
            spans.append(Span(
                span_id=o.span_id,
                kind=o.kind,
                citation=o.citation,
                parent_span_id=None,
                byte_start=o.byte_start,
                byte_end=byte_end,
                text=text,
                page_number=0,
            ))
        return spans
