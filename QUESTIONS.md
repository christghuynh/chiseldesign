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
