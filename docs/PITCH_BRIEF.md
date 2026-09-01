# SIH26034 — Pitch Brief & Context Prompt

A single self-contained briefing you can paste into any LLM (or read yourself before a panel)
to be fully "pitch-ready" on this project: what it is, the market it sits in, the business/
enforcement context, and a line-by-line check that we built everything the problem statement asked for.

---

## PART A — The reusable prompt

> **Context prompt — paste this into a fresh chat when you need pitch help, Q&A rehearsal, or deck copy:**
>
> You are helping me prepare for a Smart India Hackathon (SIH) panel and a possible follow-up
> demo to officials from the Department of Consumer Affairs (DoCA), Ministry of Consumer Affairs,
> Food & Public Distribution, Government of India.
>
> **The project (SIH26034):** "Legal Metrology Packaged Commodities Compliance Scanner." A web
> application that scans a photo of a packaged-commodity label, uses multilingual OCR
> (English + Hindi + Gujarati, Tesseract) to read the printed declarations, extracts the
> mandatory declarations required by the **Legal Metrology (Packaged Commodities) Rules, 2011**
> (as amended through 2026), runs a **rule-based compliance engine** (14 itemised checks across
> Rule 6 mandatory declarations, Rule 7 numeral/letter height, and Rule 8 placement), and produces
> an **itemised, clause-cited compliance report** as PDF and editable DOCX. Every scan is stored
> in a searchable repository; enforcement admins get a dashboard (status breakdown, 30-day volume
> trend, non-compliant scans needing follow-up). Two roles: `inspector` and `admin`, JWT auth.
>
> **Stack:** Python 3.11 / FastAPI / SQLAlchemy (SQLite default, Postgres-swappable), Tesseract
> OCR via pytesseract, OpenCV + Pillow preprocessing, ReportLab (PDF), python-docx (DOCX),
> React + Vite frontend. Ships as a Docker image that bundles Tesseract with all three language
> packs. Deployed on Render free tier (frontend static site + backend web service). 96 backend
> tests pass, including an end-to-end walkthrough of 12 synthetic demo labels.
>
> **Design philosophy — "honesty by construction":** the tool never fabricates a legal verdict.
> Any legal threshold not confirmed against primary Gazette text returns `NEEDS_VERIFICATION`,
> not a fake PASS/FAIL. Absolute millimetre font-height checks (Rule 7) are two-tier: Tier 1
> (uncalibrated phone photo) gives only a *relative* signal; Tier 2 (user supplies a reference
> dimension) gives a real mm measurement against Rule 7 Table-I. Every report states which tier
> produced each finding, the ruleset version, and the OCR engine/languages used.
>
> **Known, disclosed limitations (v1 scope):** retail packages only (no wholesale / Rule 24);
> e-commerce listing text ingestion is schema-ready but not wired to the UI; regex/keyword
> extraction only (no LLM extraction fallback); 2D bounding-box clustering as a proxy for
> "same principal display panel" (no true 3D package reconstruction); OCR language is chosen
> per text-line, not per word.
>
> Help me with: [pitch narrative / anticipated judge questions / objection handling / deck
> slide copy / demo script / impact framing / competitive positioning]. Keep answers grounded
> in Indian Legal Metrology enforcement reality; don't overclaim accuracy.

---

## PART B — Project summary (the 60-second version)

Packaged goods in India must legally carry six-plus mandatory declarations (maker's name &
address, net quantity, MRP inclusive of all taxes, month/year of manufacture, consumer-care
contact, country of origin for imports, plus font-size and placement rules). Enforcement is
done by **state Legal Metrology departments** — a few thousand inspectors nationwide against
crores of SKUs across kirana stores, supermarkets, and e-commerce. Inspection today is manual,
visual, subjective, and slow: an inspector eyeballs a pack, maybe measures a font with a scale,
and hand-writes a notice.

Our system turns a **phone photo into a clause-cited compliance report in seconds**. It reads
the label (including Hindi/Gujarati), checks each declaration against the actual 2011 Rules,
flags what's missing or non-standard, measures relative font size, checks the net-quantity
keep-clear space, and generates a PDF/DOCX report an inspector can attach to an enforcement
file. Everything is logged in a searchable repository with an oversight dashboard.

The differentiator is **defensibility**: every verdict cites the exact rule clause and shows the
OCR evidence (cropped region + confidence). Where the law is genuinely ambiguous, the tool says
"verify with DoCA" instead of guessing — which is exactly what a system that might feed a legal
notice must do.

---

## PART C — Market & enforcement-context knowledge (for judges' business questions)

### The regulatory landscape
- **Governing law:** Legal Metrology Act, 2009 + Legal Metrology (Packaged Commodities) Rules,
  2011. Rules amended many times; the big recent ones: GSR 629(E) 2017 (collapsed Rule 7 to a
  single Table-I), country-of-origin mandate (2020, post-GeM), 2022 unit-sale-price / COO
  tightening, GSR 722(E) 2023, and 2025–26 amendments (medical-device carve-out GSR 778(E),
  pan-masala, e-commerce COO filter Rule 6(10A)). Our `LEGAL_REQUIREMENTS.md` tracks this chain
  with confidence tags.
