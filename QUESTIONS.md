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

Reply (GEO-18, Lane C, 2026-09-26): confirmed. `/export/cutlist.csv` now ships exactly those 9 columns in that order, CRLF line endings, RFC 4180 quoting (stdlib `csv`, `QUOTE_MINIMAL`). `part_ids` are space-joined, `cut_notes` joined with `"; "`, matching your `exports.ts`. The server sets `Content-Disposition: attachment; filename="sketchbuild-<template>[-<layout>]-cut-list.csv"` (layout dropped when absent or `auto`), so the header filename matches your fixture-mode fallback and your client's "server filename wins" rule. STEP/STL use `sketchbuild-<template>[-<layout>].step|stl`. The plan is computed via `engine.generate`, so when P1 lands the real engine the CSV updates automatically.

### FE-7 — Plan screen clears the 3D highlight when it opens and closes (p4/plan, 2026-09-26)
Question: The Plan screen resets `highlightedPartIds` on mount, when the plan changes, and on unmount, so Build mode (Lane B) and Design start clean. Is that OK with P2 (Design) and Lane B (Build mode sets its own highlight)?
Options I see: A) Keep it. B) Only clear on unmount.
What I did meanwhile: A.


### AI-2 — parse.json fake shape changed to a LIST; one AI-1 test updated (Lane A — Parse, 2026-09-26 05:xx)
Question: The lane decision requires `ai/fakes/parse.json` to represent params as a LIST of `{name, value, unit, confidence, source}` (better for Gemini structured output). The already-merged AI-1 test `tests/test_ai_client.py::test_shipped_parse_fake_is_used_when_nothing_is_queued` asserted the OLD dict-keyed shape (`out["params"]["total_rise_in"]["value"]`). The two shapes are mutually exclusive, and the common rules require the full suite to stay green.
Options I see: A) update the single assertion in that AI-1 test to read the list shape (intent-preserving); B) keep the fake dict-shaped and abandon the list decision.
What I did meanwhile: A. Changed only the two assertion lines in that test to `rise = next(p for p in out["params"] if p["name"] == "total_rise_in")`, with a comment pointing here. Please confirm at merge; the AI-1 owner may prefer to own that edit.

### AI-3 — measurements field shape is defined by this lane (Lane A — Parse, 2026-09-26 05:xx)
Question: The frontend sends `measurements` as an opaque JSON blob (`unknown` in `frontend/src/api/client.ts`); its shape was never pinned down. The Capture form (PRD §4.1) collects total rise, available length, desired width and a contractor quote.
Options I see: A) accept a flat object with both form-field names and canonical param keys; B) require canonical `*_in` keys only.
What I did meanwhile: A. `parse_measurements()` maps aliases (`total_rise`/`rise`→`total_rise_in`, `available_length`/`length`→`available_length_in`, `desired_width`/`clear_width`→`clear_width_in`) and `contractor_quote`/`quote`→`spec.meta['contractor_quote_cad']`. Numbers are inches; strings go through `parse_length`. Unknown keys are ignored. FE-3 should send one of these keys.

### AI-3 — null default params are omitted, not stored (Lane A — Parse, 2026-09-26 05:xx)
Question: `available_length_in` has a `null` default meaning "no length limit", but `models.ParamValue.value` is `float|int|str|bool` and cannot hold `None`.
Options I see: A) omit the param entirely when its default is null (engine treats a missing optional as its own default); B) change the contract to allow null (not allowed — models are read-only).
What I did meanwhile: A. A null default is left out of `spec.params`. A user- or model-provided numeric length for it is still kept.

### INF-8 — F-4 stub parse test updated to the AI-3 contract (Lane A — Parse, 2026-09-26 05:xx)
Question: `tests/test_api_stubs.py::test_parse_accepts_multipart_and_returns_params_without_parts` was written for the F-4 stub (accepted arbitrary bytes as an image, never called AI, expected `template_confidence: null`). AI-3 now validates the image (rejecting non-image bytes with 415) and calls the parser.
Options I see: A) update the stub test to post a real PNG and assert the fake-AI result; B) leave it failing.
What I did meanwhile: A. It now posts a real PNG, sets `FAKE_AI=1`, and asserts the user-measurement override + `template_confidence == 0.92`. Flagged as a shared-file (other-lane) test edit.

### AI-10 — rate limiter wired to /parse only (Lane A — Parse, 2026-09-26 05:xx)
Question: The limiter should also cover `/edit`, `/instructions`, `/voice/*` (AGENT A5), but those routes are Lane B's and don't exist in this worktree.
What I did meanwhile: Implemented a reusable dependency in `ai/ratelimit.py` (`from app.ai.ratelimit import rate_limit`) and applied it to `/parse`. Lane B should add `dependencies=[Depends(rate_limit)]` to its routes after merge.
Resolved (P3, 2026-09-26, at the Lane A merge): wired onto `/edit`, `/instructions`, `/voice/stt` (each `RATE_LIMIT_PER_MIN`, default 20) and `/voice/tts` (`RATE_LIMIT_TTS_PER_MIN`, default 120, because Build mode prefetches every step's audio). Each route group has its own budget.

### GEO-17 — STEP/STL export when the posted spec has no parts (Lane C, 2026-09-26)
Question: `POST /export/step|stl` takes `{spec}`. On the Plan screen the frontend already has a generated spec (with `parts`), but a spec loaded straight from `/parse` (or an older saved version) can have `parts == []`. Exporting an empty spec would produce an empty file.
Options I see: A) if `spec.parts` is empty, recompute parts via `engine.generate(template, params, meta)` before exporting; B) return a 422 telling the client to generate first.
What I did meanwhile: A. Non-empty specs export exactly what they carry; empty ones are regenerated deterministically through the engine, so the export always contains geometry. If the product prefers a hard error, switch to B (one line in `api/export.py`).


