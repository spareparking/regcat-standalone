"""Stage 1: Ingest PDF -> canonical-ready text + per-page text + sha256.

Deterministic. Uses PyMuPDF (fitz) for layout-aware text extraction.

Output:
  data/source/raw_text.txt       all pages concatenated, separated by \\f
  data/source/raw_ingest.json    structured (per-page text, char counts, sha)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz  # PyMuPDF

from ..schemas import IngestArtifact, PageText


def run(ctx) -> None:
    pdf_path = ctx.paths.pdf
    pdf_bytes = pdf_path.read_bytes()
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    pages: list[PageText] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            # `sort=True` orders by reading order; this is critical for the CFR layout
            # where lettered paragraphs are indented.
            text = page.get_text("text", sort=True)
            pages.append(PageText(page_number=i, text=text, char_count=len(text)))

    raw_text = "\f".join(p.text for p in pages)
    artifact = IngestArtifact(
        pdf_path=str(pdf_path),
        pdf_sha256=sha,
        page_count=len(pages),
        pages=pages,
        raw_text=raw_text,
    )
    ctx.meta.pdf_sha256 = sha

    out_dir = ctx.paths.source_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw_text.txt").write_text(raw_text, encoding="utf-8")
    ctx.write_json(out_dir / "raw_ingest.json", artifact)
    ctx.log(f"    ingest: {len(pages)} pages, {sum(p.char_count for p in pages)} chars, sha={sha[:12]}")
