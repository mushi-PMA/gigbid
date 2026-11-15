#!/usr/bin/env bash
# Deploy (or update) GigBid on the VM created by provision.sh.
#   SITE_HOST=<fqdn> bash infra/deploy/azure/deploy.sh gigbid@<fqdn>
# The VM checks out the public repository at the given ref (default: origin/main), receives the local
# .env.production as .env (never committed), and starts the stack with the HTTPS override.
set -euo pipefail

TARGET="${1:?usage: deploy.sh user@host}"
SITE_HOST="${SITE_HOST:?set SITE_HOST to the public name of the VM}"
ENV_FILE="${ENV_FILE:-.env.production}"
REPO_URL="${REPO_URL:-https://github.com/mushi-PMA/gigbid.git}"
REF="${REF:-origin/main}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
[ -f "$ENV_FILE" ] || { echo "create $ENV_FILE first (copy .env.example and fill it; keep it out of git)"; exit 1; }

ssh "${SSH_OPTS[@]}" "$TARGET" "cloud-init status --wait >/dev/null; cd /opt/gigbid && \
  { [ -d .git ] || git clone -q '$REPO_URL' . ; } && git fetch -q origin && git reset -q --hard '$REF'"
scp "${SSH_OPTS[@]}" "$ENV_FILE" "$TARGET:/opt/gigbid/.env"
ssh "${SSH_OPTS[@]}" "$TARGET" "cd /opt/gigbid && { grep -q '^SITE_HOST=' .env || echo 'SITE_HOST=$SITE_HOST' >> .env; } && \
  docker compose -f infra/docker-compose.yml -f infra/deploy/docker-compose.prod.yml --env-file .env up -d --build && \
  docker compose -f infra/docker-compose.yml -f infra/deploy/docker-compose.prod.yml --env-file .env ps"
echo "Live at https://$SITE_HOST (the first certificate takes a minute)"
