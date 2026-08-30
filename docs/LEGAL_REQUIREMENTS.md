# Legal Requirements Checklist — Legal Metrology (Packaged Commodities) Rules, 2011

**Status: DRAFT, built from secondary/search-engine access to primary sources on 2026-08-26.**

This document is the single source of truth the rule engine (`backend/app/rules/`) must implement
against. Every rule function must cite its row number from this table in its docstring and in the
generated compliance report. Do not add or change a rule in code without updating this file first.

## ⚠️ Important caveat on sourcing (read before trusting any number below)

The research for this document was done via web search and `WebFetch` against secondary sources
(IndianKanoon extracts, law-firm summaries, IndiaCode) because full PDF text of the primary
government notification could not be reliably fetched in this environment (several PDF hosts
returned HTTP errors or fetch tool failures). Every item below is annotated with a confidence tag:

- **[VERIFIED-TEXT]** — clause wording pulled directly from a legal-text extraction (IndianKanoon),
  high confidence but not confirmed byte-for-byte against the Gazette PDF.
- **[VERIFIED-SECONDARY]** — confirmed by multiple secondary summaries (law firm articles,
  compliance guides) but not seen in primary clause text during this session.
- **[VERIFY WITH DoCA]** — could not be confirmed with confidence; the rule engine must mark
  this check `NEEDS_VERIFICATION` rather than auto PASS/FAIL, and the UI/report must say so
  explicitly.

**Before this system is used for anything beyond a hackathon demo, every row must be re-verified
against the consolidated Gazette-notified text of the Act and Rules (as amended up to the
Legal Metrology (Packaged Commodities) Amendment Rules, 2023, in force 2024-01-01), ideally by
someone at DoCA or a copy of the official consolidated PDF.**

---

## 1. Governing instruments

| Instrument | Status |
|---|---|
| Legal Metrology Act, 2009 | [VERIFIED-TEXT] Sections 18, 36 confirmed via IndianKanoon |
| Legal Metrology (Packaged Commodities) Rules, 2011 | [VERIFIED-TEXT] Rules 2, 6, 7, 18 confirmed; **Rule 8 additionally verified against the official Gazette scan itself** — see §1.1 |

### 1.1 Full amendment chain — [VERIFIED-TEXT], official Gazette PDFs (2026-08-27 pass)

