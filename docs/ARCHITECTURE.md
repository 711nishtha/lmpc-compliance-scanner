# Architecture — Legal Metrology Packaged Commodities Compliance Scanner (SIH26034)

## 1. Overview

A prototype that scans a photograph of a packaged commodity's label, extracts the declarations
mandated by the Legal Metrology (Packaged Commodities) Rules, 2011, checks each one against the
rule set documented in [`LEGAL_REQUIREMENTS.md`](LEGAL_REQUIREMENTS.md), and produces an itemized,
rule-cited compliance report (PDF + editable DOCX), stored in a searchable repository with a
dashboard for enforcement officials.

## 2. Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy (SQLite by default, swappable to Postgres via
  `DATABASE_URL` env var — see `backend/app/db.py`).
- **OCR:** Tesseract via `pytesseract`, `eng+hin+guj` language packs. **Requires the Tesseract
  binary to be installed on the host** (`apt install tesseract-ocr tesseract-ocr-hin
  tesseract-ocr-guj` on Debian/Ubuntu, or the Windows installer with those language packs — the
  UB-Mannheim build is the standard choice). If unavailable, OCR calls degrade to a clear "OCR
  engine unavailable" error rather than crashing — the rule engine and API are fully testable
  independent of a live OCR install (see `backend/tests/`). Verified against a real Tesseract
  5.4 install + real Devanagari/Gujarati script (not just the combined-model string) — see the
  script-detection note below and `backend/scripts/run_real_ocr_pipeline.py`.
- **OCR script selection:** `app/ocr/engine.py` gets word/line layout from one combined-model
  pass, then re-OCRs each merged line against only its dominant script's language model
  (`_dominant_script`: a region is restricted to eng/hin/guj only when every letter in it belongs
  to that one script; anything with letters from more than one script falls back to the combined
  model). This is deliberately *not* a highest-confidence-wins comparison — an earlier version
  tried that and it measurably picked a wrong-but-confident answer (the combined model misread
  "200 g" as "200 <Gujarati digit>" at confidence 90.5, beating the correct eng-only reading at
  86.0). Known residual gap: a genuinely mixed-script line whose only Latin content is a single
  unit letter immediately adjacent to a native-script digit (e.g. Devanagari "८० g") can still
  have that unit letter misread as a digit by every candidate model tried, English included —
  this is a per-line, not per-word, script decision, so a line that's legitimately "mostly
  Devanagari but ends in one Latin letter" has no single correct language to restrict to.
  Per-word (not per-line) script segmentation would close this; out of scope for this prototype.
  Digit *values* (not unit letters) that get OCR'd in the wrong script are still recovered by
  `app/extraction/fields.py`'s `_normalize_digits` regardless of which of the above happens —
  see `backend/tests/test_extraction.py`'s Devanagari/Gujarati digit tests.
- **Image processing:** OpenCV (`opencv-python-headless`) + Pillow for preprocessing.
- **Reports:** ReportLab (PDF), `python-docx` (editable export).
- **Auth:** JWT (`pyjwt` + `passlib[bcrypt]`), two roles: `inspector`, `admin`.
- **Frontend:** React + Vite, plain `fetch` calls, no state-management framework.

## 3. Directory layout

```
backend/app/
  main.py            FastAPI app, mounts routers
  db.py              SQLAlchemy engine/session, DATABASE_URL config
  config.py          Ruleset version, thresholds import from rules/
  ocr/
    preprocess.py     deskew, CLAHE contrast, upscale (OpenCV)
    engine.py         pytesseract wrapper, per-region language selection, confidence capture
  extraction/
    fields.py         regex/keyword-anchored extraction -> structured Declarations
    keywords.py       per-language (en/hi/gu) anchor terms for each field
  rules/
    schema.py         RuleResult, Status enum (PASS/FAIL/NEEDS_VERIFICATION), Declarations model
    mandatory_declarations.py   R6-1..R6-10 (Rule 6)
    font_size.py       Rule 7 Table-I/II, Tier 1 (relative) / Tier 2 (calibrated) checks
    placement.py        R8-1/R8-2 (Rule 2(h)/Rule 8) -- see LEGAL_REQUIREMENTS.md §10: R8-1 is a
                         2D-clustering proxy for "grouped on the same principal display panel",
                         R8-2 checks the net-quantity clear-space proviso directly (no
                         calibration needed, unlike Rule 7)
    engine.py          runs all rule functions over a Declarations object -> ComplianceReport
  reports/
    pdf.py             ReportLab itemized PDF export
    docx_export.py     python-docx editable export
  models/
    orm.py             Product, Scan, ComplianceReportRecord, User (SQLAlchemy)
  api/
    auth.py            JWT login, role dependency
    scans.py            upload/scan endpoint, retrieval, search
    reports.py          PDF/DOCX download endpoints
    dashboard.py         aggregate stats endpoint
backend/tests/
  test_rules.py        unit tests for every rule function: PASS/FAIL/NEEDS_VERIFICATION cases
  test_extraction.py   regex extraction tests
  test_e2e.py           demo_data images -> full pipeline -> expected verdicts
frontend/src/           React app: upload, report view, dashboard, search
demo_data/               synthetic mock label images + README describing which rule each exercises
docs/
  LEGAL_REQUIREMENTS.md  ground truth checklist (Step 0 output)
  ARCHITECTURE.md         this file
```

## 4. Pipeline

