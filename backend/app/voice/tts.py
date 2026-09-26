"""VOX-2: synthesize a short spoken line to MP3 via ElevenLabs, with a disk cache.

Answers P4's QUESTIONS.md entry (INF-3) with option A+B for the cache location:
- If `TTS_CACHE_DIR` is set, use it.
- else if `DATABASE_PATH` is set, use `<its directory>/tts-cache` (compose sets
  /data/sketchbuild.db, so the cache lands on the same persistent, writable volume — no compose
  change needed).
- else `backend/data/tts-cache` (gitignored) for local dev.

Cache key = sha256(voice_id + "\\0" + model + "\\0" + text); the file is `<key>.mp3`. A repeated
request for the same voice/model/text is served from disk without calling ElevenLabs.

Text longer than 500 characters is rejected (422) — spoken lines are single sentences. `FAKE_VOICE=1`
returns a short valid silent MP3 (committed fixture) without touching the network.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from app.config import REPO_ROOT
from app.voice.client import fake_mode, request, tts_model, voice_id, TTS_OUTPUT_FORMAT

log = logging.getLogger("app.voice")

MAX_TEXT_CHARS = 500
_FAKE_MP3_PATH = Path(__file__).parent / "fakes" / "silent.mp3"


class TextTooLong(Exception):
    """The text is longer than MAX_TEXT_CHARS (route -> 422)."""


def cache_dir() -> Path:
    override = os.environ.get("TTS_CACHE_DIR", "").strip()
    if override:
        base = Path(override)
    else:
        db_path = os.environ.get("DATABASE_PATH", "").strip()
        if db_path:
            base = Path(db_path).resolve().parent / "tts-cache"
        else:
            base = REPO_ROOT / "backend" / "data" / "tts-cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _cache_key(vid: str, model: str, text: str) -> str:
    digest = hashlib.sha256(f"{vid}\0{model}\0{text}".encode("utf-8")).hexdigest()
    return digest


def _cache_path(vid: str, model: str, text: str) -> Path:
    return cache_dir() / f"{_cache_key(vid, model, text)}.mp3"


def synthesize(text: str) -> bytes:
    """Return MP3 bytes for `text`, from cache when possible.

    Raises TextTooLong (route -> 422) or VoiceUnavailable (route -> 503).
    """
    text = text.strip()
    if len(text) > MAX_TEXT_CHARS:
        raise TextTooLong(f"Text is {len(text)} characters; the limit is {MAX_TEXT_CHARS}")

    if fake_mode():
        # Cache the silent MP3 too, so cache-hit tests work identically in fake mode.
        return _fake_audio(text)

    vid, model = voice_id(), tts_model()
    path = _cache_path(vid, model, text)
    if path.is_file():
        log.info("tts cache=hit")
        return path.read_bytes()

    log.info("tts cache=miss")
    response = request(
        "POST",
        f"/text-to-speech/{vid}",
        params={"output_format": TTS_OUTPUT_FORMAT},
        headers={"Content-Type": "application/json"},
        json={"text": text, "model_id": model},
    )
    audio = response.content
    _write_atomically(path, audio)
    return audio


def _fake_audio(text: str) -> bytes:
    audio = _FAKE_MP3_PATH.read_bytes()
    path = _cache_path(voice_id() or "fake-voice", tts_model(), text)
    if path.is_file():
        log.info("tts cache=hit")
        return path.read_bytes()
    log.info("tts cache=miss")
    _write_atomically(path, audio)
    return audio


def _write_atomically(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(".mp3.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
