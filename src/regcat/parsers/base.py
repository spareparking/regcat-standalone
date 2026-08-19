"""Parser base class for citation-aware segmenters.

A Segmenter takes canonical text and emits an ordered list of Span objects,
each with a stable byte_start / byte_end into the canonical text.

The contract:
  - Every byte of canonical text falls inside exactly one Span (no gaps, no overlaps).
  - Spans form a tree via parent_span_id.
  - Citations are structured (not free-text) and roundtrip through Citation.raw.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import Span


class SegmenterBase(ABC):
    name: str = "base"

    @abstractmethod
    def segment(self, canonical_text: str) -> list[Span]:
        ...
