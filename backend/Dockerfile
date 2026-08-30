# LMPC Compliance Scanner — backend image.
#
# A Dockerfile (rather than Render's native Python runtime) is MANDATORY here: the OCR
# layer needs the Tesseract binary plus the Hindi and Gujarati language packs, and a
# native Python environment provides none of them. Without hin/guj the multilingual
# checks silently degrade to English-only.
#
# Also used unchanged by the documented Hugging Face Spaces (Docker SDK) fallback.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps:
#   tesseract-ocr{,-hin,-guj} — OCR engine + the two Indic language packs
#   libgl1 / libglib2.0-0     — required by opencv-python-headless at import time
#   libpq5                    — psycopg2 runtime for Postgres
#   curl                      — container HEALTHCHECK below
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-hin \
        tesseract-ocr-guj \
        libgl1 \
        libglib2.0-0 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Debian's tesseract-ocr-{hin,guj} packages ship the *fast* (quantised) models, which are
# measurably worse than the standard models used in local development: on the Gujarati
# demo label the fast guj model missed the manufacture date entirely and found only 2/4
# consumer-care fields, flipping the verdict NEEDS_VERIFICATION -> FAIL.
#   local guj.traineddata      1,963,128 bytes  (standard)
#   Debian guj.traineddata     1,418,394 bytes  (fast)
# Pull the standard models so deployed behaviour matches local. Pinned to a tagged
# release rather than main so a rebuild cannot silently change OCR behaviour.
ARG TESSDATA_REF=4.1.0
RUN set -eux;     TD=/usr/share/tesseract-ocr/5/tessdata;     for L in eng hin guj; do       curl -fsSL -o "$TD/$L.traineddata"         "https://raw.githubusercontent.com/tesseract-ocr/tessdata/${TESSDATA_REF}/$L.traineddata";     done;     ls -l "$TD"/eng.traineddata "$TD"/hin.traineddata "$TD"/guj.traineddata

WORKDIR /app

# Requirements first so the layer caches independently of application code.
COPY requirements.txt .
# psycopg2-binary is a deployment-only dependency: local dev defaults to SQLite, but
# Render's Postgres add-on hands us a postgresql:// URL that SQLAlchemy cannot open
# without a driver. Pinned like everything else in requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary==2.9.11

COPY . .

# Fail the build rather than the demo if a language pack is missing.
RUN tesseract --list-langs 2>&1 | grep -qx eng \
    && tesseract --list-langs 2>&1 | grep -qx hin \
    && tesseract --list-langs 2>&1 | grep -qx guj \
    && echo "OCR language packs present: eng, hin, guj"

# Uploads/reports live here. On Render's free tier this is EPHEMERAL — it is wiped on
# every deploy and on the free-tier sleep/wake cycle. Scan rows in Postgres survive;
# the stored images and generated report files do not. Attach a Render Disk (paid) to
# make it durable. Documented in docs/DEPLOYMENT.md.
ENV STORAGE_DIR=/app/data/uploads
RUN mkdir -p /app/data/uploads /app/data/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8000}/api/health || exit 1

# Render injects $PORT and expects the process to bind it on 0.0.0.0.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