- **Regulator:** Department of Consumer Affairs (DoCA) sets the rules; **enforcement is by state
  Legal Metrology / Weights & Measures departments** (Controllers + Assistant Controllers +
  Inspectors). DoCA runs the **National Consumer Helpline (NCH, 1915)** and the
  **eDaakhil** consumer-complaint portal.
- **Penalties (Act §36):** non-conforming pre-packaged commodity — fine up to ₹25,000 (1st
  offence), ₹50,000 (2nd), ₹50,000–₹1,00,000 or up to 1 year imprisonment (subsequent).
  Net-quantity error carries its own band. Selling above MRP is a separate offence (Rule 18(2)).
- **Compounding:** most first offences are *compounded* (settled by paying a fee) rather than
  prosecuted — so enforcement volume matters more than severity, which is exactly where
  automation helps.

### Market size / who has this problem
- **Direct users:** ~ state LM departments across 28 states + 8 UTs; a few thousand inspectors.
  Also: **BIS**, **FSSAI** (food labelling overlaps), and **legal-metrology consultants /
  compliance cells inside FMCG companies** who self-audit before dispatch.
- **Adjacent buyers:** large retail chains (DMart, Reliance Retail, big-basket type) and
  **e-commerce platforms** — since 2020 marketplaces are liable for seller label compliance,
  so Amazon/Flipkart/Meesho run label-vetting pipelines. Brand-protection and packaging-artwork
  QA vendors are an adjacent commercial market.
- **Scale of the problem:** India has an estimated 10+ crore retail outlets and millions of
  packaged SKUs; e-commerce adds lakhs of new listings monthly. Manual inspection covers a
  vanishingly small sample. Common violations (from DoCA advisories and press): missing/blurred
  MRP, MRP not "inclusive of all taxes", undersized fonts, missing consumer-care details,
  missing country of origin on imports, dual-MRP stickering.

### Comparable / competing approaches
- **Nothing government-side that's automated** — inspections are manual. That's the gap SIH
  is asking to fill.
- **Private-sector analogues:** packaging-artwork proofing tools (GlobalVision, Schawk),
  e-commerce content-compliance vendors, and in-house marketplace ML classifiers. These are
  closed, expensive, English-centric, and tuned to catalogue text, not photographed Indian
  retail labels in vernacular scripts.
- **Our positioning:** open, offline-capable, multilingual, *clause-cited*, and built to the
  Indian 2011 Rules specifically — designed to produce an artefact that survives challenge in a
  compounding hearing or consumer forum.

### Business / deployment model (if asked "how would this actually roll out")
- **Phase 1 (pilot):** one state LM department, inspectors use it on field tablets; reports
  attach to existing enforcement workflow. Runs on a single Docker container / small VM.
- **Phase 2:** integrate with the state's case-management system; add the exemptions lookup
  table and Tier-2 calibration hardware (a printed reference card).
- **Phase 3:** DoCA-hosted central instance + e-commerce listing ingestion (schema already
  supports it) so platforms can self-serve pre-listing checks; anonymised violation analytics
  feed DoCA policy.
- **Cost:** effectively hosting only — Tesseract and the rule engine are free; no per-scan API
  cost because v1 deliberately avoids a paid LLM dependency.

---

## PART D — Problem-statement compliance matrix (did we build what SIH26034 asked?)

Legend: ✅ built & tested · 🟡 built, partial / disclosed scope · ⬜ not in v1 (documented)

### "The system should be capable of:"
| PS requirement | Status | Where / how |
|---|---|---|
| Scanning and analyzing images of packaged commodities | ✅ | `POST /api/scans` upload → OpenCV decode → preprocess (deskew, CLAHE, upscale) → OCR. Resolution cap after a real OOM incident (`preprocess.cap_dimension`). |
| Detecting mandatory declarations prescribed under LM rules | ✅ | `extraction/fields.py` + `rules/mandatory_declarations.py` — 10 active checks spanning R6-1 through R6-11 (maker, COO, generic name, net qty, mfg date, best-before, MRP, consumer care, unit sale price, misleading-qualifier check). R6-8 (dimensions) is documented in `LEGAL_REQUIREMENTS.md` as category-dependent, not universal, and is deliberately not implemented as an active check — not an oversight. |
| Checking correctness, completeness **and placement** of declarations | ✅ | Correctness/completeness: Rule 6 checks. Placement: `rules/placement.py` — R8-1 (grouping / same principal display panel, 2D-cluster proxy) + R8-2 (net-quantity clear-space proviso, scale-invariant, no calibration). |
| Identifying missing or non-compliant declarations | ✅ | Each check returns PASS / FAIL / NEEDS_VERIFICATION / NOT_APPLICABLE with evidence + notes. 8 of the 12 demo labels are built to each trigger one specific violation; `test_e2e.py` asserts each fires. |
| Checking readability and font size requirements | 🟡 | `rules/font_size.py` — Rule 7 Table-I. Tier 1 (uncalibrated) = relative signal → NEEDS_VERIFICATION; Tier 2 (user reference dimension) = real mm check → hard PASS/FAIL. Honest limitation, disclosed in every report. Medical devices → NOT_APPLICABLE (GSR 778(E) carve-out). |
| Generating compliance reports and violation summaries | ✅ | `reports/pdf.py` (ReportLab, itemised + annotated image + methodology footer) and `reports/docx_export.py` (editable). Overall status + `compliance_score` as secondary summary, never instead of the checklist. |
| Maintaining a repository of scanned products and compliance history | ✅ | SQLAlchemy `Product` / `Scan` — stores raw OCR blob, declarations JSON, rule-results JSON, all images, both report files. `GET /api/scans` with text/status/date filters. |
| Providing dashboards for enforcement officials | ✅ | `GET /api/dashboard/summary` (admin-only) — total scans, status breakdown, 30-day volume trend, 10 most recent non-compliant scans. `frontend/src/pages/Dashboard.jsx`. |

