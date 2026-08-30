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
