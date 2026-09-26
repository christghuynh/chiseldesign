"""VOX-1: transcribe a short recorded audio clip to text via ElevenLabs Scribe.

Validation lives here so the route stays thin:
- Reject audio larger than 2 MB (413) and non-audio content types (415).
- A hard 15 s duration limit would need decoding the container; without ffmpeg we can't do that
  reliably for webm/opus, so we rely on the 2 MB size cap as a proxy and log the limitation
  (see QUESTIONS.md). At the app's 128 kbps-ish voice clips, 2 MB is comfortably over 15 s, so the
  cap is conservative on size and permissive on the exact duration.

`FAKE_VOICE=1` returns fixture text without touching the network.
"""

from __future__ import annotations

import logging

from app.voice.client import fake_mode, request, stt_model

log = logging.getLogger("app.voice")

MAX_AUDIO_BYTES = 2 * 1024 * 1024  # 2 MB
FAKE_TRANSCRIPT = "make the ramp six inches wider"


class AudioTooLarge(Exception):
    """The clip is larger than MAX_AUDIO_BYTES (route -> 413)."""


class UnsupportedAudioType(Exception):
    """The content type is not an audio type (route -> 415)."""


def _check(content_type: str | None, data: bytes) -> None:
    if content_type is None or not content_type.split(";")[0].strip().lower().startswith("audio/"):
        raise UnsupportedAudioType(f"Unsupported audio type: {content_type!r}")
    if len(data) > MAX_AUDIO_BYTES:
        raise AudioTooLarge(f"Audio is {len(data)} bytes; the limit is {MAX_AUDIO_BYTES} bytes (2 MB)")


def transcribe(data: bytes, content_type: str | None, *, filename: str = "audio.webm") -> str:
    """Validate and transcribe. Raises AudioTooLarge / UnsupportedAudioType, or VoiceUnavailable."""
    _check(content_type, data)
    if fake_mode():
        return FAKE_TRANSCRIPT

    response = request(
        "POST",
        "/speech-to-text",
        files={"file": (filename, data, content_type)},
        data={"model_id": stt_model()},
    )
    body = response.json()
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str):
        from app.voice.client import VoiceUnavailable

        raise VoiceUnavailable("ElevenLabs did not return a transcript")
    return text.strip()
