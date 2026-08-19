"""Document registry for the multi-doc regcat catalog.

Every regulatory document the system processes lives at:

    docs/<jurisdiction>/<short_id>/
        meta.json         <- DocMeta (this module)
        source.pdf
        source/{canonical.txt, spans.jsonl, ...}
        catalog/{classifications, requirements, relationships}.jsonl
        audit/{coverage_report, completeness_report, ...}
        fixtures/         (optional, for mock-mode replay)

A global registry at `docs/registry.json` indexes all known docs by doc_id
(`<jurisdiction>/<short_id>`) and is regenerated from the individual meta.json
files. Treat per-doc meta.json files as source-of-truth; the registry is a
denormalized view.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# --- taxonomy ---------------------------------------------------------------

class Jurisdiction(str, Enum):
    """Top-level regulatory authorities. Extend as we onboard more docs."""
    FDA   = "fda"      # US Food and Drug Administration
    EMA   = "ema"      # European Medicines Agency
    ICH   = "ich"      # International Council for Harmonisation
    ISO   = "iso"      # International Organization for Standardization
    IEC   = "iec"      # International Electrotechnical Commission
    NMPA  = "nmpa"     # China NMPA
    PMDA  = "pmda"     # Japan PMDA
    MHRA  = "mhra"     # UK MHRA
    HC    = "hc"       # Health Canada
    TGA   = "tga"      # Australia TGA
    ANVISA = "anvisa"  # Brazil ANVISA
    OTHER = "other"


class DocumentType(str, Enum):
    REGULATION = "regulation"     # e.g. 21 CFR Part 11
    GUIDANCE   = "guidance"       # e.g. FDA guidance docs, EMA Q&A
    STANDARD   = "standard"       # e.g. ISO 14155
    DIRECTIVE  = "directive"      # e.g. EU directives
    NOTICE     = "notice"         # public notices, FR notices


class CitationFormat(str, Enum):
    """Which segmenter to use for this doc."""
    CFR  = "cfr"     # CFR-style citation tree (§ X.Y(a)(1)(i))
    ICH  = "ich"     # ICH section numbering
    ISO  = "iso"     # ISO clause numbering
    EU   = "eu"      # EU article numbering
    GENERIC = "generic"   # fallback


class Subsystem(str, Enum):
    """CTMS subsystems a document applies to. Fixed taxonomy.

    Extend this enum as new subsystems become relevant.
    """
    EDC        = "edc"             # Electronic Data Capture
    IWRS       = "iwrs"            # Interactive Web Response (randomization, drug supply)
    ECOA       = "ecoa"            # electronic Clinical Outcome Assessment
    ETMF       = "etmf"            # electronic Trial Master File
    SAFETY     = "safety"          # safety / pharmacovigilance systems
    CDM        = "cdm"             # clinical data management broadly
    CTMS_GENERAL = "ctms_general"  # cross-cutting / general CTMS


class DocStatus(str, Enum):
    REGISTERED  = "registered"   # ingested, not yet processed
    IN_PROGRESS = "in_progress"  # pipeline running or partially complete
    COMPLETED   = "completed"    # pipeline ran to completion, audit passed
    NEEDS_REVIEW = "needs_review"  # completed but flagged for manual attention
    SUPERSEDED  = "superseded"   # an older version, kept for history
    ARCHIVED    = "archived"     # excluded from active processing


# --- schema -----------------------------------------------------------------

class DocStats(BaseModel):
    spans: int = 0
    requirements: int = 0
    relationships: int = 0
    coverage_pct: float = 0.0
    ambiguous_classifications: int = 0
    ambiguous_requirements: int = 0
    ambiguous_relationships: int = 0
    cycles_flagged: int = 0


class DocMeta(BaseModel):
    """Per-doc metadata; lives at docs/<doc_id>/meta.json."""
    doc_id: str                          # canonical "<jurisdiction>/<short_id>"
    jurisdiction: Jurisdiction
    short_id: str                        # slug-style, unique within jurisdiction
    title: str
    document_type: DocumentType = DocumentType.REGULATION
    citation_format: CitationFormat = CitationFormat.GENERIC
    version: Optional[str] = None        # human-readable version (e.g. "2026-04-02 eCFR")
    effective_date: Optional[str] = None # ISO date when the reg became effective
    source_url: Optional[str] = None
    language: str = "en"
    applies_to: list[Subsystem] = Field(default_factory=list)
    status: DocStatus = DocStatus.REGISTERED
    pdf_path: str = "source.pdf"         # relative to the doc directory
    pdf_sha256: Optional[str] = None
    canonical_sha256: Optional[str] = None
    ingested_at: Optional[str] = None
    completed_at: Optional[str] = None
    stats: DocStats = Field(default_factory=DocStats)
    depends_on: list[str] = Field(default_factory=list)   # doc_ids this doc references
    supersedes: Optional[str] = None     # previous-version doc_id
    notes: str = ""


# --- helpers ----------------------------------------------------------------

_SLUG_RX = re.compile(r"[^a-z0-9-]+")
_SHORT_ID_RX = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")


def slugify(s: str) -> str:
    """Produce a URL-safe lowercase-with-hyphens slug from arbitrary text."""
    s = s.lower().strip()
    s = re.sub(r"\s+", "-", s)
    s = _SLUG_RX.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def doc_id_for(jurisdiction: Jurisdiction, short_id: str) -> str:
    return f"{jurisdiction.value}/{short_id}"


def parse_doc_id(doc_id: str) -> tuple[Jurisdiction, str]:
    parts = doc_id.strip().split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"doc_id must be '<jurisdiction>/<short_id>', got: {doc_id!r}")
    jurisdiction = Jurisdiction(parts[0])
    short_id = parts[1]
    if not _SHORT_ID_RX.fullmatch(short_id):
        raise ValueError(f"doc_id short_id must be a slug, got: {short_id!r}")
    return jurisdiction, short_id


def doc_dir(root: Path, doc_id: str) -> Path:
    juris, short = parse_doc_id(doc_id)
    return root / "docs" / juris.value / short


def meta_path(root: Path, doc_id: str) -> Path:
    return doc_dir(root, doc_id) / "meta.json"


def load_meta(root: Path, doc_id: str) -> DocMeta:
    p = meta_path(root, doc_id)
    if not p.exists():
        raise FileNotFoundError(f"no meta.json at {p}")
    return DocMeta.model_validate_json(p.read_text(encoding="utf-8"))


def save_meta(root: Path, meta: DocMeta) -> None:
    p = meta_path(root, meta.doc_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(meta.model_dump_json(indent=2), encoding="utf-8")


def all_docs(root: Path) -> list[DocMeta]:
    """Scan docs/<jurisdiction>/<short>/meta.json files and return each as DocMeta."""
    docs_root = root / "docs"
    if not docs_root.exists():
        return []
    out: list[DocMeta] = []
    for juris_dir in sorted(docs_root.iterdir()):
        if not juris_dir.is_dir() or juris_dir.name in {"review_site"}:
            continue
        for d in sorted(juris_dir.iterdir()):
            if not d.is_dir():
                continue
            m = d / "meta.json"
            if m.exists():
                try:
                    out.append(DocMeta.model_validate_json(m.read_text(encoding="utf-8")))
                except Exception as e:
                    # Don't let one bad meta.json crash listing
                    print(f"warning: failed to load {m}: {e}")
    return out


def write_registry(root: Path) -> Path:
    """Rebuild docs/registry.json from per-doc meta.json files."""
    docs = all_docs(root)
    payload = {
        "generated_at": date.today().isoformat(),
        "doc_count": len(docs),
        "docs": [d.model_dump(mode="json") for d in docs],
    }
    out = root / "docs" / "registry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_registry_md(root: Path) -> Path:
    """Human-readable index at docs/registry.md."""
    docs = all_docs(root)
    lines: list[str] = []
    lines.append("# Document registry")
    lines.append("")
    lines.append(f"Total documents: **{len(docs)}**")
    lines.append("")
    lines.append("| doc_id | title | jurisdiction | type | status | reqs | coverage |")
    lines.append("|---|---|---|---|---|---:|---:|")
    for d in sorted(docs, key=lambda x: x.doc_id):
        lines.append(
            f"| `{d.doc_id}` | {d.title} | {d.jurisdiction.value} | "
            f"{d.document_type.value} | {d.status.value} | {d.stats.requirements} | "
            f"{d.stats.coverage_pct:.2f}% |"
        )
    out = root / "docs" / "registry.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
