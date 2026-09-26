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

### FE-7 — Plan screen clears the 3D highlight when it opens and closes (p4/plan, 2026-09-26)
Question: The Plan screen resets `highlightedPartIds` on mount, when the plan changes, and on unmount, so Build mode (Lane B) and Design start clean. Is that OK with P2 (Design) and Lane B (Build mode sets its own highlight)?
Options I see: A) Keep it. B) Only clear on unmount.
What I did meanwhile: A.
