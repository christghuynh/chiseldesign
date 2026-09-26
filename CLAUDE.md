# CLAUDE.md

Instructions for Claude Code agents (and humans) working in this repo.

Read these before starting a task:
- `foundation.md`: what the foundation delivered, where things live, the locked conventions (units, world frame, part transforms), the integration stubs and the open questions. **Start here.** Like `PRD.md` it is **local-only and gitignored**; the owner gives it to you, and if it is missing, ask for it.
- Your `AGENT_<Pn>_<handle>.md` file: your lanes, tasks, acceptance tests and rules.
- `PRD.md`: the team spec. It is **local-only and gitignored**, so it won't exist in a fresh clone or a new worktree. If you can't find it, ask for it. Work from the section and task ID you were assigned, plus the data contracts (Section 5), repo conventions (Section 16) and ownership (Section 23).

## Directory ownership

Each person owns their own paths. Only edit outside them when your task explicitly says so. Parallel agents work in separate worktrees, and this is what keeps their changes from conflicting.

| Person | Area | Owns |
|---|---|---|
| **P1** | Geometry engine | `backend/app/templates/`, `rules/`, `cutlist/`, `nesting/`, `pricing/`, `util/`, `data/`, `engine.py` (bodies only: `generate`, `get_skeleton`, `list_templates`), `plan.py`, `api/templates.py`, `api/generate.py`, their tests, `fixtures/specs/`, `fixtures/skeletons/` |
| **P2** | Frontend core and design flow | `frontend/src/` shell (`App.tsx`, `main.tsx`), `api/`, `three/`, store slices `specSlice`, `uiSlice`, `voiceSlice`, screens Landing/Capture/Confirm/Design and the screen registry `screens/index.ts`, components ParamPanel/RuleBadges/PushToTalk/TypedEditBox/common, `dev/registry.ts` |
| **P3** | AI, voice and backend services | `backend/app/ai/`, `voice/`, `cad/`, `store/`, `auth/`, the `api/` routes parse/edit/instructions/voice/export/projects, `evals/`, `fixtures/sketches/`, `fixtures/demo/` |
| **P4** | Plan/Build UI, infra and launch | screens Plan/BuildMode/Projects/Overlay and their components, store slices `buildSlice`, `authSlice`, `deploy/`, `.github/`, `Makefile` (append a section to `CLAUDE.md` when you add targets), `backend/app/observability.py`, the README |
| **Shared** (no single owner) | Foundation files | `backend/app/main.py`, `config.py`, `fixtures.py`, `api/errors.py`, the root files, `fixtures/frames/`, `fixtures/units/`, `fixtures/templates.json`, `fixtures/instructions/` |

Notes:
- **Contracts.** These need an announcement to the whole team first, then `make types` if a model changed: `backend/app/models/**` and `shared/schema/`, the signatures and exceptions in `backend/app/engine.py`, `SceneProps` in `three/Scene.tsx`, `PushToTalkProps`, `TypedEditBoxProps`, and the slice interfaces in `frontend/src/store/`. `shared/schema/` and `frontend/src/types/index.ts` are generated and never hand-edited.
- **Store.** Each person edits only their own slice files. `frontend/src/store/index.ts` combines them and is not edited after the foundation.
- **Dev pages.** Anyone may add `frontend/src/dev/routes/<name>.tsx` (default-export a component) for their own screens. It is served at `/dev/<name>` by `npm run dev` with no shared file to edit (for example P2's `scene.tsx` and P4's `plan.tsx`).
- **Allowed cross-area edits (announce first):** P4 wraps the app in `Auth0Provider` in `main.tsx` (coordinated with P2), and adds one import line for `observability.py` in `backend/app/main.py`.
- **Stubs.** The engine, the route handlers and the fixtures are stubs. The owner of a route or of the engine replaces the stub's body and leaves the signature alone. `foundation.md` lists which task replaces which.
- If your task needs a change in a path you don't own, stop and say so (in `QUESTIONS.md` if your agent file uses one) instead of making it.

## Commit messages

Format: `<task ID>: <summary of what was done>`

