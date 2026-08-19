# Side-by-side review — fda/21-cfr-part-11

For each requirement:

1. **VERBATIM_QUOTE** — exact source substring. Confirm it's in the paragraph below.
2. **ATOMIC_STATEMENT** — LLM paraphrase. Confirm fidelity.
3. **SOURCE PARAGRAPH** — full span text, for context.

Total requirements: **153** over **58** spans.

---

## § 11.1(b) [scope_inclusion  (+ embedded: requirement_bearing, scope_exclusion)] — 8 requirements

**Source paragraph (verbatim):**

> (b)  This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations. This part also applies to
> electronic records submitted to the agency under requirements of the Federal Food, Drug, and Cosmetic
> Act and the Public Health Service Act, even if such records are not specifically identified in agency
> regulations. However, this part does not apply to paper records that are, or have been, transmitted by
> electronic means.

### R00001  [unspecified]

**VERBATIM_QUOTE:**

> This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records that are created under any records requirements set forth in agency regulations.

`subject=persons subject to agency records requirements  |  object=electronic records that are created  |  conditions=record is in electronic form; subject to agency records requirements  |  tags=scope, electronic_records, creation`

### R00002  [unspecified]

**VERBATIM_QUOTE:**

> This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records that are modified under any records requirements set forth in agency regulations.

`subject=persons subject to agency records requirements  |  object=electronic records that are modified  |  conditions=record is in electronic form; subject to agency records requirements  |  tags=scope, electronic_records, modification`

### R00003  [unspecified]

**VERBATIM_QUOTE:**

> This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records that are maintained under any records requirements set forth in agency regulations.

`subject=persons subject to agency records requirements  |  object=electronic records that are maintained  |  conditions=record is in electronic form; subject to agency records requirements  |  tags=scope, electronic_records, maintenance`

### R00004  [unspecified]

**VERBATIM_QUOTE:**

> This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records that are archived under any records requirements set forth in agency regulations.

`subject=persons subject to agency records requirements  |  object=electronic records that are archived  |  conditions=record is in electronic form; subject to agency records requirements  |  tags=scope, electronic_records, archival, retention`

### R00005  [unspecified]

**VERBATIM_QUOTE:**

> This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records that are retrieved under any records requirements set forth in agency regulations.

`subject=persons subject to agency records requirements  |  object=electronic records that are retrieved  |  conditions=record is in electronic form; subject to agency records requirements  |  tags=scope, electronic_records, retrieval`

### R00006  [unspecified]

**VERBATIM_QUOTE:**

> This part applies to records in electronic form that are created, modified, maintained, archived, retrieved,
> or transmitted, under any records requirements set forth in agency regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records that are transmitted under any records requirements set forth in agency regulations.

`subject=persons subject to agency records requirements  |  object=electronic records that are transmitted  |  conditions=record is in electronic form; subject to agency records requirements  |  tags=scope, electronic_records, transmission`

### R00007  [unspecified]

**VERBATIM_QUOTE:**

> This part also applies to
> electronic records submitted to the agency under requirements of the Federal Food, Drug, and Cosmetic
> Act and the Public Health Service Act, even if such records are not specifically identified in agency
> regulations.

**ATOMIC_STATEMENT:**

> This part applies to electronic records submitted to the agency under requirements of the Federal Food, Drug, and Cosmetic Act and the Public Health Service Act, even when such records are not specifically identified in agency regulations.

`subject=persons submitting electronic records to the agency  |  object=electronic records submitted to the agency  |  conditions=record is submitted to the agency under FD&C Act or PHS Act requirements  |  tags=scope, electronic_records, submission, fdc_act, phs_act`

### R00008  [unspecified]

**VERBATIM_QUOTE:**

> this part does not apply to paper records that are, or have been, transmitted by
> electronic means.

**ATOMIC_STATEMENT:**

> This part does not apply to paper records that are or have been transmitted by electronic means.

`subject=persons handling paper records  |  object=paper records transmitted by electronic means  |  conditions=record is a paper record; transmitted by electronic means  |  tags=scope_exclusion, paper_records, transmission`

---

## § 11.1(c) [scope_inclusion  (+ embedded: requirement_bearing)] — 2 requirements

**Source paragraph (verbatim):**

> (c)  Where electronic signatures and their associated electronic records meet the requirements of this part,
> the agency will consider the electronic signatures to be equivalent to full handwritten signatures, initials,
> and other general signings as required by agency regulations, unless specifically excepted by
> regulation(s) effective on or after August 20, 1997.

### R00009  [shall]

**VERBATIM_QUOTE:**

> Where electronic signatures and their associated electronic records meet the requirements of this part,
> the agency will consider the electronic signatures to be equivalent to full handwritten signatures, initials,
> and other general signings as required by agency regulations

**ATOMIC_STATEMENT:**

> The agency shall consider electronic signatures and their associated electronic records that meet the requirements of Part 11 to be equivalent to full handwritten signatures, initials, and other general signings required by agency regulations.

`subject=the agency (FDA)  |  object=electronic signatures and associated electronic records  |  conditions=electronic signatures and associated electronic records meet the requirements of Part 11  |  tags=electronic_signature, electronic_records, equivalence`

### R00010  [shall]

**VERBATIM_QUOTE:**

> unless specifically excepted by
> regulation(s) effective on or after August 20, 1997

**ATOMIC_STATEMENT:**

> The equivalence of electronic signatures to handwritten signatures shall not apply where specifically excepted by regulation(s) effective on or after August 20, 1997.

`subject=the agency (FDA)  |  object=exceptions to electronic signature equivalence  |  conditions=regulation(s) effective on or after August 20, 1997 specifically except the equivalence  |  tags=electronic_signature, exception, scope`

---

## § 11.1(d) [scope_inclusion  (+ embedded: cross_reference, requirement_bearing)] — 2 requirements

**Source paragraph (verbatim):**

> (d)  Electronic records that meet the requirements of this part may be used in lieu of paper records, in
> accordance with § 11.2, unless paper records are specifically required.

### R00011  [may]

**VERBATIM_QUOTE:**

> Electronic records that meet the requirements of this part may be used in lieu of paper records, in
> accordance with § 11.2

**ATOMIC_STATEMENT:**

> Electronic records that meet the requirements of Part 11 may be used in lieu of paper records in accordance with § 11.2.

`subject=persons subject to Part 11  |  object=electronic records used in lieu of paper records  |  conditions=electronic records meet the requirements of Part 11; use is in accordance with § 11.2  |  tags=electronic_records, paper_records, paper_substitution, scope`

### R00012  [shall]

**VERBATIM_QUOTE:**

> unless paper records are specifically required

**ATOMIC_STATEMENT:**

> Electronic records may not be substituted for paper records when paper records are specifically required.

`subject=persons subject to Part 11  |  object=paper records that are specifically required  |  conditions=paper records are specifically required  |  tags=electronic_records, paper_records, paper_substitution, exception`

---

## § 11.1(e) [requirement_bearing] — 6 requirements

**Source paragraph (verbatim):**

> (e)  Computer systems (including hardware and software), controls, and attendant documentation maintained
> under this part shall be readily available for, and subject to, FDA inspection.

### R00013  [shall]

**VERBATIM_QUOTE:**

> Computer systems (including hardware and software)

**ATOMIC_STATEMENT:**

> Computer systems (including hardware and software) maintained under this part shall be readily available for FDA inspection.

`subject=persons maintaining computer systems under this part  |  object=computer systems (hardware and software)  |  conditions=maintained under this part  |  tags=fda_inspection, availability, computer_systems`

### R00014  [shall]

**VERBATIM_QUOTE:**

> Computer systems (including hardware and software)

**ATOMIC_STATEMENT:**

> Computer systems (including hardware and software) maintained under this part shall be subject to FDA inspection.

`subject=persons maintaining computer systems under this part  |  object=computer systems (hardware and software)  |  conditions=maintained under this part  |  tags=fda_inspection, computer_systems`

### R00015  [shall]

**VERBATIM_QUOTE:**

> controls

**ATOMIC_STATEMENT:**

> Controls maintained under this part shall be readily available for FDA inspection.

`subject=persons maintaining controls under this part  |  object=controls  |  conditions=maintained under this part  |  tags=fda_inspection, availability, controls`

### R00016  [shall]

**VERBATIM_QUOTE:**

> controls

**ATOMIC_STATEMENT:**

> Controls maintained under this part shall be subject to FDA inspection.

`subject=persons maintaining controls under this part  |  object=controls  |  conditions=maintained under this part  |  tags=fda_inspection, controls`

### R00017  [shall]

**VERBATIM_QUOTE:**

> attendant documentation

**ATOMIC_STATEMENT:**

> Attendant documentation maintained under this part shall be readily available for FDA inspection.

`subject=persons maintaining attendant documentation under this part  |  object=attendant documentation  |  conditions=maintained under this part  |  tags=fda_inspection, availability, documentation, retention`

### R00018  [shall]

**VERBATIM_QUOTE:**

> attendant documentation

**ATOMIC_STATEMENT:**

> Attendant documentation maintained under this part shall be subject to FDA inspection.

`subject=persons maintaining attendant documentation under this part  |  object=attendant documentation  |  conditions=maintained under this part  |  tags=fda_inspection, documentation, retention`

---

## § 11.1(f) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (f)  This part does not apply to records required to be established or maintained by §§ 1.326 through 1.368 of
> this chapter. Records that satisfy the requirements of part 1, subpart J of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

### R00019  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by §§ 1.326 through 1.368 of
> this chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by §§ 1.326 through 1.368 of this chapter.

`subject=records required by §§ 1.326 through 1.368  |  object=applicability of Part 11  |  conditions=record is required to be established or maintained by §§ 1.326 through 1.368  |  tags=scope, exemption, recordkeeping`

### R00020  [shall]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of part 1, subpart J of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy part 1, subpart J but are also required under other applicable statutory provisions or regulations remain subject to Part 11.

