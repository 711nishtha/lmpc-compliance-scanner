"""Production-hardening regression tests (Part B).

These lock in behaviours that are easy to silently regress: a hardcoded secret creeping back,
CORS drifting to a wildcard, upload validation being bypassed, stack traces leaking to clients.
"""
import importlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rate_limit import reset_rate_limits


# ---------- B1: no hardcoded secret fallback ----------

def test_production_refuses_to_start_without_jwt_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    import app.config as config
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        importlib.reload(config)


def test_dev_secret_is_generated_not_a_committed_literal(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    import app.config as config
    importlib.reload(config)
    assert config.JWT_SECRET != "dev-secret-change-me"
    assert len(config.JWT_SECRET) >= 32
    # restore a deterministic dev state for any later import
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-suite")
    importlib.reload(config)


def test_no_hardcoded_secret_literal_anywhere_in_app():
    """Grep guard: the old committed fallback must not reappear."""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = [
        p for p in app_dir.rglob("*.py")
        if "dev-secret-change-me" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not offenders, f"hardcoded secret literal found in: {offenders}"


# ---------- B3: CORS is not a wildcard ----------

def test_cors_origins_are_explicit_not_wildcard():
    import app.config as config
    importlib.reload(config)
    assert "*" not in config.CORS_ORIGINS
    assert all(o.startswith("http") for o in config.CORS_ORIGINS)


# ---------- B5: unhandled errors do not leak internals ----------

def test_unhandled_exception_returns_generic_message_with_error_id():
    from app.main import unhandled_exception_handler
    import asyncio

    class _Req:
        method = "GET"
        class url:  # noqa: N801
            path = "/boom"

    resp = asyncio.get_event_loop().run_until_complete(
        unhandled_exception_handler(_Req(), ValueError("secret internal path C:/app/x.py"))
    )
    body = resp.body.decode()
    assert resp.status_code == 500
    assert "secret internal path" not in body
    assert "Traceback" not in body
    assert "error_id" in body


# ---------- B7: rate limiting ----------

def test_scan_rate_limit_trips_and_reports_retry_after(monkeypatch):
    import app.config as config
    import app.api.rate_limit as rl
    monkeypatch.setattr(rl, "SCAN_RATE_LIMIT", 3)
    monkeypatch.setattr(rl, "SCAN_RATE_WINDOW_SECONDS", 60)
    reset_rate_limits()

    class _Req:
        class client:  # noqa: N801
            host = "1.2.3.4"

    user = {"email": "a@example.com"}
    for _ in range(3):
        rl.enforce_scan_rate_limit(_Req(), user)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        rl.enforce_scan_rate_limit(_Req(), user)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers
    reset_rate_limits()


def test_rate_limit_is_per_identity_not_global(monkeypatch):
    import app.api.rate_limit as rl
    monkeypatch.setattr(rl, "SCAN_RATE_LIMIT", 2)
    reset_rate_limits()

    class _Req:
        class client:  # noqa: N801
            host = "1.2.3.4"

    for _ in range(2):
        rl.enforce_scan_rate_limit(_Req(), {"email": "one@example.com"})
    # A different user must still be allowed through.
    rl.enforce_scan_rate_limit(_Req(), {"email": "two@example.com"})
    reset_rate_limits()


# ---------- B2: upload validation constants are sane ----------

def test_upload_limits_configured():
    import app.config as config
    importlib.reload(config)
    assert 0 < config.MAX_UPLOAD_BYTES <= 64 * 1024 * 1024
    assert "image/jpeg" in config.ALLOWED_UPLOAD_CONTENT_TYPES
    assert "application/pdf" not in config.ALLOWED_UPLOAD_CONTENT_TYPES
    assert ".exe" not in config.ALLOWED_UPLOAD_EXTENSIONS