- One task: `F1: Added CLAUDE.md, README.md, .gitignore, and the Makefile skeleton` or `GEO-4: Ramp stringer, deck board and curb parts`
- Several tasks in one commit: `<first>-<last>: <summary of the tasks completed>`, e.g. `F2-F6: <summary of what F-2 through F-6 delivered>` or `GEO-3-GEO-6: <summary>`
- Foundation tasks are written without the hyphen (`F1`, `F2-F6`); every other workstream keeps it (`GEO-4`, `AI-5`).
- Commit small and often, one task per commit where you can. Judges read the commit history.
- Never commit secrets. Keys go in `.env` only. `.env` and `.env.example` are both gitignored. The variable names are in Section 14 of `PRD.md`.

## Branches

- `main` is always deployable and `make test` must pass on it. Nobody pushes work-in-progress to it, and it is never force-pushed once anyone else has cloned it.
- Humans: one feature branch per task, named after the task ID (e.g. `geo-4-ramp-parts`), merged through a pull request.
- Agent lanes: one worktree and one branch per lane, `<pn>/<lane>` (e.g. `p1/ramp`), created with `git worktree add ../sb-<pn>-<lane> -b <pn>/<lane>`. Agents never merge into `main`. The owner reviews and merges the lane branches, with CI green once CI exists.
- Worktrees don't contain gitignored files, so copy `PRD.md`, `foundation.md` and your `AGENT_*.md` file into each one.

## Running things

Prerequisites: [uv](https://docs.astral.sh/uv/) (Python 3.11 is pinned in `backend/.python-version`), Node 24, and GNU Make (on Windows it may be installed as `mingw32-make`).

- `make test`: backend pytest, frontend vitest and the TypeScript type-check. Must pass before you merge.
- `make types`: regenerate `shared/schema/contracts.schema.json` and `frontend/src/types/index.ts` from the Pydantic models. Run it after any model change.
- Backend: `cd backend && uv sync`, then `uv run uvicorn app.main:app --reload --port 8000`.
- Frontend: `cd frontend && npm install`, then `npm run dev` (proxies `/api` to the backend on :8000) or `npm run dev:fixtures` to run without a backend.
- `make dev` and `make eval` are still stubs (tasks INF-9 and AI-8).
- **New dependencies:** Python packages with `uv add <package>` (updates `backend/pyproject.toml` and `uv.lock`; there is no `requirements.txt`), JavaScript with `npm install <package>` inside `frontend/`. List them in your report.

## Make targets (INF-9)

Run from the repo root. `make` alone prints this list.

| Target | What it does |
|---|---|
| `make install` | `uv sync` in `backend/` and `npm ci` in `frontend/`. |
| `make dev` | Backend on :8000 with `--reload` and Vite on :5173 (proxies `/api` to :8000), in one terminal. Ctrl-C stops both. For the UI without a backend, use `npm run dev:fixtures` in `frontend/`. |
| `make test` | `test-backend` + `test-frontend`. Must pass before you merge; CI runs the same checks. |
| `make test-backend` | `pytest` in `backend/`. |
| `make test-frontend` | `vitest` and `tsc --noEmit` in `frontend/`. |
| `make types` | Regenerates `shared/schema/` and `frontend/src/types/` from the Pydantic models. Run it after any model change. |
| `make eval` | Runs `evals/run_parse_eval.py` (AI-8). Fails with a message until that file exists. |
| `make up-local` / `make down-local` | The production Docker stack (backend + Caddy with the built frontend) on http://localhost:8080 with no TLS (`deploy/docker-compose.local.yml`). `LOCAL_PORT` changes the port. The first build takes a few minutes (CadQuery). |
| `make deploy` | `deploy/deploy.sh`: ssh to the VM, `git pull`, `docker compose up -d --build`, then polls `https://$DOMAIN/api/health` and fails loudly if it isn't healthy. Needs `DEPLOY_HOST` (ssh target) and `DOMAIN` in the environment or the root `.env`; the other settings are listed at the top of the script. |

Docker files live in `deploy/`: `backend.Dockerfile` (Python 3.11 + CadQuery, non-root, with a smoke test at build time), `web.Dockerfile` (builds the frontend, serves it with Caddy), `Caddyfile`, `docker-compose.yml` (production, HTTPS for `$DOMAIN`) and `docker-compose.local.yml`. Build context is always the repo root, and each Dockerfile's `.dockerignore` sits next to it. Build for the VM with `--platform linux/amd64`.
