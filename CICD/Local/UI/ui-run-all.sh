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
ours=0
foreign=0
for app in $APPS; do
  port="$(port_of "$app")"
  if port_busy "$port"; then
    pid="$(listener_pid "$port")"
    if is_our_server "$app"; then
      echo "==  $app is already serving on http://localhost:$port (pid $pid)"
      ours=$((ours + 1))
    else
      echo "!! port $port is held by an unrelated process (pid $pid):" >&2
      ps -o command= -p "$pid" 2>/dev/null | cut -c1-90 | sed 's/^/     /' >&2
      foreign=$((foreign + 1))
    fi
    continue
  fi
  echo "==> $app  http://localhost:$port"
  ( cd "$(path_of "$app")" && npx ng serve --port "$port" 2>&1 | sed "s/^/[$app] /" ) &
  PIDS="$PIDS $!"
  started=$((started + 1))
done

if [ "$started" -eq 0 ]; then
  echo ""
  if [ "$foreign" -gt 0 ]; then
    echo "Nothing started: $foreign port(s) are held by processes that are not ours." >&2
    echo "Free the port, or change the port in CICD/Local/UI/_ports.sh." >&2
    exit 1
  fi
  # Every app is already up as a detached server. The intent -- "the UIs are running" --
  # is already satisfied, so this is not an error.
  echo "All portals are already running (started detached). Nothing to do."
  for app in $APPS; do echo "  $app  http://localhost:$(port_of "$app")"; done
  echo ""
  echo "To take them over in the foreground instead:"
  echo "  npm run local:ui:stop-all && npm run local:ui:run-all"
  exit 0
fi

if [ "$ours" -gt 0 ]; then
  echo ""
  echo "note: $ours portal(s) were already running detached and were left alone."
fi
echo ""
echo "Ctrl-C stops everything started here."
wait
