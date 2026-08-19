"""Deterministic regulatory-text signal detectors.

A "signal" is a span of text matching a pattern that often indicates an obligation,
scope clause, or other substantive content. Signals are used by the Embedded-Obligation
Auditor (Stage 5.5) to find content that the classifier may have overlooked.

These are deterministic regex-based detectors — they err on the side of recall
(flag aggressively), and a downstream LLM decomposer filters false positives by
returning zero requirements when there's no real obligation.

Signal classes:
  MODAL_OBLIGATION   "shall", "must" — the strongest obligation markers
  MODAL_PERMISSIVE   "may", "should" — softer obligations
  NOMINAL_IMPERATIVE "Use of", "Determination that", "Establishment of" — CFR's
                     nominalized imperative form (the §11.10(a)-(k) pattern)
  INCLUSION_CLAUSE   "may also be applied to", "shall include", "includes"
  EXCLUSION_CLAUSE   "does not apply to", "is not subject to"
  RE_INCLUSION       "Records that satisfy X but ... remain subject to this part"
                     — CFR Part 11 scope re-inclusion pattern

Patterns target English-language regulatory writing. Add jurisdiction-specific
classes (ICH "should be considered", EU "the holder shall ensure", etc.) as we
process more documents.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class SignalClass(str, Enum):
    MODAL_OBLIGATION   = "modal_obligation"     # shall, must
    MODAL_PERMISSIVE   = "modal_permissive"     # may, should
    NOMINAL_IMPERATIVE = "nominal_imperative"   # Use of, Determination that, ...
    INCLUSION_CLAUSE   = "inclusion_clause"     # may also be applied to, shall include
    EXCLUSION_CLAUSE   = "exclusion_clause"     # does not apply to
    RE_INCLUSION       = "re_inclusion"         # CFR scope re-inclusion


@dataclass
class Signal:
    sig_class: SignalClass
    pattern_id: str
    matched_text: str
    start: int        # char offset within the input string
    end: int


# --- patterns ---------------------------------------------------------------
# Each entry: (pattern_id, SignalClass, compiled_regex)
# Order matters only for reporting; detection is exhaustive.

_MODAL_OBLIGATION_PATTERNS = [
    ("shall", SignalClass.MODAL_OBLIGATION, re.compile(r"\bshall\b", re.IGNORECASE)),
    ("must",  SignalClass.MODAL_OBLIGATION, re.compile(r"\bmust\b",  re.IGNORECASE)),
]

_MODAL_PERMISSIVE_PATTERNS = [
    # `\bmay\b` would over-match date abbreviations like "May 27, 2016". We require lowercase
    # "may" and not "May" at start-of-sentence, AND not followed by a digit (date) or year-like.
    # The reaudit logic also filters source_note spans which is where most date hits live.
    ("may",    SignalClass.MODAL_PERMISSIVE, re.compile(r"(?<![\.\!\?]\s)\bmay\b(?!\s+\d{1,2}(?:,?\s+\d{4})?)")),
    ("should", SignalClass.MODAL_PERMISSIVE, re.compile(r"\bshould\b", re.IGNORECASE)),
]

_NOMINAL_IMPERATIVE_PATTERNS = [
    ("use_of",            SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Use of\s",       re.MULTILINE)),
    ("determination",     SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Determination\s", re.MULTILINE)),
    ("establishment",     SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?(?:The\s+)?[Ee]stablishment\s", re.MULTILINE)),
    ("implementation",    SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Implementation\s",re.MULTILINE)),
    ("maintenance",       SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Maintenance\s",   re.MULTILINE)),
    ("validation",        SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Validation\s",    re.MULTILINE)),
    ("protection",        SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Protection\s",    re.MULTILINE)),
    ("limiting",          SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Limiting\s",      re.MULTILINE)),
    ("ensuring",          SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Ensuring\s",      re.MULTILINE)),
    ("maintaining",       SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Maintaining\s",   re.MULTILINE)),
    ("following_procs",   SignalClass.NOMINAL_IMPERATIVE, re.compile(r"^\s*(?:\([a-z0-9ivxlcdm]+\)\s+)?Following\s",     re.MULTILINE)),
]

_INCLUSION_PATTERNS = [
    # Constructive scope inside definitions — the §11.3(b)(8) pattern
    ("may_also_apply",   SignalClass.INCLUSION_CLAUSE, re.compile(r"\bmay\s+also\s+be\s+applied\s+to\b",   re.IGNORECASE)),
    ("shall_include",    SignalClass.INCLUSION_CLAUSE, re.compile(r"\bshall\s+include\b",                  re.IGNORECASE)),
    ("includes",         SignalClass.INCLUSION_CLAUSE, re.compile(r"\bincludes?\b",                        re.IGNORECASE)),
    ("is_intended_to",   SignalClass.INCLUSION_CLAUSE, re.compile(r"\bis\s+intended\s+to\b",               re.IGNORECASE)),
    ("for_purposes_of",  SignalClass.INCLUSION_CLAUSE, re.compile(r"\bfor\s+(?:the\s+)?purposes?\s+of\b",  re.IGNORECASE)),
]

_EXCLUSION_PATTERNS = [
    ("does_not_apply",   SignalClass.EXCLUSION_CLAUSE, re.compile(r"\bdoes\s+not\s+apply\b",          re.IGNORECASE)),
    ("not_subject_to",   SignalClass.EXCLUSION_CLAUSE, re.compile(r"\bis\s+not\s+subject\s+to\b",     re.IGNORECASE)),
    ("not_applicable",   SignalClass.EXCLUSION_CLAUSE, re.compile(r"\bnot\s+applicable\b",            re.IGNORECASE)),
]

_RE_INCLUSION_PATTERNS = [
    # The CFR Part 11 pattern: "Records that satisfy the requirements of part X ... but that also are
    # required under other applicable statutory provisions or regulations, remain subject to this part."
    ("remain_subject_to", SignalClass.RE_INCLUSION,
     re.compile(r"\bremain\s+subject\s+to\b", re.IGNORECASE)),
]


ALL_PATTERNS = (
    _MODAL_OBLIGATION_PATTERNS
    + _MODAL_PERMISSIVE_PATTERNS
    + _NOMINAL_IMPERATIVE_PATTERNS
    + _INCLUSION_PATTERNS
    + _EXCLUSION_PATTERNS
    + _RE_INCLUSION_PATTERNS
)


# --- date false positives ---------------------------------------------------

_DATE_RX = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b")


def _is_inside_date_phrase(text: str, start: int, end: int) -> bool:
    """Return True if the (start, end) range falls inside a recognizable date phrase
    like 'May 27, 2016' or 'Mar. 20, 1997'. Used to filter false-positive modal-verb
    hits in source notes and amendment lists.
    """
    # Look in a window of ±20 chars around the hit
    window_start = max(0, start - 12)
    window_end = min(len(text), end + 20)
    window = text[window_start:window_end]
    for m in _DATE_RX.finditer(window):
        if window_start + m.start() <= start and window_start + m.end() >= end:
            return True
    return False


def scan(text: str, *, drop_date_false_positives: bool = True) -> list[Signal]:
    """Find every signal in `text`. Returns a list of Signal objects sorted by start offset."""
    out: list[Signal] = []
    for pattern_id, sig_class, rx in ALL_PATTERNS:
        for m in rx.finditer(text):
            if drop_date_false_positives and sig_class == SignalClass.MODAL_PERMISSIVE:
                if _is_inside_date_phrase(text, m.start(), m.end()):
                    continue
            out.append(Signal(
                sig_class=sig_class,
                pattern_id=pattern_id,
                matched_text=m.group(0),
                start=m.start(),
                end=m.end(),
            ))
    out.sort(key=lambda s: s.start)
    return out


def has_obligation_signal(text: str) -> bool:
    """Cheap predicate: does this text plausibly contain an embedded obligation?

    Returns True if any modal-obligation, inclusion, or nominal-imperative pattern matches.
    Modal-permissive ("may", "should") alone is weaker evidence and the LLM decomposer
    is the right place to triage it — but we still consider it.
    """
    sigs = scan(text)
    classes = {s.sig_class for s in sigs}
    return bool(classes & {
        SignalClass.MODAL_OBLIGATION,
        SignalClass.MODAL_PERMISSIVE,
        SignalClass.NOMINAL_IMPERATIVE,
        SignalClass.INCLUSION_CLAUSE,
    })
