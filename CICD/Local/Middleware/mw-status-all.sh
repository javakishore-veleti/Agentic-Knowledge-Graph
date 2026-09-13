#!/usr/bin/env bash
# Exits non-zero unless every service answers, so it works as a smoke check.
. "$(dirname "${BASH_SOURCE[0]}")/_services.sh"

printf "  %-14s %-6s %-8s %-6s %-10s %s\n" "SERVICE" "PORT" "PID" "HTTP" "HEALTH" "URL"
rc=0
for svc in $SERVICES; do
  port="$(port_of "$svc")"
  pid="$(svc_pid "$svc" 2>/dev/null || echo '-')"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://localhost:$port/health" 2>/dev/null || echo '-')"
  health='-'
  if [ "$code" = "200" ]; then
    # A service can answer while its dependencies are down; "ok" and "degraded" are
    # different answers and both are more useful than a bare 200.
    health="$(curl -s --max-time 2 "http://localhost:$port/health" 2>/dev/null \
      | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p')"
    [ -z "$health" ] && health="?"
  else
    rc=1
  fi
  printf "  %-14s %-6s %-8s %-6s %-10s http://localhost:%s\n" \
    "$svc" "$port" "$pid" "$code" "$health" "$port"
done
exit $rc