### "Expected Solution:"
| PS requirement | Status | Where / how |
|---|---|---|
| User-friendly web and/or mobile-based application | ✅ | React + Vite web app, responsive, light/dark theme, contrast-verified ≥ 4.5:1, status never colour-only. |
| Automated extraction and validation of mandatory declarations | ✅ | See extraction + rule engine above. |
| Rule-based compliance checking for LM (Packaged Commodities) Rules, 2011 | ✅ | `rules/engine.py` runs all 14 checks; each cites its row in `docs/LEGAL_REQUIREMENTS.md`, which is itself cited to Gazette notifications. `RULESET_VERSION` stamped on every report. |
| Generation of digital compliance reports in PDF **and editable formats** | ✅ | PDF + DOCX, both generated per scan, downloadable via `/api/scans/{id}` report endpoints. |
| Dashboard for monitoring inspections, violations, product compliance | ✅ | Admin dashboard (above). |
| Search and retrieval of previously scanned products and reports | ✅ | Repository page + `GET /api/scans` filters + per-scan detail view with annotated image. |
| Technical documentation (architecture + deployment framework) | ✅ | `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`, `docs/LEGAL_REQUIREMENTS.md`, `docs/DESIGN_SYSTEM.md`. |

### "Key Functional Requirements:"
| PS requirement | Status | Where / how |
|---|---|---|
| Image upload and product scanning functionality | ✅ | Scan page; upload validation (extension, content-type, byte size, real decode) before pipeline. |
| Extraction of declarations + detection of mandatory declarations | ✅ | Multilingual, per-line script selection, native-numeral normalisation to Arabic digits. |
| Font size and readability analysis | 🟡 | Tier 1/Tier 2, disclosed limitation (see above). |
| Detection of missing, misleading or non-standard declarations | ✅ | R6-11 (Rule 12(6)) specifically checks for misleading qualifiers ("approx", "not less than", "average"…); missing/non-standard covered by Rule 6 checks. |
| Generation of compliance / non-compliance reports | ✅ | PDF + DOCX. |
| Attachment of photographs and supporting evidence | ✅ | Original + preprocessed + annotated (per-declaration bounding boxes + rule IDs) images stored and shown; embedded in PDF. |
| Repository of scanned products and inspection history | ✅ | As above. |
| Role-based user access and secure authentication | ✅ | JWT (`pyjwt` + bcrypt), roles `inspector` / `admin`, `require_role` dependency, no hardcoded secret fallback, rate limiting, CORS locked (not wildcard), no stack traces to client — all covered by `test_hardening.py`. |
| Dashboard for monitoring compliance status and enforcement activities | ✅ | Admin dashboard. |
| Export of reports to PDF and editable formats | ✅ | PDF + DOCX. |

### Deliberately out of v1 (documented in `ARCHITECTURE.md` §6, not hidden)
| Item | Why | Path to add |
|---|---|---|
| E-commerce product-listing scanning | v1 scans physical package photos | Field schema already accepts a listing text dump — no schema change needed |
| LLM extraction fallback | v1 is offline-first, no paid API dependency | Documented as the natural v2 for unusual layouts |
| Wholesale-package rules (Rule 24) | Retail packages only per scope | Add `wholesale` ruleset module |
| True 3D multi-panel reconstruction | Single 2D photo | R8-1 discloses it's a proxy in every result |
| Per-word OCR script segmentation | Per-line is enough for standard Indian labels | Documented known residual gap |
| Auto-applied exemptions (bidi, LPG, ≤10g/ml, seeds…) | Miscategorisation risk near a legal notice | `exemptions.py` lookup table + inspector confirmation |

**Bottom line for the panel:** every "should be capable of", "expected solution", and "key
functional requirement" bullet is implemented and tested, except font-size *absolute mm*
checking, which is physically impossible from an uncalibrated photo and is handled with an
honest two-tier design rather than a fabricated number. Two items (e-commerce listings, LLM
extraction) are scoped out of v1 with the integration path already built into the schema.
