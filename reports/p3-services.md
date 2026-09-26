# p3-services report

Lane C — Services (store, auth, CAD export, CSV). Branch `p3/services`, worktree `sb-p3-services`.

## Done (tests passing)
- **INF-6 (C1): SQLite store + projects API** — `backend/app/store/db.py`, `backend/app/store/repo.py`, `backend/app/api/projects.py`, `backend/tests/test_projects_api.py`. stdlib `sqlite3`; `DATABASE_PATH` read at call time (default `backend/data/sketchbuild.db`, gitignored); parent dir + tables created lazily on first connect (no `main.py` hook). Tables per PRD §12 (`users`, `projects`, `versions`). User upsert by `auth0_sub`. Create stores the initial spec as version 1 (`source: manual`); add-version increments `n` and bumps `updated_at`. Owners only see their own projects — a foreign or missing project id returns 404 without revealing existence. Shapes follow `models/api.py` exactly. 4 tests.
- **INF-5 (C2): Auth0 JWT verification** — `backend/app/auth/verify.py`, `backend/tests/test_auth_verify.py`. RS256 via JWKS from `https://<AUTH0_DOMAIN>/.well-known/jwks.json`, cached in-process, refetched once on an unknown kid. Verifies audience (`AUTH0_AUDIENCE`) and issuer (`https://<AUTH0_DOMAIN>/`). `current_user` dependency used by project routes only. `AUTH_DISABLED=1` → fixed dev user `dev|local`; auth enabled but `AUTH0_*` missing → 503 `AUTH_NOT_CONFIGURED` (no crash); missing/invalid token → 401. Tests use a local RSA key + stubbed JWKS (no network). 7 tests.
- **GEO-17 (C3): CadQuery STEP/STL export** — `backend/app/cad/exporter.py`, `backend/app/cad/naming.py`, `backend/app/api/export.py`, `backend/tests/test_cad_export.py`. Pipeline copied from `tests/test_frame_convention.py`'s `part_to_solid_zup` (not imported from tests): profile → extrude → Euler-XYZ rotate → translate → Y-up→Z-up with **+90° about X** (the PRD/agent-file −90 is wrong; foundation.md PRD-issue #1). Named assembly, part id as each solid's name. In-memory LRU (maxsize 32) keyed by `sha256(canonical parts JSON + format)`; temp files under the system temp dir, removed immediately — no writes to the read-only code dir. Routes return the file with `Content-Disposition: attachment; filename="sketchbuild-<template>[-<layout>].step|stl"`. Acceptance on `fixtures/specs/ramp_straight.json`: STEP non-empty with one solid per part (54); overall min Z = −0.0 (nothing below grade); deck-board top (the walking surface) = 15.0 in = `total_rise_in` (handrails/posts extend above to ~51 in, so the check is the deck top, not overall height). 5 tests.
- **GEO-18 (C4): cut-list CSV** — `backend/app/cad/cutlist_csv.py`, `backend/tests/test_cutlist_csv.py`, route in `api/export.py`. Plan via `engine.generate` (never importing cutlist/pricing directly). Columns `label,name,material,actual_dims_in,length_in,length,qty,part_ids,cut_notes`, CRLF, RFC 4180 quoting (stdlib `csv`, `QUOTE_MINIMAL`); `part_ids` space-joined, `cut_notes` joined with `"; "`. Filename `sketchbuild-<template>[-<layout>]-cut-list.csv`. Matches P4's `frontend/src/components/plan/exports.ts`; confirmed under FE-10 in QUESTIONS.md. 4 tests.

Also updated the shared F-4 test `backend/tests/test_api_stubs.py`: removed the `/projects/*` and `/export/*` routes from the "returns 501" list (they are now implemented); the voice routes stay as stubs. Behavior for the built routes is covered by the new lane tests.

## Verification
- Full backend suite: **185 passed** (`FAKE_AI=1 FAKE_VOICE=1 AUTH_DISABLED=1 uv run pytest -q`), up from 146 at foundation; 20 of those are the new Lane C tests.
- CadQuery 2.8.0 imports and runs on this Linux box (libGL present); no system packages installed.
- Export timings (cold, `ramp_straight` fixture, 54 parts): **STEP ≈ 0.73 s** (well under the 5 s target); cache hit ≈ 0.003 s. STL non-empty.

## Questions logged
- FE-10 (reply): confirmed the CSV columns/quoting/filenames to P4.
- GEO-17: export when the posted spec has no `parts` — chose to recompute via `engine.generate` (option A); documented the 422 alternative.

## New dependencies
- `PyJWT==2.10.1`, `cryptography==44.0.0` (pinned via `uv add`; in `backend/pyproject.toml` + `uv.lock`). There is no `requirements.txt`.

## Check this in the morning
- **Auth0 tenant values (owner-only):** set `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` (from P4) and unset `AUTH_DISABLED` to turn on real verification. Until then the app uses the dev user; with `AUTH_DISABLED` unset and the vars missing, project routes return 503 by design.
- **DB path in Docker:** compose already sets `DATABASE_PATH=/data/sketchbuild.db` on the writable volume; the code creates the dir/tables lazily, so no migration/startup step is needed.
- **Merge order** (per the agent file): `p3/step0` → `p3/services` → `p3/assist` → `p3/parse`. This lane touched the shared `test_api_stubs.py`; if another lane also edits it, reconcile the 501 list.
- The STEP/STL routes trust the posted `spec`; when P1's real engine lands, re-run the CAD acceptance test against real `/generate` output (a straight ramp above ~17 in rise hits the known oversize-stringer issue, foundation PRD-issue #3 — not exercised by the 15 in fixture).
