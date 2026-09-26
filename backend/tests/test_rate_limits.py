"""AI-10: every AI/voice route is rate limited per client IP, each route group with its own budget."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())
SPEC = client.post("/api/generate", json={"template": "ramp", "params": {"total_rise_in": {"value": 15, "source": "user"}}, "meta": {}}).json()["spec"]


@pytest.fixture(autouse=True)
def _limits(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    monkeypatch.setenv("RATE_LIMIT_TTS_PER_MIN", "3")


def _edit():
    return client.post("/api/edit", json={"spec": SPEC, "utterance": "make it 6 inches wider"})


def _instructions():
    return client.post("/api/instructions", json={"spec": SPEC})


def _stt():
    return client.post("/api/voice/stt", files={"audio": ("a.webm", b"\x1aE\xdf\xa3fake", "audio/webm")})


def _tts():
    return client.post("/api/voice/tts", json={"text": "Cut all stringers."})


@pytest.mark.parametrize("call", [_edit, _instructions, _stt], ids=["edit", "instructions", "stt"])
def test_route_returns_429_after_the_general_limit(call):
    codes = [call().status_code for _ in range(3)]
    assert codes[:2] == [200, 200]
    assert codes[2] == 429
    assert call().json()["error"]["code"] == "RATE_LIMITED"


def test_tts_has_its_own_higher_limit():
    codes = [_tts().status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_route_groups_do_not_share_a_budget():
    assert [_edit().status_code for _ in range(3)][-1] == 429
    # Edit is exhausted; the others still have their full budget.
    assert _instructions().status_code == 200
    assert _stt().status_code == 200
    assert _tts().status_code == 200
