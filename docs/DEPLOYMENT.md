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

## 7. Pre-deploy checklist

```bash
cd backend
python -m pytest tests/ -q                    # 76 tests
alembic upgrade head
cd ../frontend
npm run build
node scripts/check-bundle-isolation.mjs       # 3D libs must not enter the app bundle
```
