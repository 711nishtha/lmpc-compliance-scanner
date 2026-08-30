# Browser QA harness

Real Playwright scripts driving the actual running frontend + backend — no mocked API. These
caught real bugs that unit tests could not (an absent annotated-image feature, a date-filter that
excluded same-day scans, a role gate that existed only in the backend, a hero that pushed its own
stat row below the projector fold).

**These are not a substitute for looking.** Every script writes PNGs to `shots/`; the point is to
open them and check the UI actually shows what it should. "No console errors" is not a pass.

## Setup

```bash
npm install playwright && npx playwright install chromium
```

Start both servers first:

```bash
# backend  (needs tesseract on PATH)
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# frontend
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

## Order

`01_auth.js` must run first — it registers the inspector/admin accounts and writes
`inspector_state.json` / `admin_state.json`, which every other script loads for its session.

| Script | Checks |
|---|---|
| `01_auth.js` | Login for both roles; admin-only Dashboard gate is visibly different, not just a backend 403 |
| `02_scan_all.js` | Uploads all 12 demo labels through the real scan flow |
| `03_exports.js` | Downloads PDF + DOCX for a PASS-heavy and a FAIL-heavy scan |
| `04_repository.js` | Search by name, filter by status, filter by date range |
| `05_dashboard.js` | Aggregate counts — cross-check these by hand against the repository |
| `06_responsive.js` | 1280×720 projector resolution, viewport-only screenshots (not fullPage) |
| `07_slow_path.js` | Injects a 6s delay to confirm a real loading state, not a frozen screen |
| `08_error_path.js` | Blank + noise images — must show the advisory banner, never a false PASS |
| `10_restyle_check.js` | All app screens after a design change + horizontal-overflow assertion |
| `11_landing.js` | 3D landing: canvas present, WebGL live, **measured FPS**, per-section screenshots |

## Bundle isolation

Separate from these, and important after any landing-page change:

```bash
npm run build && node scripts/check-bundle-isolation.mjs
```

Fails the build if Three.js/GSAP ever end up in the same chunk as an authenticated screen.

## After running

`07`/`08` add throwaway scans. Reset before a demo:

```bash
# stop backend, then
rm -f backend/data/compliance.db backend/data/uploads/* backend/data/reports/*
# restart backend, then re-run 01 + 02 for a clean 12-scan state
```
