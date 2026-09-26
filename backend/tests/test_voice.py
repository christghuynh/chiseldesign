"""VOX-1 / VOX-2 tests. FAKE_VOICE mode by default; real paths use httpx.MockTransport.

No test reaches the real ElevenLabs API (there is no key in CI). The real-path tests replace
`voice.client._client` with an httpx.Client bound to a MockTransport so we can assert the exact
endpoint, headers, model ids and how each response is parsed, per the official docs.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.voice import client as voice_client
from app.voice import stt as stt_mod
from app.voice import tts as tts_mod

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fake_voice_and_no_network(monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_VOICE", "1")
    # Point the TTS cache at a temp dir so tests don't touch the real cache or the repo.
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "tts-cache"))
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")

    def _refuse():
        raise AssertionError("a test tried to open a real ElevenLabs client")

    monkeypatch.setattr(voice_client, "_client", _refuse)


@pytest.fixture
def real_voice(monkeypatch, tmp_path):
    """Real code path with a scripted httpx MockTransport. Returns the recorded requests + a setter."""
    monkeypatch.setenv("FAKE_VOICE", "0")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "tts-cache"))
    recorded: list[httpx.Request] = []
    state: dict = {"handler": None}

    def _handler(req: httpx.Request) -> httpx.Response:
        recorded.append(req)
        return state["handler"](req)

    def _make_client():
        return httpx.Client(base_url=voice_client.API_BASE, transport=httpx.MockTransport(_handler))

    monkeypatch.setattr(voice_client, "_client", _make_client)
    return recorded, state


# ---------------------------------------------------------------------------------------------
# STT — fake mode and validation


def test_stt_fake_returns_fixture_text():
    r = client.post("/api/voice/stt", files={"audio": ("clip.webm", b"\x00" * 100, "audio/webm")})
    assert r.status_code == 200
    assert r.json()["text"] == stt_mod.FAKE_TRANSCRIPT


def test_stt_rejects_oversized_audio_with_413():
    big = b"\x00" * (stt_mod.MAX_AUDIO_BYTES + 1)
    r = client.post("/api/voice/stt", files={"audio": ("big.webm", big, "audio/webm")})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_stt_rejects_non_audio_type_with_415():
    r = client.post("/api/voice/stt", files={"audio": ("note.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_stt_accepts_audio_at_the_size_limit():
    ok = b"\x00" * stt_mod.MAX_AUDIO_BYTES
    r = client.post("/api/voice/stt", files={"audio": ("clip.webm", ok, "audio/webm")})
    assert r.status_code == 200


# ---------------------------------------------------------------------------------------------
# STT — real path (mocked httpx) verifies the ElevenLabs contract


def test_stt_real_path_calls_elevenlabs_and_parses_text(real_voice):
    recorded, state = real_voice
    state["handler"] = lambda req: httpx.Response(200, json={"language_code": "en", "text": "make it wider"})
    r = client.post("/api/voice/stt", files={"audio": ("clip.webm", b"\x01\x02\x03", "audio/webm")})
    assert r.status_code == 200
    assert r.json()["text"] == "make it wider"

    sent = recorded[0]
    assert sent.method == "POST"
    assert str(sent.url) == f"{voice_client.API_BASE}/speech-to-text"
    assert sent.headers["xi-api-key"] == "test-key-not-real"
    body = sent.content.decode("latin-1")
    assert "scribe_v1" in body  # default model id sent as a form field
    assert 'name="file"' in body and 'name="model_id"' in body


def test_stt_missing_key_returns_503(monkeypatch, real_voice):
    _, state = real_voice
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    r = client.post("/api/voice/stt", files={"audio": ("clip.webm", b"\x01", "audio/webm")})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "VOICE_UNAVAILABLE"


def test_stt_upstream_error_returns_503(real_voice):
    _, state = real_voice
    state["handler"] = lambda req: httpx.Response(500, text="boom")
    r = client.post("/api/voice/stt", files={"audio": ("clip.webm", b"\x01", "audio/webm")})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "VOICE_UNAVAILABLE"


def test_stt_timeout_returns_503(real_voice):
    _, state = real_voice

    def _raise(req):
        raise httpx.ReadTimeout("scripted", request=req)

    state["handler"] = _raise
    r = client.post("/api/voice/stt", files={"audio": ("clip.webm", b"\x01", "audio/webm")})
    assert r.status_code == 503


# ---------------------------------------------------------------------------------------------
# TTS — fake mode, validation, cache


def _is_mp3(data: bytes) -> bool:
    return data[:2] == b"\xff\xfb" or data[:3] == b"ID3"


def test_tts_fake_returns_a_valid_silent_mp3():
    r = client.post("/api/voice/tts", json={"text": "Widened to forty-two inches."})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert _is_mp3(r.content) and len(r.content) > 0


def test_tts_rejects_text_over_500_chars_with_422():
    r = client.post("/api/voice/tts", json={"text": "x" * 501})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "TEXT_TOO_LONG"


def test_tts_accepts_text_at_the_limit():
    r = client.post("/api/voice/tts", json={"text": "x" * 500})
    assert r.status_code == 200


def test_tts_second_identical_request_is_served_from_cache(real_voice, monkeypatch, tmp_path):
    recorded, state = real_voice
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "cache2"))
    audio = b"\xff\xfb\x90\x00" + b"\x00" * 400
    state["handler"] = lambda req: httpx.Response(200, content=audio, headers={"content-type": "audio/mpeg"})

    r1 = client.post("/api/voice/tts", json={"text": "Same line."})
    assert r1.status_code == 200 and r1.content == audio
    r2 = client.post("/api/voice/tts", json={"text": "Same line."})
    assert r2.status_code == 200 and r2.content == audio
    # Only the first request hit ElevenLabs; the second came from disk.
    assert len(recorded) == 1


def test_tts_real_path_calls_elevenlabs_with_voice_and_model(real_voice, monkeypatch, tmp_path):
    recorded, state = real_voice
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "cache3"))
    audio = b"\xff\xfb\x90\x00" + b"\x00" * 100
    state["handler"] = lambda req: httpx.Response(200, content=audio)
    r = client.post("/api/voice/tts", json={"text": "Hello there."})
    assert r.status_code == 200

    sent = recorded[0]
    assert sent.method == "POST"
    assert str(sent.url).startswith(f"{voice_client.API_BASE}/text-to-speech/test-voice")
    assert "output_format=mp3_44100_128" in str(sent.url)
    assert sent.headers["xi-api-key"] == "test-key-not-real"
    payload = json.loads(sent.content)
    assert payload["text"] == "Hello there."
    assert payload["model_id"] == "eleven_multilingual_v2"


def test_tts_missing_key_returns_503(monkeypatch, real_voice):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    r = client.post("/api/voice/tts", json={"text": "Hi."})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "VOICE_UNAVAILABLE"


# ---------------------------------------------------------------------------------------------
# Cache location resolution (B5 decision A+B)


def test_cache_dir_prefers_tts_cache_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "explicit"))
    assert tts_mod.cache_dir() == (tmp_path / "explicit")


def test_cache_dir_falls_back_to_database_path_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("TTS_CACHE_DIR", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "data" / "sketchbuild.db"))
    assert tts_mod.cache_dir() == (tmp_path / "data" / "tts-cache")