`subject=records that satisfy part 1 subpart J and are also required under other applicable statutes or regulations  |  object=applicability of Part 11  |  conditions=record satisfies part 1, subpart J; record is also required under other applicable statutory provisions or regulations  |  tags=scope, applicability, recordkeeping, dual_requirement`

---

## § 11.1(h) [scope_exclusion  (+ embedded: cross_reference, requirement_bearing)] — 1 requirements

**Source paragraph (verbatim):**

> (h)  This part does not apply to electronic signatures obtained under § 101.8(d) of this chapter.

### R00152  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to electronic signatures obtained under § 101.8(d) of this chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to electronic signatures obtained under § 101.8(d) of this chapter.

`subject=Part 11 (regulated entities applying Part 11)  |  object=electronic signatures obtained under § 101.8(d)  |  conditions=electronic signature obtained under § 101.8(d) of this chapter  |  tags=scope_exclusion, electronic_signature`

---

## § 11.1(i) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 1 requirements

**Source paragraph (verbatim):**

> (i)  This part does not apply to records required to be established or maintained by part 117 of this chapter.
> Records that satisfy the requirements of part 117 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

### R00153  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of part 117 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy part 117 requirements but are also required under other applicable statutory provisions or regulations are subject to Part 11.

`subject=Records satisfying part 117 that are also required under other applicable statutory provisions or regulations  |  object=Applicability of Part 11 requirements  |  conditions=record satisfies part 117 requirements; record is also required under other applicable statutory provisions or regulations  |  tags=scope, re_inclusion, part_117_overlap`

---

## § 11.1(j) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (j)  This part does not apply to records required to be established or maintained by part 507 of this chapter.
> Records that satisfy the requirements of part 507 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

### R00021  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by part 507 of this chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records that are required to be established or maintained by part 507 of this chapter.

`subject=regulated entities subject to part 507  |  object=records required by part 507  |  conditions=record is required to be established or maintained by part 507  |  tags=scope, exemption, part_507`

### R00022  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of part 507 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy part 507 but are also required under other applicable statutory provisions or regulations remain subject to part 11.

`subject=regulated entities maintaining records under part 507 and other applicable statutes or regulations  |  object=records dually required under part 507 and other provisions  |  conditions=record satisfies part 507 requirements; record is also required under other applicable statutory provisions or regulations  |  tags=scope, applicability, part_507, dual_requirement`

---

## § 11.1(k) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (k)  This part does not apply to records required to be established or maintained by part 112 of this chapter.
> Records that satisfy the requirements of part 112 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

### R00023  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by part 112 of this chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by part 112 of this chapter.

`subject=records under part 112  |  object=applicability of Part 11  |  conditions=record is required to be established or maintained by part 112  |  tags=scope_exclusion, part_112`

### R00024  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of part 112 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy part 112 but are also required under other applicable statutory provisions or regulations remain subject to Part 11.

`subject=records satisfying part 112 and other applicable statutes/regulations  |  object=applicability of Part 11  |  conditions=record satisfies part 112; record is also required under other applicable statutory provisions or regulations  |  tags=scope_inclusion, part_112, dual_applicability`

---

## § 11.1(l) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (l)  This part does not apply to records required to be established or maintained by subpart L of part 1 of this
> chapter. Records that satisfy the requirements of subpart L of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

### R00025  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by subpart L of part 1 of this
> chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by subpart L of part 1 of this chapter.

`subject=records required to be established or maintained by subpart L of part 1  |  object=applicability of Part 11  |  conditions=record is required to be established or maintained by subpart L of part 1  |  tags=scope_exclusion, subpart_l`

### R00026  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of subpart L of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy subpart L of part 1 but are also required under other applicable statutory provisions or regulations remain subject to Part 11.

`subject=records satisfying subpart L of part 1 that are also required under other statutes or regulations  |  object=applicability of Part 11  |  conditions=record satisfies subpart L of part 1; record is also required under other applicable statutory provisions or regulations  |  tags=scope_inclusion, subpart_l, dual_applicability`

---

## § 11.1(m) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (m)  This part does not apply to records required to be established or maintained by subpart M of part 1 of this
> chapter. Records that satisfy the requirements of subpart M of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

### R00027  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by subpart M of part 1 of this
> chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by subpart M of part 1 of this chapter.

`subject=records required by subpart M of part 1  |  object=applicability of Part 11  |  conditions=record is required to be established or maintained by subpart M of part 1  |  tags=scope_exclusion, subpart_m`

### R00028  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of subpart M of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy subpart M of part 1 but are also required under other applicable statutory provisions or regulations remain subject to Part 11.

`subject=records satisfying subpart M that are also required under other statutes or regulations  |  object=applicability of Part 11  |  conditions=record satisfies subpart M of part 1; record is also required under other applicable statutory provisions or regulations  |  tags=scope_inclusion, subpart_m, dual_requirement`

---

## § 11.1(n) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (n)  This part does not apply to records required to be established or maintained by subpart O of part 1 of this
> chapter. Records that satisfy the requirements of subpart O of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

### R00029  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by subpart O of part 1 of this
> chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by subpart O of part 1 of this chapter.

`subject=records required by subpart O of part 1  |  object=applicability of part 11  |  conditions=record is required to be established or maintained by subpart O of part 1  |  tags=scope, exclusion, subpart_o`

### R00030  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of subpart O of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy subpart O of part 1 but are also required under other applicable statutory provisions or regulations remain subject to Part 11.

`subject=persons maintaining records that satisfy subpart O and are also required under other statutory provisions or regulations  |  object=applicability of part 11 to dual-required records  |  conditions=record satisfies subpart O of part 1; record is also required under other applicable statutory provisions or regulations  |  tags=scope, applicability, subpart_o, dual_requirement`

---

## § 11.1(o) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (o)  This part does not apply to records required to be established or maintained by part 121 of this chapter.
> Records that satisfy the requirements of part 121 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

### R00031  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by part 121 of this chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by part 121 of this chapter.

`subject=records under part 121  |  object=applicability of part 11  |  conditions=record is required to be established or maintained by part 121  |  tags=scope_exclusion, part_121`

### R00032  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of part 121 of this chapter, but that also are required under other
> applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy part 121 requirements but are also required under other applicable statutory provisions or regulations remain subject to part 11.

`subject=records satisfying part 121 and other applicable statutes or regulations  |  object=applicability of part 11  |  conditions=record satisfies part 121 requirements; record is also required under other applicable statutory provisions or regulations  |  tags=scope_inclusion, part_121, dual_applicability`

---

## § 11.1(p) [scope_exclusion  (+ embedded: requirement_bearing, scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (p)  This part does not apply to records required to be established or maintained by subpart R of part 1 of this
> chapter. Records that satisfy the requirements of subpart R of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

### R00033  [unspecified]

**VERBATIM_QUOTE:**

> This part does not apply to records required to be established or maintained by subpart R of part 1 of this
> chapter.

**ATOMIC_STATEMENT:**

> Part 11 does not apply to records required to be established or maintained by subpart R of part 1 of this chapter.

`subject=records required by subpart R of part 1  |  object=applicability of Part 11  |  conditions=record is required to be established or maintained by subpart R of part 1  |  tags=scope, exclusion, applicability, subpart_r`

### R00034  [unspecified]

**VERBATIM_QUOTE:**

> Records that satisfy the requirements of subpart R of part 1 of this chapter, but that also are
> required under other applicable statutory provisions or regulations, remain subject to this part.

**ATOMIC_STATEMENT:**

> Records that satisfy subpart R of part 1 but are also required under other applicable statutory provisions or regulations remain subject to Part 11.

`subject=records satisfying subpart R that are also required under other statutes or regulations  |  object=applicability of Part 11  |  conditions=record satisfies subpart R of part 1; record is also required under other applicable statutory provisions or regulations  |  tags=scope, applicability, subpart_r, dual_requirement`

---

## § 11.2(a) [scope_inclusion  (+ embedded: requirement_bearing)] — 3 requirements

**Source paragraph (verbatim):**

> (a)  For records required to be maintained but not submitted to the agency, persons may use electronic
> records in lieu of paper records or electronic signatures in lieu of traditional signatures, in whole or in part,
> provided that the requirements of this part are met.

### R00035  [may]

**VERBATIM_QUOTE:**

> For records required to be maintained but not submitted to the agency, persons may use electronic
> records in lieu of paper records

**ATOMIC_STATEMENT:**

> Persons may use electronic records in lieu of paper records for records that are required to be maintained but not submitted to the agency.

`subject=persons  |  object=electronic records in lieu of paper records  |  conditions=records are required to be maintained but not submitted to the agency; the requirements of this part are met  |  tags=electronic_records, recordkeeping, not_submitted`

### R00036  [may]

**VERBATIM_QUOTE:**

> electronic signatures in lieu of traditional signatures, in whole or in part

**ATOMIC_STATEMENT:**

> Persons may use electronic signatures in lieu of traditional signatures, in whole or in part, for records required to be maintained but not submitted to the agency.

`subject=persons  |  object=electronic signatures in lieu of traditional signatures  |  conditions=records are required to be maintained but not submitted to the agency; the requirements of this part are met  |  tags=electronic_signature, recordkeeping, not_submitted`

### R00037  [must]

**VERBATIM_QUOTE:**

> provided that the requirements of this part are met

**ATOMIC_STATEMENT:**

> Any use of electronic records or electronic signatures in lieu of paper records or traditional signatures must comply with the requirements of Part 11.

`subject=persons using electronic records or electronic signatures  |  object=compliance with Part 11 requirements  |  conditions=electronic records or electronic signatures are used in lieu of paper records or traditional signatures  |  tags=electronic_records, electronic_signature, part_11`

---

## § 11.2(b) [requirement_bearing  (+ embedded: scope_inclusion)] — 2 requirements

**Source paragraph (verbatim):**

> (b)  For records submitted to the agency, persons may use electronic records in lieu of paper records or
> electronic signatures in lieu of traditional signatures, in whole or in part, provided that:

### R00038  [may]

**VERBATIM_QUOTE:**

