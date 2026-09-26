# Web image: Caddy serving the built frontend and proxying /api to the backend (INF-3).
# Build context is the repo root; the file list is in web.Dockerfile.dockerignore.
#
# The frontend is built inside Docker, so the VM needs no Node. Vite reads frontend/.env* as it
# would for a local `npm run build`, plus the VITE_AUTH0_* build args below; only VITE_* values end
# up in the bundle, and the build stage is thrown away.

# The bundle is plain JS/CSS, so build it on the host's native platform (no emulation).
FROM --platform=$BUILDPLATFORM node:24-bookworm-slim AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
# Auth0 SPA settings (FE-11), passed from the root .env by docker-compose.yml. Vite reads VITE_* from
# the environment; they are public values that end up in the bundle anyway. Empty = login off.
ARG VITE_AUTH0_DOMAIN=""
ARG VITE_AUTH0_CLIENT_ID=""
ARG VITE_AUTH0_AUDIENCE=""
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/frontend/dist /srv