`Image` → **resolution cap** (see below) → **preprocess** (deskew, CLAHE, upscale small text) → **OCR** (per-region language pick,
confidence capture) → **extraction** (regex/keyword → `Declarations` object, each field carrying
its source OCR bounding box + confidence) → **rule engine** (`Declarations` → list of `RuleResult`,
each citing a row in LEGAL_REQUIREMENTS.md) → **report** (PDF/DOCX with itemized results,
annotated image, methodology footer) → **repository** (SQLAlchemy: `Scan` row links `Product`,
raw OCR blob, `Declarations` JSON, list of `RuleResult` JSON, and both exported files).

The primary output at every stage is **itemized and cited**, never a single opaque score. A
`compliance_score` is computed only as a secondary summary (`pass_count / applicable_count`) and
is always rendered alongside — never instead of — the itemized checklist.

### 4.1 Resolution cap — a real production incident, not a hypothetical

`demo_data/`'s mockups are small (under 1200px, pre-cropped to just the label). A real phone
photo of a whole product is a different shape of input entirely: 12–48MP, with the label
occupying a small fraction of the frame. Deployed with no pixel-dimension cap (only upload byte
size was capped), a real photo measurably drove a single request to **367 MB RSS** for
preprocessing + one annotation copy + a real Tesseract pass — 72% of Render's free-tier 512 MB
container — and OOM-killed the live instance mid-request.

Fix: `app/ocr/preprocess.py::cap_dimension()` downscales immediately after decode, before any
other processing, to `MAX_PROCESSING_DIMENSION` (2200px longest side, env-configurable);
`upscale_if_needed()` additionally enforces an absolute output ceiling (`MAX_UPSCALED_DIMENSION`,
3200px) independent of its relative-factor heuristic. Three intermediate full-resolution arrays
(`deskewed`, `contrast_normalized`, the raw `original`) that a grep of the entire codebase
confirmed had zero downstream consumers were also dropped from `PreprocessResult`. Measured
after the fix, the identical scenario: **192 MB** (moderate case) / **295 MB** (worst-case 48MP
photo) — see `backend/tests/test_memory_ceiling.py`, which locks this in with a real RSS
measurement rather than a code-review assumption.

## 5. Font-size / readability: Tier 1 vs Tier 2 (see LEGAL_REQUIREMENTS.md §5)

Absolute millimetre font height (as required by Rule 7 Table-I/II) **cannot** be derived from an
uncalibrated phone photo — there's no known pixels-per-mm ratio. This is a hard, honest limitation,
not a bug to hide:

- **Tier 1 (always available, no calibration):** compare the detected text-height (in pixels) of
  each declaration against the tallest declaration on the same label (typically the brand name).
  Flags disproportionately small MRP/net-quantity text — a real, common violation pattern — as a
  **relative** finding. Result status is always `NEEDS_VERIFICATION` with a note, never a hard
  Rule-7 PASS/FAIL, because no mm threshold was actually checked.
- **Tier 2 (opt-in, calibrated):** if the user supplies a known reference dimension (package
  width/height in mm, entered manually, or a reference card of known size placed in frame),
  compute pixels-per-mm and derive true text height in mm, then check directly against Table-I/II.
  Only Tier 2 results may return a hard `PASS`/`FAIL` against Rule 7.

The UI and PDF/DOCX report must visibly label which tier produced each font-size finding. Never
merge Tier 1 and Tier 2 into one undifferentiated "readability score."

## 6. What is NOT implemented in this prototype (explicit, for the pitch)

- Wholesale-package rules (Rule 24 area) — retail packages only.
- E-commerce listing scanning (schema supports it; scanner UI does not yet ingest listing text).
- LLM-based extraction fallback (Step 4 option (b)) — regex/keyword extraction (option (a)) only
  for this prototype; documented as the natural v2 extension for higher accuracy on unusual label
  layouts, at the cost of an external API dependency this offline-first v1 deliberately avoids.
- Any check whose underlying rule is marked "VERIFY WITH DoCA" in LEGAL_REQUIREMENTS.md returns
  `NEEDS_VERIFICATION`, never an automated PASS/FAIL.
- True multi-panel/3D package reconstruction. Placement check R8-1 (LEGAL_REQUIREMENTS.md §10)
  uses 2D bounding-box clustering on the single photographed image as a proxy for "same principal
  display panel" — it cannot tell a genuinely separate panel from an unusual-but-single-panel
  layout with certainty, and says so in every result's notes.
- Per-word script segmentation for OCR. The script-detection pre-pass (§2 above) decides
  language per merged *line*, not per word — see that section for the specific known failure
  mode this leaves open (a native-script digit immediately adjacent to a single Latin unit
  letter, on an otherwise single-script line, can still misread that unit letter). Confirmed via
  a real Tesseract run against `demo_data/11_hindi_gujarati_imported_missing_coo.png` — see
  `backend/scripts/run_real_ocr_pipeline.py`.

## 7. Honesty-by-construction in the UI/report

Every `RuleResult` carries: `rule_reference`, `requirement_text`, `status`, `evidence`
(extracted value + OCR bounding box + OCR confidence), and `notes`. The report's methodology
footer states the ruleset version, OCR engine/languages used, and which font-size tier was applied.
No accuracy numbers are claimed anywhere in the UI/pitch unless measured against
`demo_data`/a labeled test set — see `backend/tests/test_e2e.py`.