> For records submitted to the agency, persons may use electronic records in lieu of paper records

**ATOMIC_STATEMENT:**

> Persons may use electronic records in lieu of paper records for records submitted to the agency, provided the stated conditions are met.

`subject=persons submitting records to the agency  |  object=electronic records used in lieu of paper records  |  conditions=records are submitted to the agency; conditions in § 11.2(b) are satisfied  |  tags=electronic_records, agency_submission`

### R00039  [may]

**VERBATIM_QUOTE:**

> electronic signatures in lieu of traditional signatures, in whole or in part, provided that:

**ATOMIC_STATEMENT:**

> Persons may use electronic signatures in lieu of traditional signatures, in whole or in part, for records submitted to the agency, provided the stated conditions are met.

`subject=persons submitting records to the agency  |  object=electronic signatures used in lieu of traditional signatures  |  conditions=records are submitted to the agency; conditions in § 11.2(b) are satisfied  |  tags=electronic_signature, agency_submission`

---

## § 11.2(b)(1) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (1)  The requirements of this part are met; and

### R00040  [shall]

**VERBATIM_QUOTE:**

> The requirements of this part are met

**ATOMIC_STATEMENT:**

> The requirements of part 11 shall be met as a condition for the use referenced in the parent provision.

`subject=persons relying on this provision  |  object=requirements of part 11  |  conditions=applies to the use of electronic records/signatures in lieu of paper as scoped by § 11.2(b)  |  tags=compliance, part_11`

---

## § 11.2(b)(2) [administrative  (+ embedded: requirement_bearing, scope_inclusion)] — 4 requirements

**Source paragraph (verbatim):**

> (2)  The document or parts of a document to be submitted have been identified in public docket No.
> 92S-0251 as being the type of submission the agency accepts in electronic form. This docket will
> identify specifically what types of documents or parts of documents are acceptable for submission
> in electronic form without paper records and the agency receiving unit(s) (e.g., specific center, office,
> division, branch) to which such submissions may be made. Documents to agency receiving unit(s)
> not specified in the public docket will not be considered as official if they are submitted in electronic
> form; paper forms of such documents will be considered as official and must accompany any
> electronic records. Persons are expected to consult with the intended agency receiving unit for
> details on how (e.g., method of transmission, media, file formats, and technical protocols) and
> whether to proceed with the electronic submission.

### R00041  [must]

**VERBATIM_QUOTE:**

> The document or parts of a document to be submitted have been identified in public docket No.
> 92S-0251 as being the type of submission the agency accepts in electronic form.

**ATOMIC_STATEMENT:**

> Documents or parts of documents submitted electronically must have been identified in public docket No. 92S-0251 as a type of submission the agency accepts in electronic form.

`subject=persons submitting electronic records to the agency  |  object=documents identified in public docket No. 92S-0251  |  conditions=submission is in electronic form  |  tags=electronic_submission, public_docket, agency_acceptance`

### R00042  [shall]

**VERBATIM_QUOTE:**

> Documents to agency receiving unit(s)
> not specified in the public docket will not be considered as official if they are submitted in electronic
> form

**ATOMIC_STATEMENT:**

> Electronic documents submitted to agency receiving units not specified in the public docket shall not be considered official.

`subject=agency  |  object=electronic documents submitted to unlisted receiving units  |  conditions=receiving unit is not specified in the public docket; document is submitted in electronic form  |  tags=electronic_submission, public_docket, official_status`

### R00043  [must]

**VERBATIM_QUOTE:**

> paper forms of such documents will be considered as official and must accompany any
> electronic records

**ATOMIC_STATEMENT:**

> Paper forms of documents submitted to unlisted receiving units must accompany any electronic records and shall be considered the official version.

`subject=persons submitting documents to agency receiving units not specified in the public docket  |  object=paper forms of documents  |  conditions=receiving unit is not specified in the public docket; electronic records are submitted  |  tags=electronic_submission, paper_records, official_status`

### R00044  [should]

**VERBATIM_QUOTE:**

> Persons are expected to consult with the intended agency receiving unit for
> details on how (e.g., method of transmission, media, file formats, and technical protocols) and
> whether to proceed with the electronic submission.

**ATOMIC_STATEMENT:**

> Persons are expected to consult with the intended agency receiving unit for details on how and whether to proceed with the electronic submission.

`subject=persons intending to make electronic submissions  |  object=consultation with the intended agency receiving unit  |  conditions=prior to electronic submission  |  tags=electronic_submission, agency_consultation, transmission, file_format`

---

## § 11.3(b)(8) [definition  (+ embedded: requirement_bearing)] — 2 requirements

**Source paragraph (verbatim):**

> (8)  Handwritten signature means the scripted name or legal mark of an individual handwritten by that
> individual and executed or adopted with the present intention to authenticate a writing in a
> permanent form. The act of signing with a writing or marking instrument such as a pen or stylus is
> preserved. The scripted name or legal mark, while conventionally applied to paper, may also be
> applied to other devices that capture the name or mark.

### R00045  [must]

**VERBATIM_QUOTE:**

> The act of signing with a writing or marking instrument such as a pen or stylus is
> preserved.

**ATOMIC_STATEMENT:**

> The act of signing with a writing or marking instrument such as a pen or stylus must be preserved.

`subject=system capturing handwritten signatures  |  object=act of signing with a writing or marking instrument  |  tags=handwritten_signature, signing_act, preservation`

### R00046  [may]

**VERBATIM_QUOTE:**

> The scripted name or legal mark, while conventionally applied to paper, may also be
> applied to other devices that capture the name or mark.

**ATOMIC_STATEMENT:**

> The scripted name or legal mark may be applied to devices other than paper that capture the name or mark.

`subject=individual providing a handwritten signature  |  object=device used to capture scripted name or legal mark  |  tags=handwritten_signature, capture_device, non_paper_medium`

---

## § 11.10 chapeau [requirement_bearing] — 5 requirements

**Source paragraph (verbatim):**

> Persons who use closed systems to create, modify, maintain, or transmit electronic records shall employ
> procedures and controls designed to ensure the authenticity, integrity, and, when appropriate, the confidentiality of
> electronic records, and to ensure that the signer cannot readily repudiate the signed record as not genuine. Such
> procedures and controls shall include the following:

### R00047  [shall]

**VERBATIM_QUOTE:**

> Persons who use closed systems to create, modify, maintain, or transmit electronic records shall employ
> procedures and controls designed to ensure the authenticity

**ATOMIC_STATEMENT:**

> Persons who use closed systems to create, modify, maintain, or transmit electronic records shall employ procedures and controls designed to ensure the authenticity of electronic records.

`subject=persons using closed systems to create, modify, maintain, or transmit electronic records  |  object=procedures and controls ensuring authenticity of electronic records  |  tags=closed_system, electronic_records, authenticity`

### R00048  [shall]

**VERBATIM_QUOTE:**

> procedures and controls designed to ensure the authenticity, integrity

**ATOMIC_STATEMENT:**

> Persons who use closed systems to create, modify, maintain, or transmit electronic records shall employ procedures and controls designed to ensure the integrity of electronic records.

`subject=persons using closed systems to create, modify, maintain, or transmit electronic records  |  object=procedures and controls ensuring integrity of electronic records  |  tags=closed_system, electronic_records, integrity`

### R00049  [shall]

**VERBATIM_QUOTE:**

> when appropriate, the confidentiality of
> electronic records

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ procedures and controls designed to ensure the confidentiality of electronic records when appropriate.

`subject=persons using closed systems to create, modify, maintain, or transmit electronic records  |  object=procedures and controls ensuring confidentiality of electronic records  |  conditions=when appropriate  |  tags=closed_system, electronic_records, confidentiality`

### R00050  [shall]

**VERBATIM_QUOTE:**

> to ensure that the signer cannot readily repudiate the signed record as not genuine

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ procedures and controls designed to ensure that the signer cannot readily repudiate the signed record as not genuine.

`subject=persons using closed systems to create, modify, maintain, or transmit electronic records  |  object=procedures and controls ensuring non-repudiation of signed records  |  tags=closed_system, electronic_signature, non_repudiation, signature_record_linking`

### R00051  [shall]

**VERBATIM_QUOTE:**

> Such
> procedures and controls shall include the following:

**ATOMIC_STATEMENT:**

> The procedures and controls employed by persons using closed systems shall include the items enumerated in the subsequent provisions of § 11.10.

`subject=persons using closed systems to create, modify, maintain, or transmit electronic records  |  object=required components of procedures and controls  |  tags=closed_system, procedural`

---

## § 11.10(a) [requirement_bearing] — 4 requirements

**Source paragraph (verbatim):**

> (a)  Validation of systems to ensure accuracy, reliability, consistent intended performance, and the ability to
> discern invalid or altered records.

### R00052  [shall]

**VERBATIM_QUOTE:**

> Validation of systems to ensure accuracy

**ATOMIC_STATEMENT:**

> Persons using closed systems shall validate systems to ensure accuracy.

`subject=persons using closed systems  |  object=system validation for accuracy  |  tags=closed_system, validation, accuracy`

### R00053  [shall]

**VERBATIM_QUOTE:**

> Validation of systems to ensure accuracy, reliability

**ATOMIC_STATEMENT:**

> Persons using closed systems shall validate systems to ensure reliability.

`subject=persons using closed systems  |  object=system validation for reliability  |  tags=closed_system, validation, reliability`

### R00054  [shall]

**VERBATIM_QUOTE:**

> consistent intended performance

**ATOMIC_STATEMENT:**

> Persons using closed systems shall validate systems to ensure consistent intended performance.

`subject=persons using closed systems  |  object=system validation for consistent intended performance  |  tags=closed_system, validation, performance`

### R00055  [shall]

**VERBATIM_QUOTE:**

> the ability to
> discern invalid or altered records

**ATOMIC_STATEMENT:**

> Persons using closed systems shall validate systems to ensure the ability to discern invalid or altered records.

`subject=persons using closed systems  |  object=system validation for detection of invalid or altered records  |  tags=closed_system, validation, record_integrity, audit_trail`

