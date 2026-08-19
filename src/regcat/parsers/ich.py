"""Citation-aware segmenter for ICH-formatted guidelines.

ICH guidelines (E6, E8, E9, ...) use a different structure than CFR:

    - Major sections are roman-numeral parts:  "I. INTRODUCTION",
      "III   TRIAL DESIGN CONSIDERATIONS".
    - Subsections are decimal-numbered:  "2.3", "2.3.2", "5.2.1".
    - A few named sections appear at the end:  "GLOSSARY", "APPENDICES".
    - A dot-leader table of contents precedes the body
      ("2.1.1 Development Plan ................ 6").
    - Page furniture is a per-doc running header/footer
      ("ICH E6(R3) Guideline", "© EMEA 2006   23").

The boilerplate stage is responsible for stripping page furniture, but this
segmenter is also defensively robust to any residual furniture lines: they are
*absorbed* into the surrounding span rather than emitted as spurious section
headers. (An earlier, since-lost ICH segmenter turned every page-number footer
into a fake `section_header`; this one does not — see the E9 onboarding notes.)

Coverage is gap-free and non-overlapping by construction: each emitted span's
byte_end is the next emitted span's byte_start, so non-emitting lines fold into
the preceding span, and the first span is pinned to byte 0.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..schemas import Citation, Span, SpanKind
from .base import SegmenterBase


# --- regexes ---------------------------------------------------------------

# Known roman numerals I..XX as an explicit alternation, so a sentence that
# merely starts with "I " or "V " is not mistaken for a part header.
_ROMAN = (
    "XX|XIX|XVIII|XVII|XVI|XV|XIV|XIII|XII|XI|X|"
    "IX|VIII|VII|VI|V|IV|III|II|I"
)
# A roman part header: roman numeral, optional period, whitespace, then an
# ALL-CAPS title. The title-case check happens in code (handles digits like
# "ANNEX 1").
RX_ROMAN_HDR = re.compile(rf"^({_ROMAN})\.?\s+([A-Z][A-Z0-9].*?)\s*$")

# Named sections that appear without a number.
RX_NAMED_HDR = re.compile(
    r"^(GLOSSARY|APPENDICES|APPENDIX\b.*|REFERENCES|ANNEX(?:\s+\d+)?|"
    r"ABBREVIATIONS|LIST OF ABBREVIATIONS)\s*$"
)

# A decimal section number ("2.3", "2.3.2", "5.2.1") followed by its title/text.
RX_DECIMAL = re.compile(r"^(\d+(?:\.\d+)+)\s+(\S.*)$")

# Table-of-contents line: dot leaders ending in a page number.
RX_TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$")

# Residual page furniture the boilerplate stage may not have stripped.
RX_FURNITURE = re.compile(
    r"^(?:[\W_]{0,3}EMEA\s+\d{4}\b.*"          # "© EMEA 2006   23"
    r"|\d*\s*ICH\s+E\d[\w()]*\s+Guideline.*"   # "12 ICH E6(R3) Guideline"
    r"|ICH\s+Harmonised\s+Guideline.*"
    r")$",
    re.IGNORECASE,
)

RX_BLANK = re.compile(r"^\s*$")


@dataclass
class _Open:
    kind: SpanKind
    citation: Citation
    parent_span_id: Optional[str]
    byte_start: int
    span_id: str


class _IdGen:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> str:
        self.n += 1
        return f"S{self.n:04d}"


def _is_caps_title(text: str) -> bool:
    """True if the title portion is upper-case (ignoring digits/punctuation)."""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


class ICHSegmenter(SegmenterBase):
    name = "ich"

    def segment(self, canonical_text: str) -> list[Span]:
        canonical_byte_count = len(canonical_text.encode("utf-8"))

        raw_split = canonical_text.split("\n")
        if raw_split and raw_split[-1] == "":
            raw_split = raw_split[:-1]

        lines: list[tuple[int, str]] = []
        offset = 0
        for line in raw_split:
            lines.append((offset, line))
            offset += len(line.encode("utf-8")) + 1  # +1 for the \n

        ids = _IdGen()
        emitted: list[_Open] = []

        # Document state
        cur_part_id: Optional[str] = None         # roman/named header currently open
        decimal_spans: dict[str, str] = {}        # decimal citation -> span_id
        seen_title = False
        chapeau_open = False                       # a chapeau already started this section

        def emit(o: _Open) -> None:
            emitted.append(o)

        def decimal_parent(decimal: str) -> Optional[str]:
            """Parent = longest dotted prefix already seen, else the current part."""
            parts = decimal.split(".")
            for cut in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:cut])
                if prefix in decimal_spans:
                    return decimal_spans[prefix]
            return cur_part_id

        for byte_off, line in lines:
            stripped = line.strip()

            if RX_BLANK.match(line):
                continue
            if RX_FURNITURE.match(stripped):
                # Page header/footer that survived boilerplate — absorb it.
                continue

            # 1) Front matter: first real content line opens a DOCUMENT_TITLE span.
            if not seen_title:
                seen_title = True
                emit(_Open(SpanKind.DOCUMENT_TITLE, Citation(raw=stripped[:60]),
                           None, byte_off, ids.next()))
                continue

            # 2) Table-of-contents line.
            if RX_TOC_LINE.search(stripped):
                emit(_Open(SpanKind.TOC_ENTRY, Citation(raw=stripped[:60]),
                           None, byte_off, ids.next()))
                chapeau_open = False
                continue

            # 3) Roman-numeral part header (not a TOC line, ALL-CAPS title).
            m = RX_ROMAN_HDR.match(stripped)
            if m and _is_caps_title(m.group(2)):
                sp = _Open(SpanKind.SECTION_HEADER,
                           Citation(raw=m.group(1)), None, byte_off, ids.next())
                emit(sp)
                cur_part_id = sp.span_id
                decimal_spans.clear()
                chapeau_open = False
                continue

            # 4) Named section header (GLOSSARY, APPENDICES, ...).
            if RX_NAMED_HDR.match(stripped):
                sp = _Open(SpanKind.SECTION_HEADER,
                           Citation(raw=stripped[:40]), None, byte_off, ids.next())
                emit(sp)
                cur_part_id = sp.span_id
                decimal_spans.clear()
                chapeau_open = False
                continue

            # 5) Decimal subsection.
            m = RX_DECIMAL.match(stripped)
            if m:
                decimal = m.group(1)
                parent = decimal_parent(decimal)
                sp = _Open(SpanKind.PARAGRAPH,
                           Citation(section=decimal, raw=decimal),
                           parent, byte_off, ids.next())
                emit(sp)
                decimal_spans[decimal] = sp.span_id
                chapeau_open = False
                continue

            # 6) Prose: the first prose block under a header is a chapeau; the
            #    rest is absorbed into the preceding span via byte_end chaining.
            if cur_part_id and not chapeau_open:
                emit(_Open(SpanKind.SECTION_CHAPEAU, Citation(raw="chapeau"),
                           cur_part_id, byte_off, ids.next()))
                chapeau_open = True
            # else: continuation line, no emission (absorbed).

        # Pin the first span to byte 0 so leading front matter is covered, then
        # chain byte_end = next span's byte_start for gap-free, non-overlapping
        # coverage.
        if emitted:
            emitted[0].byte_start = 0

        spans: list[Span] = []
        data = canonical_text.encode("utf-8")
        for idx, o in enumerate(emitted):
            byte_end = emitted[idx + 1].byte_start if idx + 1 < len(emitted) else canonical_byte_count
            text = data[o.byte_start:byte_end].decode("utf-8", errors="replace")
            spans.append(Span(
                span_id=o.span_id,
                kind=o.kind,
                citation=o.citation,
                parent_span_id=o.parent_span_id,
                byte_start=o.byte_start,
                byte_end=byte_end,
                text=text,
                page_number=0,
            ))
        return spans
