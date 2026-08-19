"""Citation-aware segmenter for CFR-formatted text.

CFR paragraph hierarchy (4 levels):
    level 1 = letter   "(a)", "(b)", ...
    level 2 = number   "(1)", "(2)", ...
    level 3 = roman    "(i)", "(ii)", ...
    level 4 = upper    "(A)", "(B)", ...

A single-character marker drawn from the roman alphabet ("i", "v", "x", "l",
"c", "d", "m") is ambiguous between a level-1 *letter* and a level-3 *roman*.
Older code disambiguated purely by depth: "if a level-2 number is open, treat
the marker as roman." That over-fires badly on real CFR text — e.g.
§164.312 runs (a)(1)(2)(b)(c)(1)(2)(d)(e)... where (d) is a level-1 letter
that *follows* a level-2 list under (c). The depth rule mislabeled (d) as a
roman child "(c)(2)(d)", collapsing the citation path. The same class hits
(c) after a numbered list, and (l)/(m).

We disambiguate by **sequence continuity** instead
(``disambiguate_single_char`` inside ``segment``): a roman-valued single char is
read as a roman only when it is the next roman in
an open roman sub-sequence (or the first roman ``i`` directly under a level-2
number); otherwise it is read as the letter that continues the section's
level-1 letter run. Letters c/d/l/m are never valid sequential roman markers in
CFR enumerations (roman list markers go i, ii, iii, iv, v, vi ... — d/c/l/m
only appear as positions 100/500/50/1000 which never occur as list items), so
those always resolve to letters. ``i``/``v``/``x`` resolve by which sequence
they continue.

Title and part are not hard-coded: ``_segmenter_for`` derives the CFR title
(e.g. "45" for HIPAA, "21" for FDA) from the doc meta, and the part is taken
from each section number's own prefix ("164.312" -> part "164"). The legacy
21/11 defaults remain only as a last-resort fallback for callers that supply
neither.

The output is gap-free, non-overlapping span coverage of canonical text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..schemas import Citation, Span, SpanKind
from .base import SegmenterBase


# --- regexes ---------------------------------------------------------------

RX_TOC_SUBPART  = re.compile(r"^Subpart\s+([A-Z])\s+(.+?)\s*$")     # "Subpart A General Provisions"
RX_SUBPART      = re.compile(r"^Subpart\s+([A-Z])[—-](.+?)\s*$")    # "Subpart A—General Provisions"
RX_TOC_SECTION  = re.compile(r"^§\s*(\d+\.\d+)\s+(.+?)\s*$")        # "§ 11.1 Scope."
RX_SECTION_HDR  = re.compile(r"^§\s*(\d+\.\d+)\s+(.+?)\s*$")
RX_PART_HDR     = re.compile(r"^PART\s+(\d+)[—-](.+)$")
RX_PART_TOC     = re.compile(r"^Part\s+(\d+)\s+(.+)$")
RX_TITLE        = re.compile(r"^Title\s+\d+\s*[—-].+$")
RX_CHAPTER      = re.compile(r"^Chapter\s+[IVX]+\s*[—-].+$")
RX_SUBCHAPTER   = re.compile(r"^Subchapter\s+[A-Z]\s*[—-].+$")
RX_AUTHORITY    = re.compile(r"^Authority:\s*.+$")
RX_SOURCE       = re.compile(r"^Source:\s*.+$")
RX_AMEND_NOTE       = re.compile(r"^\[\s*\d+\s+FR\s+.+\]\s*$")    # single-line form
RX_AMEND_NOTE_START = re.compile(r"^\[\s*\d+\s+FR\s+.+$")          # multi-line form: opens on this line
RX_PARA_LETTER  = re.compile(r"^\(([a-z])\)\s*(.*)$")               # single lowercase letter — level 1
RX_PARA_NUMBER  = re.compile(r"^\((\d+)\)\s*(.*)$")                  # level 2
RX_PARA_ROMAN   = re.compile(r"^\(([ivxlcdm]+)\)\s*(.*)$")           # lowercase roman — level 3
RX_PARA_UPPER   = re.compile(r"^\(([A-Z])\)\s*(.*)$")                # uppercase letter — level 4
RX_BLANK        = re.compile(r"^\s*$")


# --- roman / letter sequence helpers ---------------------------------------

# Single characters that are simultaneously a lowercase letter and a roman digit.
_ROMAN_LETTERS = set("ivxlcdm")

_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _roman_to_int(s: str) -> Optional[int]:
    """Parse a lowercase roman numeral to an int, or None if not well-formed."""
    if not s or any(ch not in _ROMAN_VALUES for ch in s):
        return None
    total = 0
    prev = 0
    for ch in reversed(s):
        val = _ROMAN_VALUES[ch]
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    # Round-trip guard so only canonical forms (i, ii, iv, ...) parse.
    return total if _int_to_roman(total) == s else None


def _int_to_roman(n: int) -> str:
    table = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
        (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    ]
    out = []
    for value, sym in table:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def _is_cross_reference_line(match: "re.Match[str]", section_part: str, doc_part: str) -> bool:
    """True if a "§ N.M ..." line is an inline cross-reference, not a section header.

    HIPAA bodies soft-wrap so an inline citation like "§ 160.202 of this
    subchapter." can land at the start of a line and look like a section header.
    Two independent tells distinguish a real header:

    - A real section header's number belongs to the DOCUMENT's own part; an
      inline citation to another part (e.g. § 160.202 inside a Part-164 body) is
      a cross-reference. This is the decisive, part-aware signal.
    - A real header's title is capitalized prose ("The hearing.", "Definitions.",
      "Notice of privacy practices."); a sentence continuing after an inline cite
      begins with a *lowercase* word ("of this subchapter", "relating to ...",
      "applies ..."). So a lowercase first word marks a continuation. (Capitalized
      first words are NOT treated as cross-references — CFR titles like "The"
      legitimately start that way.)
    """
    heading = (match.group(2) or "").strip()
    first_char = heading[0] if heading else ""
    looks_like_continuation = first_char.islower()
    other_part = section_part != doc_part
    return other_part or looks_like_continuation


def _is_title_softwrap_continuation(stripped: str) -> bool:
    """True if ``stripped`` is the soft-wrapped tail of a section title, not a new line.

    The TOC-vs-body lookahead (step 5) must skip these so it lands on the next
    genuine structural line. A continuation fragment of a section title — e.g.
    the "not required." tail of a TOC entry "§ 164.512 Uses ... agree or object
    is\nnot required." (45 CFR 164.512) — is plain lowercase-initial prose: it is
    NOT a section/subpart/part/Appendix header and NOT a "(marker)" paragraph
    opener. Without skipping it the lookahead lands on the fragment, fails to see
    the *following* "§ ..." TOC entry, mis-classifies the soft-wrapped TOC line as
    a body SECTION_HEADER, and — because section numbers are de-duped via
    ``seen_section_headers`` — then swallows the REAL body header further down
    (§ 164.512's body content was being absorbed into § 164.510). Anything that
    opens a structure (uppercase header, parenthesised marker, bracketed
    amendment note, "§"/Subpart/PART/Appendix) is a real next line and stops the
    skip.
    """
    if not stripped:
        return True
    if (RX_SECTION_HDR.match(stripped)
            or RX_SUBPART.match(stripped)
            or RX_PART_HDR.match(stripped)
            or RX_PART_TOC.match(stripped)
            or RX_AMEND_NOTE.match(stripped)
            or RX_AMEND_NOTE_START.match(stripped)
            or stripped.startswith("Appendix")
            or stripped.startswith("§")):
        return False
    if stripped[0] == "(":
        # A parenthesised paragraph marker "(a)" / "(1)" / "(i)" opens body content.
        return False
    # A title soft-wrap tail is lowercase-initial prose. An uppercase-initial line
    # is the start of new prose/title, not a wrapped tail, so do not skip it.
    return stripped[0].islower()


# --- internal state --------------------------------------------------------

@dataclass
class OpenSpan:
    kind: SpanKind
    citation: Citation
    parent_span_id: Optional[str]
    byte_start: int
    page_number: int
    span_id: str
    level: Optional[int] = None     # 1/2/3 for paragraph spans; None otherwise


class CFRSegmenter(SegmenterBase):
    name = "cfr"

    def __init__(self, default_title: str = "21", default_part: str = "11"):
        # ``default_part`` is a last-resort fallback only; the live part is taken
        # from each section number's own prefix (see ``_part_for_section``).
        self.default_title = default_title
        self.default_part = default_part

    def _part_for_section(self, section: Optional[str]) -> str:
        """Derive the part from a section number ("164.312" -> "164")."""
        if section and "." in section:
            return section.split(".", 1)[0]
        return self.default_part

    def segment(self, canonical_text: str) -> list[Span]:
        canonical_byte_count = len(canonical_text.encode("utf-8"))
        # Split into lines, dropping the phantom empty trailing entry that comes from a final "\n".
        raw_split = canonical_text.split("\n")
        if raw_split and raw_split[-1] == "":
            raw_split = raw_split[:-1]

        lines: list[tuple[int, str]] = []
        offset = 0
        for line in raw_split:
            lines.append((offset, line))
            offset += len(line.encode("utf-8")) + 1  # +1 for the \n

        next_id = _IdGen()
        open_specs: list[OpenSpan] = []           # emitted spans in order

        def emit(span: OpenSpan) -> None:
            open_specs.append(span)

        # Document state
        seen_part_header = False
        seen_section_headers: set[str] = set()
        # Sections matched while still in TOC mode (no PART header seen yet).
        # When we see one of these again, the second sighting is the body header
        # and we flip into body mode — needed for docs like 45 CFR Parts 160/164
        # that present "Part 164 —..." (lowercase, in the TOC area) and never
        # emit an all-caps "PART 164—..." body marker.
        seen_section_in_toc: set[str] = set()
        cur_subpart: Optional[Citation] = None
        cur_subpart_id: Optional[str] = None
        cur_section: Optional[Citation] = None
        cur_section_id: Optional[str] = None
        para_stack: list[OpenSpan] = []           # only paragraph-level OpenSpans, ordered shallow->deep
        # Markers opened directly under each parent id (section id or a paragraph
        # span id), in order. Used for sequence-aware roman/letter disambiguation.
        seq_seen: dict[str, list[str]] = {}

        def reset_paragraphs() -> None:
            nonlocal para_stack, seq_seen
            para_stack = []
            seq_seen = {}

        def open_paragraph(level: int, marker: str, byte_off: int) -> None:
            """Open a new paragraph span at `level`, popping any deeper-or-equal levels first."""
            nonlocal para_stack
            # Pop until the top of para_stack has level < new level
            while para_stack and (para_stack[-1].level or 0) >= level:
                para_stack.pop()
            parent_id = para_stack[-1].span_id if para_stack else cur_section_id
            parent_paragraphs = list(para_stack[-1].citation.paragraphs) if para_stack else []
            cit_paragraphs = parent_paragraphs + [marker]
            seq_seen.setdefault(parent_id or "", []).append(marker)
            cit = Citation(
                title=self.default_title,
                part=self._part_for_section(cur_section.section if cur_section else None),
                subpart=cur_subpart.subpart if cur_subpart else None,
                section=cur_section.section if cur_section else None,
                paragraphs=cit_paragraphs,
                raw=_render_citation(cur_section, cit_paragraphs),
            )
            sp = OpenSpan(
                kind=SpanKind.PARAGRAPH,
                citation=cit,
                parent_span_id=parent_id,
                byte_start=byte_off,
                page_number=0,
                span_id=next_id.next(),
                level=level,
            )
            emit(sp)
            para_stack.append(sp)

        def disambiguate_single_char(ch: str) -> tuple[int, str]:
            """Resolve a single roman-valued char to (level, marker).

            A single char like ``i``/``v``/``x``/``c``/``d``/``l``/``m`` is both a
            level-1 letter and a roman digit. We choose by sequence continuity:

            - ROMAN (level 3) iff it continues an open roman sub-list under a
              level-2 number, i.e. either (a) the immediate level-2 parent already
              has roman children and ``ch`` is the next roman after the last one,
              or (b) ``ch == 'i'`` and the deepest open paragraph is a level-2
              number with no children yet (a fresh roman list opening).
            - LETTER (level 1) otherwise — including the common case where ``ch``
              is the next level-1 letter after the section's last letter (e.g.
              ``c`` -> ``d``), which previously collapsed into a bogus roman path.

            Letters c/d/l/m are never valid sequential roman list markers, so they
            always resolve to letters here unless they would be a *first* ``i``
            (which they cannot be).
            """
            deepest = para_stack[-1] if para_stack else None
            deepest_level = deepest.level or 0 if deepest else 0

            # Candidate roman continuation only makes sense beneath a level-2 number.
            if deepest_level >= 2:
                # The parent that a new roman (level 3) would attach to is the
                # deepest level-2 (number) paragraph on the stack.
                lvl2 = next((sp for sp in reversed(para_stack) if (sp.level or 0) == 2), None)
                if lvl2 is not None:
                    roman_siblings = [
                        m for m in seq_seen.get(lvl2.span_id, [])
                        if _roman_to_int(m) is not None
                    ]
                    this_val = _roman_to_int(ch)
                    if roman_siblings:
                        last_val = _roman_to_int(roman_siblings[-1])
                        if this_val is not None and last_val is not None and this_val == last_val + 1:
                            return 3, ch
                        # ``ch`` is roman-valued but does NOT continue the roman run
                        # -> it is a letter restarting the level-1 sequence.
                        return 1, ch
                    # No roman children yet under this number: only a fresh ``i``
                    # opens a roman list; anything else (c/d/v/x/l/m) is a letter.
                    if deepest_level == 2 and ch == "i":
                        return 3, ch
            return 1, ch

        i = 0
        n = len(lines)
        while i < n:
            byte_off, line = lines[i]
            stripped = line.strip()

            if RX_BLANK.match(line):
                i += 1
                continue

            # 1) Pre-PART document headers
            if not seen_part_header:
                if RX_TITLE.match(stripped) or RX_CHAPTER.match(stripped) or RX_SUBCHAPTER.match(stripped):
                    emit(OpenSpan(SpanKind.DOCUMENT_TITLE, Citation(raw=stripped), None, byte_off, 0, next_id.next()))
                    i += 1
                    continue
                m = RX_PART_TOC.match(stripped)
                if m:
                    emit(OpenSpan(SpanKind.DOCUMENT_TITLE,
                                  Citation(part=m.group(1), raw=stripped), None, byte_off, 0, next_id.next()))
                    i += 1
                    continue
                m = RX_TOC_SUBPART.match(stripped)
                if m:
                    emit(OpenSpan(SpanKind.TOC_ENTRY,
                                  Citation(subpart=m.group(1), raw=stripped), None, byte_off, 0, next_id.next()))
                    i += 1
                    continue
                m = RX_TOC_SECTION.match(stripped)
                if m:
                    section_num = m.group(1)
                    if section_num in seen_section_in_toc:
                        # Second sighting — the TOC is over, this line opens the body.
                        # Flip into body mode and fall through to the section-header
                        # branch below, which will emit a SECTION_HEADER span.
                        seen_part_header = True
                    else:
                        seen_section_in_toc.add(section_num)
                        cit = Citation(title=self.default_title, part=self._part_for_section(section_num),
                                       section=section_num, raw=f"§ {section_num}")
                        emit(OpenSpan(SpanKind.TOC_ENTRY, cit, None, byte_off, 0, next_id.next()))
                        i += 1
                        continue

            # 2) PART header — real content begins
            m = RX_PART_HDR.match(stripped)
            if m:
                seen_part_header = True
                cit = Citation(title=self.default_title, part=m.group(1), raw=f"PART {m.group(1)}")
                emit(OpenSpan(SpanKind.PART_HEADER, cit, None, byte_off, 0, next_id.next()))
                cur_section = cur_section_id = None
                cur_subpart = cur_subpart_id = None
                reset_paragraphs()
                i += 1
                continue

            # 3) Authority / Source notes
            if RX_AUTHORITY.match(stripped):
                emit(OpenSpan(SpanKind.AUTHORITY, Citation(raw="Authority"), None, byte_off, 0, next_id.next()))
                i += 1
                continue
            if RX_SOURCE.match(stripped):
                emit(OpenSpan(SpanKind.SOURCE_NOTE, Citation(raw="Source"), None, byte_off, 0, next_id.next()))
                i += 1
                continue

            # 4) Subpart header (post-PART)
            if seen_part_header:
                m = RX_SUBPART.match(stripped)
                if m:
                    cit = Citation(title=self.default_title, part=self.default_part,
                                   subpart=m.group(1), raw=f"Subpart {m.group(1)}")
                    sp = OpenSpan(SpanKind.SUBPART_HEADER, cit, None, byte_off, 0, next_id.next())
                    emit(sp)
                    cur_subpart, cur_subpart_id = cit, sp.span_id
                    cur_section = cur_section_id = None
                    reset_paragraphs()
                    i += 1
                    continue

            # 5) Section header (only after PART, only first occurrence per section number)
            m = RX_SECTION_HDR.match(stripped)
            if m and seen_part_header and not _is_cross_reference_line(m, self._part_for_section(m.group(1)), self.default_part):
                section_num = m.group(1)
                # Lookahead — HIPAA-style docs (45 CFR 160/164) interleave per-subpart
                # TOCs with body content. A section header that's immediately followed
                # by another section/subpart/part header (after blank lines) is a TOC
                # entry, not body, even though we're past the global TOC.
                #
                # Soft-wrap defence (see _is_title_softwrap_continuation): a TOC
                # section title can soft-wrap onto the next physical line, so we skip
                # blank lines AND any lowercase-prose continuation fragment to reach
                # the next genuine structural line. Without this, § 164.512's
                # soft-wrapped TOC entry was mistaken for its body header and the real
                # body header was swallowed into § 164.510.
                j = i + 1
                while j < n and (
                    RX_BLANK.match(lines[j][1])
                    or _is_title_softwrap_continuation(lines[j][1].strip())
                ):
                    j += 1
                if j < n:
                    next_stripped = lines[j][1].strip()
                    if (RX_SECTION_HDR.match(next_stripped)
                            or RX_SUBPART.match(next_stripped)
                            or RX_PART_HDR.match(next_stripped)
                            or next_stripped.startswith("Appendix")):
                        cit = Citation(title=self.default_title, part=self._part_for_section(section_num),
                                       subpart=cur_subpart.subpart if cur_subpart else None,
                                       section=section_num, raw=f"§ {section_num}")
                        emit(OpenSpan(SpanKind.TOC_ENTRY, cit, cur_subpart_id, byte_off, 0, next_id.next()))
                        i += 1
                        continue
                if section_num not in seen_section_headers:
                    seen_section_headers.add(section_num)
                    cit = Citation(title=self.default_title, part=self._part_for_section(section_num),
                                   subpart=cur_subpart.subpart if cur_subpart else None,
                                   section=section_num, raw=f"§ {section_num}")
                    sp = OpenSpan(SpanKind.SECTION_HEADER, cit, cur_subpart_id, byte_off, 0, next_id.next())
                    emit(sp)
                    cur_section, cur_section_id = cit, sp.span_id
                    reset_paragraphs()
                    i += 1
                    continue

            # 6) Amendment note in brackets — single line, or opens here and closes on a later line
            if RX_AMEND_NOTE.match(stripped) or RX_AMEND_NOTE_START.match(stripped):
                cit = Citation(raw="amendment_note",
                               section=cur_section.section if cur_section else None)
                emit(OpenSpan(SpanKind.SOURCE_NOTE, cit, cur_section_id, byte_off, 0, next_id.next()))
                # Skip ahead past the closing "]" so the wrapped lines are absorbed as continuation
                # of this SOURCE_NOTE span (handled by the byte_end computation later).
                if not RX_AMEND_NOTE.match(stripped):
                    j = i + 1
                    while j < n and "]" not in lines[j][1]:
                        j += 1
                    if j < n:
                        i = j  # consume up to and including the closing-bracket line
                # Amendment notes don't change para_stack; the section continues
                i += 1
                continue

            # 7) Paragraph markers — disambiguate level
            m_let = RX_PARA_LETTER.match(stripped)
            m_num = RX_PARA_NUMBER.match(stripped)
            m_rom = RX_PARA_ROMAN.match(stripped)
            m_upp = RX_PARA_UPPER.match(stripped)

            # Determine intended level
            level: Optional[int] = None
            marker: Optional[str] = None
            if m_num:
                level = 2
                marker = m_num.group(1)
            elif m_rom and len(m_rom.group(1)) >= 2:
                # multi-char roman: definitely level 3 (no letter is multi-char)
                level = 3
                marker = m_rom.group(1)
            elif m_let:
                # Single char marker — could be a level-1 letter or a single-char
                # roman (i, v, x, l, c, d, m). Decide by SEQUENCE continuity, not
                # by raw depth: a roman-valued char is only a roman if it continues
                # an open roman sub-list under a level-2 number; otherwise it is a
                # letter advancing the section's level-1 run. This fixes the path
                # collapse where (d) after (c)(1)(2) was mislabeled "(c)(2)(d)".
                ch = m_let.group(1)
                if ch in _ROMAN_LETTERS:
                    level, marker = disambiguate_single_char(ch)
                else:
                    level = 1
                    marker = ch
            elif m_rom:
                # single roman char with no letter match (shouldn't happen since [ivxlcdm] ⊂ [a-z])
                level = 3
                marker = m_rom.group(1)
            elif m_upp:
                # uppercase letter — CFR convention is level 4 (deepest standard nesting)
                level = 4
                marker = m_upp.group(1)

            if level is not None and cur_section_id:
                open_paragraph(level, marker, byte_off)
                i += 1
                continue

            # 8) Fallback: a content line that doesn't start a new paragraph
            if cur_section_id and not para_stack:
                # Lead-in chapeau under a section
                last_span = open_specs[-1] if open_specs else None
                if last_span and last_span.kind == SpanKind.SECTION_CHAPEAU and last_span.parent_span_id == cur_section_id:
                    i += 1
                    continue
                cit = Citation(
                    title=self.default_title,
                    part=self._part_for_section(cur_section.section if cur_section else None),
                    subpart=cur_subpart.subpart if cur_subpart else None,
                    section=cur_section.section if cur_section else None,
                    raw=f"§ {cur_section.section} chapeau" if cur_section else "chapeau",
                )
                emit(OpenSpan(SpanKind.SECTION_CHAPEAU, cit, cur_section_id, byte_off, 0, next_id.next()))
                i += 1
                continue

            # continuation line of an open span — no new emission
            i += 1

        # Compute byte_end for each emitted span as the byte_start of the next span,
        # so coverage is exact, gap-free, non-overlapping.
        spans: list[Span] = []
        for idx, osp in enumerate(open_specs):
            byte_end = open_specs[idx + 1].byte_start if idx + 1 < len(open_specs) else canonical_byte_count
            text = canonical_text.encode("utf-8")[osp.byte_start:byte_end].decode("utf-8")
            spans.append(Span(
                span_id=osp.span_id,
                kind=osp.kind,
                citation=osp.citation,
                parent_span_id=osp.parent_span_id,
                byte_start=osp.byte_start,
                byte_end=byte_end,
                text=text,
                page_number=osp.page_number,
            ))
        return spans


# --- helpers ----------------------------------------------------------------

class _IdGen:
    def __init__(self):
        self.n = 0

    def next(self) -> str:
        self.n += 1
        return f"S{self.n:04d}"


def _render_citation(section: Optional[Citation], paragraphs: list[str]) -> str:
    head = f"§ {section.section}" if section and section.section else "§"
    tail = "".join(f"({p})" for p in paragraphs)
    return head + tail