---

## § 11.10(b) [requirement_bearing  (+ embedded: administrative)] — 5 requirements

**Source paragraph (verbatim):**

> (b)  The ability to generate accurate and complete copies of records in both human readable and electronic
> form suitable for inspection, review, and copying by the agency. Persons should contact the agency if
> there are any questions regarding the ability of the agency to perform such review and copying of the
> electronic records.

### R00056  [shall]

**VERBATIM_QUOTE:**

> The ability to generate accurate and complete copies of records in both human readable and electronic
> form suitable for inspection, review, and copying by the agency.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall have the ability to generate accurate and complete copies of records in human readable form suitable for inspection, review, and copying by the agency.

`subject=persons using closed systems  |  object=human readable copies of records  |  conditions=copies must be suitable for agency inspection, review, and copying  |  tags=closed_system, record_copying, human_readable`

### R00057  [shall]

**VERBATIM_QUOTE:**

> The ability to generate accurate and complete copies of records in both human readable and electronic
> form suitable for inspection, review, and copying by the agency.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall have the ability to generate accurate and complete copies of records in electronic form suitable for inspection, review, and copying by the agency.

`subject=persons using closed systems  |  object=electronic copies of records  |  conditions=copies must be suitable for agency inspection, review, and copying  |  tags=closed_system, record_copying, electronic_records`

### R00058  [shall]

**VERBATIM_QUOTE:**

> copies of records in both human readable and electronic
> form suitable for inspection, review, and copying by the agency

**ATOMIC_STATEMENT:**

> Generated copies of records shall be accurate.

`subject=persons using closed systems  |  object=accuracy of record copies  |  tags=closed_system, record_copying, accuracy`

### R00059  [shall]

**VERBATIM_QUOTE:**

> accurate and complete copies of records

**ATOMIC_STATEMENT:**

> Generated copies of records shall be complete.

`subject=persons using closed systems  |  object=completeness of record copies  |  tags=closed_system, record_copying, completeness`

### R00060  [should]

**VERBATIM_QUOTE:**

> Persons should contact the agency if
> there are any questions regarding the ability of the agency to perform such review and copying of the
> electronic records.

**ATOMIC_STATEMENT:**

> Persons should contact the agency if they have any questions regarding the agency's ability to perform review and copying of the electronic records.

`subject=persons using closed systems  |  object=communication with the agency  |  conditions=questions exist regarding agency's review/copying capability  |  tags=closed_system, agency_contact, electronic_records`

---

## § 11.10(c) [requirement_bearing] — 2 requirements

**Source paragraph (verbatim):**

> (c)  Protection of records to enable their accurate and ready retrieval throughout the records retention period.

### R00061  [shall]

**VERBATIM_QUOTE:**

> Protection of records to enable their accurate and ready retrieval throughout the records retention period.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall protect records to enable their accurate retrieval throughout the records retention period.

`subject=persons using closed systems  |  object=records  |  conditions=throughout the records retention period  |  tags=closed_system, retention, record_protection`

### R00062  [shall]

**VERBATIM_QUOTE:**

> Protection of records to enable their accurate and ready retrieval throughout the records retention period.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall protect records to enable their ready retrieval throughout the records retention period.

`subject=persons using closed systems  |  object=records  |  conditions=throughout the records retention period  |  tags=closed_system, retention, record_protection`

---

## § 11.10(d) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (d)  Limiting system access to authorized individuals.

### R00063  [shall]

**VERBATIM_QUOTE:**

> Limiting system access to authorized individuals.

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall limit system access to authorized individuals.

`subject=persons using closed systems  |  object=system access  |  tags=closed_system, access_control, identity_verification`

---

## § 11.10(e) [requirement_bearing] — 11 requirements

**Source paragraph (verbatim):**

> (e)  Use of secure, computer-generated, time-stamped audit trails to independently record the date and time of
> operator entries and actions that create, modify, or delete electronic records. Record changes shall not
> obscure previously recorded information. Such audit trail documentation shall be retained for a period at
> least as long as that required for the subject electronic records and shall be available for agency review
> and copying.

### R00064  [shall]

**VERBATIM_QUOTE:**

> secure, computer-generated, time-stamped audit trails

**ATOMIC_STATEMENT:**

> Audit trails shall be secure.

`subject=persons using closed systems  |  object=audit trail  |  tags=closed_system, audit_trail, security`

### R00065  [shall]

**VERBATIM_QUOTE:**

> secure, computer-generated, time-stamped audit trails

**ATOMIC_STATEMENT:**

> Audit trails shall be computer-generated.

`subject=persons using closed systems  |  object=audit trail  |  tags=closed_system, audit_trail`

### R00066  [shall]

**VERBATIM_QUOTE:**

> secure, computer-generated, time-stamped audit trails

**ATOMIC_STATEMENT:**

> Audit trails shall be time-stamped.

`subject=persons using closed systems  |  object=audit trail  |  tags=closed_system, audit_trail, timestamp`

### R00067  [shall]

**VERBATIM_QUOTE:**

> to independently record the date and time of
> operator entries and actions

**ATOMIC_STATEMENT:**

> Audit trails shall independently record the date and time of operator entries and actions.

`subject=audit trail system  |  object=date and time of operator entries and actions  |  tags=closed_system, audit_trail, independence`

### R00068  [shall]

**VERBATIM_QUOTE:**

> actions that create, modify, or delete electronic records

**ATOMIC_STATEMENT:**

> The audit trail shall capture actions that create electronic records.

`subject=audit trail system  |  object=record creation events  |  tags=closed_system, audit_trail, electronic_records`

### R00069  [shall]

**VERBATIM_QUOTE:**

> actions that create, modify, or delete electronic records

**ATOMIC_STATEMENT:**

> The audit trail shall capture actions that modify electronic records.

`subject=audit trail system  |  object=record modification events  |  tags=closed_system, audit_trail, electronic_records`

### R00070  [shall]

**VERBATIM_QUOTE:**

> actions that create, modify, or delete electronic records

**ATOMIC_STATEMENT:**

> The audit trail shall capture actions that delete electronic records.

`subject=audit trail system  |  object=record deletion events  |  tags=closed_system, audit_trail, electronic_records`

### R00071  [shall]

**VERBATIM_QUOTE:**

> Record changes shall not
> obscure previously recorded information.

**ATOMIC_STATEMENT:**

> Record changes shall not obscure previously recorded information.

`subject=persons using closed systems  |  object=previously recorded information  |  conditions=when records are changed  |  tags=closed_system, audit_trail, data_integrity`

### R00072  [shall]

**VERBATIM_QUOTE:**

> Such audit trail documentation shall be retained for a period at
> least as long as that required for the subject electronic records

**ATOMIC_STATEMENT:**

> Audit trail documentation shall be retained for a period at least as long as that required for the subject electronic records.

`subject=persons using closed systems  |  object=audit trail documentation  |  tags=closed_system, audit_trail, retention`

### R00073  [shall]

**VERBATIM_QUOTE:**

> shall be available for agency review
> and copying

**ATOMIC_STATEMENT:**

> Audit trail documentation shall be available for agency review.

`subject=persons using closed systems  |  object=audit trail documentation  |  tags=closed_system, audit_trail, agency_access`

### R00074  [shall]

**VERBATIM_QUOTE:**

> shall be available for agency review
> and copying

**ATOMIC_STATEMENT:**

> Audit trail documentation shall be available for agency copying.

`subject=persons using closed systems  |  object=audit trail documentation  |  tags=closed_system, audit_trail, agency_access`

---

## § 11.10(f) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (f)  Use of operational system checks to enforce permitted sequencing of steps and events, as appropriate.

### R00075  [shall]

**VERBATIM_QUOTE:**

> Use of operational system checks to enforce permitted sequencing of steps and events, as appropriate.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall use operational system checks to enforce permitted sequencing of steps and events, as appropriate.

`subject=persons using closed systems  |  object=operational system checks  |  conditions=as appropriate  |  tags=closed_system, operational_checks, sequencing, validation`

---

## § 11.10(g) [requirement_bearing] — 5 requirements

**Source paragraph (verbatim):**

> (g)  Use of authority checks to ensure that only authorized individuals can use the system, electronically sign a
> record, access the operation or computer system input or output device, alter a record, or perform the
> operation at hand.

### R00076  [shall]

**VERBATIM_QUOTE:**

> Use of authority checks to ensure that only authorized individuals can use the system

**ATOMIC_STATEMENT:**

> Persons using closed systems shall employ authority checks to ensure that only authorized individuals can use the system.

`subject=persons using closed systems  |  object=authority checks for system use  |  tags=closed_system, authority_checks, access_control`

### R00077  [shall]

**VERBATIM_QUOTE:**

> only authorized individuals can use the system, electronically sign a
> record

**ATOMIC_STATEMENT:**

> Persons using closed systems shall employ authority checks to ensure that only authorized individuals can electronically sign a record.

`subject=persons using closed systems  |  object=authority checks for electronic signing  |  tags=closed_system, authority_checks, electronic_signature, access_control`

### R00078  [shall]

**VERBATIM_QUOTE:**

> access the operation or computer system input or output device

**ATOMIC_STATEMENT:**

> Persons using closed systems shall employ authority checks to ensure that only authorized individuals can access the operation or computer system input or output device.

`subject=persons using closed systems  |  object=authority checks for device access  |  tags=closed_system, authority_checks, access_control, device_access`

### R00079  [shall]

**VERBATIM_QUOTE:**

> alter a record

**ATOMIC_STATEMENT:**

> Persons using closed systems shall employ authority checks to ensure that only authorized individuals can alter a record.

`subject=persons using closed systems  |  object=authority checks for record alteration  |  tags=closed_system, authority_checks, access_control, record_modification`

### R00080  [shall]

**VERBATIM_QUOTE:**

> perform the
> operation at hand

**ATOMIC_STATEMENT:**

> Persons using closed systems shall employ authority checks to ensure that only authorized individuals can perform the operation at hand.

