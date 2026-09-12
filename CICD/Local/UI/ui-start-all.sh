#!/usr/bin/env bash
# Start every portal DETACHED, then wait for each to answer. Logs and pids in .local-run/.
#
# Run this directly, not through a pipe. A detached ng serve keeps the inherited pipe
# open, so `ui-start-all.sh | tail` appears to hang even though the servers are up.
# Read the logs in .local-run/ or run ui-status-all.sh instead.
. "$(dirname "${BASH_SOURCE[0]}")/_ports.sh"

for app in $APPS; do
  port="$(port_of "$app")"

  if pid="$(app_pid "$app")"; then
    echo "==  $app already running (pid $pid, port $port)"
    continue
  fi
  if port_busy "$port"; then
    echo "!!  port $port in use by another process; skipping $app" >&2
    continue
  fi

  log="$(log_file "$app")"
  # </dev/null matters: without it the child inherits the caller's stdin pipe and
  # `npm run` will not return until the server exits, which defeats "detached".
  ( cd "$(path_of "$app")" \
    && nohup npx ng serve --port "$port" < /dev/null > "$log" 2>&1 &
    echo $! > "$(pid_file "$app")"
    disown 2>/dev/null || true )
  echo "==> $app starting (pid $(cat "$(pid_file "$app")")) -> ${log#"$REPO_ROOT/"}"
done

echo ""
echo "waiting up to 30s each for a first response..."
for app in $APPS; do
  port="$(port_of "$app")"
  ok=no
  i=0
  while [ "$i" -lt 30 ]; do
    if curl -fsS -o /dev/null "http://localhost:$port" 2>/dev/null; then ok=yes; break; fi
    i=$((i + 1))
    sleep 1
  done
  if [ "$ok" = yes ]; then
    echo "  $app     ready    http://localhost:$port"
  else
    # Not fatal: a cold compile can outlast the wait. The server is still coming up;
    # ui-status-all.sh is the authority on whether it arrived.
    echo "  $app     still compiling - check: npm run local:ui:status-all"
  fi
done
