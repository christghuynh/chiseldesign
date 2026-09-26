# Questions

### AI-5 — /edit has no history field for multi-turn clarification (p3/assist, 2026-09-26)
Question: EditResponse can set `needs_clarification`, and a good clarification flow ("wider" → "how much wider?" → "six inches") needs the model to see the earlier turns. `EditRequest` (models/api.py, a contract I can't edit) has only `{spec, utterance}`, so there is nowhere to send the prior turns.
Options I see: A) add an optional `history: list[{role, text}]` field to `EditRequest` (contract change, needs team announce + `make types`); B) carry the turns in `spec.meta['edit_turns']` (no contract change), the frontend appends each user utterance and each spoken reply.
What I did meanwhile: B. `/edit` reads `spec.meta.get('edit_turns')` (list of `{role, text}`), keeps the last 5, and passes them to Gemini as prior messages; malformed entries are ignored. If the team prefers A, the reader in `ai/edit.py::_history` moves to the new field with no other change.


### INF-3 — Where does the TTS cache live in the container? (p4/infra, 2026-09-26 03:00)
Question: PRD §14 has `DATABASE_PATH` but no variable for the ElevenLabs TTS cache (VOX-2, P3). In Docker only `/data` is a persistent, writable volume (the code is read-only to the non-root user), so a cache written next to the code would fail or be lost on every deploy.
Options I see: A) P3 adds a `TTS_CACHE_DIR` variable and compose sets it to `/data/tts-cache`; B) the voice module puts its cache next to the SQLite file (the directory of `DATABASE_PATH`).
What I did meanwhile: compose mounts a volume at `/data` and sets `DATABASE_PATH=/data/sketchbuild.db`. If A is chosen, it's one line in both compose files.

> **P3 reply (VOX-2, p3/assist, 2026-09-26):** Implemented A+B, no compose change required. `app/voice/tts.py::cache_dir()` uses `TTS_CACHE_DIR` if set; else `<dir of DATABASE_PATH>/tts-cache` when `DATABASE_PATH` is set (so in compose it lands at `/data/tts-cache` on the persistent volume automatically); else `backend/data/tts-cache` (already gitignored) for local dev. Cache key = `sha256(voice_id + model + text)`, file `<key>.mp3`. So option A works with zero compose change; if you'd rather set `TTS_CACHE_DIR=/data/tts-cache` explicitly in compose that's honoured too, but it isn't needed.

### VOX-1 — STT 15-second duration limit needs decoding (p3/assist, 2026-09-26)
Question: The task says reject clips longer than 15 s, but measuring duration of a webm/opus blob means decoding the container. The runtime image has no ffmpeg, and there's no pure-Python webm/opus duration reader I trust.
Options I see: A) rely on the 2 MB size cap as a conservative proxy (2 MB of Opus voice is well over 15 s, so anything ≤ 2 MB is fine and long clips get cut off by size); B) add ffmpeg/ffprobe to the image and decode to check duration.
What I did meanwhile: A. `/voice/stt` enforces the 2 MB (413) and audio-type (415) checks; there is no exact duration check. If a hard 15 s limit matters, adopt B (P4 owns the Dockerfile) and I'll add a `ffprobe`-based check behind an env flag.


### INF-3 — Where do the frontend's build-time VITE_* values (Auth0 SPA) come from on the VM? (p4/infra, 2026-09-26 03:00)
Question: the frontend is built inside Docker (`deploy/web.Dockerfile`) so the VM needs no Node. Vite bakes `VITE_*` values in at build time, from `frontend/.env*`, as a local `npm run build` does. The backend reads the root `.env`. So the VM needs two env files, or the root one has to feed the build.
Options I see: A) keep it: on the VM, put the `VITE_AUTH0_*` values in `frontend/.env` (gitignored; only `VITE_*` ends up in the bundle); B) pass them as build args from the root `.env` in `docker-compose.yml`, so there's one file.
What I did meanwhile: A, since it needs no code. B is ~6 lines once B5 (FE-11) fixes the variable names.


### FE-10 — Where the export client lives, and the CSV columns (p4/plan, 2026-09-26)
Question: The comment in `frontend/src/api/client.ts` says FE-10 adds the export calls there, but `api/` is P2's directory. And the fixture-mode CSV is built in the browser, so its columns should match what GEO-18's `/export/cutlist.csv` returns.
Options I see: A) Keep the export calls in `components/plan/exports.ts` (P4), which reuses `USE_FIXTURES` and `ApiError` from the client. B) Move them into `api/client.ts` after P2 agrees. For the CSV: GEO-18 adopts the columns below, or the frontend copies whatever GEO-18 ships.
What I did meanwhile: A. The local CSV columns are `label,name,material,actual_dims_in,length_in,length,qty,part_ids,cut_notes` (CRLF, RFC 4180 quoting). Filenames are `sketchbuild-<template>[-<layout>].step|stl` and `...-cut-list.csv`; a `Content-Disposition` filename from the server wins.

### FE-7 — Plan screen clears the 3D highlight when it opens and closes (p4/plan, 2026-09-26)
Question: The Plan screen resets `highlightedPartIds` on mount, when the plan changes, and on unmount, so Build mode (Lane B) and Design start clean. Is that OK with P2 (Design) and Lane B (Build mode sets its own highlight)?
Options I see: A) Keep it. B) Only clear on unmount.
What I did meanwhile: A.
