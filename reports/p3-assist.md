# p3-assist report

Lane B — Edit, instructions, voice. Branch `p3/assist`. Full backend suite: **273 passed**
(101 in this lane's four new test files). CI env: `FAKE_AI=1 FAKE_VOICE=1 AUTH_DISABLED=1`.

## Done (tests passing)

- **AI-7 (B1): spoken numbers** — `backend/app/ai/numwords.py`, `tests/test_numwords.py` (61 cases).
  `material_words`, `length_words`/`inches_words` (round to 1/16, feet-and-inches ≥ 12″),
  `angle_words`, `cut_callout_spoken`, `cardinal_words`. Matches the strings in
  `fixtures/instructions/ramp_switchback.json`.
- **AI-5 (B2): POST /edit** — `ai/edit.py`, `ai/prompts/edit.md`, `api/edit.py`, `tests/test_edit.py`
  (15 cases). Builds `set_params`/`apply_fix`/`ask_clarification` tools; validates patch names/enums
  and clamps numbers to the template bounds (source `user`); `apply_fix` uses the rule's
  `fix.params_patch`; unknown name/enum/rule → clarification; text-only reply → clarification;
  `force_tool=True`; spoken one-sentence message built in code from patched values; AIUnavailable /
  AIInvalidOutput → **503 `AI_UNAVAILABLE`** (suggests sliders). Reads prior turns from
  `spec.meta['edit_turns']` (last 5). Engine is always called via `app.engine.generate` so tests
  monkeypatch it with an echoing fake.
- **AI-6 (B3): POST /instructions** — `ai/instructions.py`, `ai/prompts/instructions.md`,
  `ai/fakes/instructions.json`, `api/instructions.py`, `tests/test_instructions.py` (9 cases).
  Skeleton from `engine.get_skeleton`, cut list from `engine.generate`; Gemini (`call="instructions"`)
  rewrites; validation rejects invented `part_labels` and a step count outside ±3 of the skeleton →
  falls back to skeleton-derived steps; **all AI errors fall back with 200**. `cut_callouts[].spoken`
  always from `numwords`, never Gemini.
- **VOX-1 (B4): POST /voice/stt** — `voice/client.py`, `voice/stt.py`, `api/voice.py`,
  `tests/test_voice.py`. ElevenLabs Scribe via httpx (`POST /v1/speech-to-text`, `xi-api-key`,
  multipart `file`+`model_id`, default `scribe_v1`, parses `text`). Rejects > 2 MB (**413**) and
  non-audio types (**415**); missing key / timeout / upstream error → **503 `VOICE_UNAVAILABLE`**.
  `FAKE_VOICE=1` returns fixture text.
- **VOX-2 (B5): POST /voice/tts** — `voice/tts.py`, `voice/fakes/silent.mp3`, `api/voice.py`,
  `tests/test_voice.py` (16 voice cases total). ElevenLabs TTS
  (`POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_128`, JSON `{text, model_id}`, default
  `eleven_multilingual_v2`, returns `audio/mpeg`). sha256(voice+model+text) disk cache — a second
  identical request is served from disk (verified). Text > 500 chars → **422**. Cache dir:
  `TTS_CACHE_DIR` → else `<dir of DATABASE_PATH>/tts-cache` → else `backend/data/tts-cache`.
  `FAKE_VOICE=1` returns a committed silent MP3.

Endpoints, headers, model ids and response shapes for STT/TTS were checked against the current
official ElevenLabs docs (2026-09). No test reaches the real ElevenLabs API (there is no key);
real-path tests use `httpx.MockTransport`.

## Failed / partial
- None. VOX-1 has no exact 15 s duration check (no ffmpeg); relies on the 2 MB cap — see QUESTIONS.md.

## Questions logged (see QUESTIONS.md)
- **AI-5** — `EditRequest` has no history field; carrying turns in `spec.meta['edit_turns']` meanwhile.
- **VOX-1** — 15 s STT duration limit needs decoding; using the 2 MB size cap as a proxy.
- **INF-3 (reply to P4)** — TTS cache location decided (A+B): no compose change required.

## New dependencies
- `httpx==0.28.1` (pinned, main deps) — ElevenLabs REST calls. No new ElevenLabs SDK.

## Real API calls made
- Gemini: 2 real calls via `python -m app.ai.smoke` (generate_json + call_with_tools), both HTTP 200,
  ~1.2–1.6 s each, model `gemini-3.8-flash`. Confirms the client path that /edit and /instructions
  use. (Budget: 2 of 3 used; key never printed.)
- ElevenLabs: 0 (no key present; built and tested against mocked httpx + FAKE_VOICE).

## Check this in the morning
- The `/edit` and `/instructions` prompts (`ai/prompts/edit.md`, `instructions.md`) are first drafts —
  tune with the real Gemini once the demo spec exists.
- Confirm the `spec.meta['edit_turns']` approach vs. adding a real `history` field to `EditRequest`
  (contract change → `make types`).
- Rate limiting on /edit, /instructions, /voice/* is Lane A's (AI-10); wire it after merge.
- STT 15 s duration: decide whether to add ffprobe to the image (Lane C/P4 own the Dockerfile).
- Pick the ElevenLabs voice (`ELEVENLABS_VOICE_ID`) and add the key for a real voice smoke.
