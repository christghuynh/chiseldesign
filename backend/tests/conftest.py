"""Shared test setup: no test may reach a paid API.

Runs before any test module imports the app, so these values win over the repo-root .env
(app.config only fills variables that are not already set). Tests that exercise a real code
path opt in explicitly with monkeypatch and a stubbed transport.
"""

import os

import pytest


def pytest_configure(config):
    os.environ["FAKE_AI"] = "1"
    os.environ["FAKE_VOICE"] = "1"
    # Blank keys: even a test that turns fake mode off without stubbing the transport fails
    # with AIUnavailable / VOICE_UNAVAILABLE instead of making a billed call.
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["ELEVENLABS_API_KEY"] = ""


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Every TestClient shares one client IP, so rate-limit counters would leak between tests."""
    from app.ai import ratelimit

    ratelimit.reset()
    yield
    ratelimit.reset()
