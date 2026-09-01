"""Test-wide safety net: no test may make a live vision-API call.

app/config.py loads backend/.env for local development convenience, which means a developer with
a real GEMINI_API_KEY on disk would otherwise have the suite silently start calling a paid,
rate-limited third-party service -- slow, non-deterministic, and quietly dependent on network
access in CI. Vision behaviour is covered by tests/test_vision.py, which mocks the transport.

Autouse and session-scoped so it applies before any test imports or calls into app.vision.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _no_live_vision_calls(monkeypatch):
    from app.vision import gemini

    monkeypatch.setattr(gemini, "VISION_EXTRACTION_ENABLED", False, raising=False)
    monkeypatch.setattr(gemini, "GEMINI_API_KEY", "", raising=False)
