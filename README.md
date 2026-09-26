# SketchBuild (working name)

Photo of a sketch or site + a few measurements → a safe, buildable plan for a home accessibility modification: 3D model, accessibility checks, cut list, cutting layouts, shopping list with cost, and voice-guided build steps.

Built for Hack the Hill III (uOttawa). **Status: early development.**

> **Guidelines, not code compliance.** Plans show accessibility guidelines only and are simplified construction models for planning, not engineered designs. Check local permit requirements before building.

## The problem

Home accessibility modifications such as ramps are expensive to hire out. DIY is far cheaper, but people routinely get safety constraints wrong, and a ramp that's too steep is dangerous. Existing tools are either generic ramp calculators or generic cut-list optimizers. Nothing takes a non-expert from "here's my porch" to "here's exactly what to buy and cut" with safety checks built in.

Example: ramps follow a 1:12 slope guideline, so a 21″ rise needs about 21 ft of ramp. That won't fit in a 12 ft yard, so the app catches it and proposes a switchback layout.

## How it works

1. **Capture** - upload or photograph a sketch or site, and optionally enter measurements and a contractor quote.
2. **Confirm** - see which values the app read, inferred or defaulted, and correct them before trusting the plan.
3. **Design** - live 3D model, parameter editing by slider or voice, and accessibility rule checks with one-click fixes.
4. **Plan** - cut list with actual lumber dimensions, cutting layouts on stock, shopping list with cost, and downloads (STEP, STL, cut list CSV).
5. **Build mode** - step-by-step instructions read aloud, with the current step's parts highlighted in 3D.

Geometry, rules, cut lists, nesting and pricing are computed deterministically in code. AI is used to read the sketch, interpret voice edits and word the instructions, never to compute dimensions, quantities or prices.

## Tech

- **Frontend:** React, TypeScript, Vite, Tailwind, React Three Fiber, Zustand
- **Backend:** Python, FastAPI, Pydantic, CadQuery (STEP/STL export), SQLite
- **AI:** Google Gemini (sketch parsing, voice-edit intent, instruction wording)
- **Voice:** ElevenLabs (speech-to-text and text-to-speech)
- **Auth:** Auth0
- **Hosting:** Vultr VM, Docker Compose, Caddy (automatic HTTPS), domain via GoDaddy Registry

## Repository layout

```
shared/schema/     JSON Schema generated from the Pydantic models
backend/app/       FastAPI app: templates, rules, cutlist, nesting, pricing, cad, ai, voice, store, auth
backend/tests/     pytest suite
frontend/src/      React app: screens, components, three (3D), store, api client
fixtures/          example specs/plans, test sketches, cached demo data
evals/             sketch-parsing eval set and runner
deploy/            Dockerfile(s), docker-compose.yml, Caddyfile, deploy script
```
