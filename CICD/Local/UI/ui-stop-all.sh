#!/usr/bin/env bash
# Stop each portal.
#
# Kills the recorded pid and its direct children only. An earlier version killed the
# process GROUP, which also killed sibling portals started from the same shell -- and in
# the worst case could reach the calling terminal.
. "$(dirname "${BASH_SOURCE[0]}")/_ports.sh"

stop_one() {
  app="$1"
  port="$(port_of "$app")"
  stopped=no

  if pid="$(app_pid "$app")"; then
    # ng serve spawns a build worker; take the children first so nothing is orphaned.
    for child in $(pgrep -P "$pid" 2>/dev/null); do kill -TERM "$child" 2>/dev/null || true; done
    kill -TERM "$pid" 2>/dev/null || true
    i=0
    while [ "$i" -lt 10 ]; do
      kill -0 "$pid" 2>/dev/null || break
      i=$((i + 1)); sleep 1
    done
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
    echo "==> stopped $app (pid $pid)"
    stopped=yes
  fi
  rm -f "$(pid_file "$app")"

  # Whatever the pid file said, the port is the thing that must end up free.
  holder="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$holder" ]; then
    echo "    port $port still held by pid $holder; terminating"
    for h in $holder; do kill -TERM "$h" 2>/dev/null || true; done
    sleep 1
    holder="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    for h in $holder; do kill -KILL "$h" 2>/dev/null || true; done
    stopped=yes
  fi

  [ "$stopped" = no ] && echo "==  $app not running"
  return 0
}

for app in $APPS; do stop_one "$app"; done
