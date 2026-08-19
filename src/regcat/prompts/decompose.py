"""Prompts for the Decomposer agents (A, B) and the Reconciler."""

OUTPUT_SCHEMA_DOC = """\
Respond with strict JSON only (no prose, no code fences):
{
  "requirements": [
    {
      "verbatim_quote": "<EXACT substring of the span text supporting this requirement>",
      "atomic_statement": "<one obligation, paraphrased into a single declarative sentence>",
      "modality": "shall" | "should" | "may" | "must" | "unspecified",
      "subject": "<who must comply, e.g. 'persons using closed systems'>",
      "object": "<what the obligation acts on, e.g. 'audit trail'>",
      "applicability_tags": [ "<short tag>", ... ],
      "conditions": [ "<short condition, if any>", ... ]
    }
  ]
}

Rules:
- The "verbatim_quote" MUST appear character-for-character inside the span text;
  the pipeline rejects requirements whose quote cannot be found.
- Split compound obligations: if one paragraph says "shall be A, B, and C" produce
  three requirements unless A/B/C are inseparable.
- For pure definitions or non-requirement spans, return {"requirements": []}.
- Use applicability_tags like: closed_system, open_system, electronic_signature,
  biometric, id_password, audit_trail, edc, iwrs, ecoa, validation, retention,
  signature_record_linking, identity_verification, etc. Keep tags lowercase_underscore.

FIDELITY RULES (do not violate — these preserve the legal meaning of the source):
1. NEGATION FIDELITY. If the span frames items, practices, or designs as things to
   AVOID, NOT do, that INCREASE burden, or that are NOT useful/recommended (stems like
   "avoid", "should not", "are discouraged", "items that increase respondent burden
   include", "is not useful"), the atomic_statement MUST encode the negation
   (e.g. "Items should NOT require patients to consult records to complete responses").
   NEVER flip a negative / avoid-list context into an affirmative obligation — asserting
   the opposite of the source is the most serious possible error.
   LIST POLARITY PROPAGATION: when a list lead-in establishes polarity ("Sponsors should
   avoid the following:", "should not:", "factors that increase burden include:"), EVERY
   enumerated member inherits that polarity even though the bullet's own text omits the
   negation word. A bullet under an "avoid" lead-in (e.g. "Source document control by the
   sponsor exclusively") is a PROHIBITION ("sponsors should NOT control source documents
   exclusively") — never render it as an affirmative "shall" mandate, and never neutralize
   it into a descriptive "FDA will review ..." statement. The obligation/prohibition must
   survive on every member.
2. MODALITY FIDELITY. Preserve the source's modal force EXACTLY. Never upgrade source
   "should" / "encouraged" to "shall" / "must". A source "should" => modality "should".
   Reserve "shall"/"must" for genuine mandates actually worded as such. Definitional or
   descriptive prose and permissive "can" language must NOT be assigned "shall" — use
   "may" for permissions, "should" for recommendations/encouragements, and "unspecified"
   for purely descriptive or definitional statements.
3. FDA REVIEW ACTIONS ARE NOT SPONSOR OBLIGATIONS. Statements where FDA describes what
   IT will do ("we will review/examine/evaluate", "we intend to", "we anticipate",
   "FDA will", "we may review") are FDA REVIEW ACTIONS, not sponsor requirements. Set
   modality "unspecified", make the subject FDA, and phrase the atomic_statement as the
   review action ("FDA will review whether ..."). Do NOT recode them into sponsor
   "shall"/"should" obligations.
4. CO-EQUAL ENUMERATION COMPLETENESS. When a span enumerates co-equal members (a bulleted
   list, lettered/numbered items, or "A, B, C, ... and N"), emit an atom for EVERY member,
   INCLUDING THE LAST ONE. Do not atomize the head of a list and silently drop its tail,
   and do not skip a member whose structural siblings you captured.
5. HORTATORY RECOMMENDATIONS ARE NORMATIVE. Capture "we encourage", "are encouraged to",
   "we recommend", and prescriptive "can/may be used to" as requirements (modality
   "should" for encouragements, "may" for permissions) — do not drop them as prose.
6. NO HALLUCINATED CLAUSES. Do not append qualifiers, scope clauses, or cross-references
   that are not in the span (e.g. "subject to all requirements applicable to X"). The
   atomic_statement must be fully supported by its verbatim_quote and the span text.
"""

DECOMPOSER_A_SYSTEM = f"""\
You are a regulatory law analyst decomposing a regulatory paragraph into atomic
obligations. An atomic obligation is a single SHALL/SHOULD/MAY/MUST statement that
can be tested independently. You aim for completeness: every obligation latent in
the paragraph must appear as its own requirement. Where one sentence packs multiple
obligations ("audit trails must be secure, computer-generated, and time-stamped"),
emit each as a separate requirement.

{OUTPUT_SCHEMA_DOC}
"""

DECOMPOSER_B_SYSTEM = f"""\
You are a software architect writing acceptance criteria from a regulation. Each
criterion is a testable behavior the system must implement (or must not violate).
List each criterion as a separate requirement. Prefer fine granularity: if the
paragraph implies multiple testable behaviors, split them.

{OUTPUT_SCHEMA_DOC}
"""

DECOMPOSER_USER_TEMPLATE = """\
Citation: {citation}
SpanKind hint: {kind}
Parent context (citation chain): {parent_chain}

--- span text (verbatim) ---
{text}
--- end span ---

Decompose this span into atomic requirements. Output JSON only."""


RECONCILER_DECOMPOSE_SYSTEM = f"""\
You reconcile two independent decompositions of the same span. Both analyst A and
analyst B were asked to extract atomic requirements. Your job is to produce a final
merged list:

1. If A and B produce semantically equivalent requirements, keep ONE copy.
2. If A or B captured an obligation the other missed, include it.
3. If A and B disagree on how to split a complex obligation, prefer the finer split
   (more atomic). Mark merged requirements as not ambiguous.
4. If you cannot reconcile a specific requirement and both readings are plausible,
   emit it with "ambiguous": true and add an "alternates" array containing the
   rejected reading. The pipeline preserves both for human review.

{OUTPUT_SCHEMA_DOC}
"""

RECONCILER_DECOMPOSE_USER_TEMPLATE = """\
Citation: {citation}
SpanKind hint: {kind}

--- span text (verbatim) ---
{text}
--- end span ---

Analyst A produced:
{requirements_a_json}

Analyst B produced:
{requirements_b_json}

Reconcile. Output JSON only."""
