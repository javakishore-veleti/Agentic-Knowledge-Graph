#!/usr/bin/env bash
# Stop each API service. Kills the listener and its direct children only -- never the
# process GROUP, which would take siblings started from the same shell with it.
. "$(dirname "${BASH_SOURCE[0]}")/_services.sh"

stop_one() {
  local svc port pid child holder stopped
  svc="$1"; port="$(port_of "$svc")"; stopped=no

  if pid="$(svc_pid "$svc")"; then
    for child in $(pgrep -P "$pid" 2>/dev/null); do kill -TERM "$child" 2>/dev/null || true; done
    kill -TERM "$pid" 2>/dev/null || true
    i=0
    while [ "$i" -lt 10 ]; do
      kill -0 "$pid" 2>/dev/null || break
      i=$((i + 1)); sleep 1
    done
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
    echo "==> stopped $svc (pid $pid)"
    stopped=yes
  fi
  rm -f "$(pid_file "$svc")"

  holder="$(listener_pid "$port")"
  if [ -n "$holder" ]; then
    echo "    port $port still listening on pid $holder; terminating"
    kill -TERM "$holder" 2>/dev/null || true
    sleep 1
    holder="$(listener_pid "$port")"
    [ -n "$holder" ] && kill -KILL "$holder" 2>/dev/null || true
    stopped=yes
  fi

  if [ "$stopped" = no ]; then echo "==  $svc not running"; fi
  return 0
}

for svc in $SERVICES; do stop_one "$svc"; done