### VOX-6 — Where should the TTS client call live? (p4 Lane B, 2026-09-26)
Question: `POST /voice/tts` returns audio, not JSON, and `api/client.ts` (P2's file) only has JSON helpers. Build mode needs the call now.
Options I see: A) P2 adds `api.tts(text): Promise<Blob>` to `client.ts` and Build mode switches to it. B) Keep it in P4's `hooks/useBuildAudio.ts` (`fetchTts`).
What I did meanwhile: B. `fetchTts` in `frontend/src/hooks/useBuildAudio.ts` throws the client's `ApiError`, so moving it later is a one-line import change.

### FE-8 — Part highlight is hard to see in Build mode (p4 Lane B, 2026-09-26)
Question: Build mode passes the current step's part ids to `Scene` as `highlightedIds`. With the skeleton `PartMesh` (amber emissive tint), the highlighted parts barely stand out in the small view.
Options I see: A) P2 makes the highlight stronger in FE-5 (outline, or dim the parts that aren't highlighted). B) Build mode passes the ids as `selectedIds` too (blue).
What I did meanwhile: kept `highlightedIds` only, as the spec says. Nothing to change on my side if A happens.

### FE-8 — Wording on the Done screen (p4 Lane B, 2026-09-26)
Question: The Done screen says "Walk the ramp slowly once before anyone relies on it, and check every fastener." That's placeholder safety text I wrote. Should it come from the rules/safety copy (NC-3), and should it depend on the template?
What I did meanwhile: left the placeholder in `frontend/src/components/build/BuildDone.tsx`.

### FE-11 — Project thumbnails have no field in the API (p4 FE-11, 2026-09-26)
Question: `ProjectSummary.thumb` exists and `projects.thumb_png` is in SQLite, but `ProjectCreateRequest` and `VersionCreateRequest` have no thumbnail field, and `repo.create_project` always stores NULL. So the frontend can't send the Scene capture (PRD §12).
Options I see: A) P3 adds `thumb: str | None = None` (PNG data URL) to both requests and stores it (contract change: announce, then `make types`); P4 then captures the canvas on save. B) Keep no thumbnails for the hackathon.
What I did meanwhile: B. The list shows the template name in the thumbnail slot, and renders `thumb` when the server sends one.

### FE-11 — Where the login button mounts in the header (p4 FE-11, 2026-09-26; for P2)
Question: `AuthButton` (`components/auth/AuthButton.tsx`) is ready but `App.tsx` is P2's. It shows "Log in", or the user's name with "Log out", or "Login off (local dev)" when Auth0 isn't configured.
Options I see: A) P2 adds `<AuthButton />` next to the theme and shortcuts buttons in the header (one import, one element). B) Leave it on the Projects screen only.
What I did meanwhile: B. The Projects screen has it, and "Save" on the Plan and Projects screens offers "Log in to save" when needed.

### FE-11 — Starting a new design while a saved project is open (p4 FE-11, 2026-09-26; for P2)
Question: `currentProjectId` stays set after opening a project, so if the user then starts a fresh design in Capture, "Save new version" would add it to the old project.
Options I see: A) Capture calls `setCurrentProjectId(null)` when it applies a new parse result (P2's screen). B) Keep the current safeguard only.
What I did meanwhile: B. Whenever a project is open, Save offers both "Save new version" and "Save as new project".

### GEO-20 — Forced step counts: very tall risers, uncuttable stringers, and the "No limit" hint (p4/tpl-step-platform, 2026-09-27)
Question: `step_count` can force risers taller than any riser board (e.g. 2 steps at 21 in = 10-1/2 in, over the 9-1/4 in 2x10), and the task needs that design to derive so STEP-001 can fail with a fix.
What I did: such a riser is built from equal stacked strips of 2x10 (`Derived.riser_boards_per_riser`, 1 in every design without a forced count), so the model still builds and the rule fails with `{"step_count": <smallest passing>}`. The fix is only offered when that count is within 1–12 and builds.
Resolved: (A) a forced count whose notches leave too little wood in the stringer (e.g. 2 steps at 30 in) still raises ParamValidationError, but the message now names the fix: "2 steps of 15" are too tall to cut from a 2x10 stringer. Use at least 3 steps, or leave Number of steps empty." (B) New schema hint `empty_label` (step_count sets "Automatic"); ParamPanel uses it for the placeholder and the range hint and falls back to "No limit", so the ramp is unchanged. **P2:** heads-up that ParamPanel reads this new hint.
