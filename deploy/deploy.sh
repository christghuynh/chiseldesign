#!/usr/bin/env bash
# Deploy to the VM (INF-7): ssh in, git pull, rebuild and restart the stack, then check health.
#
#   DEPLOY_HOST=deploy@203.0.113.5 DOMAIN=example.com deploy/deploy.sh      (or `make deploy`)
#
# Settings come from the environment, falling back to the root .env:
#   DEPLOY_HOST            ssh target, e.g. deploy@203.0.113.5 (required)
#   DOMAIN                 public domain, used for the health check (required unless
#                          DEPLOY_HEALTH_URL is set). Also used by Caddy on the VM, from the VM's .env.
#   DEPLOY_DIR             repo checkout on the VM, relative to the ssh user's home (default: sketchbuild)
#   DEPLOY_BRANCH          branch to deploy (default: main)
#   DEPLOY_COMPOSE_FILE    compose file, relative to the repo (default: deploy/docker-compose.yml)
#   DEPLOY_HEALTH_URL      default: https://$DOMAIN/api/health
#   DEPLOY_HEALTH_TIMEOUT  seconds to wait for a healthy response (default: 180)
#   DEPLOY_SSH_OPTS        extra ssh options, e.g. "-i ~/.ssh/vultr"
#
# The VM needs: the repo cloned at DEPLOY_DIR, a .env at its root (with DOMAIN), Docker + Compose.
# The frontend is built by `docker compose up --build` (deploy/web.Dockerfile), so no Node on the VM.
set -euo pipefail

red() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { red "DEPLOY FAILED: $*"; exit 1; }

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Fill unset variables from the root .env (KEY=value lines; the environment wins).
env_file="$repo_root/.env"
if [[ -f "$env_file" ]]; then
  for key in DEPLOY_HOST DOMAIN DEPLOY_DIR DEPLOY_BRANCH DEPLOY_COMPOSE_FILE DEPLOY_HEALTH_URL \
             DEPLOY_HEALTH_TIMEOUT DEPLOY_SSH_OPTS; do
    if [[ -z "${!key:-}" ]]; then
      value="$(sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$env_file" | tail -n 1 | tr -d '\r')"
      value="${value%\"}"; value="${value#\"}"; value="${value%\'}"; value="${value#\'}"
      [[ -n "$value" ]] && printf -v "$key" '%s' "$value"
    fi
  done
fi

: "${DEPLOY_HOST:?set DEPLOY_HOST (ssh target, e.g. deploy@203.0.113.5) in the environment or .env}"
DEPLOY_DIR="${DEPLOY_DIR:-sketchbuild}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
DEPLOY_COMPOSE_FILE="${DEPLOY_COMPOSE_FILE:-deploy/docker-compose.yml}"
DEPLOY_HEALTH_TIMEOUT="${DEPLOY_HEALTH_TIMEOUT:-180}"
if [[ -z "${DEPLOY_HEALTH_URL:-}" ]]; then
  : "${DOMAIN:?set DOMAIN (or DEPLOY_HEALTH_URL) in the environment or .env}"
  DEPLOY_HEALTH_URL="https://$DOMAIN/api/health"
fi

# DEPLOY_SSH_OPTS is a list of options (SC2086); remote commands are %q-quoted here on purpose (SC2029).
# shellcheck disable=SC2086,SC2029
remote() { ssh ${DEPLOY_SSH_OPTS:-} "$DEPLOY_HOST" "$@"; }

step "Deploying $DEPLOY_BRANCH to $DEPLOY_HOST:$DEPLOY_DIR"

# Everything below the heredoc runs on the VM. Arguments are passed quoted, not interpolated.
remote "bash -s -- $(printf '%q ' "$DEPLOY_DIR" "$DEPLOY_BRANCH" "$DEPLOY_COMPOSE_FILE")" <<'REMOTE' \
  || die "remote build/restart failed (see output above)"
set -euo pipefail
dir="$1" branch="$2" compose_file="$3"
cd "$dir" || { echo "no repo at ~/$dir on the VM; clone it there first" >&2; exit 1; }
[[ -f .env ]] || { echo "no .env in ~/$dir on the VM" >&2; exit 1; }

echo "--- git pull ($branch)"
git fetch --prune origin
git checkout --quiet "$branch"
git pull --ff-only origin "$branch"
git log -1 --format='deploying %h %s (%an, %cr)'

echo "--- docker compose up --build (builds the backend image and the frontend)"
docker compose --env-file .env -f "$compose_file" up -d --build --remove-orphans
docker compose --env-file .env -f "$compose_file" ps
docker image prune -f >/dev/null
REMOTE

step "Waiting for $DEPLOY_HEALTH_URL (up to ${DEPLOY_HEALTH_TIMEOUT}s)"
deadline=$((SECONDS + DEPLOY_HEALTH_TIMEOUT))
body=""
while ((SECONDS < deadline)); do
  if body="$(curl -fsS --max-time 5 "$DEPLOY_HEALTH_URL" 2>&1)" && [[ "$body" == *'"ok":true'* ]]; then
    green "Healthy: $body"
    green "Deployed $DEPLOY_BRANCH to $DEPLOY_HOST."
    exit 0
  fi
  sleep 3
done

red "Last response: ${body:-<none>}"
red "Recent logs from the VM:"
remote "cd $(printf '%q' "$DEPLOY_DIR") && docker compose --env-file .env -f $(printf '%q' "$DEPLOY_COMPOSE_FILE") ps && docker compose --env-file .env -f $(printf '%q' "$DEPLOY_COMPOSE_FILE") logs --tail 40" >&2 || true
die "$DEPLOY_HEALTH_URL was not healthy within ${DEPLOY_HEALTH_TIMEOUT}s"
