"""Stage 3: Segment canonical text into a citation-aware span tree.

The segmenter is chosen by the document's citation_format (set at ingest):
  - cfr  -> CFRSegmenter   (§ X.Y paragraph tree)
  - ich  -> ICHSegmenter   (roman parts + decimal subsections)
  - else -> CFRSegmenter   (generic fallback)

The CFR title/part are not hard-coded: they are derived from the doc's
``short_id`` (e.g. ``45-cfr-part-160`` -> title 45, part 160; ``21-cfr-part-11``
-> title 21, part 11). The part is then refined per-section inside the
segmenter (each section number carries its own part prefix). Without this,
every span inherited the legacy 21/11 default, collapsing HIPAA (45 CFR
160/164) citations onto the wrong title/part.

Output:
  data/source/spans.jsonl  — one Span per line (Pydantic JSON)
"""
from __future__ import annotations

import json
import re

from ..parsers.base import SegmenterBase
from ..parsers.cfr import CFRSegmenter
from ..parsers.generic import GenericSegmenter
from ..parsers.ich import ICHSegmenter


# "45-cfr-part-160", "21-cfr-part-11", "45-cfr-part-164" -> (title, part)
_CFR_SHORT_ID = re.compile(r"^(\d+)-cfr-part-(\w+)$", re.IGNORECASE)


def _cfr_title_part(meta: dict) -> tuple[str, str]:
    """Derive (title, part) from the doc meta's short_id, defaulting to 21/11."""
    short_id = (meta or {}).get("short_id") or ""
    m = _CFR_SHORT_ID.match(short_id.strip())
    if m:
        return m.group(1), m.group(2)
    return "21", "11"


def _segmenter_for(ctx) -> SegmenterBase:
    # citation_format lives in the registry meta.json (DocMeta), not in the
    # run-scoped ctx.meta (RunMetadata), so read it from the file like the
    # boilerplate stage does.
    meta: dict = {}
    if ctx.paths.meta_path.exists():
        try:
            meta = json.loads(ctx.paths.meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    fmt = meta.get("citation_format")
    if fmt == "ich":
        return ICHSegmenter()
    if fmt == "generic":
        return GenericSegmenter()
    title, part = _cfr_title_part(meta)
    return CFRSegmenter(default_title=title, default_part=part)


def run(ctx) -> None:
    canonical_text = (ctx.paths.source_dir / "canonical.txt").read_text(encoding="utf-8")
    segmenter = _segmenter_for(ctx)
    ctx.log(f"    segment: using {segmenter.name} segmenter")
    spans = segmenter.segment(canonical_text)
    ctx.write_jsonl(ctx.paths.source_dir / "spans.jsonl", spans)

    # Quick coverage sanity check (the full audit happens in Stage 6, but it's useful to see now)
    canonical_bytes = len(canonical_text.encode("utf-8"))
    covered = 0
    prev_end = 0
    overlaps = 0
    gaps = 0
    for s in spans:
        if s.byte_start < prev_end:
            overlaps += 1
        if s.byte_start > prev_end:
            gaps += s.byte_start - prev_end
        covered += s.byte_end - s.byte_start
        prev_end = max(prev_end, s.byte_end)
    if prev_end < canonical_bytes:
        gaps += canonical_bytes - prev_end

    ctx.log(f"    segment: {len(spans)} spans, covered {covered}/{canonical_bytes} bytes, "
            f"gaps={gaps}, overlaps={overlaps}")
