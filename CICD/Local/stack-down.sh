#!/usr/bin/env bash
# Stop the API and Postgres. Data survives unless -v is passed.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PG_CONTAINER="${AKG_PG_CONTAINER:-akg-postgres}"
API_PORT="${AKG_CATALOG_PORT:-9001}"

pid="$( { lsof -ti tcp:"$API_PORT" -sTCP:LISTEN 2>/dev/null || true; } | head -1)"
if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; echo "==> stopped API (pid $pid)"; fi

if [ "${1:-}" = "-v" ]; then
  docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 && echo "==> removed Postgres AND its data"
else
  docker stop "$PG_CONTAINER" >/dev/null 2>&1 && echo "==> stopped Postgres (data kept)"
fi
