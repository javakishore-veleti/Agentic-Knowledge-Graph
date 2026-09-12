#!/usr/bin/env bash
# Exits non-zero unless every portal answers 200, so it is usable as a smoke check.
. "$(dirname "${BASH_SOURCE[0]}")/_ports.sh"

printf "  %-10s %-6s %-8s %-6s %s\n" "APP" "PORT" "PID" "HTTP" "URL"
rc=0
for app in $APPS; do
  port="$(port_of "$app")"
  pid="$(app_pid "$app" 2>/dev/null || echo '-')"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://localhost:$port" 2>/dev/null || echo '-')"
  [ "$code" = "200" ] || rc=1
  printf "  %-10s %-6s %-8s %-6s http://localhost:%s\n" "$app" "$port" "$pid" "$code" "$port"
done
exit $rc
