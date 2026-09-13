#!/usr/bin/env bash
# Run every API service in the FOREGROUND, interleaved, until Ctrl-C.
. "$(dirname "${BASH_SOURCE[0]}")/_services.sh"

PIDS=""
cleanup() {
  echo ""; echo "==> stopping"
  for p in $PIDS; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

started=0
for svc in $SERVICES; do
  port="$(port_of "$svc")"
  if port_busy "$port"; then
    echo "==  $svc already serving on http://localhost:$port"
    continue
  fi
  echo "==> $svc  http://localhost:$port"
  ( cd "$(path_of "$svc")" \
    && AKG_DATABASE_URL="$(db_url)" uv run \
         --with 'fastapi>=0.115' --with 'uvicorn[standard]>=0.32' \
         --with 'pydantic-settings>=2.6' --with 'httpx>=0.27' \
         $(deps_of "$svc") --python 3.13 \
         --with-editable ../../Libraries/python/akg-service-core --with-editable . \
         uvicorn "$(module_of "$svc")" --port "$port" 2>&1 | sed "s/^/[$svc] /" ) &
  PIDS="$PIDS $!"
  started=$((started + 1))
done

if [ "$started" -eq 0 ]; then
  echo ""; echo "All services are already running. Nothing to do."
  for svc in $SERVICES; do echo "  $svc  http://localhost:$(port_of "$svc")"; done
  exit 0
fi
echo ""; echo "Ctrl-C stops everything started here."
wait
