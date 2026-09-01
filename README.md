# Legal Metrology Packaged Commodities Compliance Scanner (SIH26034)

Prototype for **Ministry of Consumer Affairs, Food & Public Distribution / Department of
Consumer Affairs (DoCA)** — Smart India Hackathon problem statement SIH26034. Scans packaged
commodity labels and checks the declarations against the **Legal Metrology (Packaged
Commodities) Rules, 2011**, producing an itemized, rule-cited compliance report.

## Live demo

<!-- TODO: fill in once the deployment completes. -->

| Service | URL |
|---|---|
| Frontend (Render Static Site) | <https://lmpc-compliance-scanner-1.onrender.com> |
| Backend API (Render Web Service) | <https://lmpc-compliance-scanner.onrender.com> |
| API docs (Swagger) | disabled in this deployment (`ENABLE_DOCS` unset — off by default in production, see `docs/DEPLOYMENT.md`) |

Demo accounts (seeded by `backend/scripts/seed_demo.py`):

| Role | Email | Password |
|---|---|---|
| Inspector | `inspector1@example.com` | `password123` |
| Admin (dashboard) | `admin1@example.com` | `password123` |

> The backend runs on Render's **free tier**, which sleeps after ~15 minutes idle.
> `.github/workflows/keepalive.yml` pings it every 11 minutes to avoid a ~50s cold start.
> If the first request is slow, that is the cold start, not the OCR pipeline.

Start here:
- [`docs/LEGAL_REQUIREMENTS.md`](docs/LEGAL_REQUIREMENTS.md) — the source-cited legal checklist every rule check implements. Read this before touching `backend/app/rules/`.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — pipeline design, stack, and the honest Tier 1/Tier 2 font-size limitation.
- [`demo_data/README.md`](demo_data/README.md) — which rule violation each synthetic mock label exercises.

## What it does

- **Multilingual OCR** — Tesseract with `eng` + `hin` + `guj`, run per-region with a
  dominant-script pre-pass, so a bilingual label is not forced through one model.
  Native-script numerals are normalised to Arabic digits before any value is parsed.
  Region refinement runs concurrently (`OCR_REFINE_WORKERS`), which took a two-pass scan of a
  real 33-region photo from 11.2s to 4.9s for byte-identical output.
- **Optional second reading by a vision model** — Gemini reads the same photograph into the same
  declaration fields, and the two engines are merged per field. Tesseract has a measured ceiling
  on real packaging (glossy foil, curvature, partial defocus); on a real retail packet the vision
  pass recovered the manufacturer, consumer-care block, unit sale price and tax qualifier that OCR
  could not resolve. Each value records its provenance — `ocr`, `vision`, or `ocr+vision` when
  both engines agree, which is the strongest corroboration the pipeline can produce.
  **The vision model never decides compliance**: every PASS/FAIL still comes from the
  deterministic, rule-citing engine. It supplies evidence; the rules supply judgement.
  Entirely optional — with no API key the pipeline runs on OCR alone, exactly as before.
