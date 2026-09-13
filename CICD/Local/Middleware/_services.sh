#!/usr/bin/env bash
# The API services and the port each one owns.
#
# Adding a service is one line in each case block below. Ports follow the 9001 block so
# every service is guessable from one number:
#
#   9001  data-catalog   domains, datasets, MIOs, endpoints, workflows, initial data
#   9002  data-mgmt      dataset acquisition; triggers Airflow
#   9003  Admin portal   (CICD/Local/UI)
#   9004  Customer portal
#
# No associative arrays and no mapfile: macOS ships bash 3.2 and has neither, and a script
# that only runs on the CI image is not a dev script.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN_DIR="$REPO_ROOT/.local-run"
mkdir -p "$RUN_DIR"

SERVICES="data-catalog data-mgmt"

port_of() {
  case "$1" in
    data-catalog) echo 9001 ;;
    data-mgmt)    echo 9002 ;;
    *) echo "unknown service: $1" >&2; return 1 ;;
  esac
}

path_of() {
  case "$1" in
    data-catalog) echo "$REPO_ROOT/Middleware/data-catalog" ;;
    data-mgmt)    echo "$REPO_ROOT/Middleware/data-mgmt" ;;
    *) echo "unknown service: $1" >&2; return 1 ;;
  esac
}

module_of() {
  case "$1" in
    data-catalog) echo "data_catalog.app:app" ;;
    data-mgmt)    echo "data_mgmt.app:app" ;;
    *) echo "unknown service: $1" >&2; return 1 ;;
  esac
}

#: Extra uv --with flags. data-catalog talks to Postgres; data-mgmt holds no database.
deps_of() {
  case "$1" in
    data-catalog) echo "--with sqlalchemy>=2.0 --with psycopg[binary]>=3.2" ;;
    *) echo "" ;;
  esac
}

log_file() { echo "$RUN_DIR/$1.log"; }
pid_file() { echo "$RUN_DIR/$1.pid"; }

# -sTCP:LISTEN matters: the unfiltered form also returns every CLIENT connected to the
# port, including a browser with the API open. An earlier version of the UI stop script
# used it and would have killed Chrome.
#
# The `|| true` is load-bearing too: this file sets pipefail, and lsof exits non-zero when
# nothing matches, which would abort the caller mid-loop.
listener_pid() { { lsof -ti tcp:"$1" -sTCP:LISTEN 2>/dev/null || true; } | head -1; }

port_busy() { [ -n "$(listener_pid "$1")" ]; }

# The listening socket is the source of truth; the pid file is a reconciled hint.
svc_pid() {
  local port p
  port="$(port_of "$1")"
  p="$(listener_pid "$port")"
  if [ -n "$p" ]; then echo "$p" > "$(pid_file "$1")"; echo "$p"; return 0; fi
  rm -f "$(pid_file "$1")" 2>/dev/null || true
  return 1
}

db_url() {
  echo "${AKG_DATABASE_URL:-postgresql+psycopg://akg:akg-local-only@localhost:${AKG_PG_PORT:-5432}/akg}"
}

# Airflow credentials for the services that trigger DAGs. Read from the same CICD/Local
# .env the Airflow container is started with, so the two cannot drift: a mismatch shows
# up as "airflow_unavailable" in the portal, which says nothing about a wrong password.
airflow_user() {
  echo "${AKG_AIRFLOW_USER:-$(env_value AIRFLOW_USER admin)}"
}
airflow_password() {
  echo "${AKG_AIRFLOW_PASSWORD:-$(env_value AIRFLOW_PASSWORD akg-local-only)}"
}

# One key out of CICD/Local/.env, falling back to a default. Deliberately not `source`:
# that file is compose syntax and sourcing it would export every unrelated key into the
# service environment.
env_value() {
  local key="$1" fallback="$2" line
  line="$(grep -E "^${key}=" "$REPO_ROOT/CICD/Local/.env" 2>/dev/null | tail -1 || true)"
  if [ -n "$line" ]; then echo "${line#*=}"; else echo "$fallback"; fi
}
