"""Stage 2: Strip page headers/footers and structural boilerplate.

Combines deterministic regex rules (per-page-format patterns) with dynamic
rules derived from the document's meta.json (e.g. the per-doc title that
repeats on every page).

Every stripped line is logged with its rule_id so the Coverage Auditor can
prove that nothing substantive was removed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..schemas import CanonicalSource, StrippedSpan


PAGE_BREAK = "\f"


# Generic CFR-format patterns. We accept any part number (Part 11, Part 50, etc.)
# and any section/paragraph citation (11.1, 50.20(a), 56.108(a)(3)(ii), ...).
_BASE_RULES: list[tuple[str, re.Pattern]] = [
    ("PAGE_HEADER_PART_DATE",
     re.compile(r"^21 CFR Part \d+ \(up to date as of \d{1,2}/\d{1,2}/\d{4}\)\s*$")),
    ("PAGE_HEADER_PART_PUBDATE",
     re.compile(r"^21 CFR Part \d+ \([A-Z][a-z]+\.? \d{1,2},? \d{4}\)\s*$")),
    # Combined footer with citation + page label glued together
    ("PAGE_FOOTER_COMBINED",
     re.compile(r"^21 CFR \d+\.\d+[\w\.\(\)]* \(enhanced display\)\s+page \d+ of \d+\s*$")),
    ("PAGE_FOOTER_CITATION",
     re.compile(r"^21 CFR \d+\.\d+[\w\.\(\)]* \(enhanced display\)\s*$")),
    ("PAGE_FOOTER_PAGE",
     re.compile(r"^page \d+ of \d+\s*$")),
    # Bare-citation echo (the odd-page footer-left text)
    ("PAGE_FOOTER_CITATION_BARE",
     re.compile(r"^21 CFR \d+\.\d+(?:\([a-z0-9]+\))*\s*$")),
    ("ECFR_DISCLAIMER",
     re.compile(r"^This content is from the eCFR and is authoritative but unofficial\.\s*$")),
]


# ICH/EMEA page furniture. Gated on citation_format == "ich" so these never
# touch CFR documents. ICH guidelines carry a per-doc running header/footer and
# (for EMEA-published copies) a "© EMEA <year> <page#>" footer.
_ICH_RULES: list[tuple[str, re.Pattern]] = [
    ("PAGE_FOOTER_EMEA",
     re.compile(r"^[\W_]{0,3}EMEA\s+\d{4}\b.*$")),
    ("PAGE_HEADER_ICH_GUIDELINE",
     re.compile(r"^\d*\s*ICH\s+E\d[\w()]*\s+Guideline\s*$")),
    ("PAGE_HEADER_ICH_HARMONISED",
     re.compile(r"^ICH\s+Harmonised\s+Guideline\s*$", re.IGNORECASE)),
]


# Margin line numbers: a 1-4 digit number, a wide gap, then content. Many FDA
# *draft* guidances (and some finals) print sequential line numbers in the left
# margin; the PDF extractor renders them as a prefix on each line
# ("141        For interviews, issues might arise ..."). They are furniture, but
# unlike page headers they sit ON a content line, so we strip the PREFIX rather
# than the whole line. To avoid clobbering legitimate leading numbers ("21 CFR",
# "100 patients", a numbered list), we only strip prefixes that form an
# INCREASING RUN — margin numbers increment down the page; real leading numbers
# don't. This breaks verbatim matching otherwise (a quote spanning two source
# lines straddles an embedded "\n<number>").
_MARGIN_NUM = re.compile(r"^(\d{1,4})(\s{2,})(\S.*)$")


def _strip_margin_line_numbers(lines: list[str]) -> tuple[list[str], list[int]]:
    cand: dict[int, int] = {}
    for i, line in enumerate(lines):
        m = _MARGIN_NUM.match(line)
        if m:
            cand[i] = int(m.group(1))
    if len(cand) < 3:
        return lines, []
    idxs = sorted(cand)
    in_run: set[int] = set()
    for a, b in zip(idxs, idxs[1:]):
        # nearby candidate lines (allow small index gap for blanks) whose numbers
        # increase by 1-3 form a margin-number run.
        if b - a <= 3 and 1 <= cand[b] - cand[a] <= 3:
            in_run.add(a)
            in_run.add(b)
    if len(in_run) < 3:
        return lines, []
    out: list[str] = []
    stripped_idx: list[int] = []
    for i, line in enumerate(lines):
        if i in in_run:
            out.append(_MARGIN_NUM.match(line).group(3))
            stripped_idx.append(i)
        else:
            out.append(line)
    return out, stripped_idx


def _build_dynamic_rules(title: str | None,
                         citation_format: str | None) -> list[tuple[str, re.Pattern]]:
    """Build rules that depend on this doc's meta.json (title + citation_format)."""
    rules: list[tuple[str, re.Pattern]] = []
    if title:
        # Match the doc title exactly as a line — it repeats on every page header.
        rules.append((
            "PAGE_HEADER_DOC_TITLE",
            re.compile(rf"^{re.escape(title)}\s*$"),
        ))
    if citation_format == "ich":
        rules.extend(_ICH_RULES)
    return rules


