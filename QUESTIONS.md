# Questions

### INF-3 — Where does the TTS cache live in the container? (p4/infra, 2026-09-26 03:00)
Question: PRD §14 has `DATABASE_PATH` but no variable for the ElevenLabs TTS cache (VOX-2, P3). In Docker only `/data` is a persistent, writable volume (the code is read-only to the non-root user), so a cache written next to the code would fail or be lost on every deploy.
Options I see: A) P3 adds a `TTS_CACHE_DIR` variable and compose sets it to `/data/tts-cache`; B) the voice module puts its cache next to the SQLite file (the directory of `DATABASE_PATH`).
What I did meanwhile: compose mounts a volume at `/data` and sets `DATABASE_PATH=/data/sketchbuild.db`. If A is chosen, it's one line in both compose files.

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
