"""Minimal in-process rate limiter for the OCR scan endpoint.

Why this exists: a single scan costs ~1-3s of Tesseract CPU. Without a cap, an accidental retry
loop (or a demo laptop being hammered) exhausts OCR compute and makes the whole app appear hung.

Scope, stated honestly: this is a fixed-window counter held in process memory. It is correct for a
single-process deployment (what this prototype runs as) and is NOT a distributed rate limiter —
run more than one worker and each gets its own budget. For multi-worker production, move this to
Redis. Documented in docs/DEPLOYMENT.md rather than silently assumed.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.config import SCAN_RATE_LIMIT, SCAN_RATE_WINDOW_SECONDS

_lock = threading.Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request, user: dict | None) -> str:
    # Prefer the authenticated identity — it survives NAT/shared IPs and is what we actually
    # want to budget per. Fall back to peer IP for unauthenticated paths.
    if user and user.get("email"):
        return f"user:{user['email']}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def enforce_scan_rate_limit(request: Request, user: dict | None = None) -> None:
    key = _client_key(request, user)
    now = time.monotonic()
    cutoff = now - SCAN_RATE_WINDOW_SECONDS
    with _lock:
        recent = [t for t in _hits[key] if t > cutoff]
        if len(recent) >= SCAN_RATE_LIMIT:
            retry_after = max(1, int(SCAN_RATE_WINDOW_SECONDS - (now - recent[0])))
            _hits[key] = recent
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Scan rate limit reached ({SCAN_RATE_LIMIT} per "
                    f"{SCAN_RATE_WINDOW_SECONDS}s). Try again in {retry_after}s."
                ),
                headers={"Retry-After": str(retry_after)},
            )
        recent.append(now)
        _hits[key] = recent


def reset_rate_limits() -> None:
    """Test hook — the limiter is process-global, so tests must be able to clear it."""
    with _lock:
        _hits.clear()
