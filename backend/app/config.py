"""Central runtime configuration, all environment-driven.

Production safety rule: anything security-sensitive must FAIL LOUDLY when it is missing in
production rather than silently falling back to a development default. A hardcoded dev fallback
that reaches production is a real and common failure mode — see JWT_SECRET below, which
previously defaulted to a fixed literal string committed to this repo.
"""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

# "development" | "production". Anything not explicitly "production" is treated as development.
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"


def _require_in_production(name: str, dev_default_factory, description: str) -> str:
    """Return an env var; in production refuse to start without it, in dev synthesise one."""
    value = os.environ.get(name)
    if value:
        return value
    if IS_PRODUCTION:
        raise RuntimeError(
            f"{name} is not set. It is mandatory when APP_ENV=production ({description}). "
            f"Refusing to start rather than fall back to a development value."
        )
    generated = dev_default_factory()
    logger.warning(
        "%s not set — using a generated development value. NEVER run production this way.", name
    )
    return generated


# ---- Auth ------------------------------------------------------------------------------------
# Dev fallback is randomly generated per process, not a fixed literal: a committed constant is
# forgeable by anyone who can read the repo. The cost is that dev tokens do not survive a restart,
# which is the correct trade.
JWT_SECRET = _require_in_production(
    "JWT_SECRET", lambda: secrets.token_urlsafe(48), "signs every access token"
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", str(60 * 12)))

# ---- Storage ---------------------------------------------------------------------------------
# Resolved against the backend package root, NOT the current working directory. The previous
# default ("backend/data/uploads") was cwd-relative, so running uvicorn from inside backend/
# silently created a nested backend/backend/data/ tree — which then escaped .gitignore and
# staged ~74 MB of generated reports and uploads. Mirrors how db.py resolves the SQLite path.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = os.environ.get("STORAGE_DIR") or str(_BACKEND_ROOT / "data" / "uploads")

# ---- Upload limits (enforced in api/scans.py before the OCR pipeline is touched) --------------
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))  # 12 MB
ALLOWED_UPLOAD_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
}
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# ---- CORS ------------------------------------------------------------------------------------
# Comma-separated list. Default covers the local Vite dev server only — never "*".
# A wildcard combined with allow_credentials=True is also rejected by browsers, so the previous
# ["*"] + credentials configuration was both insecure and functionally wrong.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# ---- Image processing resolution caps (ocr/preprocess.py) ------------------------------------
# Real-world root cause, measured, not assumed: a phone photo of a whole product (bottle/packet
# on a shelf, label filling ~3% of the frame -- not a pre-cropped label mockup like demo_data)
# routinely decodes to 4000x3000+ px. With no cap, preprocess()'s upscale_if_needed could then
# multiply that by up to 3x on EACH dimension, and every stage held its own full-resolution copy
# simultaneously. Measured before this fix: preprocess() + one annotation copy + a real Tesseract
# pass on a realistic simulated photo hit 367 MB RSS -- 72% of Render's free-tier 512 MB container,
# before FastAPI's own baseline or PDF generation. That is the exact shape of the "memory limit
# exceeded, instance restarted" failure.
#
# MAX_PROCESSING_DIMENSION caps the image immediately after decode, before ANY processing --
# every downstream array inherits this bound. 2200px is generous for OCR: printed retail-label
# text is legible at far lower effective DPI than a raw 12MP+ photo provides.
MAX_PROCESSING_DIMENSION = int(os.environ.get("MAX_PROCESSING_DIMENSION", "2200"))
# MAX_UPSCALED_DIMENSION is a second, independent ceiling on upscale_if_needed's OUTPUT, so a
# pathological median-text-height estimate (e.g. a photo that is almost entirely blank
# background) can never multiply its way past this regardless of the computed factor.
MAX_UPSCALED_DIMENSION = int(os.environ.get("MAX_UPSCALED_DIMENSION", "3200"))

# ---- Minimum image-quality floor (ocr/preprocess.py: assess_image_quality_floor) --------------
# Real bug, not a hypothetical: a 400x250px test photo (shorter side 250px) went through the
# entire pipeline with no gate at all and came back a normal-looking itemized report -- 0% pass,
# 5 FAILs, "manufacturer not found" etc -- indistinguishable from a genuine finding, on an image
# where no OCR engine could plausibly have read anything. Everything above was a ceiling (memory
# protection); nothing was a floor. These two constants close that gap. Both numbers were picked
# empirically against real measurements, not guessed:
#
#   MIN_IMAGE_SHORTER_SIDE_PX -- measured shorter-side across all 12 demo_data labels: 404-739px
#   (these are pre-cropped synthetic label mockups and must never be flagged). The known failing
#   case measures 250px. 320px sits with ~28% margin on both sides of that gap -- comfortably
#   below every demo label, comfortably above the failing case. A naive guess of "800px" (a
#   plausible-sounding floor for a real phone photo) would have false-positived on all 12 demo
#   labels, which run far smaller since they're pre-cropped mockups, not whole-shelf photos.
#
#   MIN_LAPLACIAN_VARIANCE -- variance of the Laplacian (edge energy) as a cheap blur/sharpness
#   signal: catches "high enough resolution but badly out of focus," a real failure mode a photo
#   can hit independently of resolution (confirmed: downscaling a sharp label to 400x250 actually
#   *raises* its measured variance to ~10800 via resize aliasing -- resolution and blur are
#   genuinely orthogonal failure modes, not the same check twice). Measured on real deployed
#   phone-camera scans (Aldi can, two Maggi retakes): 228-790. Measured on demo_data: 2474-6806.
#   Measured on synthetic Gaussian blur applied to a sharp demo label: mildly blurred (k=5) 362,
#   genuinely unreadable (k=9) 38. 100 sits below every real photo on file and above genuinely
#   unreadable blur, with margin on both sides.
MIN_IMAGE_SHORTER_SIDE_PX = int(os.environ.get("MIN_IMAGE_SHORTER_SIDE_PX", "320"))
MIN_LAPLACIAN_VARIANCE = float(os.environ.get("MIN_LAPLACIAN_VARIANCE", "100"))

# ---- Rate limiting (api/rate_limit.py) -------------------------------------------------------
SCAN_RATE_LIMIT = int(os.environ.get("SCAN_RATE_LIMIT", "12"))          # requests
SCAN_RATE_WINDOW_SECONDS = int(os.environ.get("SCAN_RATE_WINDOW_SECONDS", "60"))

# ---- API docs --------------------------------------------------------------------------------
# Deliberate decision, not an accidental default: docs stay ON in development (they double as
# judge-facing technical documentation for this prototype) and are OFF in production unless
# ENABLE_DOCS=true is set explicitly. See docs/DEPLOYMENT.md.
ENABLE_DOCS = os.environ.get(
    "ENABLE_DOCS", "false" if IS_PRODUCTION else "true"
).strip().lower() == "true"
