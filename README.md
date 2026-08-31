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
- **13 itemised rule checks** — Rule 6 mandatory declarations, Rule 7 numeral height
  (Table-I, with the G.S.R. 778(E) medical-device carve-out), and Rule 8 **placement**
  (R8-1/R8-2: the quantity declaration's clear-space requirement).
- **Every verdict cited** to the clause it came from; anything unconfirmed against the
  Gazette text returns `NEEDS_VERIFICATION` rather than a fabricated pass or fail.
- **Annotated label image** with per-declaration bounding boxes and rule IDs.
- **Report export** — rule-cited **PDF** and an editable **DOCX**.
- **Searchable repository** of past scans plus an **enforcement dashboard** (admin-only)
  with status breakdown, 30-day volume, and non-compliant scans needing follow-up.
- **Light/dark theme**, contrast-verified in both (>= 4.5:1); status colour is always
  backed by a text label and a glyph, never colour alone.

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