`subject=persons using closed systems  |  object=authority checks for operation execution  |  tags=closed_system, authority_checks, access_control`

---

## § 11.10(h) [requirement_bearing] — 2 requirements

**Source paragraph (verbatim):**

> (h)  Use of device (e.g., terminal) checks to determine, as appropriate, the validity of the source of data input
> or operational instruction.

### R00081  [shall]

**VERBATIM_QUOTE:**

> Use of device (e.g., terminal) checks to determine, as appropriate, the validity of the source of data input

**ATOMIC_STATEMENT:**

> Persons using closed systems shall use device checks (e.g., terminal checks) to determine, as appropriate, the validity of the source of data input.

`subject=persons using closed systems  |  object=device checks for source of data input  |  conditions=as appropriate  |  tags=closed_system, device_checks, data_input, source_validation`

### R00082  [shall]

**VERBATIM_QUOTE:**

> Use of device (e.g., terminal) checks to determine, as appropriate, the validity of the source of data input
> or operational instruction.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall use device checks (e.g., terminal checks) to determine, as appropriate, the validity of the source of operational instructions.

`subject=persons using closed systems  |  object=device checks for source of operational instruction  |  conditions=as appropriate  |  tags=closed_system, device_checks, operational_instruction, source_validation`

---

## § 11.10(i) [requirement_bearing] — 4 requirements

**Source paragraph (verbatim):**

> (i)  Determination that persons who develop, maintain, or use electronic record/electronic signature systems
> have the education, training, and experience to perform their assigned tasks.

### R00083  [shall]

**VERBATIM_QUOTE:**

> Determination that persons who develop, maintain, or use electronic record/electronic signature systems
> have the education, training, and experience to perform their assigned tasks.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall determine that personnel who develop electronic record/electronic signature systems have the education, training, and experience to perform their assigned tasks.

`subject=persons using closed systems  |  object=developer qualifications (education, training, experience)  |  tags=closed_system, electronic_signature, training, personnel_qualification, developers`

### R00084  [shall]

**VERBATIM_QUOTE:**

> Determination that persons who develop, maintain, or use electronic record/electronic signature systems
> have the education, training, and experience to perform their assigned tasks.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall determine that personnel who maintain electronic record/electronic signature systems have the education, training, and experience to perform their assigned tasks.

`subject=persons using closed systems  |  object=maintainer qualifications (education, training, experience)  |  tags=closed_system, electronic_signature, training, personnel_qualification, maintainers`

### R00085  [shall]

**VERBATIM_QUOTE:**

> Determination that persons who develop, maintain, or use electronic record/electronic signature systems
> have the education, training, and experience to perform their assigned tasks.

**ATOMIC_STATEMENT:**

> Persons using closed systems shall determine that personnel who use electronic record/electronic signature systems have the education, training, and experience to perform their assigned tasks.

`subject=persons using closed systems  |  object=user qualifications (education, training, experience)  |  tags=closed_system, electronic_signature, training, personnel_qualification, end_users`

### R00086  [shall]

**VERBATIM_QUOTE:**

> Determination that persons who develop, maintain, or use electronic record/electronic signature systems
> have the education, training, and experience to perform their assigned tasks.

**ATOMIC_STATEMENT:**

> A determination process shall exist to verify that personnel involved with electronic record/electronic signature systems possess the requisite education, training, and experience for their assigned tasks.

`subject=organization operating electronic record/electronic signature systems  |  object=qualification determination process  |  tags=closed_system, electronic_signature, training, personnel_qualification, validation`

---

## § 11.10(j) [requirement_bearing] — 4 requirements

**Source paragraph (verbatim):**

> (j)  The establishment of, and adherence to, written policies that hold individuals accountable and responsible
> for actions initiated under their electronic signatures, in order to deter record and signature falsification.

### R00087  [shall]

**VERBATIM_QUOTE:**

> The establishment of, and adherence to, written policies that hold individuals accountable and responsible
> for actions initiated under their electronic signatures

**ATOMIC_STATEMENT:**

> Persons using closed systems shall establish written policies that hold individuals accountable and responsible for actions initiated under their electronic signatures.

`subject=persons using closed systems  |  object=written accountability policies  |  conditions=to deter record and signature falsification  |  tags=closed_system, electronic_signature, policy, accountability`

### R00088  [shall]

**VERBATIM_QUOTE:**

> adherence to, written policies that hold individuals accountable and responsible
> for actions initiated under their electronic signatures

**ATOMIC_STATEMENT:**

> Persons using closed systems shall adhere to the written policies that hold individuals accountable and responsible for actions initiated under their electronic signatures.

`subject=persons using closed systems  |  object=written accountability policies  |  conditions=to deter record and signature falsification  |  tags=closed_system, electronic_signature, policy, adherence`

### R00089  [shall]

**VERBATIM_QUOTE:**

> hold individuals accountable and responsible
> for actions initiated under their electronic signatures

**ATOMIC_STATEMENT:**

> The written policies shall hold individuals accountable and responsible for actions initiated under their electronic signatures.

`subject=written policies  |  object=individual accountability for electronic-signature actions  |  tags=closed_system, electronic_signature, accountability, policy`

### R00090  [shall]

**VERBATIM_QUOTE:**

> in order to deter record and signature falsification

**ATOMIC_STATEMENT:**

> The accountability policies shall be designed to deter record and signature falsification.

`subject=written accountability policies  |  object=deterrence of record and signature falsification  |  tags=closed_system, electronic_signature, falsification_prevention, policy`

---

## § 11.10(k) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (k)  Use of appropriate controls over systems documentation including:

### R00091  [shall]

**VERBATIM_QUOTE:**

> Use of appropriate controls over systems documentation

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ appropriate controls over systems documentation.

`subject=persons using closed systems  |  object=systems documentation controls  |  tags=closed_system, systems_documentation, controls`

---

## § 11.10(k)(1) [requirement_bearing] — 3 requirements

**Source paragraph (verbatim):**

> (1)  Adequate controls over the distribution of, access to, and use of documentation for system
> operation and maintenance.

### R00092  [shall]

**VERBATIM_QUOTE:**

> Adequate controls over the distribution of

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ adequate controls over the distribution of documentation for system operation and maintenance.

`subject=persons using closed systems  |  object=distribution of documentation for system operation and maintenance  |  tags=closed_system, documentation_controls, systems_documentation`

### R00093  [shall]

**VERBATIM_QUOTE:**

> access to,

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ adequate controls over access to documentation for system operation and maintenance.

`subject=persons using closed systems  |  object=access to documentation for system operation and maintenance  |  tags=closed_system, documentation_controls, access_control, systems_documentation`

### R00094  [shall]

**VERBATIM_QUOTE:**

> use of documentation for system
> operation and maintenance.

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ adequate controls over the use of documentation for system operation and maintenance.

`subject=persons using closed systems  |  object=use of documentation for system operation and maintenance  |  tags=closed_system, documentation_controls, systems_documentation`

---

## § 11.10(k)(2) [requirement_bearing] — 5 requirements

**Source paragraph (verbatim):**

> (2)  Revision and change control procedures to maintain an audit trail that documents time-sequenced
> development and modification of systems documentation.

### R00095  [shall]

**VERBATIM_QUOTE:**

> Revision and change control procedures to maintain an audit trail that documents time-sequenced
> development and modification of systems documentation.

**ATOMIC_STATEMENT:**

> Persons who use closed systems shall employ revision and change control procedures for systems documentation.

`subject=persons using closed systems  |  object=revision and change control procedures  |  tags=closed_system, systems_documentation, change_control`

### R00096  [shall]

**VERBATIM_QUOTE:**

> maintain an audit trail that documents time-sequenced
> development and modification of systems documentation

**ATOMIC_STATEMENT:**

> The revision and change control procedures shall maintain an audit trail of systems documentation development and modification.

`subject=persons using closed systems  |  object=audit trail for systems documentation  |  tags=closed_system, audit_trail, systems_documentation`

### R00097  [shall]

**VERBATIM_QUOTE:**

> time-sequenced
> development and modification of systems documentation

**ATOMIC_STATEMENT:**

> The audit trail for systems documentation shall be time-sequenced.

`subject=persons using closed systems  |  object=time sequencing of the audit trail  |  tags=closed_system, audit_trail, systems_documentation, time_sequenced`

### R00098  [shall]

**VERBATIM_QUOTE:**

> documents time-sequenced
> development

**ATOMIC_STATEMENT:**

> The audit trail shall document the development of systems documentation.

`subject=persons using closed systems  |  object=development records of systems documentation  |  tags=closed_system, audit_trail, systems_documentation`

### R00099  [shall]

**VERBATIM_QUOTE:**

> time-sequenced
> development and modification of systems documentation

**ATOMIC_STATEMENT:**

> The audit trail shall document modifications to systems documentation.

`subject=persons using closed systems  |  object=modification records of systems documentation  |  tags=closed_system, audit_trail, systems_documentation, change_control`

---

## § 11.30 chapeau [requirement_bearing  (+ embedded: cross_reference)] — 6 requirements

**Source paragraph (verbatim):**

> Persons who use open systems to create, modify, maintain, or transmit electronic records shall employ procedures
> and controls designed to ensure the authenticity, integrity, and, as appropriate, the confidentiality of electronic
> records from the point of their creation to the point of their receipt. Such procedures and controls shall include
> those identified in § 11.10, as appropriate, and additional measures such as document encryption and use of
> appropriate digital signature standards to ensure, as necessary under the circumstances, record authenticity,
> integrity, and confidentiality.

### R00100  [shall]

**VERBATIM_QUOTE:**

> Persons who use open systems to create, modify, maintain, or transmit electronic records shall employ procedures
> and controls designed to ensure the authenticity, integrity, and, as appropriate, the confidentiality of electronic
> records from the point of their creation to the point of their receipt.

**ATOMIC_STATEMENT:**

> Persons who use open systems to create, modify, maintain, or transmit electronic records shall employ procedures and controls designed to ensure the authenticity of electronic records from the point of creation to the point of receipt.

