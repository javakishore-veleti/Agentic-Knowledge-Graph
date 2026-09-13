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

# Ports these portals used BEFORE the move to the 9001 block. A dev server left running
# on one of these outlives the change, keeps serving a months-old bundle, and answers on
# a URL still sitting in a browser tab -- which reads as "the app is broken" rather than
# "you are looking at the wrong port". stop-all sweeps them.
LEGACY_PORTS="4300 4301"

# AKG local port scheme (ADR-019)
#   9001  data-catalog API
#   9002  data-mgmt API
#   9003  Admin portal
#   9004  Customer portal
# Chosen as a contiguous block starting at 9001 so every service is guessable from one
# number, and away from 8000-8080 where Docker Desktop, Airflow and most other local
# tooling already live -- 8001 was taken by Docker's own backend on the first attempt.

port_of() {
  case "$1" in
    Admin)    echo 9003 ;;
    Customer) echo 9004 ;;
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

# -sTCP:LISTEN matters. Plain `lsof -ti tcp:PORT` also returns every CLIENT holding a
# connection to that port -- including the browser you have the page open in. An earlier
# version of the stop script used the unfiltered form and would have killed Chrome.
# The `|| true` is load-bearing. This file sets `pipefail`, and lsof exits non-zero when
# nothing matches, so without it every "is anything listening?" check on a free port
# fails the pipeline and `set -e` kills the calling script mid-loop.
listener_pid() { { lsof -ti tcp:"$1" -sTCP:LISTEN 2>/dev/null || true; } | head -1; }

port_busy() { [ -n "$(listener_pid "$1")" ]; }

# The listening socket is the source of truth, not the pid file: `$!` through a
# backgrounded `cd && nohup` chain proved unreliable, and a stale file is worse than no
# file. The pid file is only a hint, reconciled against the port here.
app_pid() {
  local port p f
  port="$(port_of "$1")"
  p="$(listener_pid "$port")"
  if [ -n "$p" ]; then
    echo "$p" > "$(pid_file "$1")"
    echo "$p"
    return 0
  fi
  # Nothing listening: the recorded pid, if any, is stale.
  f="$(pid_file "$1")"
  [ -f "$f" ] && rm -f "$f"
  return 1
}

# Is the process listening on this app's port one of OUR dev servers, or something
# unrelated that happens to have taken the port? The difference decides whether the
# right advice is "stop-all" or "free that port yourself".
is_our_server() {
  local pid cmd
  pid="$(listener_pid "$(port_of "$1")")"
  [ -n "$pid" ] || return 1
  cmd="$(ps -o command= -p "$pid" 2>/dev/null || true)"
  case "$cmd" in
    *ng*serve*|*angular*|*node*) return 0 ;;
    *) return 1 ;;
  esac
}
