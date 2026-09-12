#!/usr/bin/env bash
# One view of the whole local stack: containers, health, and the ports they expose.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK="${AKG_NETWORK:-akg-net}"

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not running"
  exit 1
fi

echo "network: $NETWORK  $(docker network inspect "$NETWORK" -f '({{len .Containers}} attached)' 2>/dev/null || echo '(absent)')"
echo ""
printf "%-16s %-11s %-22s %s\n" "CONTAINER" "STATE" "HEALTH" "PORTS"

found=0
for c in $(docker ps -a --filter "name=akg-" --format '{{.Names}}' | sort); do
  found=1
  state="$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}—{{end}}' "$c" 2>/dev/null)"
  ports="$(docker port "$c" 2>/dev/null | awk -F' -> ' '{print $2}' | sed 's/0.0.0.0://' | paste -sd, - )"
  printf "%-16s %-11s %-22s %s\n" "$c" "$state" "$health" "${ports:-—}"
done
[ "$found" = "0" ] && echo "(no akg-* containers)"

echo ""
echo "portals:"
"$HERE/UI/ui-status-all.sh" 2>/dev/null || echo "  (ui status unavailable)"
