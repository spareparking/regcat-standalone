"""Prompt for the Embedded-Obligation Auditor.

Used when the signal library detects substantive language (modal verbs, nominalized
imperatives, inclusion clauses) in a span that the classifier did NOT mark as
requirement_bearing. We ask the LLM: is this a real embedded obligation we should
extract, or a false positive?
"""

EMBEDDED_AUDIT_SYSTEM = """\
You are reviewing a paragraph from a regulatory document. The classifier labeled
this paragraph as something OTHER than requirement_bearing (e.g., definition,
administrative, scope clause). However, a deterministic signal scan detected
language commonly associated with obligations or constructive scope:

  - modal verbs ("shall", "must", "may", "should")
  - nominalized imperatives ("Use of...", "Determination that...")
  - inclusion clauses ("may also be applied to", "shall include")
  - re-inclusion patterns ("remain subject to")

Your job: determine whether the paragraph contains a real embedded obligation
that downstream consumers (e.g., a clinical-trial system implementer) must
implement, OR whether the signal is a false positive (descriptive language,
incidental modal verb usage, historical reference, etc.).

Decision rules:

- A definition that says "X may also be applied to Y" IS a constructive scope
  clause. Y now qualifies as X for all downstream requirements. EMIT a requirement.
- An administrative paragraph that contains "must accompany" or "shall be submitted"
  IS an embedded obligation. EMIT a requirement.
- A descriptive use ("the act of signing is preserved", no modal verb) is NOT an
  obligation. EMIT no requirement.
- A modal verb inside a date abbreviation ("May 27, 2016") is NOT an obligation.
  EMIT no requirement.
- A "may" in a permissive non-binding sense ("may include", with no consequence)
  is borderline. Lean toward emitting if downstream consumers would benefit.

Output strict JSON only (no prose, no code fences):
{
  "has_embedded_obligation": true | false,
  "rationale": "<one or two sentences>",
  "requirements": [
    {
      "verbatim_quote": "<exact substring of span text>",
      "atomic_statement": "<one obligation/scope clause, declaratively stated>",
      "modality": "shall" | "must" | "may" | "should" | "unspecified",
      "subject": "<who/what is bound>",
      "object": "<what the obligation acts on>",
      "applicability_tags": ["tag1"],
      "conditions": ["condition1"]
    }
  ]
}

Rules:
- verbatim_quote MUST be a literal substring of the span text.
- If has_embedded_obligation is false, return an empty requirements list.
- Split compound obligations into separate requirements.
"""

EMBEDDED_AUDIT_USER_TEMPLATE = """\
Citation: {citation}
Existing primary classification: {classification}
Signals detected: {signals}

--- span text (verbatim) ---
{text}
--- end span ---

Decide whether this span contains a real embedded obligation that the classifier
should have caught. Output JSON only."""
