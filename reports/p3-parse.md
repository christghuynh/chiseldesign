# p3-parse report

Lane A — Parse (branch `p3/parse`). Sketch/site photo → template parameters via Gemini, with
deterministic unit normalization, defaults, user overrides, failure handling, upload validation,
rate limiting, a demo cache and an eval harness. The AI only reads; all numbers come from code.

## Done (tests passing)

- **AI-2 — parse prompt + pipeline** — `backend/app/ai/prompts/parse.md`, `backend/app/ai/parse.py`,
  `backend/app/ai/fakes/parse.json`, tests in `backend/tests/test_parse.py`.
  - Gemini response schema: params as a LIST of `{name, value, unit, confidence, source}`.
  - Prompt catalog rebuilt from `engine.list_templates()` (keys, titles, bounds, enums,
    required-ness) so new P1 templates appear with no code change.
  - Units normalized to inches (`in/ft/cm/mm/m` + ft-in strings via `app.util.units.parse_length`).
  - Precedence user > read/inferred > default; `assumed` = inferred+default; a required param with
    no reading and no default is left out and a question is added (never invented).
  - Readings validated against the template JSON Schema with `jsonschema`; out-of-bounds/invalid
    readings are dropped and fall back to defaults. Null defaults are omitted (ParamValue can't be
    None). Contractor quote → `spec.meta['contractor_quote_cad']`. Unknown object → `spec=null`.
- **AI-3 — POST /parse** — `backend/app/api/parse.py`, tests in `backend/tests/test_parse_route.py`.
  Multipart image + optional `measurements` (JSON) + `note`. Returns `{spec, template_confidence,
  questions, raw_notes}` with no parts/rule_checks.
- **AI-4 — failure handling** — invalid output retried once in `parse.py`; then route → **502
  PARSE_FAILED** ("pick a template manually"). `AIUnavailable` → **503 AI_UNAVAILABLE**.
- **INF-8 — upload validation + request logging** — `backend/app/ai/imageprep.py`,
  `backend/app/api/request_log.py`. Accepts only JPEG/PNG/WebP **verified by decoding** with
  Pillow (not just content-type), ≤ 10 MB (else 413), applies EXIF orientation, resizes to ≤ 1600 px
  long side, re-encodes JPEG. Middleware logs `method path status latency_ms` (never bodies/keys).
- **AI-10 — rate limiter** — `backend/app/ai/ratelimit.py`. Reusable FastAPI dependency, per client
  IP, fixed 60 s window, `RATE_LIMIT_PER_MIN` (default 20), 429 `RATE_LIMITED`. Applied to `/parse`.
- **AI-9 — demo parse cache** — `backend/app/ai/parsecache.py`, `evals/cache_demo.py`. Keyed by
  sha256 of the RAW uploaded bytes; files `fixtures/demo/<sha256>.json` hold a ParseResponse;
  checked before any AI call. `cache_demo.py <image>` runs one real parse and writes the file.
- **AI-8 — eval harness** — `evals/parse_cases.json` (2 placeholder cases),
  `evals/run_parse_eval.py` (per-param accuracy, `--fake` flag), test in
  `backend/tests/test_parse_eval.py`. `make eval` runs the real runner (skips missing images
  cleanly until the owner adds real sketches).

## Test counts
- Full backend suite: **212 passed** (was 174 at branch start; +38 this lane).
- New test files: `test_parse.py` (20), `test_parse_route.py` (16), `test_parse_eval.py` (2).
- Verified green with `uv run pytest` and with the CI env (`FAKE_AI=1 FAKE_VOICE=1 AUTH_DISABLED=1`).

## Real API calls made
- **1** real Gemini `generate_json` parse (of 3 allowed), via `app.ai.client`, on a hand-drawn-style
  test sketch (rise 21 in, width 36 in, yard 12 ft). Result: template `ramp` (conf 0.95), read
  `total_rise_in=21`, `clear_width_in=36`, `available_length_in=144` (12 ft normalized), sensible
  defaults + a switchback question. Prompt/schema validated end to end. Key never printed or logged.
  Model in use: `gemini-3.8-flash`.

## Shared-file edits to announce
- `backend/app/main.py` — added `add_request_logging(app)` (import + one line). **Allowed A4 edit.**
- `backend/tests/test_ai_client.py` — updated ONE assertion in `test_shipped_parse_fake_is_used_...`
  to read the new list-shaped `fakes/parse.json` (AI-1 owner should confirm at merge). See QUESTIONS.
- `backend/tests/test_api_stubs.py` — updated `test_parse_accepts_multipart_...` from the F-4 stub
  behavior to the AI-3 contract (real PNG, fake-mode result). See QUESTIONS.
- `backend/app/ai/fakes/parse.json` — rewritten to the list schema (owned by this lane).

## Failed / partial
- None. All acceptance checks pass.

## New dependencies
- `pillow==12.3.0` (pinned, in `backend/pyproject.toml` + `uv.lock`) for image validation/resize.

## Questions logged
- AI-2: parse.json list-shape vs a merged AI-1 test — see QUESTIONS.md.
- AI-3: measurements field shape defined by this lane — see QUESTIONS.md.
- AI-3: null-default params omitted — see QUESTIONS.md.
- INF-8: F-4 stub parse test updated to the AI-3 contract — see QUESTIONS.md.
- AI-10: limiter wired to /parse only; Lane B wires its routes after merge — see QUESTIONS.md.

## Check this in the morning
- Confirm the `test_ai_client.py` and `test_api_stubs.py` edits are acceptable to their owners
  (or let them re-do them); they were required to keep the suite green under the new fake schema.
- Rate limiter is in-memory per process (fine for the demo VM; not multi-worker safe).
- Done at merge: the limiter now covers `/edit`, `/instructions`, `/voice/stt` and `/voice/tts`
  (TTS has its own `RATE_LIMIT_TTS_PER_MIN`, default 120), each with a separate budget.
- Owner (NC-5/NC-6): drop real sketches into `fixtures/sketches/`, wire `evals/parse_cases.json`
  to them, and run `evals/cache_demo.py` on the demo sketch. `RATE_LIMIT_PER_MIN` and
  `DEMO_CACHE_DIR` are configurable via env if needed.
