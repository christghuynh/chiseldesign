# Backend image: FastAPI + CadQuery (INF-2). Build context is the repo root:
#   docker build --platform linux/amd64 -f deploy/backend.Dockerfile -t sketchbuild-backend .
# The file list sent to the build is in backend.Dockerfile.dockerignore (next to this file).

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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY backend/app ./app
COPY fixtures /app/fixtures
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Non-root user. The code and venv stay root-owned (read-only to the app); /data is the volume
# for SQLite and the TTS cache.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data && chown app:app /data
USER app

COPY deploy/smoke_cadquery.py /app/smoke_cadquery.py
RUN python /app/smoke_cadquery.py

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4))['ok']"]

# Behind Caddy: trust its X-Forwarded-* headers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