`subject=persons using open systems  |  object=procedures and controls ensuring record authenticity  |  conditions=from point of creation to point of receipt  |  tags=open_system, electronic_records, authenticity`

### R00101  [shall]

**VERBATIM_QUOTE:**

> Persons who use open systems to create, modify, maintain, or transmit electronic records shall employ procedures
> and controls designed to ensure the authenticity, integrity, and, as appropriate, the confidentiality of electronic
> records from the point of their creation to the point of their receipt.

**ATOMIC_STATEMENT:**

> Persons who use open systems shall employ procedures and controls designed to ensure the integrity of electronic records from the point of creation to the point of receipt.

`subject=persons using open systems  |  object=procedures and controls ensuring record integrity  |  conditions=from point of creation to point of receipt  |  tags=open_system, electronic_records, integrity`

### R00102  [shall]

**VERBATIM_QUOTE:**

> authenticity, integrity, and, as appropriate, the confidentiality of electronic
> records from the point of their creation to the point of their receipt

**ATOMIC_STATEMENT:**

> Persons who use open systems shall employ procedures and controls designed to ensure the confidentiality of electronic records from the point of creation to the point of receipt, as appropriate.

`subject=persons using open systems  |  object=procedures and controls ensuring record confidentiality  |  conditions=as appropriate; from point of creation to point of receipt  |  tags=open_system, electronic_records, confidentiality`

### R00103  [shall]

**VERBATIM_QUOTE:**

> Such procedures and controls shall include
> those identified in § 11.10, as appropriate

**ATOMIC_STATEMENT:**

> The procedures and controls for open systems shall include those identified in § 11.10, as appropriate.

`subject=persons using open systems  |  object=procedures and controls from § 11.10  |  conditions=as appropriate  |  tags=open_system, closed_system_controls_reference, cross_reference`

### R00104  [shall]

**VERBATIM_QUOTE:**

> additional measures such as document encryption and use of
> appropriate digital signature standards to ensure, as necessary under the circumstances, record authenticity,
> integrity, and confidentiality

**ATOMIC_STATEMENT:**

> The procedures and controls for open systems shall include additional measures such as document encryption, as necessary under the circumstances, to ensure record authenticity, integrity, and confidentiality.

`subject=persons using open systems  |  object=document encryption  |  conditions=as necessary under the circumstances  |  tags=open_system, encryption, authenticity, integrity, confidentiality`

### R00105  [shall]

**VERBATIM_QUOTE:**

> additional measures such as document encryption and use of
> appropriate digital signature standards to ensure, as necessary under the circumstances, record authenticity,
> integrity, and confidentiality

**ATOMIC_STATEMENT:**

> The procedures and controls for open systems shall include use of appropriate digital signature standards, as necessary under the circumstances, to ensure record authenticity, integrity, and confidentiality.

`subject=persons using open systems  |  object=digital signature standards  |  conditions=as necessary under the circumstances  |  tags=open_system, digital_signature, authenticity, integrity, confidentiality`

---

## § 11.50(a) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (a)  Signed electronic records shall contain information associated with the signing that clearly indicates all of
> the following:

### R00106  [shall]

**VERBATIM_QUOTE:**

> Signed electronic records shall contain information associated with the signing that clearly indicates all of
> the following:

**ATOMIC_STATEMENT:**

> Signed electronic records shall contain information associated with the signing that clearly indicates all of the specified items.

`subject=signed electronic records  |  object=information associated with the signing  |  conditions=record is signed electronically  |  tags=electronic_signature, signature_record_linking, signed_record`

---

## § 11.50(a)(1) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (1)  The printed name of the signer;

### R00107  [shall]

**VERBATIM_QUOTE:**

> The printed name of the signer;

**ATOMIC_STATEMENT:**

> Signed electronic records shall contain the printed name of the signer.

`subject=signed electronic records  |  object=printed name of the signer  |  tags=electronic_signature, signature_manifestation, signed_record_content`

---

## § 11.50(a)(2) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (2)  The date and time when the signature was executed; and

### R00108  [shall]

**VERBATIM_QUOTE:**

> The date and time when the signature was executed

**ATOMIC_STATEMENT:**

> Signed electronic records shall contain the date and time when the signature was executed.

`subject=persons using electronic signatures  |  object=signed electronic record  |  tags=electronic_signature, signature_manifestation, timestamp`

---

## § 11.50(a)(3) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (3)  The meaning (such as review, approval, responsibility, or authorship) associated with the signature.

### R00109  [shall]

**VERBATIM_QUOTE:**

> The meaning (such as review, approval, responsibility, or authorship) associated with the signature.

**ATOMIC_STATEMENT:**

> Signed electronic records shall contain information indicating the meaning (such as review, approval, responsibility, or authorship) associated with the signature.

`subject=persons using electronic signatures on electronic records  |  object=signed electronic record  |  conditions=when an electronic signature is executed on an electronic record  |  tags=electronic_signature, signature_manifestation, signed_record_content`

---

## § 11.50(b) [requirement_bearing  (+ embedded: cross_reference)] — 2 requirements

**Source paragraph (verbatim):**

> (b)  The items identified in paragraphs (a)(1), (a)(2), and (a)(3) of this section shall be subject to the same
> controls as for electronic records and shall be included as part of any human readable form of the
> electronic record (such as electronic display or printout).

### R00110  [shall]

**VERBATIM_QUOTE:**

> The items identified in paragraphs (a)(1), (a)(2), and (a)(3) of this section shall be subject to the same
> controls as for electronic records

**ATOMIC_STATEMENT:**

> The signature manifestation items identified in § 11.50(a)(1), (a)(2), and (a)(3) shall be subject to the same controls as for electronic records.

`subject=persons using electronic signatures  |  object=signature manifestation items (signer name, date/time, meaning)  |  tags=electronic_signature, signature_manifestation, controls, electronic_records`

### R00111  [shall]

**VERBATIM_QUOTE:**

> shall be included as part of any human readable form of the
> electronic record (such as electronic display or printout)

**ATOMIC_STATEMENT:**

> The signature manifestation items shall be included as part of any human readable form of the electronic record, such as electronic display or printout.

`subject=persons using electronic signatures  |  object=human readable form of the electronic record  |  conditions=when the electronic record is rendered in human readable form  |  tags=electronic_signature, signature_manifestation, human_readable, display, printout`

---

## § 11.70 chapeau [requirement_bearing] — 4 requirements

**Source paragraph (verbatim):**

> Electronic signatures and handwritten signatures executed to electronic records shall be linked to their respective
> electronic records to ensure that the signatures cannot be excised, copied, or otherwise transferred to falsify an
> electronic record by ordinary means.

### R00112  [shall]

**VERBATIM_QUOTE:**

> Electronic signatures and handwritten signatures executed to electronic records shall be linked to their respective
> electronic records

**ATOMIC_STATEMENT:**

> Electronic signatures and handwritten signatures executed to electronic records shall be linked to their respective electronic records.

`subject=persons using electronic signatures or handwritten signatures executed to electronic records  |  object=signature-to-record linkage  |  tags=electronic_signature, signature_record_linking, handwritten_signature`

### R00113  [shall]

**VERBATIM_QUOTE:**

> the signatures cannot be excised, copied, or otherwise transferred to falsify an
> electronic record by ordinary means

**ATOMIC_STATEMENT:**

> The linkage shall ensure that signatures cannot be excised from their electronic records by ordinary means to falsify a record.

`subject=persons using electronic signatures or handwritten signatures executed to electronic records  |  object=signature-record linkage integrity (excision prevention)  |  conditions=by ordinary means  |  tags=electronic_signature, signature_record_linking, falsification_prevention`

### R00114  [shall]

**VERBATIM_QUOTE:**

> the signatures cannot be excised, copied, or otherwise transferred to falsify an
> electronic record by ordinary means

**ATOMIC_STATEMENT:**

> The linkage shall ensure that signatures cannot be copied from their electronic records by ordinary means to falsify a record.

`subject=persons using electronic signatures or handwritten signatures executed to electronic records  |  object=signature-record linkage integrity (copying prevention)  |  conditions=by ordinary means  |  tags=electronic_signature, signature_record_linking, falsification_prevention`

### R00115  [shall]

**VERBATIM_QUOTE:**

> the signatures cannot be excised, copied, or otherwise transferred to falsify an
> electronic record by ordinary means

**ATOMIC_STATEMENT:**

> The linkage shall ensure that signatures cannot otherwise be transferred from their electronic records by ordinary means to falsify a record.

`subject=persons using electronic signatures or handwritten signatures executed to electronic records  |  object=signature-record linkage integrity (transfer prevention)  |  conditions=by ordinary means  |  tags=electronic_signature, signature_record_linking, falsification_prevention`

---

## § 11.100(a) [requirement_bearing] — 3 requirements

**Source paragraph (verbatim):**

> (a)  Each electronic signature shall be unique to one individual and shall not be reused by, or reassigned to,
> anyone else.

### R00116  [shall]

**VERBATIM_QUOTE:**

> Each electronic signature shall be unique to one individual

**ATOMIC_STATEMENT:**

> Each electronic signature shall be unique to one individual.

`subject=persons using electronic signatures  |  object=electronic signature  |  tags=electronic_signature, identity_verification, uniqueness`

### R00117  [shall]

**VERBATIM_QUOTE:**

> shall not be reused by, or reassigned to,
> anyone else

**ATOMIC_STATEMENT:**

> An electronic signature shall not be reused by anyone else.

`subject=persons using electronic signatures  |  object=electronic signature  |  tags=electronic_signature, reuse_prohibition`

### R00118  [shall]

**VERBATIM_QUOTE:**

> shall not be reused by, or reassigned to,
> anyone else

**ATOMIC_STATEMENT:**

> An electronic signature shall not be reassigned to anyone else.

`subject=persons using electronic signatures  |  object=electronic signature  |  tags=electronic_signature, reassignment_prohibition`

---

## § 11.100(b) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (b)  Before an organization establishes, assigns, certifies, or otherwise sanctions an individual's electronic
> signature, or any element of such electronic signature, the organization shall verify the identity of the
> individual.

