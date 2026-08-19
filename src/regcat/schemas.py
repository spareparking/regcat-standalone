"""Pydantic schemas for every stage's input and output.

Conventions:
- Byte offsets are into the canonical source text (Stage 2 output), UTF-8 encoded.
- `verbatim_quote` fields must appear EXACTLY inside their referenced span's text;
  the Coverage Auditor (Stage 6) asserts this.
- `span_id` and `req_id` are stable identifiers used throughout the pipeline.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Stage 1: Ingest
# ---------------------------------------------------------------------------

class PageText(BaseModel):
    page_number: int
    text: str
    char_count: int


class IngestArtifact(BaseModel):
    pdf_path: str
    pdf_sha256: str
    page_count: int
    pages: list[PageText]
    raw_text: str  # all pages concatenated with form-feed (\f) separators


# ---------------------------------------------------------------------------
# Stage 2: Boilerplate strip
# ---------------------------------------------------------------------------

class StrippedSpan(BaseModel):
    rule_id: str           # which regex rule matched
    page_number: int
    text: str              # what was stripped, verbatim


class CanonicalSource(BaseModel):
    text: str                          # post-strip canonical text (UTF-8)
    sha256: str
    byte_count: int
    stripped: list[StrippedSpan]


# ---------------------------------------------------------------------------
# Stage 3: Segment
# ---------------------------------------------------------------------------

class Citation(BaseModel):
    """A structured CFR-like citation."""
    title: Optional[str] = None        # e.g., "21"
    part: Optional[str] = None         # e.g., "11"
    section: Optional[str] = None      # e.g., "11.10"
    paragraphs: list[str] = Field(default_factory=list)  # e.g., ["a"], ["k", "2"], ["a", "1", "i"]
    subpart: Optional[str] = None      # e.g., "A"
    raw: str = ""                      # canonical rendering, e.g. "§ 11.10(k)(2)"


class SpanKind(str, Enum):
    DOCUMENT_TITLE = "document_title"      # "Title 21 — Food and Drugs" etc.
    TOC_ENTRY = "toc_entry"                # table of contents lines
    PART_HEADER = "part_header"            # "PART 11—ELECTRONIC RECORDS..."
    AUTHORITY = "authority"                # "Authority: 21 U.S.C. ..."
    SOURCE_NOTE = "source_note"            # "Source: 62 FR ..." or bracketed amendment list
    SUBPART_HEADER = "subpart_header"      # "Subpart A—General Provisions"
    SECTION_HEADER = "section_header"      # "§ 11.1 Scope."
    SECTION_CHAPEAU = "section_chapeau"    # lead-in paragraph before lettered list
    PARAGRAPH = "paragraph"                # numbered/lettered paragraphs (a), (1), (i)
    DISCLAIMER = "disclaimer"              # "This content is from the eCFR..."
    UNKNOWN = "unknown"


class Span(BaseModel):
    span_id: str                       # e.g. "S0042"
    kind: SpanKind
    citation: Citation
    parent_span_id: Optional[str] = None
    byte_start: int                    # offset into canonical source
    byte_end: int                      # exclusive
    text: str                          # verbatim text of this span
    page_number: int


# ---------------------------------------------------------------------------
# Stage 4: Classify
# ---------------------------------------------------------------------------

class ClassificationLabel(str, Enum):
    REQUIREMENT_BEARING = "requirement_bearing"
    DEFINITION = "definition"
    SCOPE_EXCLUSION = "scope_exclusion"
    SCOPE_INCLUSION = "scope_inclusion"
    ADMINISTRATIVE = "administrative"
    CROSS_REFERENCE = "cross_reference"
    STRUCTURAL = "structural"           # headers, TOC, part/subpart titles
    SOURCE_NOTE = "source_note"
    DISCLAIMER = "disclaimer"


class ClassifierOutput(BaseModel):
    """Output for a single span from one classifier agent (A or B)."""
    label: ClassificationLabel
    reason: str                         # one-sentence rationale
    confidence: Literal["low", "medium", "high"]


class ReconciledClassification(BaseModel):
    span_id: str
    label_a: ClassificationLabel
    label_b: ClassificationLabel
    reason_a: str
    reason_b: str
    final_label: ClassificationLabel              # primary label
    final_embedded: list[ClassificationLabel] = Field(default_factory=list)
    # Additional labels that also apply to this span (e.g., a definition that ALSO
    # contains a constructive scope clause: primary="definition", embedded=["requirement_bearing"]).
    # The decomposer runs on any span where requirement_bearing appears in primary or embedded.
    embedded_a: list[ClassificationLabel] = Field(default_factory=list)
    embedded_b: list[ClassificationLabel] = Field(default_factory=list)
    ambiguous: bool
    reconciler_note: str = ""
    # Decomposer/classifier disagreement preservation (Workstream C):
    # When the decomposers return ZERO requirements for a span whose labels include
    # requirement_bearing, the labels are NOT silently changed. Instead the record
    # is flagged `downgrade_pending` and the would-have-been downgrade is preserved
    # in `downgrade_proposal`:
    #   {"kind": "primary"|"embedded", "proposed_label": ..., "proposed_embedded":
    #    [...], "reason": ..., "source": ..., ["resolution": {...}]}
    # Finalization blocks while any record has downgrade_pending=True; the
    # downgrade adjudicator resolves it via `confirm_downgrade` or `extract`.
    # Absent fields (all catalogs produced before this change) mean no pending
    # downgrade — old catalogs parse and finalize unchanged.
    downgrade_pending: bool = False
    downgrade_proposal: Optional[dict] = None


# ---------------------------------------------------------------------------
# Stage 5: Decompose
# ---------------------------------------------------------------------------

class Modality(str, Enum):
    SHALL = "shall"        # mandatory
    SHOULD = "should"      # recommended
    MAY = "may"            # permissive / optional
    MUST = "must"          # mandatory (rare in CFR; treat as SHALL)
    UNSPECIFIED = "unspecified"


class AtomicRequirement(BaseModel):
    req_id: str                            # e.g. "R00031"
    source_span_id: str
    citation_raw: str                      # the citation of the source span (denormalized for readability)
    verbatim_quote: str                    # exact substring of the source span supporting this requirement
    atomic_statement: str                  # paraphrased into a single obligation
    modality: Modality
    subject: str                           # who must comply (e.g., "persons using closed systems")
    object: str                            # what is obligated (e.g., "audit trail")
    applicability_tags: list[str] = Field(default_factory=list)
    # e.g. ["closed_system", "edc", "audit_trail", "id_password_signatures"]
    conditions: list[str] = Field(default_factory=list)
    # e.g. ["only when records contain electronic signatures"]
    ambiguous: bool = False
    alternates: list[dict] = Field(default_factory=list)
    # when ambiguous=True, holds the rejected-but-preserved alternate readings


class DecomposerOutput(BaseModel):
    """Output for a single span from one decomposer agent (A or B)."""
    requirements: list[AtomicRequirement]


# ---------------------------------------------------------------------------
# Stage 6: Coverage audit
# ---------------------------------------------------------------------------

class CoverageReport(BaseModel):
    canonical_source_sha256: str
    total_bytes: int
    covered_bytes: int
    coverage_pct: float
    span_count: int
    spans_by_classification: dict[str, int]
    requirements_extracted: int
    verbatim_quote_failures: list[str] = Field(default_factory=list)
    unclassified_spans: list[str] = Field(default_factory=list)
    unrequirementized_spans: list[str] = Field(default_factory=list)
    # Requirement-bearing spans with zero requirements that are FLAGGED for
    # downgrade adjudication. These are attributed (not a coverage failure) but
    # reported distinctly; finalize blocks until they are adjudicated.
    downgrade_pending_spans: list[str] = Field(default_factory=list)
    reconciler_unresolved: list[str] = Field(default_factory=list)
    overlap_failures: list[str] = Field(default_factory=list)
    gap_failures: list[dict] = Field(default_factory=list)
    passed: bool


# ---------------------------------------------------------------------------
# Stage 7: Relationships
# ---------------------------------------------------------------------------

class RelationshipType(str, Enum):
    REFINES = "refines"                 # child requirement narrows a parent obligation
    REFERENCES = "references"           # one requirement points to another
    EXCEPTION_TO = "exception_to"       # carves out an exception
    CONDITIONAL_ON = "conditional_on"   # only applies if another is met
    DEFINED_BY = "defined_by"           # uses a term defined elsewhere
    COMPOSED_OF = "composed_of"         # parent obligation aggregates child obligations


class Relationship(BaseModel):
    rel_id: str
    source_req_id: str
    target_req_id: str
    type: RelationshipType
    evidence: str = ""                  # short rationale or quoted phrase
    ambiguous: bool = False


# ---------------------------------------------------------------------------
# Pipeline run metadata
# ---------------------------------------------------------------------------

class RunMetadata(BaseModel):
    started_at: str
    completed_at: Optional[str] = None
    pdf_path: str
    pdf_sha256: str
    canonical_sha256: Optional[str] = None
    mode: Literal["live", "claude-code", "openai", "mock"]
    model: Optional[str] = None
    stages_completed: list[str] = Field(default_factory=list)
    error: Optional[str] = None
