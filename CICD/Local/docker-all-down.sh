#!/usr/bin/env bash
# Stop tiers. Volumes survive unless -v is passed, so data is not lost by accident.
#   ./docker-all-down.sh            stop all, keep data
#   ./docker-all-down.sh -v         stop all and DELETE volumes
#   ./docker-all-down.sh Postgres   stop one tier
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK="${AKG_NETWORK:-akg-net}"

# up creates .env from the example; down assumed it already existed, so stopping before
# ever starting failed on a missing env file. Compose needs it either way, to resolve the
# ${...} defaults in the tier compose files.
[ -f "$HERE/.env" ] || cp "$HERE/.env.example" "$HERE/.env"

wipe=""
args=""
for a in "$@"; do
  case "$a" in
    -v|--volumes) wipe="-v" ;;
    *) args="$args $a" ;;
  esac
done
args="$(echo "$args" | sed 's/^ *//')"

# Reverse tier order on the way down: Airflow depends on Postgres.
if [ -n "$args" ]; then
  tiers="$args"
else
  raw="$(grep -vE '^[[:space:]]*(#|$)' "$HERE/tiers.conf")"
  tiers=""
  for t in $raw; do tiers="$t $tiers"; done
fi

[ -n "$wipe" ] && echo "!! deleting volumes as well"

for tier in $tiers; do
  compose="$HERE/$tier/docker-compose.yml"
  [ -f "$compose" ] || continue
  echo "==> down $tier"
  docker compose --env-file "$HERE/.env" -f "$compose" down $wipe
done

# Only remove the shared network when nothing is attached to it.
if [ -z "$args" ] && docker network inspect "$NETWORK" >/dev/null 2>&1; then
  attached="$(docker network inspect "$NETWORK" -f '{{len .Containers}}')"
  if [ "$attached" = "0" ]; then
    docker network rm "$NETWORK" >/dev/null && echo "==> removed network $NETWORK"
  else
    echo "==  network $NETWORK kept ($attached container(s) still attached)"
  fi
fi