### R00119  [shall]

**VERBATIM_QUOTE:**

> Before an organization establishes, assigns, certifies, or otherwise sanctions an individual's electronic
> signature, or any element of such electronic signature, the organization shall verify the identity of the
> individual.

**ATOMIC_STATEMENT:**

> An organization shall verify the identity of an individual before establishing, assigning, certifying, or otherwise sanctioning that individual's electronic signature or any element of such electronic signature.

`subject=organization  |  object=identity of the individual  |  conditions=prior to establishing, assigning, certifying, or otherwise sanctioning an electronic signature or any element thereof  |  tags=electronic_signature, identity_verification`

---

## § 11.100(c) [requirement_bearing] — 3 requirements

**Source paragraph (verbatim):**

> (c)  Persons using electronic signatures shall, prior to or at the time of such use, certify to the agency that the
> electronic signatures in their system, used on or after August 20, 1997, are intended to be the legally
> binding equivalent of traditional handwritten signatures.

### R00120  [shall]

**VERBATIM_QUOTE:**

> Persons using electronic signatures shall, prior to or at the time of such use, certify to the agency that the
> electronic signatures in their system, used on or after August 20, 1997, are intended to be the legally
> binding equivalent of traditional handwritten signatures.

**ATOMIC_STATEMENT:**

> Persons using electronic signatures shall certify to the agency that the electronic signatures in their system are intended to be the legally binding equivalent of traditional handwritten signatures.

`subject=persons using electronic signatures  |  object=certification to the agency  |  conditions=electronic signatures used on or after August 20, 1997  |  tags=electronic_signature, certification, agency_submission`

### R00121  [shall]

**VERBATIM_QUOTE:**

> prior to or at the time of such use

**ATOMIC_STATEMENT:**

> The certification to the agency shall be made prior to or at the time of using electronic signatures.

`subject=persons using electronic signatures  |  object=timing of certification  |  conditions=before or at the time of first use of electronic signatures  |  tags=electronic_signature, certification, timing`

### R00122  [shall]

**VERBATIM_QUOTE:**

> electronic signatures in their system, used on or after August 20, 1997, are intended to be the legally
> binding equivalent of traditional handwritten signatures

**ATOMIC_STATEMENT:**

> The certification shall state that the electronic signatures in the person's system are intended to be the legally binding equivalent of traditional handwritten signatures.

`subject=persons using electronic signatures  |  object=content of certification (legal equivalence to handwritten signatures)  |  conditions=electronic signatures used on or after August 20, 1997  |  tags=electronic_signature, certification, legal_equivalence, handwritten_signature`

---

## § 11.100(c)(1) [requirement_bearing  (+ embedded: administrative)] — 3 requirements

**Source paragraph (verbatim):**

> (1)  The certification shall be signed with a traditional handwritten signature and submitted in electronic
> or paper form. Information on where to submit the certification can be found on FDA's web page on
> Letters of Non-Repudiation Agreement.

### R00123  [shall]

**VERBATIM_QUOTE:**

> The certification shall be signed with a traditional handwritten signature

**ATOMIC_STATEMENT:**

> The certification shall be signed with a traditional handwritten signature.

`subject=persons submitting the certification  |  object=certification  |  tags=electronic_signature, certification, handwritten_signature`

### R00124  [shall]

**VERBATIM_QUOTE:**

> submitted in electronic
> or paper form

**ATOMIC_STATEMENT:**

> The certification shall be submitted in either electronic or paper form.

`subject=persons submitting the certification  |  object=certification  |  tags=electronic_signature, certification, submission`

### R00125  [may]

**VERBATIM_QUOTE:**

> Information on where to submit the certification can be found on FDA's web page on
> Letters of Non-Repudiation Agreement.

**ATOMIC_STATEMENT:**

> Submitters may locate information on where to submit the certification on FDA's web page on Letters of Non-Repudiation Agreement.

`subject=persons submitting the certification  |  object=submission location information  |  tags=electronic_signature, certification, submission, informational`

---

## § 11.100(c)(2) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (2)  Persons using electronic signatures shall, upon agency request, provide additional certification or
> testimony that a specific electronic signature is the legally binding equivalent of the signer's
> handwritten signature.

### R00126  [shall]

**VERBATIM_QUOTE:**

> Persons using electronic signatures shall, upon agency request, provide additional certification or
> testimony that a specific electronic signature is the legally binding equivalent of the signer's
> handwritten signature.

**ATOMIC_STATEMENT:**

> Persons using electronic signatures shall, upon agency request, provide additional certification or testimony that a specific electronic signature is the legally binding equivalent of the signer's handwritten signature.

`subject=persons using electronic signatures  |  object=additional certification or testimony of equivalence to handwritten signature  |  conditions=upon agency request  |  tags=electronic_signature, certification, agency_request`

---

## § 11.200(a) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (a)  Electronic signatures that are not based upon biometrics shall:

### R00127  [shall]

**VERBATIM_QUOTE:**

> Electronic signatures that are not based upon biometrics shall:

**ATOMIC_STATEMENT:**

> Electronic signatures that are not based upon biometrics shall comply with the requirements that follow in this paragraph.

`subject=persons using electronic signatures not based upon biometrics  |  object=electronic signature controls  |  conditions=electronic signature is not based upon biometrics  |  tags=electronic_signature, non_biometric`

---

## § 11.200(a)(1) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (1)  Employ at least two distinct identification components such as an identification code and password.

### R00128  [shall]

**VERBATIM_QUOTE:**

> Employ at least two distinct identification components such as an identification code and password.

**ATOMIC_STATEMENT:**

> Electronic signatures not based upon biometrics shall employ at least two distinct identification components such as an identification code and password.

`subject=persons using non-biometric electronic signatures  |  object=identification components  |  conditions=electronic signature is not based upon biometrics  |  tags=electronic_signature, id_password, non_biometric, identity_verification`

---

## § 11.200(a)(1)(i) [requirement_bearing] — 3 requirements

**Source paragraph (verbatim):**

> (i)  When an individual executes a series of signings during a single, continuous period of
> controlled system access, the first signing shall be executed using all electronic signature
> components; subsequent signings shall be executed using at least one electronic signature
> component that is only executable by, and designed to be used only by, the individual.

### R00129  [shall]

**VERBATIM_QUOTE:**

> When an individual executes a series of signings during a single, continuous period of
> controlled system access, the first signing shall be executed using all electronic signature
> components

**ATOMIC_STATEMENT:**

> During a single continuous period of controlled system access involving a series of signings, the first signing shall be executed using all electronic signature components.

`subject=persons using non-biometric electronic signatures  |  object=first signing in a continuous session  |  conditions=individual executes a series of signings during a single, continuous period of controlled system access; first signing  |  tags=electronic_signature, id_password, non_biometric, continuous_session, session_signing`

### R00130  [shall]

**VERBATIM_QUOTE:**

> subsequent signings shall be executed using at least one electronic signature
> component that is only executable by, and designed to be used only by, the individual

**ATOMIC_STATEMENT:**

> Subsequent signings in the same continuous session shall be executed using at least one electronic signature component that is only executable by, and designed to be used only by, the individual.

`subject=persons using non-biometric electronic signatures  |  object=subsequent signings in a continuous session  |  conditions=individual executes a series of signings during a single, continuous period of controlled system access; subsequent signings after the first  |  tags=electronic_signature, id_password, non_biometric, continuous_session, signature_component, session_signing`

### R00131  [shall]

**VERBATIM_QUOTE:**

> at least one electronic signature
> component that is only executable by, and designed to be used only by, the individual

**ATOMIC_STATEMENT:**

> At least one electronic signature component used for subsequent signings shall be designed and implemented so that it is only executable by, and only usable by, the specific individual.

`subject=electronic signature system designers  |  object=electronic signature component  |  conditions=component used for subsequent signings in a continuous session  |  tags=electronic_signature, id_password, non_biometric, signature_component, component_design`

---

## § 11.200(a)(1)(ii) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (ii) When an individual executes one or more signings not performed during a single, continuous
> period of controlled system access, each signing shall be executed using all of the electronic
> signature components.

### R00132  [shall]

**VERBATIM_QUOTE:**

> When an individual executes one or more signings not performed during a single, continuous
> period of controlled system access, each signing shall be executed using all of the electronic
> signature components.

**ATOMIC_STATEMENT:**

> When an individual executes signings that are not performed during a single, continuous period of controlled system access, each signing must be executed using all of the electronic signature components.

`subject=individuals executing electronic signings  |  object=each signing  |  conditions=signings are not performed during a single, continuous period of controlled system access  |  tags=electronic_signature, id_password, non_continuous_session, signing_execution`

---

## § 11.200(a)(2) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (2)  Be used only by their genuine owners; and

### R00133  [shall]

**VERBATIM_QUOTE:**

> Be used only by their genuine owners

**ATOMIC_STATEMENT:**

> Electronic signatures based on biometrics shall be used only by their genuine owners.

`subject=persons using non-biometric electronic signatures  |  object=electronic signature  |  tags=electronic_signature, id_password, identity_verification`

---

## § 11.200(a)(3) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (3)  Be administered and executed to ensure that attempted use of an individual's electronic signature by
> anyone other than its genuine owner requires collaboration of two or more individuals.

### R00134  [shall]

**VERBATIM_QUOTE:**

> Be administered and executed to ensure that attempted use of an individual's electronic signature by
> anyone other than its genuine owner requires collaboration of two or more individuals.

**ATOMIC_STATEMENT:**

> Electronic signatures not based on biometrics shall be administered and executed such that any attempted use by someone other than the genuine owner requires the collaboration of two or more individuals.

`subject=persons using non-biometric electronic signatures  |  object=administration and execution of electronic signatures  |  conditions=applies to attempted use by anyone other than the genuine owner  |  tags=electronic_signature, non_biometric, id_password, collaboration_required, anti_impersonation`

---

## § 11.200(b) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (b)  Electronic signatures based upon biometrics shall be designed to ensure that they cannot be used by
> anyone other than their genuine owners.

