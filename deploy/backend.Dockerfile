# Backend image: FastAPI + CadQuery (INF-2). Build context is the repo root:
#   docker build --platform linux/amd64 -f deploy/backend.Dockerfile -t sketchbuild-backend .
# The file list sent to the build is in backend.Dockerfile.dockerignore (next to this file).
# Also deployed on Railway (deploy/railway.json), which rules out `VOLUME` and cache mounts without a
# Railway cache id, so this file uses neither. Railway sets $PORT; everywhere else it's 8000.

# 3.11 matches backend/.python-version; CadQuery's OCP wheels install cleanly on it.
FROM python:3.11-slim-bookworm

# OCP (CadQuery's OpenCascade bindings) links against OpenGL and X11 client libraries even when
# nothing is rendered.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxrender1 libxext6 libx11-6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH=/app/backend/.venv/bin:$PATH \
    FIXTURES_DIR=/app/fixtures \
    DATABASE_PATH=/data/sketchbuild.db

# Same layout as the repo (backend/ next to fixtures/), so config.py's repo-root paths still work.
WORKDIR /app/backend

# Dependencies first, so code changes don't reinstall CadQuery.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

COPY backend/app ./app
COPY fixtures /app/fixtures
RUN uv sync --locked --no-dev --no-cache

# Non-root user. The code and venv stay root-owned (read-only to the app); /data is the volume
# for SQLite and the TTS cache.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data && chown app:app /data
USER app

COPY deploy/smoke_cadquery.py /app/smoke_cadquery.py
RUN python /app/smoke_cadquery.py

# /data is a volume: declared in the compose files, and a Railway volume mounted at /data.
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import json, os, urllib.request; assert json.load(urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/health\", timeout=4))['ok']"]

# Behind Caddy or Railway's proxy: trust their X-Forwarded-* headers. `exec` keeps uvicorn as PID 1 so
# it gets the stop signal.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips '*'"]
