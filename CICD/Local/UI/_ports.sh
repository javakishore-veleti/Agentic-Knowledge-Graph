#!/usr/bin/env bash
# Single source of truth for local UI ports and app locations.
#
# Admin and Customer are independent Angular workspaces, each with its own
# package.json and node_modules: they deploy independently, so they develop
# independently too.
#
# Deliberately avoids associative arrays and mapfile. macOS ships bash 3.2, which has
# neither, and a dev script that only runs on the CI image is not a dev script.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN_DIR="$REPO_ROOT/.local-run"

APPS="Admin Customer"

port_of() {
  case "$1" in
    Admin)    echo 4300 ;;
    Customer) echo 4301 ;;
    *) echo "unknown app: $1" >&2; return 1 ;;
  esac
}

path_of() {
  case "$1" in
    Admin)    echo "$REPO_ROOT/Portals/Admin" ;;
    Customer) echo "$REPO_ROOT/Portals/Customer" ;;
    *) echo "unknown app: $1" >&2; return 1 ;;
  esac
}

mkdir -p "$RUN_DIR"

pid_file() { echo "$RUN_DIR/ui-$1.pid"; }
log_file() { echo "$RUN_DIR/ui-$1.log"; }

port_busy() { lsof -ti tcp:"$1" >/dev/null 2>&1; }

# Echoes the pid and returns 0 only when the recorded process is genuinely alive, so a
# stale pid file reads as "not running" rather than as a phantom server.
app_pid() {
  local f p
  f="$(pid_file "$1")"
  [ -f "$f" ] || return 1
  p="$(cat "$f")"
  [ -n "$p" ] || return 1
  kill -0 "$p" 2>/dev/null || return 1
  echo "$p"
}