def run(ctx) -> None:
    raw_text_path = ctx.paths.source_dir / "raw_text.txt"
    raw = raw_text_path.read_text(encoding="utf-8")

    # Load doc title + citation_format from meta.json if available
    doc_title: str | None = None
    citation_format: str | None = None
    if ctx.paths.meta_path.exists():
        try:
            meta = json.loads(ctx.paths.meta_path.read_text(encoding="utf-8"))
            doc_title = meta.get("title")
            citation_format = meta.get("citation_format")
        except Exception:
            pass

    rules = _BASE_RULES + _build_dynamic_rules(doc_title, citation_format)

    canonical_lines: list[str] = []
    stripped: list[StrippedSpan] = []
    page_number = 1

    for raw_line in raw.split("\n"):
        if PAGE_BREAK in raw_line:
            sub_parts = raw_line.split(PAGE_BREAK)
            for idx, sub in enumerate(sub_parts):
                _process_line(sub, page_number, canonical_lines, stripped, rules)
                if idx < len(sub_parts) - 1:
                    page_number += 1
            continue
        _process_line(raw_line, page_number, canonical_lines, stripped, rules)

    # Strip sequential margin line-number prefixes (FDA draft-guidance furniture).
    canonical_lines, margin_idx = _strip_margin_line_numbers(canonical_lines)
    if margin_idx:
        stripped.append(StrippedSpan(
            rule_id="MARGIN_LINE_NUMBER",
            page_number=0,
            text=f"stripped sequential margin line-number prefixes from {len(margin_idx)} lines",
        ))
        ctx.log(f"    boilerplate: stripped margin line-numbers from {len(margin_idx)} lines")

    # Collapse repeated blank lines
    collapsed: list[str] = []
    for line in canonical_lines:
        if line.strip() == "":
            if collapsed and collapsed[-1] == "":
                continue
            collapsed.append("")
        else:
            collapsed.append(line)
    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()

    canonical_text = "\n".join(collapsed) + "\n"
    sha = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
    byte_count = len(canonical_text.encode("utf-8"))

    canonical = CanonicalSource(
        text=canonical_text,
        sha256=sha,
        byte_count=byte_count,
        stripped=stripped,
    )
    ctx.meta.canonical_sha256 = sha

    out_dir = ctx.paths.source_dir
    (out_dir / "canonical.txt").write_text(canonical_text, encoding="utf-8")
    ctx.write_json(out_dir / "canonical.json", canonical)
    ctx.log(f"    boilerplate: stripped {len(stripped)} lines, canonical {byte_count} bytes, sha={sha[:12]}")


def _process_line(line: str, page_number: int,
                  canonical_lines: list[str], stripped: list[StrippedSpan],
                  rules: list[tuple[str, re.Pattern]]) -> None:
    s_stripped = line.strip()
    matched = False
    for rule_id, pat in rules:
        if pat.match(s_stripped):
            stripped.append(StrippedSpan(rule_id=rule_id, page_number=page_number, text=line.rstrip()))
            matched = True
            break
    if not matched:
        canonical_lines.append(s_stripped)
