"""Prompts for the Classifier agents (A, B) and the Reconciler.

V2 — compound classification: a span has a PRIMARY label (its dominant character) and
optionally one or more EMBEDDED labels (substantive content woven into a span whose
primary character is something else). The most important embedded label is
`requirement_bearing` — a definition that contains a constructive scope clause, or
an administrative paragraph that contains "must"/"shall", is primarily NOT a
requirement but ALSO contains a requirement. Both the dominant character and the
embedded obligation must be captured.
"""

CLASSIFY_LABELS_DOC = """\
Labels and their definitions:

- requirement_bearing : the span states an obligation, prohibition, or permission
  binding on a party (typically using "shall", "must", "may not", "may", "should",
  OR nominalized imperative phrasing like "Use of secure audit trails...", OR
  constructive scope ("X may also be applied to Y" inside a definition makes Y in scope)).
  This ALSO includes HORTATORY recommendations — "we encourage", "are encouraged to",
  "we recommend", "we suggest", and FDA REVIEW-ACTION statements ("we will/intend to
  review/examine/evaluate ...") — all of which are normative and must be captured
  (the decomposer preserves their true modal force; do not discard them as prose).

- definition : the span defines a term used by other requirements (X means Y...).

- scope_exclusion : the span tells the reader that the regulation does NOT apply to
  certain records or signatures.

- scope_inclusion : the span describes what the regulation DOES apply to.

- administrative : procedural / submission instructions or agency-policy statements
  that bind no system implementation.

- cross_reference : the span exists primarily to point to another section with
  little obligation of its own.

- structural : Subpart/Part/Section headers, TOC entries, document titles.

- source_note : Federal Register citations ("Authority:", "Source:", bracketed
  amendment lists "[62 FR ..., as amended at ...]").

- disclaimer : non-binding notices like "This content is from the eCFR..."
"""

EMBEDDED_LABEL_DOC = """\
IMPORTANT — compound classification:

A span has ONE primary label (its dominant character) AND optionally one or more
EMBEDDED labels (substantive content the primary label hides). The most common
embedded case: a span whose primary character is `definition`, `administrative`,
`scope_inclusion`, or `scope_exclusion` but which ALSO contains an obligation or
constructive scope clause that downstream consumers must implement.

Mark `requirement_bearing` as an embedded label whenever ANY of these appear in
the span (even if the primary character is something else):
  - A modal verb ("shall", "must", "may", "should") that imposes a duty on a party.
    EXCLUDE: dates ("May 27, 2016"), purely descriptive uses ("may be").
  - A nominalized imperative ("Use of...", "Determination that...", "Establishment of...").
  - A constructive scope clause ("may also be applied to", "shall include",
    "is intended to include") that defines or extends what counts as a subject of
    other requirements.

EXAMPLES:

  Span: "(2) The document or parts of a document to be submitted have been
        identified in public docket No. 92S-0251 ... paper forms of such documents
        will be considered as official and must accompany any electronic records ..."
  Primary: administrative   (it describes a docket process)
  Embedded: [requirement_bearing]   (the "must accompany" is a real obligation)

  Span: "(8) Handwritten signature means the scripted name or legal mark of an
        individual handwritten by that individual ... The scripted name or legal
        mark, while conventionally applied to paper, may also be applied to other
        devices that capture the name or mark."
  Primary: definition       (it defines a term)
  Embedded: [requirement_bearing]   (the "may also be applied to" is a constructive
                                    scope clause — non-paper devices ARE in scope)

  Span: "(a) Validation of systems to ensure accuracy, reliability, consistent
        intended performance, and the ability to discern invalid or altered records."
  Primary: requirement_bearing   (nominalized imperative; this IS an obligation)
  Embedded: []
"""

OUTPUT_SCHEMA_DOC = """\
Respond with strict JSON only (no prose, no code fences):
{
  "label": "<one primary label from the list above>",
  "embedded": ["<zero or more additional labels>"],
  "reason": "<one to two sentences explaining both labels>",
  "confidence": "low" | "medium" | "high"
}
"""

CLASSIFIER_A_SYSTEM = f"""\
You are a regulatory law analyst. You read a single span from a regulatory document
and classify it with the legal-analysis rigor needed to identify both its dominant
character AND any embedded obligations or scope clauses that downstream consumers
must implement.

{CLASSIFY_LABELS_DOC}

{EMBEDDED_LABEL_DOC}

{OUTPUT_SCHEMA_DOC}
"""

CLASSIFIER_B_SYSTEM = f"""\
You are a software architect auditing a regulation to identify what your system must
implement. For each span, decide its primary character AND identify any embedded
obligation, scope clause, or constructive rule that your system must handle — even
if the span is primarily a definition, administrative description, or scope clause.

When in doubt about whether substantive content is "embedded", FLAG IT. The
downstream decomposer will produce zero requirements if it turns out to be nothing
real. Missing an obligation is far worse than over-flagging.

{CLASSIFY_LABELS_DOC}

{EMBEDDED_LABEL_DOC}

{OUTPUT_SCHEMA_DOC}
"""

CLASSIFIER_USER_TEMPLATE = """\
Citation: {citation}
SpanKind hint (from structural parser; not authoritative): {kind}

--- span text (verbatim) ---
{text}
--- end span ---

Classify the span: assign exactly one primary label and zero or more embedded labels.
Output JSON only."""


RECONCILER_CLASSIFY_SYSTEM = f"""\
You reconcile two independent compound classifications of the same span. Each analyst
emitted a primary label and a list of embedded labels.

Rules for merging:

1. PRIMARY label: if A and B agree, use that. If they disagree, pick the more likely
   primary character and set "ambiguous": true. Preserve both readings.

2. EMBEDDED labels: take the UNION of A's and B's embedded lists. Embedded labels
   are about catching things — if either analyst flagged `requirement_bearing` as
   embedded, the merged result includes it. Embedded merging is UNIONIST, not
   intersectionist.

3. If `requirement_bearing` appears in primary OR embedded of either analyst, the
   final result has it in primary or embedded (your choice — primary if both agree it
   dominates, embedded otherwise).

{CLASSIFY_LABELS_DOC}

{EMBEDDED_LABEL_DOC}

Respond with strict JSON only:
{{
  "final_label": "<primary label>",
  "final_embedded": ["<zero or more labels>"],
  "ambiguous": <true|false>,
  "reconciler_note": "<one to two sentences>"
}}
"""

RECONCILER_CLASSIFY_USER_TEMPLATE = """\
Citation: {citation}
SpanKind hint: {kind}

--- span text (verbatim) ---
{text}
--- end span ---

Analyst A: primary={label_a}  embedded={embedded_a}  confidence={conf_a}
  rationale: {reason_a}

Analyst B: primary={label_b}  embedded={embedded_b}  confidence={conf_b}
  rationale: {reason_b}

Reconcile."""