A complete enumeration of <https://consumeraffairs.gov.in/pages/legal-metrology-act> was performed
on **2026-08-27**: 207 links, of which **39 are Packaged-Commodities-related**. The amendment chain
below is taken from the *authoritative footnote* each Gazette notification carries ("The principal
rules were published … and were last amended vide …"), which makes the ordering self-certifying:

| Notification | Date | In force | Effect |
|---|---|---|---|
| G.S.R. 202(E) | 2011-03-07 | — | Principal rules |
| … (2011–2023 chain) | | | as documented in §3–§10 |
| G.S.R. 722(E) | 2023-10-06 | — | previously believed to be the latest amendment |
| **G.S.R. 778(E)** | **2025-10-23** | on publication | **Medical devices carved out of Rules 2(h), 7(2), 7(3), 33 → see §5.1. Affected a live check.** |
| **G.S.R. 881(E)** | **2025-12-02** | 2026-02-01 | Rule 26(a) exemption proviso: *"shall not apply to pan masala"* |
| **G.S.R. 128(E)** | **2026-02-13** | **2026-07-01 (IN FORCE)** | Inserts **Rule 6(10A)** — e-commerce country-of-origin filter → §8 |
| **G.S.R. 312(E)** | **2026-04-27** | 2027-07-01 (NOT yet in force) | Substitutes Rule 6(10A) → §8 |
| **G.S.R. 418(E)** | **2026-05-29** | on publication (IN FORCE) | Rule 4 Explanation-2 (AEO bonded-warehouse declarations); Rule 27 registration changes |

**Sourcing note:** the official base-Rules PDF (`8_1732871406.pdf`) is an **83-page bilingual scan
with no text layer** — this is why earlier sessions fell back to a text-extractable mirror. On this
pass the official scan was OCR'd directly to locate and confirm the English Rule 8 text (page 48);
it matches the mirror **word for word**. The base clause text is therefore now corroborated against
the primary artefact, not merely a mirror. Every *amendment* PDF above is natively text-extractable
and was read in full.

**Deliberately not re-OCR'd:** the remaining ~80 pages of the base scan. OCR of legal text carries
a real transcription-error risk, and re-deriving already-corroborated clauses through a lossy
channel would reduce, not increase, citation reliability.

The rule engine must be versioned (`RULESET_VERSION` constant) so that a report always states
which ruleset revision produced it.

---

## 2. Key definitions (Rule 2) — [VERIFIED-TEXT]

| Term | Definition | Ref |
|---|---|---|
| Retail package | "packages which are intended for retail sale to the ultimate consumer for the purpose of consumption of the commodity contained therein and includes the imported packages" | Rule 2(k) |
| Wholesale package | A package containing (i) a number of retail packages intended for sale to an intermediary, (ii) a commodity sold to an intermediary in bulk, or (iii) ten or more retail packages, where the retail packages are not intended to be sold individually | Rule 2(r) |
| Principal display panel (PDP) | "the total surface area of the package where the information required under these rules are to be given" | Rule 2(h) |
| Net quantity | "the quantity by weight, measure or number of such commodity contained in that package", excluding packaging material | Rule 2(f) |
| Pre-packaged commodity | [VERIFY WITH DoCA] — not independently confirmed with exact clause text in this session; per Section 2(l) of the Act it is a commodity placed in a package of any nature, without the purchaser being present, such that the quantity is pre-determined | Act §2(l), Rule 2 |
| MRP rounding | Fraction below 50 paise rounds down to the preceding rupee; fraction from 50 to 95 paise rounds to 50 paise | Rule 2(m) |

**Scope note for the tool:** the scanner targets **retail packages** only. Wholesale-package
declaration rules (Rule 24 area) are out of scope for this prototype — flag any package the
system cannot confidently classify as a retail package as `NEEDS_VERIFICATION` rather than
running retail-package rules on it blindly.

---

## 3. Mandatory declarations on every retail package (Rule 6) — [VERIFIED-TEXT], sub-clause list [VERIFIED-SECONDARY]

Rule engine module: `backend/app/rules/mandatory_declarations.py`. One function per row.

| # | Declaration | Requirement (plain English) | Ref | Exceptions found |
|---|---|---|---|---|
| R6-1 | Manufacturer/packer/importer name & address | Name and address of the manufacturer; if manufacturer ≠ packer, name and address of both manufacturer and packer; if imported, name and address of importer | Rule 6(1)(a) | — |
| R6-2 | Country of origin | Required for imported products (and, per 2022/2023-era amendments, in some cases for country of manufacture/assembly even for domestically sold goods) | Rule 6(1)(aa) | [VERIFY WITH DoCA] exact current scope post-amendment |
| R6-3 | Common/generic name of commodity | Plain, conspicuous common or generic name | Rule 6(1)(b) | — |
| R6-4 | Net quantity | Net quantity in standard unit of weight, measure or number (see §4 below for unit/rounding rules) | Rule 6(1)(c) | Category-specific unit rules — see §4 |
| R6-5 | Month & year of manufacture/pre-packing/import | Must state month and year | Rule 6(1)(d) | — |
| R6-6 | Best-before / use-by date | Required for perishables/commodities with a defined shelf life | Rule 6(1)(da) | Only applicable to perishable-category goods — [VERIFY WITH DoCA] the exact category list |
| R6-7 | Retail sale price (MRP) | Must be declared as Maximum Retail Price, inclusive of all taxes, in the form "MRP ₹___ (incl. of all taxes)" or equivalent | Rule 6(1)(e) | — |
| R6-8 | Dimensions | Where relevant to how the product is sold (e.g. length-sold goods) | Rule 6(1)(f) | Category-dependent, not universal |
| R6-9 | Consumer care details | Name, address, telephone number and/or e-mail address of a person/office that can be contacted for consumer complaints | Rule 6(2) | [VERIFY WITH DoCA] whether all of phone+email+address are simultaneously mandatory or whether any one contact channel suffices — treat as NEEDS_VERIFICATION if only partial info found |
| R6-10 | Unit sale price | Price per standard unit (e.g. ₹/kg), where required | Rule 6 (as amended 2017/2023) | Per the 2023 amendment, **not required** when retail sale price equals unit sale price, and **not required** for combination/group/multi-piece packages [VERIFIED-SECONDARY] |
| R6-11 | Net quantity declaration not misleading | The net quantity declaration must not contain exaggerated/misleading/inadequate qualifying words (e.g. "minimum", "not less than", "average", "about", "approximately") | Rule 12(6) | [VERIFIED-TEXT] — confirmed against the consolidated Gazette PDF. Directly answers the problem statement's "detection of missing, misleading or non-standard declarations" requirement; added on a full PS re-read, not part of the original 10-row checklist. |

**Known blanket exemptions (partial list, [VERIFY WITH DoCA] for completeness):** the rules
exempt certain categories (e.g. bidi bundles under 20 sticks, LPG cylinders, agricultural seeds
sold to farmers, some scheduled formulations, packages ≤10 g/ml) from some of the above — build
an `exemptions.py` lookup table and mark any product the OCR/extraction pipeline cannot
confidently categorize as subject to manual category confirmation before applying exemptions
automatically, rather than guessing.

---

## 4. Net quantity — unit and declaration rules (Rule 6(1)(c) / Rule 8 area)

- Net quantity must be declared in the **standard unit**: weight (g/kg), volume (ml/l), or number,
  matching the nature of the commodity. [VERIFIED-TEXT: Rule 2(f) + Rule 6(1)(c)]
- Category-specific unit selection (solid → weight, liquid → volume, countable discrete items →
  number) is a real rule but the exact boundary cases (e.g. semi-solids, aerosols) are
  **[VERIFY WITH DoCA]** — the engine should only hard-FAIL an obviously wrong unit (e.g. a liquid
  declared only "5 pieces") and should NEEDS_VERIFICATION borderline cases.
- MRP rounding rule (Rule 2(m)) applies to *retail sale price* declarations, not net quantity —
  captured in §2 above; do not conflate the two in code.

---

## 5. Principal Display Panel font/numeral size requirements (Rule 7) — [VERIFIED-TEXT]

Rule engine module: `backend/app/rules/font_size.py`.

**Correction (this session):** an earlier draft of this section documented a category-dependent
Table-I (weight/volume) vs. Table-II (length/area/number) split, matching the Rules as originally
notified in 2011, and `font_size.py` branched on `commodity_category` accordingly. Re-checked
directly against a locally-extracted copy of the consolidated Gazette PDF (same source used for
§10's placement research, not a secondary summary): **GSR 629(E), dated 23.06.2017, replaced Rule
7 sub-rule (2) and omitted Table-II entirely.** The current, post-2017 text reads: *"(2) The
height of any numeral and letter in the declaration required under these rules shall be as per
Table-I"* — one table, applying to every numeral/letter height declaration regardless of
commodity category. `font_size.py` has been corrected to match (no more category branching); the
old Table-II is deleted from this document, not just deprecated in place, so nothing here still
implies two tables are current law.

- **Rule 7(1):** packages of 10 cm³ or less may use a firmly-affixed card or tape for the
  declaration instead of printing directly on the package.
- **Rule 7(2)** (post-2017, GSR 629(E)): height of any *numeral and letter* in a declaration on
  the PDP shall not be less than the value in Table-I below, keyed to PDP area — no
  category-based table split.
- **Rule 7(3):** width of a letter/numeral shall not be less than one-third of its height, except
  numeral "1" and letters i/I/l. Minimum *letter* height (as opposed to numeral height) is 1 mm
  normal, 2 mm if blown/formed/molded/embossed/perforated.
- **Rule 7(4)–(5)** (post-2017, GSR 629(E)) — PDP area calculation, now [VERIFIED-TEXT] (was
  [VERIFY WITH DoCA], resolves §9 item 5): area excludes the top, bottom, flange at top/bottom of
  cans, and shoulders/neck of bottles/jars, determined as —
  (a) rectangular package: height × width of the side properly considered the PDP;
  (b) cylindrical/nearly-cylindrical package: 40% of (height × circumference);
  (c) any other shape: 40% of total surface area, or an area considered to be the PDP.
  The tool's engine still only *estimates* PDP area from the photographed label region (a
  heuristic proxy, not a certified area measurement — see `docs/ARCHITECTURE.md`'s Font-Size
  Tier 1/Tier 2 note); knowing the exact legal formula doesn't remove the need for a user-supplied
  reference dimension (Tier 2) to apply it precisely from a 2D photo.

### 5.1 Medical devices are OUTSIDE Table-I — [VERIFIED-TEXT], G.S.R. 778(E) dated 2025-10-23

Found on the 2026-08-27 full primary-source pass. **This changed a live check.** G.S.R. 778(E)
inserted provisos to Rule 7(2) and Rule 7(3):

> *"Provided that for packages containing medical devices, the provisions of the Medical Devices
> Rules, 2017, shall apply for the height of any numeral and letter to make declarations."*
> (and correspondingly for width under 7(3))

It also inserted a proviso to Rule 2(h) (medical-device declarations governed by MDR 2017) and
Rule 33(2) (the Rule 33 relaxation does not apply where MDR 2017 applies).

Before this pass, `font_size.py` applied Table-I unconditionally and would have asserted a
**wrong citation** — a Table-I PASS/FAIL — against a medical-device package. R7-1/R7-2 now return
`NOT_APPLICABLE` with a pointer to MDR 2017 when `is_medical_device` is set. The MDR 2017 size
tables are **not** implemented by this tool; that is stated in the result notes rather than
guessed. `is_medical_device` is inspector/catalog input and is never inferred from OCR text.

### Table-I — minimum numeral/letter height (non-medical-device packages, any commodity category)

| PDP area | Normal print | Blown/formed/molded/embossed |
|---|---|---|
| ≤ 50 cm² | 1.0 mm | 1.5 mm |
| 50–100 cm² | 1.5 mm | 3.0 mm |
| 100–500 cm² | 2.5 mm | 4.0 mm |
| 500–2500 cm² | 4.0 mm | 6.0 mm |
| > 2500 cm² | 6.0 mm | 6.0 mm |

**Critical limitation the tool must be honest about:** these are absolute millimetre thresholds.
A phone photo alone gives no reliable pixels-per-mm ratio. See `docs/ARCHITECTURE.md` §Font Size
Tier 1/Tier 2 design — Tier 1 (no calibration) can only produce a *relative* signal; Tier 2 (with
a user-supplied reference dimension) can check against this exact table. Never present a Tier-1
relative finding as if it were a Tier-2 mm-calibrated PASS/FAIL against this table.

---

## 6. Offer/sale prohibition (Rule 18) — [VERIFIED-TEXT]

- **Rule 18(1):** no wholesale or retail dealer may sell a packaged commodity unless the package
  complies in all respects with the Act and Rules.
- **Rule 18(2):** no one may sell a packaged commodity above its declared retail sale price.

Used for the report's "regulatory consequence" framing, not as a per-field check.

---

## 7. Penalties (Act, 2009) — [VERIFIED-TEXT]

| Section | Trigger | Penalty |
|---|---|---|
| §18 | Manufacturing/packing/selling/importing a pre-packaged commodity without prescribed declarations | Prohibition; enforced via §36 penalty |
| §36(1) | Non-conforming pre-packaged commodity | Fine up to ₹25,000 (1st offence); up to ₹50,000 (2nd); ₹50,000–₹100,000 or imprisonment up to 1 year or both (subsequent) |
| §36 (net quantity error) | Manufacturing/packing/importing with net-quantity error | Fine ₹10,000–₹50,000 (1st/2nd); up to ₹100,000 or imprisonment up to 1 year or both (subsequent) |

Shown in the report footer for context only — the tool does not compute or recommend an actual
fine amount (that is an enforcement officer's determination, not the system's).

---

## 8. E-commerce specific declarations — [VERIFIED-SECONDARY]

For commodities sold via e-commerce (including loose commodities where the consumer is aware of
what they're ordering), the listing must display: manufacturer/marketer name & address, consumer
care details, retail sale price in INR, and net quantity — largely mirroring Rule 6 for physical
labels. Out of scope for the image-scan prototype (v1 only scans physical package photos), but the
rule engine's field schema is built to also accept a product-listing screenshot/text dump as an
alternate input source so this can be extended later without a schema change.

### 8.1 Rule 6(10A) — e-commerce country-of-origin filter — [VERIFIED-TEXT] (resolves §9 item 6)

The 2026-08-27 pass recovered the exact sub-rule numbering that was previously flagged unknown.

**Currently in force** (G.S.R. 128(E) dated 2026-02-13, effective **2026-07-01**) — inserted after
Rule 6(10):

> *"(10A) Every e-commerce entity selling imported products shall make available the product
> listings of such imported products in a searchable and sortable filter specifying the country
> of origin."*

**Superseding text, NOT yet in force** (G.S.R. 312(E) dated 2026-04-27, effective **2027-07-01**)
substitutes Rule 6(10A):

> *"(10A) Every e-commerce entity, which offers any imported product for sale, shall ensure from
> the 1st day of July, 2027 that the product listing of such imported product contains a
> searchable and sortable filter to specify the country of origin."*

This is a **platform/listing obligation, not a package-label obligation** — it is therefore
correctly out of scope for the label scanner and creates no new rule-engine check. It is recorded
here so the scope boundary is a documented decision rather than an omission.

---

## 9. Explicit "VERIFY WITH DoCA" list (do not silently auto-pass/fail these in the UI)

Status as of the **2026-08-27 full primary-source pass**:

1. **STILL OPEN** — Exact current scope of country-of-origin declaration for domestic vs. imported
   goods (R6-2). *What the pass added:* the two 2026 amendments (§8.1) are about **e-commerce
   listing filters**, not the package-label scope, so they do not resolve this. No notification on
   the DoCA page changes Rule 6(1)(aa)'s label-side scope. R6-2 remains `NEEDS_VERIFICATION` when
   import status is unknown.
2. **STILL OPEN** — Exact category list for which best-before/use-by date is mandatory (R6-6).
   Nothing on the DoCA page enumerates it.
3. **STILL OPEN** — Whether phone **and** email **and** address are simultaneously mandatory for
   consumer care (R6-9). Rule 6(2)'s text is disjunctive-ambiguous and no amendment or guideline
   found on this pass clarifies it.
4. **PARTIALLY RESOLVED** — Exemption list. Two concrete data points recovered: G.S.R. 881(E)
   (2025-12-02, in force 2026-02-01) inserts a proviso to **Rule 26(a)** excluding **pan masala**
   from that clause's exemption; and a DoCA advisory dated 2023-03-06 covers agricultural farm
   produce up to 50 kg. A *full* enumeration with thresholds still requires reading Rule 26 and the
   Schedules in the base scan — not done, see §1.1's deliberate-scope note. The engine still does
   not auto-apply exemptions.
5. ~~Rule 7(4)–(5) PDP area formulas.~~ **RESOLVED** (prior pass) — see §5. The Table-I/Table-II
   split was also found repealed by G.S.R. 629(E) (2017).
6. ~~Full clause text and current numbering of the e-commerce declaration requirement.~~
   **RESOLVED** — it is **Rule 6(10A)**; both the in-force and the 2027 superseding text are quoted
   verbatim in §8.1 from the official Gazette PDFs.
7. **PARTIALLY RESOLVED, and materially improved.** §5 (Rule 7), §5.1 (medical devices), §8.1
   (Rule 6(10A)) and §10 (Rule 8) are now confirmed against **official DoCA Gazette PDFs**, and
   Rule 8 specifically against the **official scan of the principal rules itself** (OCR of page 48,
   matching the mirror word for word). §2–§4 and §6–§7 remain corroborated only via IndianKanoon
   extracts / the text-extractable mirror, because the official base rules PDF has no text layer
   (§1.1).
8. **NEW, STILL OPEN** — The Medical Devices Rules, 2017 numeral/letter-height tables referenced by
   Rule 7(2)'s proviso (§5.1) are **not implemented**. R7-1/R7-2 return `NOT_APPLICABLE` for medical
   devices rather than guessing an MDR threshold.

Any rule-engine check derived from a still-open item must return `NEEDS_VERIFICATION` (or
`NOT_APPLICABLE` where the rule genuinely does not apply), never `PASS` or `FAIL`, until
re-confirmed against the primary source.

---

## 10. Placement of declarations (Rule 2(h), Rule 8) — [VERIFIED-TEXT]

The problem statement asks the tool to check "correctness, completeness **and placement**" of
declarations. §3–§9 above cover correctness and completeness (the 9 mandatory-declaration checks)
and font size — nothing before this section checked *where* a declaration appears. This section
was researched directly against a locally-extracted copy of the primary Rules PDF text (not a
secondary summary) after `WebFetch` against the government PDF host failed the same way noted in
the caveat at the top of this document; the extraction was done with `pypdf` against a PDF mirror
found via web search, cross-checked against the rule numbering already used above (Rule 6 opening
clause text matches verbatim at the same rule number cited in §3, giving confidence this is the
same clause set).

**Finding: there IS a real, textual placement requirement — both a grouping rule and a genuine
numeric/geometric rule. This is not a heuristic invented to fill a checklist item.**

### 10.1 Grouping requirement — Rule 2(h) + Rule 8(1) main clause

- **Rule 2(h)** defines "principal display panel" itself in terms of grouping: *"'principal
  display panel', in relation to a package, means the total surface area of the package where the
  information required under these rules are to be given in the following manner, namely; (i) all
  the information could be grouped together and given at one place; or (ii) the pre-printed
  information could be grouped together and given in one place and on-line information grouped
  together in other place."*
- **Rule 8(1)** makes this an operative requirement, not just a definition: *"Every declaration
  required to be made under these rules shall appear on the principal display panel."*
- Net effect: **every Rule 6 mandatory declaration must appear together, on one panel** — not
  scattered across visually separate faces of the package. This is India's equivalent of the
  "same field of vision" pattern common in other jurisdictions' packaging law, even though that
  exact phrase does not appear in the Indian text — confirms Step 1's third open question (grouped
  + unobstructed is the real pattern here, not a coordinate rule for this part).

### 10.2 Numeric placement requirement — Rule 8(1) proviso (net quantity clear-space)

This is the genuine geometric rule Step 1 was checking for. Immediately after the main PDP clause,
Rule 8(1)'s proviso states: *"the area surrounding the quantity declaration shall be free from
printed information — (a) above and below by a space equal to at least the height of the numeral
in the declaration, and (b) to the left and right by a space at least twice the height of numeral
in the declaration."*

This is specific to the **net quantity** declaration only (not MRP, not any other field) and is a
real numeric rule: a keep-clear buffer proportional to the numeral's own height, not an absolute
mm distance. It's directly checkable from the bounding-box data the OCR pipeline already produces
for every declaration, without needing calibration (unlike Rule 7's mm thresholds) — the buffer is
expressed in units of the numeral's own height, so it's scale-invariant.

### 10.3 Related supporting clauses (context, not separately implemented as their own checks)

- **Rule 9(2):** "No declaration shall be made so as to require it to be read through any liquid
  commodity contained in the package." — a real placement-adjacent rule, but not checkable from a
  2D photo without knowing which side is which relative to package contents; **[VERIFY WITH DoCA]**
  — out of scope for this prototype, not implemented.
- **Rule 12(5):** additional consumer-facing information "shall also appear on the same panel in
  which the other information... have been indicated" — reinforces 10.1, not a separate rule.
- **Rule 8(2):** returnable-bottle exception allowing MRP on the crown cap/bottle for soft drinks —
  a category-specific exception to 10.1, not implemented (out of scope; flag as
  `NEEDS_VERIFICATION` if ever needed).

### 10.4 What this means for implementation (answers Step 1's engineering-effort question)

Both a grouping check **and** a numeric check are required by the actual text — this is not an
either/or. Neither requires true multi-panel 3D reconstruction:

- **R8-1 (grouping):** the codebase has no true panel/face segmentation (the OCR pipeline
  processes one 2D photo, not a 3D unwrap of the package). A defensible, honestly-disclosed proxy
  is 2D spatial clustering of the bounding boxes of found Rule 6 declarations in the photographed
  image — declarations that cluster tightly are probably the same panel; one far outside that
  cluster is probably a different panel or an unusual placement. **This is a proxy for "same
  panel," not a certified panel determination** — same honesty discipline as Tier 1 font-size
  Test, and disclosed the same way in the report methodology footer.
- **R8-2 (net-quantity clear space):** this one is NOT a proxy in the same sense — it uses the
  numeral height and surrounding OCR regions' bounding boxes directly against Rule 8(1) proviso's
  own stated ratio (1x above/below, 2x left/right), which is scale-invariant and needs no
  calibration. The only approximation is that the OCR pipeline's merged bounding box for the net
  quantity *line* (see `ocr/engine.py` `_merge_adjacent_words`) may be slightly taller than the
  bare numeral glyphs alone (it includes the "g"/"Rs."/unit-letter neighbors on the same line),
  which would make the computed buffer *larger* than the strict minimum — a conservative
  (over-cautious, not under-cautious) approximation, disclosed in the check's own notes.

Both are implemented in `backend/app/rules/placement.py` as `R8-1` and `R8-2`, following the exact
same `RuleResult` pattern (rule_reference, requirement_text, status, evidence, notes) as every
other check — see `backend/app/rules/placement.py` docstring and `backend/tests/test_placement.py`
for the PASS/FAIL cases and thresholds chosen.
