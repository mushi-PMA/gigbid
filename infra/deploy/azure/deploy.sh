#!/usr/bin/env bash
# Deploy (or update) GigBid on the VM created by provision.sh.
#   SITE_HOST=<fqdn> bash infra/deploy/azure/deploy.sh gigbid@<fqdn>
# Copies the repository (without .git, node_modules or local data), uploads the local .env.production as .env
# (never committed), and starts the stack with the HTTPS override.
set -euo pipefail

TARGET="${1:?usage: deploy.sh user@host}"
SITE_HOST="${SITE_HOST:?set SITE_HOST to the VM's public name}"
ENV_FILE="${ENV_FILE:-.env.production}"
[ -f "$ENV_FILE" ] || { echo "create $ENV_FILE first (copy .env.example and fill it; keep it out of git)"; exit 1; }

rsync -az --delete \
  --exclude .git --exclude .venv --exclude node_modules --exclude 'apps/web/dist' \
  --exclude 'data/processed' --exclude 'data/audit' --exclude 'data/raw' --exclude '*.db' --exclude 'evals/cache' \
  ./ "$TARGET:/opt/gigbid/"
scp "$ENV_FILE" "$TARGET:/opt/gigbid/.env"
ssh "$TARGET" "cd /opt/gigbid && grep -q '^SITE_HOST=' .env || echo 'SITE_HOST=$SITE_HOST' >> .env && \
  docker compose -f infra/docker-compose.yml -f infra/deploy/docker-compose.prod.yml --env-file .env up -d --build && \
  docker compose -f infra/docker-compose.yml -f infra/deploy/docker-compose.prod.yml ps"
echo "Live at https://$SITE_HOST (first certificate takes a minute)"
