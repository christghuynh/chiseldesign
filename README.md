# Chisel

**From a napkin sketch to a safe, buildable plan for simple construction projects.**

Photograph a sketch or the site, add a couple of measurements, and Chisel gives you a 3D model, safety checks with one-click fixes, a cut list, cutting layouts, a shopping list with cost, and voice-guided build steps.

**Try it:** [chiseldesign.work](https://chiseldesign.work) · Built at Hack the Hill III (uOttawa)

> **Guidelines, not code compliance.** Chisel checks designs against published guidelines. Its plans are simplified construction models for planning, not engineered designs. Check local bylaws and permit requirements before building.

## The problem

Small construction projects around the home (a ramp to the porch, a raised garden bed, a set of steps, a workbench) are expensive to hire out. A contractor might quote $4,000 for a ramp that costs a fraction of that in lumber. Doing it yourself saves the money, but non-experts routinely get the details wrong: the slope, the spacing, what to buy, how to cut it. Existing tools are either generic calculators or generic cut-list optimizers; nothing takes you from "here's my porch" to "here's exactly what to buy, cut and build" with the safety checks built in.

For example, ramps follow a 1:12 slope guideline, so a 14″ rise needs 14 ft of ramp. If the yard is only 12 ft deep, a straight ramp won't fit: Chisel flags it and its one-click fix switches to a switchback layout that does.

## What you can build

Each build is a parametric template with its own rules and build steps. Adding a template needs no frontend changes: the parameter panel is generated from the template's schema.

| Template | What it covers | Checks |
|---|---|---|
| **Accessibility ramp** | Straight or switchback runs, landings, handrails, edge curbs | Slope, rise per run, width, landings, handrails, edge protection, fit in the space, board lengths sold (RAMP-001–009) |
| **Raised garden bed** | Stacked side boards, corner posts, optional seat-height cap rail | Height, reach, path clearance (BED-001–004) |
| **Step platform** | Notched stringers, deck-board treads and risers, optional top platform | Riser height, tread depth, width (STEP-001–004) |
| **Workbench** | 4x4 legs, 2x4 aprons, plywood top, optional lower shelf | — |

Rule thresholds are cited to the 2010 ADA Standards (sections 308, 403, 405, 504, 505) in `backend/app/rules/sources.json`, and each check links to its source in the app.

## How it works

1. **Capture:** upload or photograph a sketch or site photo (JPEG, PNG, HEIC, WebP and other common formats), or start from a template. Optionally enter measurements and a contractor quote.
2. **Confirm:** see which values Chisel read from the image, inferred or filled with defaults, answer its questions, and correct anything before trusting the plan.
3. **Design:** a live 3D model you can rotate and inspect part by part. Edit with sliders, by typing, or by voice ("make it six inches wider"); voice edits remember the conversation, so you can answer a follow-up question. Rule checks come with one-click fixes, plus undo and redo.
4. **Plan:** a cut list with actual lumber dimensions, cutting diagrams for every board and sheet, a shopping list with HST and the savings against the contractor quote, and downloads (STEP, STL, cut-list CSV, printable plan). Prices come from Home Depot Canada product pages; the total is labelled as an estimate while any item still uses a placeholder price.
5. **Build mode:** large-text steps read aloud, with the current step's parts highlighted in 3D. Say "next", "back", "repeat" or "stop" to keep your hands on the tools.

Log in (Auth0) to save projects with their version history and reopen them later. Everything else works without an account.

### AI never computes numbers

For something people stand on, we don't let a model invent a dimension. Geometry, rule checks, cut lists, nesting and pricing are deterministic Python. AI reads the sketch, interprets voice edits and words the build instructions, and every AI step has a non-AI fallback:

| AI step | Fallback |
|---|---|
| Reading the sketch (Gemini) | Type the measurements or pick a template |
| Voice edits (Gemini + ElevenLabs speech-to-text) | Sliders and the typed edit box |
| Build-step wording (Gemini) | The template's own step outline |
| Spoken steps (ElevenLabs text-to-speech) | The browser's built-in speech |

Spoken cut sizes ("two-by-six, sixty-four and a half inches") are generated in code, never by the model.

## Architecture

```text
Browser (React + three.js)                         Vultr VM (Docker Compose)
┌──────────────────────────────┐   HTTPS   ┌──────────────────────────────────────────┐
│ Capture → Confirm → Design   │ ────────▶ │ Caddy: TLS, static frontend, /api proxy  │
│   → Plan → Build mode        │           │   │                                      │
│ Zustand store, R3F scene,    │           │   ▼                                      │
│ push-to-talk, Auth0 SDK      │           │ FastAPI backend                          │
└──────────────────────────────┘           │  ├─ engine: templates → parts → rules    │
                                           │  │   → cut list → nesting → pricing      │
                                           │  ├─ ai: Gemini (parse, edit, wording)    │
                                           │  ├─ voice: ElevenLabs STT / TTS (cached) │
                                           │  ├─ cad: CadQuery → STEP / STL           │
                                           │  ├─ auth: Auth0 JWT (RS256, JWKS)        │
                                           │  └─ store: SQLite projects + versions    │
                                           └──────────────────────────────────────────┘
```

The backend's Pydantic models are the contract between the two halves: `make types` generates JSON Schema (`shared/schema/`) and the TypeScript types (`frontend/src/types/`) from them.

## Tech

| | |
|---|---|
| **Frontend** | React, TypeScript, Vite, Tailwind, React Three Fiber + Drei, Zustand |
| **Backend** | Python 3.11, FastAPI, Pydantic, CadQuery (STEP/STL export), SQLite, Pillow + pillow-heif |
| **AI** | Google Gemini: sketch parsing (structured output), voice-edit intent (function calling), instruction wording |
| **Voice** | ElevenLabs: speech-to-text and text-to-speech |
| **Auth** | Auth0 |
| **Hosting** | Vultr VM, Docker Compose, Caddy (automatic HTTPS) |
| **CI** | GitHub Actions: pytest, type-check, vitest, build, Docker image builds |

## Run it locally

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 24 and GNU Make. On Linux, CadQuery also needs `libgl1`.

```bash
make install     # uv sync (backend) + npm ci (frontend)
make dev         # backend on :8000 with reload + Vite on :5173 (proxies /api)
make test        # backend pytest, frontend vitest and type-check
```

To run the UI with no backend at all: `cd frontend && npm run dev:fixtures`.

Settings go in a `.env` file at the repo root, which is never committed:

| Variable | Needed for |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Sketch parsing, voice edits, instruction wording |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Speech-to-text and text-to-speech |
| `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` | Verifying logins on the backend (`AUTH_DISABLED=1` uses a local dev user instead) |
| `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE` | Login in the frontend (for `npm run dev`, put them in `frontend/.env.development.local`) |
| `DATABASE_PATH`, `TTS_CACHE_DIR`, `CORS_ORIGINS` | Optional: where projects and cached audio are stored, and allowed origins |
| `RATE_LIMIT_PER_MIN`, `RATE_LIMIT_TTS_PER_MIN` | Optional: per-IP limits on the AI and voice routes (default 20 and 120) |
| `FAKE_AI=1`, `FAKE_VOICE=1` | Canned responses with no API calls (the test suite always uses them) |

Without the AI or voice keys the app still runs; those features fall back as described above.

To run the production stack locally (backend and Caddy with the built frontend) on http://localhost:8080: `make up-local`. To deploy to the VM: set `DEPLOY_HOST` and `DOMAIN` in `.env` and run `make deploy`, which pulls `main` on the VM, rebuilds, restarts and checks `/api/health`.

## Testing and evals

- `make test` runs the backend pytest suite and the frontend vitest suite and type-check. Tests never call the paid APIs.
- `make eval` runs the sketch-parsing eval (`evals/run_parse_eval.py`) against real Gemini. `--cases evals/synthetic_cases.json --repeat 3` runs the 17 synthetic phone-photo-style sketches in `fixtures/sketches/synthetic/` three times each and reports cases that answer inconsistently.

## Repository layout

```text
backend/app/       FastAPI app: templates, rules, cutlist, nesting, pricing, cad, ai, voice, store, auth
backend/tests/     pytest suite
frontend/src/      React app: screens, components, three (3D), store, api client
shared/schema/     JSON Schema generated from the Pydantic models
fixtures/          example specs and plans, test sketches, cached demo data
evals/             sketch-parsing eval sets and runner
deploy/            Dockerfiles, docker-compose, Caddyfile, deploy script
.github/           CI workflows
```

## Accessibility of the app itself

The app is built to be usable by everyone: 16px minimum text, 44px tap targets, WCAG AA text contrast in light and dark mode, full keyboard navigation with visible focus, labels on every control, voice as an alternative to every edit with a typed fallback, and support for `prefers-reduced-motion`.

## Team

- **christghuynh:** geometry engine (templates, rules, cut list, nesting, pricing)
- **danyeltech:** frontend core and design flow (3D scene, capture, confirm, design)
- **richardgli:** AI, voice and backend services (Gemini, ElevenLabs, CAD export, projects, auth, deployment)
- **yxshen22:** plan and build mode UI, infrastructure, deployment and launch
