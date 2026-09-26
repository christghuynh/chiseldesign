# CLAUDE.md

Instructions for Claude Code agents (and humans) working in this repo.

The team spec is `PRD.md` at the repo root. It is **local-only and gitignored**, so it won't exist in a fresh clone or a new worktree. If you can't find it, ask for it. Work from the section and task ID you were assigned, plus the data contracts (Section 5) and repo conventions (Section 16).

## Directory ownership

Each workstream owns its own directories. Only edit outside your area when your task explicitly says so. Three agents work in parallel, and this is what keeps their changes from conflicting.

| Workstream | Owns |
|---|---|
| **GEO** (geometry, rules, cut list, nesting, pricing, CAD) | `backend/app/templates/`, `backend/app/rules/`, `backend/app/cutlist/`, `backend/app/nesting/`, `backend/app/pricing/`, `backend/app/cad/`, `backend/app/data/` |
| **AI** (Gemini) | `backend/app/ai/` (including `prompts/`), `evals/` |
| **VOX** (voice) | `backend/app/voice/`, plus the voice components in `frontend/src/components/` (e.g. PushToTalk) |
| **FE** (frontend) | `frontend/` (except the voice components above) |
| **INF** (infrastructure, persistence, auth) | `deploy/`, `backend/app/store/`, `backend/app/auth/` |
| **Foundation / shared** | `backend/app/models/`, `backend/app/api/`, `backend/app/main.py`, `backend/app/util/`, `shared/`, `fixtures/`, `Makefile`, and the root files |

Notes:
- `backend/app/models/` and `shared/schema/` are the data contracts. Changes have a single owner and must be announced to everyone. `shared/schema/` is generated (`make types`), never hand-edited.
- If your task needs a change in a directory you don't own, stop and say so instead of making it.

## Commit messages

Format: `<task ID>: <summary of what was done>`

- One task: `F1: Added CLAUDE.md, README.md, .gitignore, .env.example, and the Makefile skeleton`
- Several tasks in one commit: `<first>-<last>: <summary of the tasks completed>`, e.g. `F2-F6: <summary of what F-2 through F-6 delivered>`
- Commit small and often. Judges read the commit history.
- Never commit secrets. Keys go in `.env` only. `.env` and `.env.example` are both gitignored. The variable names are in Section 14 of `PRD.md`.

## Running things

`make dev`, `make test`, `make types` and `make eval` exist as stubs and are filled in as their tasks land (each stub names its task). This section gets updated as they become real (task INF-9).
