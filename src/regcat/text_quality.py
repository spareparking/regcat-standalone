"""Shared text-quality heuristics for the extraction pipeline.

`is_degenerate_span` identifies PDF figure/table extraction artifacts — text
flung across a 2-D layout that flattens into high-whitespace "word salad". Such
spans carry no atomic requirements and, when sent to an LLM, can trip the
backend's content filter (observed on the PRO guidance conceptual-framework
figures and Table 2, span S0110). EVERY pipeline stage that sends span text to
an LLM (classify, embedded_audit, ...) must guard with this so the same garbled
span can't halt the run at a later stage. The substantive content of such spans
is instead recovered via the figure-vision pass (image-based extraction).
"""
from __future__ import annotations

import re

# Minimum size (chars) before a span is even considered — small spans are cheap
# and safe to send to the LLM normally.
DEGENERATE_MIN_CHARS = 400
# Whitespace fraction above which a large span is treated as a layout artifact.
# Real prose runs ~0.15-0.20; figure/table "word salad" runs >0.85.
DEGENERATE_WS_RATIO = 0.6
# A long run of spaces is the signature of text flattened from a 2-D figure.
_RX_LONG_SPACE_RUN = re.compile(r" {20,}")


def is_degenerate_span(text: str) -> bool:
    """True for figure/table extraction artifacts. Both conditions must hold,
    keeping the guard well clear of real prose."""
    n = len(text)
    if n < DEGENERATE_MIN_CHARS:
        return False
    ws = sum(1 for c in text if c.isspace())
    if ws / n < DEGENERATE_WS_RATIO:
        return False
    return bool(_RX_LONG_SPACE_RUN.search(text))
