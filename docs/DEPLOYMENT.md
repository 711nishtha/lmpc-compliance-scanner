# Deployment & production hardening

This prototype is demo-grade but is configured so that production mistakes fail loudly rather
than silently. Read this before running it anywhere other than a local demo.

## 1. Environment variables

| Variable | Default (dev) | Production |
|---|---|---|
| `APP_ENV` | `development` | **must** be `production` |
| `JWT_SECRET` | randomly generated per process | **mandatory** — app refuses to start without it |
| `JWT_EXPIRE_MINUTES` | `720` (12h) | tighten as policy requires |
| `DATABASE_URL` | local SQLite file | e.g. `postgresql+psycopg2://user:pass@host/db` |
| `STORAGE_DIR` | `backend/data/uploads` | a persistent volume |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | your real frontend origin(s) |
| `MAX_UPLOAD_BYTES` | `12582912` (12 MB) | as policy requires |
| `SCAN_RATE_LIMIT` / `SCAN_RATE_WINDOW_SECONDS` | `12` / `60` | tune to OCR capacity |
| `ENABLE_DOCS` | `true` in dev, `false` in prod | set `true` only deliberately |
| `OCR_REFINE_WORKERS` | `4` | raise only on a host with more cores — see below |
| `GEMINI_API_KEY` | unset (vision pass disabled) | optional; enables vision-assisted extraction |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | pin deliberately — hosted model ids get retired |
| `GEMINI_TIMEOUT_SECONDS` | `30` | bound on how long a third-party call may add to a scan |
| `GEMINI_MAX_IMAGE_DIMENSION` | `1600` | payload cap; the OCR image is upscaled to 3200 |
| `VISION_EXTRACTION_ENABLED` | `true` | kill switch independent of the key |

`GEMINI_API_KEY` is deliberately **not** wrapped in the fail-loudly check that guards
`JWT_SECRET`: a missing vision key degrades accuracy, it does not weaken security, so refusing to
boot over it would be the wrong trade. With no key the scan pipeline runs on OCR alone and makes
no outbound call. `backend/.env` is gitignored and is a local-development convenience only —
production sets real environment variables, and a real env var always wins over the file.

**Model ids get retired.** `gemini-2.5-flash` returned HTTP 404 *"no longer available to new
users"* on a freshly issued key during this build. If scans start silently coming back OCR-only,
check the logs for a 404 from the vision call before suspecting the pipeline.

`JWT_SECRET` has **no hardcoded fallback**. In development a random secret is generated per
process (so dev tokens are not forgeable from a value committed to this repo); the trade-off is
that dev tokens do not survive a restart. In production a missing `JWT_SECRET` raises at import.

Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. Database schema — Alembic is authoritative

```bash
cd backend
alembic upgrade head
```

`init_db()`'s `create_all()` is **development only** and is skipped when `APP_ENV=production`, so
a production instance cannot silently build a schema no migration describes. After changing an
ORM model:

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head          # apply
python -m pytest tests/ -q    # verify
```

Alembic reads `DATABASE_URL` from the same place the app does (`app.db`), not from `alembic.ini`,
so migrations can never target a different database than the running app.

## 3. API documentation exposure — deliberate decision

Swagger/ReDoc/`openapi.json` are **on in development** and **off in production** unless
`ENABLE_DOCS=true`.

Rationale: for this prototype the interactive docs double as judge-facing technical documentation,
so they stay available in the demo environment. In a real deployment they enumerate every endpoint
and schema to unauthenticated visitors, which is reconnaissance value with no operational benefit
— so the default flips. If enabled in production, startup logs a warning so it is never accidental.

## 4. Rate limiting — known scope limit

`app/api/rate_limit.py` is a fixed-window counter **in process memory**. It is correct for a
single-process deployment (what this runs as) and is **not** distributed: run multiple workers and
each gets its own budget. For multi-worker production, move the counter to Redis. Stated here
rather than assumed.

Requests that fail upload validation still consume budget — deliberate, so malformed uploads
cannot be used to hammer the endpoint for free.

## 5. Error handling

Deliberate `HTTPException`s (OCR unavailable, rate limited, validation) pass their message through
to the client because those messages are operator-facing and actionable. Any **unhandled**
exception returns a generic message plus a short `error_id`; the full traceback goes to the server
log against that same id. Stack traces and internal file paths never reach the frontend.

## 6. Tesseract

The OCR binary is a system dependency, not a Python package:

```bash
apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-guj   # Debian/Ubuntu
```

Without it the scan endpoint returns a clear 503; every other endpoint keeps working.

## 7. Concurrency and memory

`OCR_REFINE_WORKERS` (default 4) controls how many Tesseract subprocesses refine line crops at
once. Measured on a 33-region composite matching a real phone photo: a full two-pass scan went
from **11.2s to 4.9s**, with byte-identical output across all 12 demo labels.

The memory cost lives in **child** processes, which never appear in this process's RSS — so
`tests/test_memory_ceiling.py` structurally cannot see it. Sampled directly: peak combined child
RSS was **112 MB at 1 worker vs 111 MB at 4**, unchanged, because peak child memory is set by the
one full-image pass, not by the refinement crops. That headroom is only free while the crops stay
small; raising this to where several full-image passes could overlap would spend it. Beyond 4 the
returns flatten, and Render's free tier has far fewer cores than a dev box.

`OMP_THREAD_LIMIT=1` is set at import in `app/ocr/engine.py` so those pooled processes do not each
fan out their own OpenMP thread team on a single shared vCPU.

## 8. Scan latency — set expectations

A real phone photo now takes roughly **20–30s** end to end (two OCR passes ~18s, vision pass
4–6s, then rules, annotation and both report exports). This is not a regression: it is the
pipeline actually reading a hard label rather than failing fast on a bad deskew. The UI shows a
staged, indeterminate progress list, never a fabricated percentage.

Render free-tier web services also **sleep when idle** and take ~50s to wake, so the first scan
after a quiet period will look far slower than the numbers above.

## 9. Pre-deploy checklist

```bash
cd backend
python -m pytest tests/ -q                    # 170 tests
alembic upgrade head                          # includes a3f81c7d9e42 (rule_verifications)
cd ../frontend
npm run build
node scripts/check-bundle-isolation.mjs       # 3D libs must not enter the app bundle
```

This release adds a migration (`rule_verifications`, the human-verification audit trail) and a
new direct runtime dependency (`httpx`, pinned in `backend/requirements.txt` for the vision
call). `alembic upgrade head` is **required** on an existing instance — without it, verifying a
finding will fail on a missing table.
