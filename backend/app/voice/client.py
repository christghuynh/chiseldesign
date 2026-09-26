"""VOX: the one place that talks to ElevenLabs (speech-to-text and text-to-speech).

We call the ElevenLabs REST API directly through httpx (no extra SDK). Endpoints, headers, model ids
and response shapes were checked against the official docs (2026-09):
- STT:  POST https://api.elevenlabs.io/v1/speech-to-text  (multipart: file, model_id; header
        xi-api-key; JSON response with a "text" field).
- TTS:  POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128
        (JSON body {text, model_id}; header xi-api-key; returns MP3 audio bytes).

Behavior:
- API key from ELEVENLABS_API_KEY, voice from ELEVENLABS_VOICE_ID, read at call time.
- 20 s timeout. Missing key (and not fake mode) raises `VoiceUnavailable`, which the routes turn
  into 503 VOICE_UNAVAILABLE so the frontend falls back (typed input / browser speechSynthesis).
- `FAKE_VOICE=1` never touches the network: STT returns fixture text, TTS returns a short silent MP3.

The transport is a single function (`_client`) that tests replace with an httpx.MockTransport, so no
test reaches the real API. There is no ElevenLabs key in CI.
"""

from __future__ import annotations

import os

import httpx

import app.config  # noqa: F401  (loads the repo-root .env into os.environ)

API_BASE = "https://api.elevenlabs.io/v1"
TIMEOUT_S = 20.0
DEFAULT_STT_MODEL = "scribe_v1"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
TTS_OUTPUT_FORMAT = "mp3_44100_128"


class VoiceError(Exception):
    """Base: the voice service could not be used. Routes fall back to a non-voice path."""


class VoiceUnavailable(VoiceError):
    """No answer: missing key, timeout, network failure, or the request was rejected."""


def fake_mode() -> bool:
    return os.environ.get("FAKE_VOICE", "").strip().lower() in {"1", "true", "yes"}


def api_key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "").strip()


def voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID", "").strip()


def stt_model() -> str:
    return os.environ.get("ELEVENLABS_STT_MODEL", "").strip() or DEFAULT_STT_MODEL


def tts_model() -> str:
    return os.environ.get("ELEVENLABS_TTS_MODEL", "").strip() or DEFAULT_TTS_MODEL


def _client() -> httpx.Client:
    """The only place a network client is created. Tests replace this with a MockTransport client."""
    return httpx.Client(base_url=API_BASE, timeout=TIMEOUT_S)


def request(method: str, url: str, **kwargs) -> httpx.Response:
    """Make one ElevenLabs request with the api key header. Raises VoiceUnavailable on any failure."""
    key = api_key()
    if not key:
        raise VoiceUnavailable("ELEVENLABS_API_KEY is not set")
    headers = {"xi-api-key": key, **kwargs.pop("headers", {})}
    try:
        with _client() as client:
            response = client.request(method, url, headers=headers, **kwargs)
    except httpx.TimeoutException as exc:
        raise VoiceUnavailable(f"ElevenLabs timed out ({type(exc).__name__})") from exc
    except httpx.TransportError as exc:
        raise VoiceUnavailable(f"ElevenLabs is unreachable ({type(exc).__name__})") from exc
    if response.status_code >= 400:
        raise VoiceUnavailable(f"ElevenLabs returned HTTP {response.status_code}")
    return response
