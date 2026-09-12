#!/usr/bin/env bash
# Bring up the local stack, tier by tier, in dependency order.
#   ./docker-all-up.sh              all tiers from tiers.conf
#   ./docker-all-up.sh Postgres Kafka   only those
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK="${AKG_NETWORK:-akg-net}"
[ -f "$HERE/.env" ] || cp "$HERE/.env.example" "$HERE/.env"

command -v docker >/dev/null || { echo "docker not found" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "docker daemon not running" >&2; exit 1; }

# Tiers share one external network so each can be started and stopped alone.
docker network inspect "$NETWORK" >/dev/null 2>&1 || {
  echo "==> creating network $NETWORK"
  docker network create "$NETWORK" >/dev/null
}

# bash 3.2 has no mapfile, so read the tier list the portable way.
if [ $# -gt 0 ]; then
  tiers="$*"
else
  tiers="$(grep -vE '^[[:space:]]*(#|$)' "$HERE/tiers.conf" | tr '\n' ' ')"
fi

for tier in $tiers; do
  compose="$HERE/$tier/docker-compose.yml"
  [ -f "$compose" ] || { echo "!! no compose file for tier '$tier'" >&2; continue; }
  echo "==> up $tier"
  docker compose --env-file "$HERE/.env" -f "$compose" up -d
done

echo ""
"$HERE/all-status.sh" || true