### R00135  [shall]

**VERBATIM_QUOTE:**

> Electronic signatures based upon biometrics shall be designed to ensure that they cannot be used by
> anyone other than their genuine owners.

**ATOMIC_STATEMENT:**

> Biometric-based electronic signatures shall be designed to ensure they cannot be used by anyone other than their genuine owners.

`subject=persons using biometric electronic signatures  |  object=biometric electronic signature design  |  conditions=signature is based upon biometrics  |  tags=electronic_signature, biometric, identity_verification`

---

## § 11.300 chapeau [requirement_bearing] — 2 requirements

**Source paragraph (verbatim):**

> Persons who use electronic signatures based upon use of identification codes in combination with passwords shall
> employ controls to ensure their security and integrity. Such controls shall include:

### R00136  [shall]

**VERBATIM_QUOTE:**

> Persons who use electronic signatures based upon use of identification codes in combination with passwords shall
> employ controls to ensure their security and integrity.

**ATOMIC_STATEMENT:**

> Persons who use electronic signatures based upon identification codes combined with passwords shall employ controls to ensure the security and integrity of those identification codes and passwords.

`subject=persons who use electronic signatures based upon identification codes in combination with passwords  |  object=controls ensuring security and integrity of identification codes and passwords  |  conditions=electronic signatures based on identification codes combined with passwords are used  |  tags=electronic_signature, id_password, security, integrity`

### R00137  [shall]

**VERBATIM_QUOTE:**

> Such controls shall include:

**ATOMIC_STATEMENT:**

> The controls employed to ensure security and integrity of identification codes and passwords shall include the specific control measures enumerated in the subsequent provisions of § 11.300.

`subject=persons who use electronic signatures based upon identification codes in combination with passwords  |  object=scope of required controls enumerated in § 11.300  |  conditions=electronic signatures based on identification codes combined with passwords are used  |  tags=electronic_signature, id_password, controls_enumeration`

---

## § 11.300(a) [requirement_bearing] — 1 requirements

**Source paragraph (verbatim):**

> (a)  Maintaining the uniqueness of each combined identification code and password, such that no two
> individuals have the same combination of identification code and password.

### R00138  [shall]

**VERBATIM_QUOTE:**

> Maintaining the uniqueness of each combined identification code and password, such that no two
> individuals have the same combination of identification code and password.

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes and passwords shall maintain the uniqueness of each combined identification code and password so that no two individuals share the same combination.

`subject=persons using electronic signatures based on identification codes and passwords  |  object=combined identification code and password  |  conditions=electronic signature is based on identification code and password  |  tags=electronic_signature, id_password, identity_verification`

---

## § 11.300(b) [requirement_bearing] — 4 requirements

**Source paragraph (verbatim):**

> (b)  Ensuring that identification code and password issuances are periodically checked, recalled, or revised
> (e.g., to cover such events as password aging).

### R00139  [shall]

**VERBATIM_QUOTE:**

> Ensuring that identification code and password issuances are periodically checked

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes and passwords shall ensure that identification code and password issuances are periodically checked.

`subject=persons using identification code/password-based electronic signatures  |  object=identification code and password issuances  |  conditions=periodically  |  tags=closed_system, electronic_signature, id_password, periodic_review`

### R00140  [shall]

**VERBATIM_QUOTE:**

> identification code and password issuances are periodically checked, recalled, or revised

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes and passwords shall ensure that identification code and password issuances are periodically recalled.

`subject=persons using identification code/password-based electronic signatures  |  object=identification code and password issuances  |  conditions=periodically  |  tags=closed_system, electronic_signature, id_password, recall`

### R00141  [shall]

**VERBATIM_QUOTE:**

> identification code and password issuances are periodically checked, recalled, or revised

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes and passwords shall ensure that identification code and password issuances are periodically revised.

`subject=persons using identification code/password-based electronic signatures  |  object=identification code and password issuances  |  conditions=periodically  |  tags=closed_system, electronic_signature, id_password, revision`

### R00142  [shall]

**VERBATIM_QUOTE:**

> to cover such events as password aging

**ATOMIC_STATEMENT:**

> The periodic checking, recalling, or revising of identification code and password issuances shall cover events such as password aging.

`subject=persons using identification code/password-based electronic signatures  |  object=password aging events  |  conditions=events such as password aging  |  tags=electronic_signature, id_password, password_aging`

---

## § 11.300(c) [requirement_bearing] — 2 requirements

**Source paragraph (verbatim):**

> (c)  Following loss management procedures to electronically deauthorize lost, stolen, missing, or otherwise
> potentially compromised tokens, cards, and other devices that bear or generate identification code or
> password information, and to issue temporary or permanent replacements using suitable, rigorous
> controls.

### R00143  [shall]

**VERBATIM_QUOTE:**

> Following loss management procedures to electronically deauthorize lost, stolen, missing, or otherwise
> potentially compromised tokens, cards, and other devices that bear or generate identification code or
> password information

**ATOMIC_STATEMENT:**

> Persons using electronic identification mechanisms shall follow loss management procedures to electronically deauthorize lost, stolen, missing, or otherwise potentially compromised tokens, cards, and other devices that bear or generate identification code or password information.

`subject=persons using tokens, cards, or devices that bear or generate identification code or password information  |  object=loss management procedures for deauthorizing compromised devices  |  conditions=device is lost, stolen, missing, or otherwise potentially compromised  |  tags=id_password, tokens_cards, loss_management, deauthorization`

### R00144  [shall]

**VERBATIM_QUOTE:**

> to issue temporary or permanent replacements using suitable, rigorous
> controls

**ATOMIC_STATEMENT:**

> Persons using electronic identification mechanisms shall issue temporary or permanent replacements for compromised tokens, cards, and devices using suitable, rigorous controls.

`subject=persons using tokens, cards, or devices that bear or generate identification code or password information  |  object=issuance of temporary or permanent replacements  |  conditions=replacing a compromised, lost, stolen, or missing device  |  tags=id_password, tokens_cards, loss_management, replacement_issuance, controls`

---

## § 11.300(d) [requirement_bearing] — 3 requirements

**Source paragraph (verbatim):**

> (d)  Use of transaction safeguards to prevent unauthorized use of passwords and/or identification codes, and
> to detect and report in an immediate and urgent manner any attempts at their unauthorized use to the
> system security unit, and, as appropriate, to organizational management.

### R00145  [shall]

**VERBATIM_QUOTE:**

> Use of transaction safeguards to prevent unauthorized use of passwords and/or identification codes

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes and/or passwords shall use transaction safeguards to prevent unauthorized use of passwords and/or identification codes.

`subject=persons using id/password-based electronic signatures  |  object=transaction safeguards preventing unauthorized password/ID code use  |  tags=electronic_signature, id_password, transaction_safeguards`

### R00146  [shall]

**VERBATIM_QUOTE:**

> to detect and report in an immediate and urgent manner any attempts at their unauthorized use to the
> system security unit

**ATOMIC_STATEMENT:**

> Transaction safeguards shall detect and report any attempts at unauthorized use of passwords and/or identification codes to the system security unit in an immediate and urgent manner.

`subject=persons using id/password-based electronic signatures  |  object=detection and reporting of unauthorized use attempts to the system security unit  |  conditions=attempts at unauthorized use detected  |  tags=electronic_signature, id_password, transaction_safeguards, incident_reporting, system_security_unit`

### R00147  [shall]

**VERBATIM_QUOTE:**

> and, as appropriate, to organizational management

**ATOMIC_STATEMENT:**

> Transaction safeguards shall report attempts at unauthorized use of passwords and/or identification codes to organizational management, as appropriate.

`subject=persons using id/password-based electronic signatures  |  object=reporting of unauthorized use attempts to organizational management  |  conditions=as appropriate  |  tags=electronic_signature, id_password, transaction_safeguards, incident_reporting, organizational_management`

---

## § 11.300(e) [requirement_bearing] — 4 requirements

**Source paragraph (verbatim):**

> (e)   Initial and periodic testing of devices, such as tokens or cards, that bear or generate identification code or
> password information to ensure that they function properly and have not been altered in an unauthorized
> manner.

### R00148  [shall]

**VERBATIM_QUOTE:**

> Initial and periodic testing of devices, such as tokens or cards, that bear or generate identification code or
> password information to ensure that they function properly

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes shall perform initial and periodic testing of devices (such as tokens or cards) that bear or generate identification code or password information to ensure they function properly.

`subject=persons using identification code/password-bearing or generating devices  |  object=devices that bear or generate identification code or password information  |  conditions=device bears or generates identification code or password information  |  tags=id_password, electronic_signature, device_testing, tokens_cards`

### R00149  [shall]

**VERBATIM_QUOTE:**

> have not been altered in an unauthorized
> manner.

**ATOMIC_STATEMENT:**

> Persons using electronic signatures based on identification codes shall perform initial and periodic testing of devices (such as tokens or cards) that bear or generate identification code or password information to ensure they have not been altered in an unauthorized manner.

`subject=persons using identification code/password-bearing or generating devices  |  object=devices that bear or generate identification code or password information  |  conditions=device bears or generates identification code or password information  |  tags=id_password, electronic_signature, device_testing, tokens_cards, tamper_detection`

### R00150  [shall]

**VERBATIM_QUOTE:**

> Initial and periodic testing of devices

**ATOMIC_STATEMENT:**

> Initial testing of identification code/password devices shall be performed.

`subject=persons using identification code/password-bearing or generating devices  |  object=devices that bear or generate identification code or password information  |  tags=id_password, electronic_signature, device_testing, initial_testing`

### R00151  [shall]

**VERBATIM_QUOTE:**

> periodic testing of devices

**ATOMIC_STATEMENT:**

> Periodic testing of identification code/password devices shall be performed on an ongoing basis.

`subject=persons using identification code/password-bearing or generating devices  |  object=devices that bear or generate identification code or password information  |  tags=id_password, electronic_signature, device_testing, periodic_testing`

---
