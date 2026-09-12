#!/usr/bin/env bash
# Run every portal in the FOREGROUND, interleaved, until Ctrl-C.
# Use start-all if you want them detached.
. "$(dirname "${BASH_SOURCE[0]}")/_ports.sh"

PIDS=""
cleanup() {
  echo ""
  echo "==> stopping"
  for p in $PIDS; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

started=0
for app in $APPS; do
  port="$(port_of "$app")"
  if port_busy "$port"; then
    echo "!! port $port already in use; $app not started" >&2
    continue
  fi
  echo "==> $app  http://localhost:$port"
  ( cd "$(path_of "$app")" && npx ng serve --port "$port" 2>&1 | sed "s/^/[$app] /" ) &
  PIDS="$PIDS $!"
  started=$((started + 1))
done

if [ "$started" -eq 0 ]; then
  echo "nothing started" >&2
  exit 1
fi
wait
