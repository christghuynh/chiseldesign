# Chisel

**From a napkin sketch to a safe, buildable accessibility ramp.** Photograph a sketch or your porch, add a couple of measurements, and Chisel gives you a 3D model, accessibility checks with one-click fixes, a cut list, cutting layouts, a shopping list with cost, and voice-guided build steps.

Built for Hack the Hill III (uOttawa), civic challenges theme. **Status: in active development.**

> **Guidelines, not code compliance.** Chisel checks designs against published accessibility guidelines. Its plans are simplified construction models for planning, not engineered designs. Check local permit requirements before building.

## The problem

A family member starts using a walker. The porch has three steps, and a contractor quotes $4,000 for a ramp. Building it yourself costs a fraction of that, but people routinely get the safety constraints wrong: a ramp that's too steep is dangerous. Existing tools are generic ramp calculators or generic cut-list optimizers. Nothing takes a non-expert from "here's my porch" to "here's exactly what to buy and cut" with the safety checks built in.

Example: ramps follow a 1:12 slope guideline, so a 21″ rise needs about 21 ft of ramp. If the yard is only 12 ft deep, a straight ramp won't fit, so Chisel flags it and proposes a switchback layout.

## How it works

1. **Capture:** upload or photograph a sketch or site photo, and optionally enter measurements and a contractor quote.
2. **Confirm:** see which values Chisel read, inferred or defaulted, and correct them before trusting the plan.
3. **Design:** a live 3D model, edits by slider or by voice ("make it six inches wider"), and accessibility rule checks with one-click fixes.
4. **Plan:** a cut list with actual lumber dimensions, cutting diagrams for every board and sheet, a shopping list with tax and the savings against the contractor quote, and downloads (STEP, STL, cut-list CSV, printable plan).
5. **Build mode:** large-text steps read aloud, with the current step's parts highlighted in 3D. Say "next", "back" or "repeat" to keep your hands on the tools.

**AI never computes numbers.** Geometry, rule checks, cut lists, nesting and pricing are deterministic Python. AI reads the sketch, interprets voice edits and words the instructions, and every AI step has a non-AI fallback: pick a template manually, type an edit, use the template's own step outline, or use the browser's speech.

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
                                           │  └─ store: SQLite projects + versions    │
                                           └──────────────────────────────────────────┘
```

The backend's Pydantic models are the contract. `make types` generates JSON Schema (`shared/schema/`) and the TypeScript types (`frontend/src/types/`) from them.

## Tech

| | |
|---|---|
| **Frontend** | React, TypeScript, Vite, Tailwind, React Three Fiber + Drei, Zustand |
| **Backend** | Python 3.11, FastAPI, Pydantic, CadQuery (STEP/STL export), SQLite |
| **AI** | Google Gemini: sketch parsing, voice-edit intent, instruction wording |
| **Voice** | ElevenLabs: speech-to-text and text-to-speech |
| **Auth** | Auth0 |
| **Hosting** | Vultr VM, Docker Compose, Caddy (automatic HTTPS), domain via GoDaddy Registry |
| **CI** | GitHub Actions: pytest, type-check, vitest, build, Docker image builds |

## Run it locally

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 24, GNU Make.

```bash
make install     # uv sync (backend) + npm ci (frontend)
make dev         # backend on :8000 with reload + Vite on :5173 (proxies /api)
make test        # backend pytest, frontend vitest and type-check
```

To run the UI with no backend at all: `cd frontend && npm run dev:fixtures`.

API keys go in a `.env` file at the repo root, which is never committed: `GEMINI_API_KEY`, `GEMINI_MODEL`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `DATABASE_PATH`, `CORS_ORIGINS`.

To run the production stack locally (backend and Caddy with the built frontend) on http://localhost:8080: `make up-local`. To deploy to the VM: `make deploy` (see `CLAUDE.md` for the settings it needs).

## Repository layout

```text
backend/app/       FastAPI app: templates, rules, cutlist, nesting, pricing, cad, ai, voice, store, auth
backend/tests/     pytest suite
frontend/src/      React app: screens, components, three (3D), store, api client
shared/schema/     JSON Schema generated from the Pydantic models
fixtures/          example specs and plans, test sketches, cached demo data
evals/             sketch-parsing eval set and runner
deploy/            Dockerfiles, docker-compose, Caddyfile, deploy script
.github/           CI workflows
```

## Accessibility of the app itself

We're pitching accessibility, so the app practices it: 16px minimum text, 44px tap targets, full keyboard navigation with visible focus, labels on every icon, voice as an alternative to every edit with a typed fallback, and support for `prefers-reduced-motion` and dark mode.

## Team

- **christghuynh:** geometry engine (templates, rules, cut list, nesting, pricing)
- **danyeltech:** frontend core and design flow (3D scene, capture, confirm, design)
- **richardgli:** AI, voice and backend services (Gemini, ElevenLabs, CAD export, projects)
- **yxshen22:** plan and build mode UI, infrastructure, deployment and launch