- **14 itemised rule checks** — Rule 6 mandatory declarations, Rule 7 numeral height
  (Table-I, with the G.S.R. 778(E) medical-device carve-out), and Rule 8 **placement**
  (R8-1/R8-2: the quantity declaration's clear-space requirement).
- **Every verdict cited** to the clause it came from; anything unconfirmed against the
  Gazette text returns `NEEDS_VERIFICATION` rather than a fabricated pass or fail.
- **Annotated label image** with per-declaration bounding boxes and rule IDs.
- **Report export** — rule-cited **PDF** and an editable **DOCX**.
- **Searchable repository** of past scans plus an **enforcement dashboard** (admin-only)
  with status breakdown, 30-day volume, and non-compliant scans needing follow-up.
- **Human verification of an undecided finding** — an admin can resolve a `NEEDS_VERIFICATION`
  result to PASS after checking the physical package. Constrained deliberately: admin-only, only
  from `NEEDS_VERIFICATION` (a FAIL is a positive finding and can never be cleared this way), and
  never silent — the engine's original result, the verifying admin and the timestamp are recorded
  on the result and written to an append-only audit table, and the disclosure is carried into the
  PDF and DOCX exports.
- **Light/dark theme**, contrast-verified in both (>= 4.5:1); status colour is always
  backed by a text label and a glyph, never colour alone.
- **An instrument, not a dashboard** — the authenticated app is built from the vocabulary of real
  measuring tools (calibration tick scales, viewfinder brackets, engraved gauge readouts), which
  is the domain's own language: Legal *Metrology* is the science of measurement. See
  [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md).

## Quick start

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
API docs at `http://localhost:8000/docs`. SQLite DB is created automatically at `backend/data/compliance.db`.

**OCR requires the Tesseract binary** (with `eng`, `hin`, `guj` language packs) installed
separately — it is not bundled with the `pip install` path above. Without it, the `/api/scans`
upload endpoint returns a clear 503 rather than fabricating results; the rule engine, extraction,
reports, auth, dashboard, and repository endpoints all work without it.

**Optional — vision-assisted extraction.** Set `GEMINI_API_KEY` to have a vision model read the
label alongside Tesseract and fill in what OCR cannot resolve. Create `backend/.env` (gitignored):

```
GEMINI_API_KEY=your-key-from-aistudio.google.com
GEMINI_MODEL=gemini-3.1-flash-lite
```

Without a key nothing changes and no network call is made — scans run on OCR alone. Model
availability on hosted APIs moves on the provider's schedule, so `GEMINI_MODEL` is overridable:
if scans suddenly come back OCR-only, check the logs for a 404 before suspecting the pipeline.

**To scan without installing Tesseract locally, run the backend via Docker instead** — the image
bundles Tesseract with all three language packs, so this is the one-command path to a fully
working scan endpoint on a machine with nothing but Docker installed:
```bash
cd backend
docker build -t lmpc-backend .
docker run -p 8000:8000 -e JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))") lmpc-backend
```
Then point the frontend (below) or `curl`/Swagger at `http://localhost:8000` as usual. This is
the same image the Render deployment runs, so behaviour matches the live demo exactly.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173`, proxying `/api` to the backend on port 8000.

### Tests
```bash
cd backend
python -m pytest tests/ -q
```
76 tests: rule-engine PASS/FAIL/NEEDS_VERIFICATION coverage for every check (including placement,
R8-1/R8-2 — see docs/LEGAL_REQUIREMENTS.md §10), extraction unit tests, and an end-to-end
walkthrough of all 12 demo_data mock labels (3 with real Devanagari/Gujarati script, 1 with a
deliberate placement violation) verifying each one is flagged for the specific violation it was
built to exercise, plus production-hardening regression tests (no hardcoded secret fallback,
CORS not a wildcard, upload validation, rate limiting, no stack traces leaked to clients).

### Regenerating demo data
```bash
cd backend
python scripts/generate_demo_labels.py      # regenerate the 12 mock label images
```

### Seeding an instance with the demo scans
Works against localhost or any deployed instance — it drives the real HTTP API, so a
successful run doubles as an end-to-end check of a deployment:
```bash
python backend/scripts/seed_demo.py --base-url https://<backend>.onrender.com
```

## Deployment

The backend ships as a Docker image (`backend/Dockerfile`) that bundles Tesseract with the
`eng`/`hin`/`guj` language packs; the frontend is a static Vite build (`npm run build` ->
`dist/`). Configuration, environment variables, the migration workflow and the runtime
notes are documented in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

The frontend needs `VITE_API_BASE_URL` set at **build** time to the backend's origin;
without it the app falls back to same-origin `/api` requests, which only work behind the
local Vite dev proxy.

## What this prototype is honest about

- Any legal threshold not independently confirmed from primary source text is marked
  **"VERIFY WITH DoCA"** in `docs/LEGAL_REQUIREMENTS.md` and never resolves to an automated
  PASS/FAIL in the rule engine — see that file's §9 for the full list.
- Font-size/readability checks are two-tier: **Tier 1** (no calibration) gives a relative signal
  only; **Tier 2** (user supplies a reference dimension) gives a calibrated mm measurement against
  Rule 7's tables. The UI/report always states which tier produced a given finding.
- No accuracy numbers are claimed anywhere in this repo beyond what `backend/tests/` actually
  measures against `demo_data/`.
- The vision model is an **extraction** aid only and is never allowed to determine compliance. A
  legal-metrology finding that cannot be reproduced or traced to a cited rule is not worth having,
  and a non-deterministic verdict on the same photograph would be exactly that.
- Where OCR and the vision model **disagree** about a declaration, neither silently wins: the
  field is reported as needing verification with both readings shown. This was not theoretical —
  on a real packet the vision model consistently swapped the packing and use-by dates in a
  two-column block that OCR's geometric row-pairing had read correctly.
- A human-verified PASS is never rendered as though the engine reached it: the automated result,
  the verifying admin and the timestamp travel with the finding into every export.
